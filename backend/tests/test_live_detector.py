import numpy as np

from app.live.detector import LiveDetector


def run(det, scores, start=0):
    out = []
    for i, s in enumerate(scores):
        w = det.feed(start + i, float(s))
        if w:
            out.append((start + i, w))
    return out


def series(n, *spikes, base=0.0):
    s = np.full(n, base)
    for a, b, v in spikes:
        s[a:b] = v
    return s


def test_quiet_stream_never_triggers():
    assert run(LiveDetector(), series(900, base=0.05)) == []


def test_all_zero_scores_no_crash():
    assert run(LiveDetector(), np.zeros(900)) == []


def test_spike_triggers_after_post_roll_with_window_around_it():
    got = run(LiveDetector(), series(300, (100, 105, 1.0)))
    assert len(got) == 1
    fired_at, w = got[0]
    assert fired_at >= 100 + 12
    assert w.start <= 100 and w.end >= 105
    assert 30 <= w.end - w.start <= 60
    assert w.end <= fired_at


def test_cooldown_blocks_second_moment_but_later_spike_accepted():
    s = series(400, (100, 106, 1.0), (120, 126, 1.0), (200, 206, 1.0))
    got = run(LiveDetector(), s)
    starts = [w.start for _, w in got]
    assert len(got) == 2 and starts[1] > 150


def test_max_per_hour_cap():
    s = series(900, *[(100 + 60 * i, 106 + 60 * i, 1.0) for i in range(6)])
    got = run(LiveDetector(max_per_hour=2, cooldown=10), s)
    assert len(got) == 2


def test_window_clamped_to_available_start():
    det = LiveDetector()
    det.available_start = 60
    got = run(det, series(200, (100, 105, 1.0)))
    assert got and got[0][1].start >= 60


def test_spike_right_after_warmup_still_clamped_to_zero():
    got = run(LiveDetector(), series(120, (25, 30, 1.0)))
    assert got and got[0][1].start >= 0


def test_adaptive_threshold_ignores_constant_loud_stream():
    assert run(LiveDetector(), series(900, base=0.9)) == []


def test_long_loud_event_window_never_exceeds_60s():
    got = run(LiveDetector(), series(400, (100, 160, 1.0)))
    assert got and all(w.end - w.start <= 60 for _, w in got)
