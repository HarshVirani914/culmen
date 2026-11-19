import json
import tempfile
from pathlib import Path


def parse_live_chat(lines) -> list[tuple[float, str, str]]:
    """Parse yt-dlp's `live_chat` JSON lines into (seconds, text, author_channel_id) tuples."""
    out: list[tuple[float, str, str]] = []
    for raw in lines:
        try:
            d = json.loads(raw)
        except (TypeError, ValueError):
            continue
        r = d.get("replayChatItemAction") if isinstance(d, dict) else None
        if not r or "videoOffsetTimeMsec" not in r:
            continue
        try:
            t = int(r["videoOffsetTimeMsec"]) / 1000
        except (TypeError, ValueError):
            continue
        for action in r.get("actions", []):
            msg = action.get("addChatItemAction", {}).get("item", {}).get("liveChatTextMessageRenderer")
            if not msg:
                continue
            runs = msg.get("message", {}).get("runs", [])
            text = "".join(run.get("text", "") for run in runs)
            out.append((t, text, msg.get("authorExternalChannelId", "")))
    return out


def fetch_live_chat(url: str) -> list[tuple[float, str, str]]:
    """Download the whole chat replay of a YouTube video with yt-dlp (about 30 s for a 3 h stream)."""
    import yt_dlp

    with tempfile.TemporaryDirectory() as d:
        opts = {
            "skip_download": True, "writesubtitles": True, "subtitleslangs": ["live_chat"],
            "outtmpl": str(Path(d) / "c"), "quiet": True, "noplaylist": True,
            "allowed_extractors": ["youtube", "youtube:tab"],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
        files = list(Path(d).glob("*.live_chat.json"))
        if not files:
            raise RuntimeError("this video has no chat replay")
        with files[0].open() as f:
            return parse_live_chat(f)
