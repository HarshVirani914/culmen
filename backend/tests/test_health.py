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
