import subprocess

import numpy as np

from app import signals


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def test_normalize_constant_is_zeros():
    assert (signals.normalize(np.full(5, 3.0)) == 0).all()


def test_normalize_range():
    out = signals.normalize(np.array([2.0, 4.0, 6.0]))
    assert out.min() == 0 and out.max() == 1


def test_heatmap_signal_resamples():
    info = {"heatmap": [
        {"start_time": 0, "end_time": 5, "value": 0.2},
        {"start_time": 5, "end_time": 10, "value": 0.8},
    ]}
    out = signals.heatmap_signal(info, 10)
    assert len(out) == 10
    assert out[0] < out[9]


def test_heatmap_signal_missing_returns_zeros():
    out = signals.heatmap_signal({}, 10)
    assert len(out) == 10 and (out == 0).all()
    assert (signals.heatmap_signal({"heatmap": None}, 10) == 0).all()


def test_combine_skips_all_zero_parts():
    audio = np.array([0, 0, 1.0, 0, 0])
    out = signals.combine({"audio": audio, "chat": np.zeros(5)}, {"audio": 0.25, "chat": 0.35})
    assert np.allclose(out, signals.normalize(audio))


def test_audio_energy_detects_loud_burst(tmp_path):
    wav = tmp_path / "a.wav"
    ff("-f", "lavfi", "-i", "sine=f=440:d=10", "-af", "volume='if(between(t,5,6),1,0.02)':eval=frame", str(wav))
    out = signals.audio_energy(wav, 10)
    assert abs(int(np.argmax(out)) - 5) <= 1


def test_audio_energy_no_audio_stream_returns_zeros(tmp_path):
    mp4 = tmp_path / "v.mp4"
    ff("-f", "lavfi", "-i", "testsrc=d=5:s=160x90", "-an", str(mp4))
    out = signals.audio_energy(mp4, 5)
    assert len(out) == 5 and (out == 0).all()


def test_chat_rate_unavailable_returns_zeros(monkeypatch):
    def boom(url, s=None, e=None):
        raise RuntimeError("chat disabled")
    monkeypatch.setattr(signals, "_fetch_chat", boom)
    out = signals.chat_rate("http://x", 10)
    assert len(out) == 10 and (out == 0).all()


def test_chat_rate_detects_spike(monkeypatch):
    msgs = [(float(t), "hi", f"u{t}") for t in range(0, 60, 5)] + [(30.0 + i * 0.1, "LOL", f"v{i}") for i in range(40)]
    monkeypatch.setattr(signals, "_fetch_chat", lambda url, s=None, e=None: msgs)
    out = signals.chat_rate("http://x", 60)
    assert 29 <= int(np.argmax(out)) <= 34


def test_heatmap_signal_offset_slices_section():
    info = {"heatmap": [{"start_time": 100, "end_time": 110, "value": 1.0}]}
    out = signals.heatmap_signal(info, 20, offset=95)
    assert len(out) == 20
    assert (out[5:15] == 1.0).all() and out[:5].sum() == 0 and out[15:].sum() == 0


def test_chat_rate_offset_shifts_timestamps_and_requests_section(monkeypatch):
    seen = {}

    def fake(url, s=None, e=None):
        seen["range"] = (s, e)
        return ([(1000.0 + 30 + i * 0.1, "LOL", f"v{i}") for i in range(40)]
                + [(1000.0 + t, "hi", f"u{t}") for t in range(0, 60, 5)])
    monkeypatch.setattr(signals, "_fetch_chat", fake)
    out = signals.chat_rate("http://x", 60, offset=1000)
    assert seen["range"] == (1000, 1060)
    assert 29 <= int(np.argmax(out)) <= 34


def test_chat_rate_ignores_single_user_spam_but_counts_many_users(monkeypatch):
    spam = [(20.0 + i * 0.05, "KEKW", "same-user") for i in range(80)]
    crowd = [(45.0 + i * 0.1, "LOL", f"user{i}") for i in range(40)]
    background = [(float(t), "hi", f"bg{t}") for t in range(0, 60, 4)]
    monkeypatch.setattr(signals, "_fetch_chat", lambda url, s=None, e=None: spam + crowd + background)
    out = signals.chat_rate("http://x", 60)
    assert 44 <= int(np.argmax(out)) <= 49
