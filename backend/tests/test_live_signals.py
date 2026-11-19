import subprocess

import numpy as np

from app.live.signals import ScoreTracker, segment_audio_scores


def ff(*a):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)


def test_segment_audio_scores_detects_burst(tmp_path):
    p = tmp_path / "000000.ts"
    ff("-f", "lavfi", "-i", "sine=f=440:d=6", "-af", "volume='if(between(t,3,4),1,0.02)':eval=frame",
       "-c:a", "aac", "-f", "mpegts", str(p))
    s = segment_audio_scores(p, 6)
    assert len(s) >= 5 and abs(int(np.argmax(s)) - 3) <= 1


def test_segment_without_audio_returns_zeros(tmp_path):
    p = tmp_path / "000000.ts"
    ff("-f", "lavfi", "-i", "testsrc=d=6:s=64x64:r=10", "-an", "-c:v", "libx264", "-f", "mpegts", str(p))
    s = segment_audio_scores(p, 6)
    assert len(s) == 6 and (s == 0).all()


def feed_quiet(tr, seconds, rms=0.02):
    for t in range(seconds):
        tr.add_audio(t, rms)


def test_tracker_audio_spike_scores_high_after_quiet_baseline():
    tr = ScoreTracker()
    feed_quiet(tr, 100)
    tr.add_audio(100, 0.6)
    assert tr.score(100) > 0.6
    assert tr.score(50) < 0.1
    assert not tr.has_chat


def test_tracker_chat_crowd_beats_single_user_spam():
    tr = ScoreTracker()
    feed_quiet(tr, 120)
    for t in range(0, 100):
        tr.add_chat(t, f"bg{t % 3}")  # light background chat
    for i in range(60):
        tr.add_chat(110, "spammer")
    spam_score = tr.score(110)
    for i in range(40):
        tr.add_chat(115, f"user{i}")
    crowd_score = tr.score(115)
    assert tr.has_chat and crowd_score > spam_score and crowd_score > 0.5


def test_tracker_audio_only_when_no_chat_still_works():
    tr = ScoreTracker()
    feed_quiet(tr, 60)
    tr.add_audio(60, 0.8)
    assert 0 < tr.score(60) <= 1 and tr.has_chat is False


def test_tracker_never_returns_nan_on_empty():
    tr = ScoreTracker()
    assert tr.score(0) == 0.0 and tr.score(500) == 0.0
