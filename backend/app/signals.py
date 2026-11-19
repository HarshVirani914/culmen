import math
import re
import subprocess
from pathlib import Path

import numpy as np

DEFAULT_WEIGHTS = {"heatmap": 0.4, "chat": 0.35, "audio": 0.25}


def normalize(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    if a.size == 0:
        return a
    lo, hi = a.min(), a.max()
    if hi - lo < 1e-12:
        return np.zeros_like(a)
    return (a - lo) / (hi - lo)


def _spike(series: np.ndarray, window: int = 60) -> np.ndarray:
    """Score how far each second rises above its rolling median."""
    n = len(series)
    out = np.zeros(n)
    for i in range(n):
        lo, hi = max(0, i - window // 2), min(n, i + window // 2 + 1)
        med = np.median(series[lo:hi])
        out[i] = max(0.0, series[i] - med) / (med + 1e-6 + 0.05 * series.max())
    return out


def audio_energy(video_path: Path, duration: float) -> np.ndarray:
    n = math.ceil(duration)
    try:
        proc = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", str(video_path), "-vn", "-ac", "1",
             "-ar", "16000", "-f", "s16le", "-"],
            capture_output=True, check=True,
        )
    except Exception:
        return np.zeros(n)
    pcm = np.frombuffer(proc.stdout, dtype=np.int16).astype(float) / 32768.0
    if pcm.size < 16000:
        return np.zeros(n)
    secs = pcm[: (pcm.size // 16000) * 16000].reshape(-1, 16000)
    rms = np.sqrt((secs ** 2).mean(axis=1))
    out = normalize(_spike(rms))
    if len(out) < n:
        out = np.pad(out, (0, n - len(out)))
    return out[:n]


def _fetch_chat(url: str) -> list[tuple[float, str]]:
    from chat_downloader import ChatDownloader

    chat = ChatDownloader().get_chat(url, message_groups=["messages"])
    return [(float(m["time_in_seconds"]), str(m.get("message", ""))) for m in chat
            if m.get("time_in_seconds") is not None]


def chat_rate(url: str, duration: float) -> np.ndarray:
    n = math.ceil(duration)
    try:
        msgs = _fetch_chat(url)
    except Exception:
        return np.zeros(n)
    if not msgs:
        return np.zeros(n)
    counts = np.zeros(n)
    for t, text in msgs:
        i = int(t)
        if not 0 <= i < n:
            continue
        letters = re.sub(r"[^A-Za-z]", "", text)
        shouty = len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) > 0.6
        counts[i] += 1.5 if shouty else 1.0
    counts = np.convolve(counts, np.ones(3) / 3, mode="same")
    return normalize(_spike(counts))


def heatmap_signal(info: dict, duration: float) -> np.ndarray:
    n = math.ceil(duration)
    out = np.zeros(n)
    for seg in info.get("heatmap") or []:
        a, b = int(seg["start_time"]), math.ceil(seg["end_time"])
        out[max(a, 0):min(b, n)] = seg["value"]
    return out


def combine(parts: dict[str, np.ndarray], weights: dict[str, float] | None = None) -> np.ndarray:
    weights = weights or DEFAULT_WEIGHTS
    live = {k: normalize(v) for k, v in parts.items() if np.any(np.asarray(v) != 0)}
    live = {k: v for k, v in live.items() if np.any(v != 0)}
    n = max((len(v) for v in parts.values()), default=0)
    if not live:
        return np.zeros(n)
    total = sum(weights.get(k, 0.2) for k in live)
    acc = np.zeros(n)
    for k, v in live.items():
        acc[: len(v)] += weights.get(k, 0.2) * v
    return normalize(acc / total)
