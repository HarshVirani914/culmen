import subprocess
import tempfile
from pathlib import Path

from .captions import Word

_model = None


def transcribe(video_path: Path, start: float, end: float) -> list[Word]:
    """Word-level transcript for [start, end]; word times are relative to clip start."""
    global _model
    from faster_whisper import WhisperModel

    if _model is None:
        _model = WhisperModel("small", compute_type="int8")
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "a.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
                        "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
        segments, _ = _model.transcribe(str(wav), word_timestamps=True)
        return [Word(w.word, w.start, w.end) for s in segments for w in (s.words or [])]
