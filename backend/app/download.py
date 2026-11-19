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


def download_video(url: str, dest_dir: Path) -> VideoInfo:
    import yt_dlp

    dest_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "video.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "allowed_extractors": ["youtube", "youtube:tab"],
    }
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
        duration=float(info.get("duration") or 0),
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
