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
