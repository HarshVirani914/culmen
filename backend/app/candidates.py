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
) -> list[Candidate]:
    n = len(score)
    if n == 0 or float(np.max(score)) <= 0:
        return []
    smooth = np.convolve(score, np.ones(5) / 5, mode="same")
    thr = smooth.mean() + 1.5 * smooth.std()
    peaks = [
        i
        for i in range(n)
        if smooth[i] > 0
        and smooth[i] > thr
        and smooth[i] >= smooth[max(i - 1, 0)]
        and smooth[i] >= smooth[min(i + 1, n - 1)]
    ]
    peaks.sort(key=lambda i: smooth[i], reverse=True)

    length = min(max(30.0, min_len), max_len, duration)
    chosen: list[Candidate] = []
    for p in peaks:
        if len(chosen) >= top_k:
            break
        if any(c.start <= p <= c.end for c in chosen):
            continue
        start = p - 0.35 * length
        end = start + length
        if start < 0:
            start, end = 0.0, length
        if end > duration:
            end = float(duration)
            start = max(0.0, end - length)
        chosen.append(Candidate(float(start), float(end), float(smooth[p])))
    chosen.sort(key=lambda c: c.score, reverse=True)
    return chosen
