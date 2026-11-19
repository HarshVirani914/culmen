import pytest
from fastapi.testclient import TestClient

from app.download import validate_url


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=abc",
    "https://youtube.com/live/abc",
    "https://m.youtube.com/watch?v=abc",
    "https://youtu.be/abc",
])
def test_valid_urls(url):
    assert validate_url(url) == url


@pytest.mark.parametrize("url", [
    "http://localhost:8000/x",
    "http://127.0.0.1/x",
    "file:///etc/passwd",
    "https://evil.com/?youtube.com",
    "https://youtube.com.evil.com/x",
    "ftp://youtube.com/x",
    "not a url",
])
def test_rejected_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_api_rejects_bad_url(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPPER_DATA_DIR", str(tmp_path))
    from app.main import app
    r = TestClient(app).post("/api/jobs", json={"url": "http://127.0.0.1/x", "notes": ""})
    assert r.status_code == 422


@pytest.mark.parametrize("url", [
    "https://www.twitch.tv/videos/123",
    "https://twitch.tv/somechannel",
    "https://m.twitch.tv/x",
    "https://kick.com/somechannel",
    "https://www.kick.com/somechannel",
])
def test_twitch_and_kick_urls_valid(url):
    assert validate_url(url) == url


@pytest.mark.parametrize("url", [
    "https://twitch.tv.evil.com/x",
    "https://kick.com.evil.com/x",
    "https://evilkick.com/x",
    "https://nottwitch.tv/x",
])
def test_lookalike_hosts_rejected_for_new_platforms(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_extractor_list_covers_platforms():
    import re
    from app.download import ALLOWED_EXTRACTORS
    for name in ("youtube", "youtube:tab", "YoutubeYtBe", "twitch:stream", "twitch:vod", "twitch:clips", "kick:live", "kick:vod"):
        assert any(re.fullmatch(p, name) for p in ALLOWED_EXTRACTORS), name
    assert not any(re.fullmatch(p, "generic") for p in ALLOWED_EXTRACTORS)
