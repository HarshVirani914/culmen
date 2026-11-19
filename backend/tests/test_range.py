import time

import numpy as np
import pytest

from app import download, signals
from app.download import VideoInfo


def wait(client, jid):
    for _ in range(50):
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("ready", "error"):
            return j
        time.sleep(0.1)
    raise AssertionError("timeout")


def post(client, **kw):
    body = {"url": "https://youtu.be/x", "notes": "", **kw}
    return client.post("/api/jobs", json=body)


@pytest.mark.parametrize("kw", [
    {"range_start": -5, "range_end": 100},
    {"range_start": 100, "range_end": 50},
    {"range_start": 0, "range_end": 4 * 3600},
])
def test_bad_ranges_422(client, kw):
    assert post(client, **kw).status_code == 422


def test_range_passed_to_download_and_offset_recorded(client, monkeypatch):
    seen = {}

    orig = download.download_video

    def wrapper(url, d, start=None, end=None):
        seen["r"] = (start, end)
        return orig(url, d, start, end)
    monkeypatch.setattr(download, "download_video", wrapper)
    j = wait(client, post(client, range_start=3600, range_end=3640).json()["id"])
    assert seen["r"] == (3600, 3640)
    assert j["status"] == "ready" and j["video"]["offset"] == 3600


def test_no_range_offset_zero(client):
    j = wait(client, post(client).json()["id"])
    assert j["video"]["offset"] == 0


class FakeYDL:
    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        assert not download, "must not download before the length guard"
        return {"duration": 86000, "title": "t"}


def test_huge_video_without_range_refused_before_download(monkeypatch, tmp_path):
    import yt_dlp
    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    with pytest.raises(ValueError, match="range"):
        download.download_video("https://youtu.be/x", tmp_path)


def test_huge_section_refused(monkeypatch, tmp_path):
    import yt_dlp
    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    with pytest.raises(ValueError, match="range"):
        download.download_video("https://youtu.be/x", tmp_path, start=0, end=5 * 3600)


class WritingYDL(FakeYDL):
    def extract_info(self, url, download=True):
        if not download:
            return {"duration": 20000, "title": "t"}
        (self.dest / "video.mp4").write_bytes(b"x" * 300)
        return {"title": "t", "width": 1920, "height": 1080}


def test_empty_ranged_download_gives_clear_error(monkeypatch, tmp_path):
    import yt_dlp
    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda opts: _with_dest(WritingYDL(opts), tmp_path))
    monkeypatch.setattr(download, "_probe_duration", lambda p: 2.0)
    with pytest.raises(RuntimeError, match="time range"):
        download.download_video("https://youtu.be/x", tmp_path, start=100, end=700)


def _with_dest(y, dest):
    y.dest = dest
    return y


class NativeYDL(FakeYDL):
    seen = {}

    def extract_info(self, url, download=True):
        if not download:
            return {"duration": 7200, "title": "t", "is_live": False}
        NativeYDL.seen["opts"] = self.opts
        import subprocess
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=d=60:s=320x180:r=10",
                        "-f", "lavfi", "-i", "sine=d=60", "-shortest", "-pix_fmt", "yuv420p",
                        "-g", "10", str(self.dest / "video.mp4")], check=True)
        return {"title": "t", "width": 320, "height": 180, "duration": 7200}


def test_normal_length_video_downloads_natively_then_cuts_section_locally(monkeypatch, tmp_path):
    import yt_dlp
    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda opts: _with_dest(NativeYDL(opts), tmp_path))
    v = download.download_video("https://youtu.be/x", tmp_path, start=10, end=40)
    assert "download_ranges" not in NativeYDL.seen["opts"]  # fast native path, no ffmpeg downloader
    assert abs(download._probe_duration(v.path) - 30) < 3
    assert v.duration == 30
    assert [p.name for p in tmp_path.iterdir() if p.suffix == ".mp4"] == ["video.mp4"]  # full file removed


def test_live_stream_refused(monkeypatch, tmp_path):
    import yt_dlp

    class LiveYDL(FakeYDL):
        def extract_info(self, url, download=True):
            return {"duration": None, "is_live": True}
    monkeypatch.setattr(yt_dlp, "YoutubeDL", LiveYDL)
    with pytest.raises(ValueError, match="live"):
        download.download_video("https://youtu.be/x", tmp_path)


def test_not_enough_disk_refused_before_download(monkeypatch, tmp_path):
    import collections
    import yt_dlp
    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda opts: _with_dest(NativeYDL(opts), tmp_path))
    Usage = collections.namedtuple("Usage", "total used free")
    monkeypatch.setattr(download.shutil, "disk_usage", lambda p: Usage(10**12, 10**12 - 10**6, 10**6))
    with pytest.raises(RuntimeError, match="disk"):
        download.download_video("https://youtu.be/x", tmp_path, start=10, end=40)


def test_download_is_configured_to_retry_on_network_timeouts(monkeypatch, tmp_path):
    import yt_dlp
    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda opts: _with_dest(NativeYDL(opts), tmp_path))
    download.download_video("https://youtu.be/x", tmp_path)
    o = NativeYDL.seen["opts"]
    assert o["retries"] >= 5 and o["fragment_retries"] >= 5 and 0 < o["socket_timeout"] <= 60
    assert o["concurrent_fragment_downloads"] >= 16  # live-stream replays are thousands of throttled fragments


@pytest.mark.parametrize("kw", [
    {"range_start": 1, "range_end": 2},         # "1 to 2" typed meaning hours
    {"range_start": 100, "range_end": 110},
])
def test_tiny_ranges_rejected_with_a_helpful_message(client, kw):
    r = post(client, **kw)
    assert r.status_code == 422
    assert "too short" in r.json()["detail"] and "h:mm:ss" in r.json()["detail"]


class PostLiveYDL(FakeYDL):
    def extract_info(self, url, download=True):
        assert not download, "must refuse before downloading"
        return {"duration": 86000, "title": "t", "live_status": "post_live"}


def test_just_ended_long_stream_gets_a_clear_wait_message(monkeypatch, tmp_path):
    import yt_dlp
    monkeypatch.setattr(yt_dlp, "YoutubeDL", PostLiveYDL)
    with pytest.raises(ValueError, match="still processing"):
        download.download_video("https://youtu.be/x", tmp_path, start=3600, end=7200)


def test_post_live_short_stream_still_downloads_whole_and_cuts_locally(monkeypatch, tmp_path):
    import yt_dlp

    class ShortPostLive(NativeYDL):
        def extract_info(self, url, download=True):
            info = super().extract_info(url, download)
            if not download:
                info["live_status"] = "post_live"
            return info
    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda opts: _with_dest(ShortPostLive(opts), tmp_path))
    v = download.download_video("https://youtu.be/x", tmp_path, start=10, end=40)
    assert abs(download._probe_duration(v.path) - 30) < 3


def test_download_passes_cookie_file_to_ytdlp_when_configured(monkeypatch, tmp_path):
    import yt_dlp
    cf = tmp_path / "c.txt"
    cf.write_text("x")
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(cf))
    monkeypatch.setattr(yt_dlp, "YoutubeDL", lambda opts: _with_dest(NativeYDL(opts), tmp_path))
    download.download_video("https://youtu.be/x", tmp_path)
    assert NativeYDL.seen["opts"]["cookiefile"] == str(cf)
