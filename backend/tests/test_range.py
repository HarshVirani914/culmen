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
