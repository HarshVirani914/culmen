from dataclasses import dataclass
from pathlib import Path


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


MAX_SECTION = 3 * 3600  # seconds; keeps downloads to a few GB


def download_video(url: str, dest_dir: Path, start: float | None = None, end: float | None = None) -> VideoInfo:
    """Download the whole video, or only [start, end] seconds of it."""
    import yt_dlp
    from yt_dlp.utils import download_range_func

    dest_dir.mkdir(parents=True, exist_ok=True)
    base = {"quiet": True, "noplaylist": True, "allowed_extractors": ["youtube", "youtube:tab"]}
    with yt_dlp.YoutubeDL({**base, "skip_download": True}) as ydl:
        meta = ydl.extract_info(url, download=False)
    total = float(meta.get("duration") or 0)
    sec_start = float(start or 0)
    sec_end = min(float(end), total) if (end is not None and total) else (float(end) if end is not None else total)
    length = sec_end - sec_start
    if length > MAX_SECTION:
        raise ValueError(
            f"This video section is {length / 3600:.1f} h long. Set a time range of at most "
            f"{MAX_SECTION // 3600} h (range start/end) so it can be downloaded.")
    opts = {
        **base,
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "video.%(ext)s"),
    }
    ranged = start is not None or end is not None
    if ranged:
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
