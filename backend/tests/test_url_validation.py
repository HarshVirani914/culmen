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
