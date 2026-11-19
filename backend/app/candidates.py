from dataclasses import dataclass

import numpy as np


@dataclass
class Candidate:
    start: float
    end: float
    score: float


def find_candidates(
    score: np.ndarray,
    duration: float,
    min_len: float = 20,
    max_len: float = 60,
    top_k: int = 10,
    min_count: int = 3,
) -> list[Candidate]:
    """Best moments of a replay from a per-second 0..1 score.

    Peaks above mean + 1.5 std come first. If fewer than `min_count` qualify (a stream that is loud all the time
    has no standout spikes), the next best local maxima are added so the user always gets something to judge.
    Windows never overlap."""
    n = len(score)
    if n == 0 or float(np.max(score)) <= 0:
        return []
    smooth = np.convolve(score, np.ones(5) / 5, mode="same")
    thr = smooth.mean() + 1.5 * smooth.std()
    maxima = [
        i for i in range(n)
        if smooth[i] > 0 and smooth[i] >= smooth[max(i - 1, 0)] and smooth[i] >= smooth[min(i + 1, n - 1)]
    ]
    maxima.sort(key=lambda i: smooth[i], reverse=True)
    strong = [i for i in maxima if smooth[i] > thr]

    length = min(max(30.0, min_len), max_len, duration)
    chosen: list[Candidate] = []

    def try_add(p: int) -> None:
        start = p - 0.35 * length
        end = start + length
        if start < 0:
            start, end = 0.0, length
        if end > duration:
            end = float(duration)
            start = max(0.0, end - length)
        if any(start < c.end and end > c.start for c in chosen):
            return
        chosen.append(Candidate(float(start), float(end), float(smooth[p])))

    for p in strong:
        if len(chosen) >= top_k:
            break
        try_add(p)
    if len(chosen) < min_count:
        for p in maxima:
            if len(chosen) >= min_count:
                break
            try_add(p)
    chosen.sort(key=lambda c: c.score, reverse=True)
    return chosen
