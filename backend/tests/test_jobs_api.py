import subprocess
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import download, signals
from app.download import VideoInfo


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPPER_DATA_DIR", str(tmp_path / "data"))
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    vid = tmp_path / "fake.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=d=40:s=320x180:r=10",
                    "-f", "lavfi", "-i", "sine=d=40", "-shortest", "-pix_fmt", "yuv420p", str(vid)], check=True)
    monkeypatch.setattr(download, "download_video", lambda url, d: VideoInfo(
        vid, "T", "UC1", "Chan", 40.0, 320, 180, {}))
    bump = np.zeros(40); bump[20:24] = 1
    monkeypatch.setattr(signals, "audio_energy", lambda p, d: bump)
    monkeypatch.setattr(signals, "chat_rate", lambda u, d: np.zeros(40))
    from app.main import app
    return TestClient(app)


def wait_ready(client, jid):
    for _ in range(50):
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("ready", "error"):
            return j
        time.sleep(0.1)
    raise AssertionError("timeout")


def test_create_job_returns_id_and_reaches_ready(client):
    r = client.post("/api/jobs", json={"url": "https://youtube.com/watch?v=y", "notes": ""})
    assert r.status_code == 200
    j = wait_ready(client, r.json()["id"])
    assert j["status"] == "ready" and j["candidates"]
    assert j["video"]["channel_id"] == "UC1"


def test_analysis_error_sets_error_status(client, monkeypatch):
    def boom(u, d):
        raise RuntimeError("video unavailable")
    monkeypatch.setattr(download, "download_video", boom)
    j = wait_ready(client, client.post("/api/jobs", json={"url": "https://youtu.be/x", "notes": ""}).json()["id"])
    assert j["status"] == "error" and "video unavailable" in j["error"]


def test_zero_candidates_is_ready_with_empty_list(client, monkeypatch):
    monkeypatch.setattr(signals, "audio_energy", lambda p, d: np.zeros(40))
    j = wait_ready(client, client.post("/api/jobs", json={"url": "https://youtu.be/x", "notes": ""}).json()["id"])
    assert j["status"] == "ready" and j["candidates"] == []


def test_unknown_job_404(client):
    assert client.get("/api/jobs/nope").status_code == 404


def test_frame_endpoint_returns_jpeg(client):
    jid = client.post("/api/jobs", json={"url": "https://youtu.be/x", "notes": ""}).json()["id"]
    wait_ready(client, jid)
    r = client.get(f"/api/jobs/{jid}/frame")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
