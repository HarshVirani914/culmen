import time

import pytest

from app import llm, pipeline, render, transcribe
from app.captions import Word

BOX = {"x": 0.0, "y": 0.0, "w": 0.7, "h": 1.0}
FACE = {"x": 0.75, "y": 0.05, "w": 0.2, "h": 0.3}
YT = "https://youtu.be/x"


def ready_job(client):
    jid = client.post("/api/jobs", json={"url": YT, "notes": ""}).json()["id"]
    for _ in range(50):
        if client.get(f"/api/jobs/{jid}").json()["status"] == "ready":
            return jid
        time.sleep(0.1)
    raise AssertionError("not ready")


@pytest.fixture
def fake_render(monkeypatch):
    calls = []

    def fake(src, out, start, end, layout, game, face, w, h, ass_path=None):
        calls.append({"layout": layout, "ass": ass_path})
        out.write_bytes(b"mp4")
    monkeypatch.setattr(render, "render_clip", fake)
    return calls


def body(**kw):
    b = {"start": 5, "end": 25, "layout": "stacked", "game": BOX, "face": FACE, "captions": False, "credit": False}
    b.update(kw)
    return b


def wait_render(client, rid):
    for _ in range(50):
        r = client.get(f"/api/renders/{rid}").json()
        if r["status"] in ("done", "error"):
            return r
        time.sleep(0.1)
    raise AssertionError("timeout")


def test_profile_round_trip_and_missing(client):
    assert client.get("/api/profiles/UC1").json() is None
    r = client.put("/api/profiles/UC1", json={"game": BOX, "face": FACE})
    assert r.status_code == 200
    got = client.get("/api/profiles/UC1").json()
    assert got["game"] == BOX and got["face"] == FACE


def test_render_reaches_done_and_serves_file(client, fake_render):
    jid = ready_job(client)
    rid = client.post(f"/api/jobs/{jid}/render", json=body()).json()["render_id"]
    r = wait_render(client, rid)
    assert r["status"] == "done"
    assert client.get(f"/api/renders/{rid}/file").content == b"mp4"
    assert fake_render[0]["ass"] is None


def test_render_with_captions_and_credit_builds_ass(client, fake_render, monkeypatch):
    monkeypatch.setattr(transcribe, "transcribe", lambda p, s, e: [Word("hi", 0, 0.5)])
    jid = ready_job(client)
    rid = client.post(f"/api/jobs/{jid}/render", json=body(captions=True, credit=True)).json()["render_id"]
    assert wait_render(client, rid)["status"] == "done"
    assert fake_render[0]["ass"] is not None


@pytest.mark.parametrize("override", [
    {"layout": "nope"},
    {"layout": "stacked", "face": None},
    {"start": 30, "end": 20},
    {"start": 0, "end": 120},
])
def test_render_validation_422(client, fake_render, override):
    jid = ready_job(client)
    assert client.post(f"/api/jobs/{jid}/render", json=body(**override)).status_code == 422


def test_render_game_only_needs_no_face(client, fake_render):
    jid = ready_job(client)
    r = client.post(f"/api/jobs/{jid}/render", json=body(layout="game_only", face=None))
    assert r.status_code == 200


def test_llm_titles_applied_in_analysis(client, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setattr(transcribe, "transcribe_text", lambda p, s, e: "wow")
    monkeypatch.setattr(llm, "rank_candidates", lambda c, t, n, s: [
        llm.RankedCandidate(x, "LLM Title", "hook!", 9.0) for x in c])
    jid = ready_job(client)
    cand = client.get(f"/api/jobs/{jid}").json()["candidates"][0]
    assert cand["title"] == "LLM Title" and cand["hook"] == "hook!"


def test_ranking_reports_transcribing_progress(client, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "m")
    seen = []
    holder = {}

    def fake_text(p, s, e):
        job = client.get(f"/api/jobs/{holder['id']}").json()
        seen.append(job.get("progress"))
        return "wow"
    monkeypatch.setattr(transcribe, "transcribe_text", fake_text)
    monkeypatch.setattr(llm, "rank_candidates", lambda c, t, n, s: [llm.RankedCandidate(x, "T", "", 5.0) for x in c])
    from app import main
    orig = main.run_analysis
    monkeypatch.setattr(main, "run_analysis", lambda jid, *a: (holder.update(id=jid), orig(jid, *a)))
    jid = ready_job(client)
    assert seen and seen[0]["step"] == "transcribing" and seen[0]["done"] == 0
    assert seen[-1]["done"] == len(seen) - 1 and seen[-1]["total"] == len(seen)
    assert client.get(f"/api/jobs/{jid}").json()["progress"] is None
