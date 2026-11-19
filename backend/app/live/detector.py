from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class MomentWindow:
    start: float
    end: float
    score: float


class LiveDetector:
    """Turns a once-per-second 0..1 score into moment windows (session clock, seconds).

    A trigger needs the mean of the last 5 s to beat an adaptive threshold (mean + 2 std of the last
    `history` seconds, excluding the newest 10 s, never below `floor`). The window is emitted once the post-roll
    has elapsed, so the reaction is inside it.
    """

    SMOOTH = 5
    HOLDOUT = 10
    WARMUP = 20
    LEAD = 3  # trigger is seen about this many seconds after the real start (smoothing lag)
    MAX_PENDING = 25
    MIN_LEN = 30
    MAX_LEN = 60

    def __init__(self, pre_roll: float = 25, post_roll: float = 12, tail: float = 3, cooldown: float = 45,
                 max_per_hour: int = 12, history: float = 600, floor: float = 0.35, margin: float = 0.1):
        self.pre_roll, self.post_roll, self.tail = pre_roll, post_roll, tail
        self.cooldown, self.max_per_hour, self.history = cooldown, max_per_hour, history
        self.floor, self.margin = floor, margin
        self.available_start: float = 0.0
        self._hist: deque[tuple[float, float]] = deque()
        self._fired: list[float] = []
        self._cooldown_until = float("-inf")
        self._t0: float | None = None
        self._last_hot = 0.0
        self._peak = 0.0

    def _threshold(self, t: float) -> float | None:
        base = [s for (ts, s) in self._hist if ts <= t - self.HOLDOUT]
        if len(base) < self.WARMUP:
            return None
        arr = np.asarray(base)
        return max(self.floor, float(arr.mean() + max(2 * arr.std(), self.margin)))

    def feed(self, t: float, score: float) -> MomentWindow | None:
        self._hist.append((t, score))
        while self._hist and self._hist[0][0] < t - self.history:
            self._hist.popleft()
        recent = [s for (_, s) in list(self._hist)[-self.SMOOTH:]]
        current = float(np.mean(recent))
        thr = self._threshold(t)
        hot = thr is not None and current > thr

        if self._t0 is None:
            if not hot or t < self._cooldown_until:
                return None
            self._fired = [f for f in self._fired if f > t - 3600]
            if len(self._fired) >= self.max_per_hour:
                return None
            self._t0, self._last_hot, self._peak = t, t, current
            return None

        if hot:
            self._last_hot = t
            self._peak = max(self._peak, current)
        fire_at = min(max(self._t0 + self.post_roll, self._last_hot + self.tail), self._t0 + self.MAX_PENDING)
        if t < fire_at:
            return None

        start = self._t0 - self.LEAD - self.pre_roll
        end = t
        if end - start > self.MAX_LEN:
            start = end - self.MAX_LEN
        if end - start < self.MIN_LEN:
            start = end - self.MIN_LEN
        start = max(start, self.available_start)
        peak = self._peak
        self._t0 = None
        self._fired.append(t)
        self._cooldown_until = t + self.cooldown
        return MomentWindow(float(start), float(end), peak)
