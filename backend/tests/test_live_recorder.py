import subprocess
import time

import pytest

from app.live import recorder as rec_mod
from app.live.recorder import Recorder, next_start_number


@pytest.fixture(scope="module")
def src(tmp_path_factory):
    p = tmp_path_factory.mktemp("live") / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=d=10:s=160x90:r=10",
                    "-f", "lavfi", "-i", "sine=d=10", "-shortest", "-c:v", "libx264", "-g", "10",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(p)], check=True)
    return p


def wait_for(cond, timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.2)
    return False


def test_records_segments_and_reports_recording(src, tmp_path):
    got = []
    r = Recorder(lambda: [str(src)], tmp_path / "b", on_segment=got.append, seg_seconds=2, realtime=True)
    r.start()
    try:
        assert wait_for(lambda: len(got) >= 2)
        assert r.status in ("recording", "ended")
        assert all(s.path.exists() for s in got)
    finally:
        r.stop()


def test_ends_when_source_finishes_and_reports_last_segment(src, tmp_path):
    got = []
    r = Recorder(lambda: [str(src)], tmp_path / "b", on_segment=got.append, seg_seconds=2, realtime=False)
    r.start()
    assert wait_for(lambda: r.status == "ended")
    assert len(got) >= 4  # 10 s of video in 2 s segments, including the final one


def test_retries_then_errors_on_bad_source_and_re_resolves_each_time(tmp_path, monkeypatch):
    monkeypatch.setattr(rec_mod, "BACKOFF", (0.05,) * 5)
    calls = []

    def source():
        calls.append(1)
        return ["/definitely/not/here.mp4"]
    r = Recorder(source, tmp_path / "b", seg_seconds=2, retries=2)
    r.start()
    assert wait_for(lambda: r.status == "error", 15)
    assert r.error and len(calls) == 3  # first try plus 2 retries, URL re-resolved each time


def test_stop_is_idempotent_and_kills_ffmpeg(src, tmp_path):
    r = Recorder(lambda: [str(src)], tmp_path / "b", seg_seconds=2, realtime=True)
    r.start()
    time.sleep(1.0)
    r.stop()
    r.stop()
    assert r._proc is None or r._proc.poll() is not None


def test_stop_before_start_or_first_segment_is_safe(src, tmp_path):
    Recorder(lambda: [str(src)], tmp_path / "b0").stop()
    r = Recorder(lambda: [str(src)], tmp_path / "b", seg_seconds=2, realtime=True)
    r.start()
    r.stop()


def test_next_start_number_continues_after_existing_segments(tmp_path):
    (tmp_path / "000000.ts").write_bytes(b"x")
    (tmp_path / "000007.ts").write_bytes(b"x")
    assert next_start_number(tmp_path) == 8
    assert next_start_number(tmp_path / "empty") == 0
