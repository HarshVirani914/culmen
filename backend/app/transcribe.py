import subprocess
from pathlib import Path

import numpy as np

from .captions import Word

_model = None


def _audio(video_path: Path, start: float, end: float) -> np.ndarray:
    """16 kHz mono float32 samples for [start, end] (decoded by ffmpeg, not PyAV)."""
    proc = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(video_path),
         "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True, check=True)
    return np.frombuffer(proc.stdout, dtype=np.float32)


def transcribe(video_path: Path, start: float, end: float) -> list[Word]:
    """Word-level transcript for [start, end]; word times are relative to clip start."""
    global _model
    from faster_whisper import WhisperModel

    if _model is None:
        _model = WhisperModel("small", compute_type="int8")
    audio = _audio(video_path, start, end)
    if audio.size == 0:
        return []
    segments, _ = _model.transcribe(audio, word_timestamps=True)
    return [Word(w.word, w.start, w.end) for s in segments for w in (s.words or [])]
