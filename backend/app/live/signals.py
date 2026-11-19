import math
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np

from ..config import ffmpeg_bin


def segment_audio_scores(path: Path, seg_seconds: float = 6) -> np.ndarray:
    """Per-second RMS loudness (0..1) of one segment; zeros when there is no audio."""
    n = math.ceil(seg_seconds)
    try:
        proc = subprocess.run([ffmpeg_bin(), "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                               "-f", "s16le", "-"], capture_output=True, check=True)
    except Exception:
        return np.zeros(n)
    pcm = np.frombuffer(proc.stdout, dtype=np.int16).astype(float) / 32768.0
    secs = pcm.size // 16000
    if secs == 0:
        return np.zeros(n)
    rms = np.sqrt((pcm[: secs * 16000].reshape(secs, 16000) ** 2).mean(axis=1))
    out = np.zeros(n)
    out[: min(n, secs)] = rms[:n]
    return out


class ScoreTracker:
    """Combines live loudness and chat into one 0..1 score per second (session clock).

    Audio: how far the second rises above the median of the previous minute. Chat: how far the number of
    distinct chatters in the last 3 s rises above the chat baseline, so one spammer does not count."""

    def __init__(self, history: float = 600):
        self.history = history
        self._audio: dict[int, float] = {}
        self._chat: dict[int, set[str]] = defaultdict(set)
        self.has_chat = False
        self._n_chat = 0

    def add_audio(self, t: float, rms: float) -> None:
        self._audio[int(t)] = float(rms)
        self._trim(int(t))

    def add_chat(self, t: float, author: str) -> None:
        self._chat[int(t)].add(author or f"anon{self._n_chat}")
        self._n_chat += 1
        self.has_chat = True
        self._trim(int(t))

    def _trim(self, t: int) -> None:
        lo = t - int(self.history)
        for d in (self._audio, self._chat):
            for k in [k for k in d if k < lo]:
                del d[k]

    def _audio_score(self, t: int) -> float:
        rms = self._audio.get(t)
        if rms is None:
            return 0.0
        prev = [v for s, v in self._audio.items() if t - 60 <= s < t]
        med = float(np.median(prev)) if prev else rms
        x = max(0.0, rms - med) / (med + 0.05 * max(rms, 1e-3) + 1e-6)
        return x / (x + 1.5)

    def _chat_score(self, t: int) -> float:
        now = float(np.mean([len(self._chat.get(s, ())) for s in (t - 2, t - 1, t)]))
        base_vals = [len(self._chat.get(s, ())) for s in range(t - int(self.history), t - 9)]
        base = float(np.mean(base_vals)) if base_vals else 0.0
        return float(min(1.0, max(0.0, (now - base) / max(base * 2, 3.0))))

    def score(self, t: float) -> float:
        t = int(t)
        a = self._audio_score(t)
        if not self.has_chat:
            return float(a)
        c = self._chat_score(t)
        return float(0.6 * max(a, c) + 0.4 * min(a, c))
