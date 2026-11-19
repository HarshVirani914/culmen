import re
import subprocess
from dataclasses import dataclass
import threading
import time
from pathlib import Path
from typing import Callable, Literal

from ..config import ffmpeg_bin
from ..cookies import ytdlp_auth_opts
from ..download import ALLOWED_EXTRACTORS
from .buffer import Segment

BACKOFF = (2, 4, 8, 16, 32)  # seconds between reconnect attempts
STREAM_FORMAT = "b[height<=1080]/bv*[height<=1080]+ba/b"
_NAME = re.compile(r"^(\d{6})\.ts$")


@dataclass
class StreamInfo:
    urls: list[str]
    title: str = ""
    channel_id: str = "unknown"
    channel: str = ""
    width: int = 0
    height: int = 0


def resolve_stream(url: str) -> StreamInfo:
    """Direct stream URL(s) (video, plus a separate audio URL when needed) and metadata of a live stream."""
    import yt_dlp

    opts = {"quiet": True, "noplaylist": True, "format": STREAM_FORMAT, "allowed_extractors": ALLOWED_EXTRACTORS,
            **ytdlp_auth_opts()}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info.get("is_live"):
        raise ValueError("This stream is not live right now.")
    urls = [f["url"] for f in info["requested_formats"]] if info.get("requested_formats") else [info["url"]]
    title = info.get("title") or ""
    if "(live)" in title.lower() and info.get("description"):  # Twitch puts the real title in the description
        title = info["description"].splitlines()[0][:120]
    return StreamInfo(urls, title, info.get("channel_id") or info.get("uploader_id") or "unknown",
                      info.get("channel") or info.get("uploader") or "", int(info.get("width") or 0),
                      int(info.get("height") or 0))


def next_start_number(d: Path) -> int:
    nums = [int(m.group(1)) for p in Path(d).glob("*.ts") if (m := _NAME.match(p.name))] if Path(d).exists() else []
    return max(nums) + 1 if nums else 0


class Recorder:
    """Records a stream with ffmpeg stream copy into fixed-length MPEG-TS segments (no re-encode).

    `source` is called again for every (re)connect so expired URLs are re-resolved."""

    def __init__(self, source: Callable[[], list[str] | str], buffer_dir: Path,
                 on_segment: Callable[[Segment], None] | None = None, seg_seconds: float = 6,
                 retries: int = 5, realtime: bool = False):
        self.source, self.dir, self.on_segment = source, Path(buffer_dir), on_segment
        self.seg, self.retries, self.realtime = seg_seconds, retries, realtime
        self.status: Literal["starting", "recording", "ended", "error"] = "starting"
        self.error: str | None = None
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._reported: set[int] = set()

    def start(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=10)

    def _cmd(self, urls: list[str]) -> list[str]:
        cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error"]
        for u in urls:
            if u.startswith("http"):
                cmd += ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10"]
            elif self.realtime:
                cmd += ["-re"]
            cmd += ["-i", u]
        if len(urls) > 1:
            cmd += ["-map", "0:v:0", "-map", "1:a:0"]
        return cmd + ["-c", "copy", "-f", "segment", "-segment_time", str(self.seg), "-segment_format", "mpegts",
                      "-reset_timestamps", "1", "-segment_start_number", str(next_start_number(self.dir)),
                      str(self.dir / "%06d.ts")]

    def _report(self, final: bool) -> int:
        nums = sorted(int(m.group(1)) for p in self.dir.glob("*.ts") if (m := _NAME.match(p.name)))
        complete = nums if final else nums[:-1]
        new = 0
        for i in complete:
            if i not in self._reported:
                self._reported.add(i)
                new += 1
                if self.on_segment:
                    self.on_segment(Segment(i, self.dir / f"{i:06d}.ts", i * self.seg))
        return new

    def _run(self) -> None:
        failures = 0
        while not self._stop.is_set():
            try:
                urls = self.source()
                urls = [urls] if isinstance(urls, str) else urls
                self._proc = subprocess.Popen(self._cmd(urls), stderr=subprocess.PIPE, text=True)
            except Exception as e:  # noqa: BLE001
                err, produced, code = str(e), 0, 1
            else:
                self.status = "recording"
                produced = 0
                while self._proc.poll() is None and not self._stop.is_set():
                    produced += self._report(final=False)
                    time.sleep(0.3)
                if self._proc.poll() is None:
                    self._proc.terminate()
                code = self._proc.wait()
                err = (self._proc.stderr.read() or "").strip()[-300:] if self._proc.stderr else ""
                produced += self._report(final=True)
            if self._stop.is_set():
                self.status = "ended"
                return
            if code == 0 and produced > 0:
                self.status = "ended"  # the stream finished normally
                return
            failures = 0 if produced >= 3 else failures + 1
            if failures > self.retries:
                self.status, self.error = "error", err or "recording failed"
                return
            self._stop.wait(BACKOFF[min(failures - 1, len(BACKOFF) - 1)])
        self.status = "ended"
