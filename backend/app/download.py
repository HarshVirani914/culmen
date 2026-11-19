import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import ffmpeg_bin


@dataclass
class VideoInfo:
    path: Path
    title: str
    channel_id: str
    channel: str
    duration: float
    width: int
    height: int
    info: dict


def _probe_duration(path: Path) -> float:
    import subprocess

    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                              str(path)], capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out)
    except Exception:
        return 0.0


MAX_SECTION = 3 * 3600  # seconds; longest section we will fetch with the slow ranged path
NATIVE_MAX = 4 * 3600  # videos up to this length download whole at full speed, then are cut locally
GB_PER_HOUR = 2.0  # generous 1080p estimate, used for the free-disk check


def _cut_section(full: Path, start: float, end: float, out: Path) -> None:
    import subprocess

    r = subprocess.run(
        [ffmpeg_bin(), "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(full),
         "-c", "copy", "-avoid_negative_ts", "make_zero", str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"could not cut the time range: {r.stderr.strip()[-300:]}")


def download_video(url: str, dest_dir: Path, start: float | None = None, end: float | None = None) -> VideoInfo:
    """Download a video (optionally only [start, end] seconds of it).

    Videos up to NATIVE_MAX are downloaded whole with yt-dlp's fast native downloader and cut locally, because
    yt-dlp's section download goes through ffmpeg at roughly realtime speed. Longer videos fall back to the
    slow section download so a marathon stream is never downloaded whole.
    """
    import yt_dlp
    from yt_dlp.utils import download_range_func

    dest_dir.mkdir(parents=True, exist_ok=True)
    base = {"quiet": True, "noplaylist": True, "allowed_extractors": ["youtube", "youtube:tab"]}
    with yt_dlp.YoutubeDL({**base, "skip_download": True}) as ydl:
        meta = ydl.extract_info(url, download=False)
    if meta.get("is_live"):
        raise ValueError("This stream is live right now. Use live clipping, or wait for the replay.")
    total = float(meta.get("duration") or 0)
    ranged = start is not None or end is not None
    sec_start = float(start or 0)
    sec_end = min(float(end), total) if (end is not None and total) else (float(end) if end is not None else total)
    length = sec_end - sec_start
    native = total <= NATIVE_MAX
    if not native and length > MAX_SECTION:
        raise ValueError(
            f"This video is {total / 3600:.1f} h long. Set a time range (range start/end) of at most "
            f"{MAX_SECTION // 3600} h so it can be downloaded.")
    need = (total if native else length) / 3600 * GB_PER_HOUR * 1e9
    free = shutil.disk_usage(dest_dir).free
    if free < need * 1.2:
        raise RuntimeError(
            f"Not enough free disk space: need about {need / 1e9:.1f} GB, only {free / 1e9:.1f} GB free.")

    opts = {
        **base,
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "video.%(ext)s"),
    }
    if ranged and not native:
        opts["download_ranges"] = download_range_func(None, [(sec_start, sec_end)])
        opts["force_keyframes_at_cuts"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    path = dest_dir / "video.mp4"
    if not path.exists():
        found = sorted(dest_dir.glob("video.*"))
        if not found:
            raise RuntimeError("download produced no file")
        path = found[0]
    if ranged and native:
        section = dest_dir / "section.mp4"
        _cut_section(path, sec_start, sec_end, section)
        path.unlink()
        section.rename(dest_dir / "video.mp4")
        path = dest_dir / "video.mp4"
    if ranged and length > 5 and _probe_duration(path) < 0.5 * length:
        raise RuntimeError(
            "The time range could not be downloaded from this video (common with very long live-stream "
            "replays). Try a different range or a shorter replay.")
    return VideoInfo(
        path=path,
        title=info.get("title") or "",
        channel_id=info.get("channel_id") or info.get("uploader_id") or "unknown",
        channel=info.get("channel") or info.get("uploader") or "",
        duration=length if ranged else float(info.get("duration") or 0),
        width=int(info.get("width") or 1920),
        height=int(info.get("height") or 1080),
        info=info,
    )


ALLOWED_HOSTS = ("youtube.com", "youtu.be")


def validate_url(url: str) -> str:
    """Only http(s) YouTube URLs are accepted (blocks SSRF via yt-dlp's generic extractor)."""
    from urllib.parse import urlparse

    p = urlparse(url.strip())
    host = (p.hostname or "").rstrip(".").lower()
    if p.scheme not in ("http", "https") or not host:
        raise ValueError("URL must be http(s)")
    if not any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS):
        raise ValueError("Only YouTube URLs are supported")
    return url.strip()
