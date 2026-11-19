import subprocess
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import download, signals
from app.download import VideoInfo


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
    def boom(u, d, start=None, end=None):
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


def test_frame_at_time_returns_different_frames_and_clamps(client):
    jid = client.post("/api/jobs", json={"url": "https://youtu.be/x", "notes": ""}).json()["id"]
    wait_ready(client, jid)
    a = client.get(f"/api/jobs/{jid}/frame", params={"t": 2})
    b = client.get(f"/api/jobs/{jid}/frame", params={"t": 30})
    assert a.status_code == b.status_code == 200 and a.headers["content-type"] == "image/jpeg"
    assert a.content != b.content  # the test video changes over time
    assert client.get(f"/api/jobs/{jid}/frame", params={"t": 30}).content == b.content  # cached, stable
    far = client.get(f"/api/jobs/{jid}/frame", params={"t": 99999})
    assert far.status_code == 200  # clamped to the end of the video
    assert client.get(f"/api/jobs/{jid}/frame", params={"t": -5}).status_code == 422


def test_frame_without_time_still_returns_the_default_frame(client):
    jid = client.post("/api/jobs", json={"url": "https://youtu.be/x", "notes": ""}).json()["id"]
    wait_ready(client, jid)
    assert client.get(f"/api/jobs/{jid}/frame").status_code == 200
