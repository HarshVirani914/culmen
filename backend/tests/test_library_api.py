import time

import pytest

from app import render
from tests.test_profiles_render_api import BOX, FACE, body, ready_job, wait_render


@pytest.fixture
def fake_render(monkeypatch):
    def fake(src, out, start, end, layout, game, face, w, h, ass_path=None):
        out.write_bytes(b"fake-mp4-bytes" * 100)
    monkeypatch.setattr(render, "render_clip", fake)


def rendered(client, **kw):
    jid = ready_job(client)
    rid = client.post(f"/api/jobs/{jid}/render", json=body(**kw)).json()["render_id"]
    assert wait_render(client, rid)["status"] == "done"
    return jid, rid


def test_save_list_play_rename_delete_roundtrip(client, fake_render):
    jid, rid = rendered(client)
    r = client.post("/api/library", json={"render_id": rid, "title": "Clutch of the night"})
    assert r.status_code == 200
    lid = r.json()["id"]
    items = client.get("/api/library").json()
    assert len(items) == 1
    it = items[0]
    assert it["id"] == lid and it["title"] == "Clutch of the night"
    assert it["size_bytes"] == 1400 and it["layout"] == "stacked"
    assert it["channel"] == "Chan" and it["source_url"].startswith("https://")
    assert it["clip_start"] == 5 and it["clip_end"] == 25
    f = client.get(f"/api/library/{lid}/file")
    assert f.status_code == 200 and f.headers["content-type"] == "video/mp4" and f.content == b"fake-mp4-bytes" * 100
    assert client.patch(f"/api/library/{lid}", json={"title": "Renamed"}).status_code == 200
    assert client.get("/api/library").json()[0]["title"] == "Renamed"
    assert client.delete(f"/api/library/{lid}").status_code == 200
    assert client.get("/api/library").json() == []
    assert client.get(f"/api/library/{lid}/file").status_code == 404


def test_saving_the_same_render_twice_does_not_duplicate(client, fake_render):
    _, rid = rendered(client)
    a = client.post("/api/library", json={"render_id": rid}).json()["id"]
    b = client.post("/api/library", json={"render_id": rid}).json()["id"]
    assert a == b and len(client.get("/api/library").json()) == 1


def test_default_title_comes_from_the_moment_when_none_given(client, fake_render):
    _, rid = rendered(client)
    client.post("/api/library", json={"render_id": rid})
    assert client.get("/api/library").json()[0]["title"]  # never empty


def test_saved_clip_survives_deleting_the_render_and_job_files(client, fake_render):
    import shutil
    from app.config import get_settings
    jid, rid = rendered(client)
    lid = client.post("/api/library", json={"render_id": rid}).json()["id"]
    d = get_settings().data_dir
    shutil.rmtree(d / "renders" / rid)
    shutil.rmtree(d / "jobs" / jid)
    assert client.get(f"/api/library/{lid}/file").status_code == 200  # it is a copy, not a link


def test_unknown_or_unfinished_render_is_rejected(client, fake_render):
    assert client.post("/api/library", json={"render_id": "0" * 12}).status_code == 404
    assert client.post("/api/library", json={"render_id": "../x"}).status_code in (404, 422)


def test_library_is_newest_first_and_bad_ids_404(client, fake_render):
    _, r1 = rendered(client)
    a = client.post("/api/library", json={"render_id": r1, "title": "first"}).json()["id"]
    time.sleep(1.1)
    _, r2 = rendered(client)
    b = client.post("/api/library", json={"render_id": r2, "title": "second"}).json()["id"]
    assert [i["id"] for i in client.get("/api/library").json()] == [b, a]
    assert client.get("/api/library/nope/file").status_code == 404
    assert client.delete("/api/library/nope").status_code == 404
    assert client.patch("/api/library/nope", json={"title": "x"}).status_code == 404


def test_empty_rename_is_rejected(client, fake_render):
    _, rid = rendered(client)
    lid = client.post("/api/library", json={"render_id": rid, "title": "keep"}).json()["id"]
    assert client.patch(f"/api/library/{lid}", json={"title": "   "}).status_code == 422
    assert client.get("/api/library").json()[0]["title"] == "keep"
