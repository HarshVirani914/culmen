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


@pytest.fixture(scope="module")
def two_burst_src(tmp_path_factory):
    return make_source(tmp_path_factory.mktemp("lv3") / "two.mp4", 200, bursts=(60, 130))


def enable_llm(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")


def first_moment(client, sid):
    return wait_for(lambda: (lambda s: s["moments"][0] if s["moments"] else None)(client.get(f"/api/live/{sid}").json()))


def test_moment_gets_llm_title_and_hook(live, monkeypatch, burst_src):
    from app import llm, transcribe
    enable_llm(monkeypatch)
    monkeypatch.setattr(transcribe, "transcribe_text", lambda p, s, e: "he clutched it")
    monkeypatch.setattr(llm, "rank_candidates", lambda c, t, n, s: [llm.RankedCandidate(x, "Insane clutch", "wait for it", 9.0) for x in c])
    monkeypatch.setattr(live_session, "default_resolver", fake_resolver(burst_src))
    jid = first_moment(live, start(live).json()["id"])
    assert jid
    got = wait_for(lambda: (lambda c: c if c["title"] == "Insane clutch" else None)(
        live.get(f"/api/jobs/{jid}").json()["candidates"][0]))
    assert got and got["hook"] == "wait for it"


def test_titling_failure_keeps_generic_title(live, monkeypatch, burst_src):
    from app import llm, transcribe
    enable_llm(monkeypatch)
    monkeypatch.setattr(transcribe, "transcribe_text", lambda p, s, e: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(live_session, "default_resolver", fake_resolver(burst_src))
    jid = first_moment(live, start(live).json()["id"])
    time.sleep(1.0)
    assert live.get(f"/api/jobs/{jid}").json()["candidates"][0]["title"].startswith("Live moment")


def test_titling_does_not_block_new_moments(live, monkeypatch, two_burst_src):
    import threading
    from app import llm, transcribe
    enable_llm(monkeypatch)
    gate = threading.Event()
    monkeypatch.setattr(transcribe, "transcribe_text", lambda p, s, e: (gate.wait(30), "x")[1])
    monkeypatch.setattr(llm, "rank_candidates", lambda c, t, n, s: [llm.RankedCandidate(x, "T", "", 5.0) for x in c])
    monkeypatch.setattr(live_session, "default_resolver", fake_resolver(two_burst_src))
    sid = start(live).json()["id"]
    try:
        two = wait_for(lambda: (lambda s: s if len(s["moments"]) >= 2 else None)(live.get(f"/api/live/{sid}").json()), 30)
        assert two, "second moment was blocked by slow titling"
    finally:
        gate.set()


def test_llm_fallback_result_does_not_overwrite_live_title(live, monkeypatch, burst_src):
    from app import llm, transcribe
    enable_llm(monkeypatch)
    monkeypatch.setattr(transcribe, "transcribe_text", lambda p, s, e: "x")
    monkeypatch.setattr(llm, "rank_candidates", lambda c, t, n, s: [llm.RankedCandidate(x, "Moment 1", "", None) for x in c])
    monkeypatch.setattr(live_session, "default_resolver", fake_resolver(burst_src))
    jid = first_moment(live, start(live).json()["id"])
    time.sleep(1.5)
    assert live.get(f"/api/jobs/{jid}").json()["candidates"][0]["title"].startswith("Live moment")


def test_job_video_endpoint_serves_moment_preview(live, monkeypatch, burst_src):
    monkeypatch.setattr(live_session, "default_resolver", fake_resolver(burst_src))
    jid = first_moment(live, start(live).json()["id"])
    r = live.get(f"/api/jobs/{jid}/video")
    assert r.status_code == 200 and r.headers["content-type"] == "video/mp4" and len(r.content) > 1000
    assert live.get("/api/jobs/nope/video").status_code == 404


def test_stop_ends_chat_thread_cleanly(live, monkeypatch, long_src):
    import asyncio
    from app.live.chat_live import ChatSource

    class Forever(ChatSource):
        async def run(self, on_message):
            try:
                while not self._closed:
                    on_message("u1", "hi")
                    await asyncio.sleep(0.2)
                    await asyncio.sleep(1000)
            finally:
                Forever.cleaned = True
    Forever.cleaned = False
    monkeypatch.setattr(live_session, "default_resolver", fake_resolver(long_src))
    monkeypatch.setattr(live_session, "default_chat_source", lambda url: Forever())
    monkeypatch.setattr(live_session, "REALTIME", True)
    sid = start(live).json()["id"]
    time.sleep(1.5)
    s = live_session.get_manager().get(sid)
    assert s._chat_thread.is_alive()
    live.post(f"/api/live/{sid}/stop")
    assert wait_for(lambda: not s._chat_thread.is_alive(), 5), "chat thread kept running after stop"
    assert Forever.cleaned  # the chat coroutine was cancelled and its cleanup ran
