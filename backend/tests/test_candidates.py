import numpy as np

from app.candidates import find_candidates

DUR = 600


def bump(*spans, n=DUR):
    s = np.zeros(n)
    for a, b, v in spans:
        s[a:b] = v
    return s


def test_single_peak_gives_window_around_it():
    c = find_candidates(bump((100, 105, 1.0)), DUR)
    assert len(c) == 1
    assert c[0].start <= 102 <= c[0].end
    assert 20 <= c[0].end - c[0].start <= 60


def test_peak_at_start_clamped():
    c = find_candidates(bump((0, 3, 1.0)), DUR)
    assert c and c[0].start == 0


def test_peak_at_end_clamped():
    c = find_candidates(bump((DUR - 3, DUR, 1.0)), DUR)
    assert c and c[0].end <= DUR and c[0].start >= 0


def test_overlapping_peaks_deduplicated():
    assert len(find_candidates(bump((100, 104, 1.0), (110, 114, 0.9)), DUR)) == 1


def test_flat_zero_score_returns_empty():
    assert find_candidates(np.zeros(DUR), DUR) == []


def test_sorted_by_score_and_capped():
    s = bump(*[(i * 50 + 10, i * 50 + 14, 0.3 + 0.05 * i) for i in range(11)])
    c = find_candidates(s, DUR, top_k=5)
    assert len(c) == 5
    assert [x.score for x in c] == sorted((x.score for x in c), reverse=True)


def test_noisy_stream_without_strong_spikes_still_returns_best_moments():
    rng = np.random.default_rng(1)
    s = np.clip(0.4 + rng.normal(0, 0.03, DUR), 0, 1)  # loud all the time, no real spike
    s[200:205] += 0.08
    s[400:405] += 0.07
    s[50:55] += 0.06
    c = find_candidates(s, DUR)
    assert len(c) >= 3
    assert [x.score for x in c] == sorted((x.score for x in c), reverse=True)


def test_fallback_candidates_do_not_overlap_and_all_zero_still_empty():
    rng = np.random.default_rng(2)
    c = find_candidates(np.clip(0.4 + rng.normal(0, 0.03, DUR), 0, 1), DUR)
    for a, b in zip(sorted(c, key=lambda x: x.start), sorted(c, key=lambda x: x.start)[1:]):
        assert a.end <= b.start
    assert find_candidates(np.zeros(DUR), DUR) == []
