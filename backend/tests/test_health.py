from fastapi.testclient import TestClient


def test_health_reports_flags(monkeypatch):
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    from app.main import app
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert {"ok", "ffmpeg", "llm"} <= body.keys()
    assert body["llm"] is False


def test_health_reports_caption_support():
    from app.main import app
    body = TestClient(app).get("/api/health").json()
    assert body["captions"] is True  # needs an ffmpeg with libass (ffmpeg-full)


def test_render_rejects_captions_without_libass(client, monkeypatch):
    import time
    from app import main
    jid = client.post("/api/jobs", json={"url": "https://youtu.be/x", "notes": ""}).json()["id"]
    for _ in range(50):
        if client.get(f"/api/jobs/{jid}").json()["status"] == "ready":
            break
        time.sleep(0.1)
    monkeypatch.setattr(main, "captions_available", lambda: False)
    box = {"x": 0, "y": 0, "w": 1, "h": 1}
    r = client.post(f"/api/jobs/{jid}/render", json={"start": 0, "end": 10, "layout": "game_only",
                    "game": box, "face": None, "captions": True, "credit": False})
    assert r.status_code == 422 and "libass" in r.json()["detail"]
