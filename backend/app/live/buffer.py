import itertools
import re
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..config import ffmpeg_bin

_NAME = re.compile(r"^(\d{6})\.ts$")


@dataclass
class Segment:
    index: int
    path: Path
    start: float  # seconds on the session clock


class SegmentBuffer:
    """Rolling buffer of fixed-length MPEG-TS segments named 000000.ts, 000001.ts, ...

    The highest-numbered file may still be written by ffmpeg, so it is only listed once finalize() is called."""

    def __init__(self, dir: Path, max_seconds: float = 720, seg_seconds: float = 6):
        self.dir = Path(dir)
        self.max_seconds, self.seg = max_seconds, seg_seconds
        self._final = False
        self._protected: dict[int, tuple[float, float]] = {}
        self._ids = itertools.count()
        self._lock = threading.Lock()

    def finalize(self) -> None:
        self._final = True

    def _all(self) -> list[Segment]:
        segs = []
        for p in self.dir.glob("*.ts"):
            m = _NAME.match(p.name)
            if m:
                i = int(m.group(1))
                segs.append(Segment(i, p, i * self.seg))
        return sorted(segs, key=lambda s: s.index)

    def list(self) -> list[Segment]:
        segs = self._all()
        return segs if self._final else segs[:-1]

    def available_start(self) -> float:
        segs = self.list()
        return segs[0].start if segs else 0.0

    def available_end(self) -> float:
        segs = self.list()
        return segs[-1].start + self.seg if segs else 0.0

    def protect(self, start: float, end: float) -> Callable[[], None]:
        with self._lock:
            pid = next(self._ids)
            self._protected[pid] = (start, end)

        def release() -> None:
            with self._lock:
                self._protected.pop(pid, None)
        return release

    def _is_protected(self, s: Segment) -> bool:
        with self._lock:
            ranges = list(self._protected.values())
        return any(s.start < b and s.start + self.seg > a for a, b in ranges)

    def prune(self) -> list[Path]:
        segs = self._all()
        if not segs:
            return []
        newest_end = segs[-1].start + self.seg
        deleted = []
        for s in segs:
            if s.start < newest_end - self.max_seconds and not self._is_protected(s):
                s.path.unlink(missing_ok=True)
                deleted.append(s.path)
        return deleted

    def extract(self, start: float, end: float, out: Path) -> None:
        """Stream-copy [start, end] (session seconds) into `out` (.mp4). Clamped to what the buffer holds."""
        segs = self.list()
        if not segs:
            raise ValueError("the buffer is empty")
        start, end = max(start, self.available_start()), min(end, self.available_end())
        if end - start < 1:
            raise ValueError("that part of the stream is no longer in the buffer")
        chosen = [s for s in segs if s.start < end and s.start + self.seg > start]
        with tempfile.TemporaryDirectory() as d:
            lst = Path(d) / "list.txt"
            lst.write_text("".join(f"file '{s.path.resolve()}'\n" for s in chosen))
            r = subprocess.run(
                [ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                 "-ss", f"{start - chosen[0].start:.3f}", "-t", f"{end - start:.3f}", "-c", "copy",
                 "-avoid_negative_ts", "make_zero", "-movflags", "+faststart", str(out)],
                capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"could not cut the moment: {r.stderr.strip()[-300:]}")
