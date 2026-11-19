import os
import platform
import subprocess
from pathlib import Path

import numpy as np

from .captions import Word

MLX_MODEL = "mlx-community/whisper-large-v3-turbo"
_models: dict[str, object] = {}


def _mlx():
    try:
        import mlx_whisper
        return mlx_whisper
    except ImportError:
        return None


def backend() -> str:
    """"mlx" (Apple GPU, large-v3-turbo) when available, else "faster" (faster-whisper on CPU).
    Override with WHISPER_BACKEND=faster|mlx."""
    forced = os.environ.get("WHISPER_BACKEND")
    if forced in ("faster", "mlx"):
        return forced
    on_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
    return "mlx" if on_apple_silicon and _mlx() is not None else "faster"


def _faster(name: str):
    from faster_whisper import WhisperModel

    if name not in _models:
        _models[name] = WhisperModel(name, compute_type="int8")
    return _models[name]


def _audio(video_path: Path, start: float, end: float) -> np.ndarray:
    """16 kHz mono float32 samples for [start, end] (decoded by ffmpeg, not PyAV)."""
    proc = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(video_path),
         "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True, check=True)
    return np.frombuffer(proc.stdout, dtype=np.float32)


def transcribe(video_path: Path, start: float, end: float) -> list[Word]:
    """Word-level transcript for captions; word times are relative to the clip start."""
    audio = _audio(video_path, start, end)
    if audio.size == 0:
        return []
    if backend() == "mlx":
        r = _mlx().transcribe(audio, path_or_hf_repo=MLX_MODEL, word_timestamps=True)
        return [Word(w["word"], w["start"], w["end"]) for seg in r["segments"] for w in seg.get("words", [])]
    segments, _ = _faster("small").transcribe(audio, word_timestamps=True)
    return [Word(w.word, w.start, w.end) for s in segments for w in (s.words or [])]


def transcribe_text(video_path: Path, start: float, end: float) -> str:
    """Plain transcript for LLM ranking (no word timing). Language is auto-detected per clip."""
    audio = _audio(video_path, start, end)
    if audio.size == 0:
        return ""
    if backend() == "mlx":
        return _mlx().transcribe(audio, path_or_hf_repo=MLX_MODEL, word_timestamps=False)["text"].strip()
    segments, _ = _faster("base").transcribe(
        audio, beam_size=1, vad_filter=True, word_timestamps=False, condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segments).strip()
