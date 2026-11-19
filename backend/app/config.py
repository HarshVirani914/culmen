import os
import shutil
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model: str | None
    data_dir: Path

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)


def get_settings() -> Settings:
    data_dir = Path(os.environ.get("CLIPPER_DATA_DIR", ROOT / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        llm_base_url=os.environ.get("LLM_BASE_URL") or None,
        llm_api_key=os.environ.get("LLM_API_KEY") or None,
        llm_model=os.environ.get("LLM_MODEL") or None,
        data_dir=data_dir,
    )


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


_FULL_FFMPEG = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"


def _has_ass(binary: str) -> bool:
    import subprocess

    try:
        out = subprocess.run([binary, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return False
    return " ass " in out


@lru_cache(maxsize=1)
def ffmpeg_bin() -> str:
    """FFMPEG_BIN if set, else the first ffmpeg that can burn ASS captions, else plain ffmpeg."""
    env = os.environ.get("FFMPEG_BIN")
    if env:
        return env
    for cand in (shutil.which("ffmpeg"), _FULL_FFMPEG):
        if cand and os.path.exists(cand) and _has_ass(cand):
            return cand
    return shutil.which("ffmpeg") or "ffmpeg"


def captions_available() -> bool:
    return _has_ass(ffmpeg_bin())
