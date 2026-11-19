import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from app.live import session as live_session
from app.live.session import LiveSession, StreamInfo


def make_source(path, seconds, bursts=()):
    """Quiet tone with loud bursts at the given start seconds (5 s long), tiny video."""
    cond = "+".join(f"between(t,{b},{b + 5})" for b in bursts) or "0"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=d={seconds}:s=160x90:r=10",
                    "-f", "lavfi", "-i", f"sine=f=440:d={seconds}", "-af", f"volume='if({cond},1,0.02)':eval=frame",
                    "-shortest", "-c:v", "libx264", "-g", "10", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)],
                   check=True)
    return path


@pytest.fixture(scope="module")
def burst_src(tmp_path_factory):
    return make_source(tmp_path_factory.mktemp("lv") / "burst.mp4", 100, bursts=(60,))


@pytest.fixture(scope="module")
def long_src(tmp_path_factory):
    return make_source(tmp_path_factory.mktemp("lv2") / "long.mp4", 90)


def fake_resolver(path):
    return lambda url: StreamInfo([str(path)], "Test stream", "UCtest", "Tester", 160, 90)


@pytest.fixture
def live(client, monkeypatch):
    monkeypatch.setattr(live_session, "default_chat_source", lambda url: None)
    yield client
    mgr = live_session.get_manager()
    if mgr.current():
        mgr.current().stop()
    mgr.reset()


def wait_for(cond, timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        v = cond()
        if v:
            return v
        time.sleep(0.3)
    return None


def start(client, url="https://www.twitch.tv/test"):
    return client.post("/api/live", json={"url": url, "notes": "funny"})


def test_start_returns_id_and_status(live, monkeypatch, long_src):
    monkeypatch.setattr(live_session, "default_resolver", fake_resolver(long_src))
    monkeypatch.setattr(live_session, "REALTIME", True)
    r = start(live)
    assert r.status_code == 200
    s = live.get(f"/api/live/{r.json()['id']}").json()
    assert s["status"] in ("starting", "recording")
    assert s["signals"]["chat"] is False  # no chat source in this test


def test_second_start_while_running_is_409(live, monkeypatch, long_src):
    monkeypatch.setattr(live_session, "default_resolver", fake_resolver(long_src))
    monkeypatch.setattr(live_session, "REALTIME", True)
    assert start(live).status_code == 200
    assert start(live).status_code == 409


def test_non_live_url_is_422(live, monkeypatch):
    def not_live(url):
        raise ValueError("This stream is not live right now.")
    monkeypatch.setattr(live_session, "default_resolver", not_live)
    r = start(live)
    assert r.status_code == 422 and "not live" in r.json()["detail"]


def test_bad_host_is_422(live):
    assert start(live, "http://127.0.0.1/x").status_code == 422


def test_unknown_session_404(live):
    assert live.get("/api/live/nope").status_code == 404


def test_spike_creates_moment_as_ready_job_and_stop_keeps_it(live, monkeypatch, burst_src):
    monkeypatch.setattr(live_session, "default_resolver", fake_resolver(burst_src))
    sid = start(live).json()["id"]
    snap = wait_for(lambda: (lambda s: s if s["moments"] else None)(live.get(f"/api/live/{sid}").json()))
    assert snap, "no moment was created"
    jid = snap["moments"][0]
    job = live.get(f"/api/jobs/{jid}").json()
    assert job["status"] == "ready" and len(job["candidates"]) == 1
    c = job["candidates"][0]
    assert 30 <= c["end"] - c["start"] <= 60 or 28 <= c["end"] <= 62
    assert job["video"]["channel_id"] == "UCtest"
    assert live.get(f"/api/jobs/{jid}/frame").status_code == 200
    assert live.post(f"/api/live/{sid}/stop").status_code == 200
    assert live.post(f"/api/live/{sid}/stop").status_code == 200  # idempotent
    assert live.get(f"/api/jobs/{jid}").json()["status"] == "ready"  # moment survives the stop


def test_enforce_cap_keeps_used_and_newest(tmp_path):
    from app.config import Settings
    from app.jobs import JobStore
    store = JobStore(tmp_path)
    s = LiveSession("https://twitch.tv/x", "", Settings(None, None, None, tmp_path, live_cap_gb=1e-9), store)
    ids = []
    for _ in range(4):
        jid = store.create("u", "")
        (store.dir(jid) / "video.mp4").write_bytes(b"x" * 1000)
        ids.append(jid)
    s.moments = list(ids)
    (store.dir(ids[1]) / "used").write_text("1")
    deleted = s._enforce_cap()
    assert set(deleted) == {ids[0], ids[2]}
    assert store.dir(ids[1]).exists() and store.dir(ids[3]).exists()
