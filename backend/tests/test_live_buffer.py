import json
import subprocess

import pytest

from app.live.buffer import SegmentBuffer


def make_segments(d, n=6, seg=10):
    """n real MPEG-TS segments of `seg` seconds (keyframe every second), named 000000.ts ..."""
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=d={n * seg}:s=160x90:r=10",
                    "-f", "lavfi", "-i", f"sine=d={n * seg}", "-shortest", "-c:v", "libx264", "-g", "10",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-f", "segment", "-segment_time", str(seg),
                    "-reset_timestamps", "1", str(d / "%06d.ts")], check=True)


def dur(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(p)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


@pytest.fixture
def buf(tmp_path):
    make_segments(tmp_path / "buf")
    b = SegmentBuffer(tmp_path / "buf", max_seconds=30, seg_seconds=10)
    b.finalize()
    return b


def test_list_is_sorted_with_session_clock_starts(buf):
    segs = buf.list()
    assert [s.index for s in segs] == [0, 1, 2, 3, 4, 5]
    assert [s.start for s in segs] == [0, 10, 20, 30, 40, 50]


def test_newest_segment_is_incomplete_until_finalized(tmp_path):
    make_segments(tmp_path / "b")
    b = SegmentBuffer(tmp_path / "b", max_seconds=30, seg_seconds=10)
    assert [s.index for s in b.list()] == [0, 1, 2, 3, 4]  # last one may still be written
    b.finalize()
    assert len(b.list()) == 6


def test_prune_removes_old_segments_keeps_recent(buf):
    deleted = buf.prune()
    assert len(deleted) == 3
    assert [s.index for s in buf.list()] == [3, 4, 5]
    assert buf.available_start() == 30


def test_protected_segments_survive_prune_until_released(buf):
    release = buf.protect(5, 25)  # segments 0,1,2
    buf.prune()
    assert {0, 1, 2} <= {s.index for s in buf.list()}
    release()
    buf.prune()
    assert [s.index for s in buf.list()] == [3, 4, 5]


def test_extract_has_expected_duration(buf, tmp_path):
    out = tmp_path / "m.mp4"
    buf.extract(15, 40, out)
    assert abs(dur(out) - 25) < 2.5


def test_extract_clamps_to_buffer_and_raises_when_nothing_left(buf, tmp_path):
    buf.prune()  # buffer now holds 30..60
    out = tmp_path / "m.mp4"
    buf.extract(20, 45, out)  # start already rolled off: clamped to 30
    assert abs(dur(out) - 15) < 2.5
    with pytest.raises(ValueError):
        buf.extract(0, 10, tmp_path / "x.mp4")
