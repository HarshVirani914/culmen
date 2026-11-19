from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_frontend


def make(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "a.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path.parent / "secret.txt").write_text("nope")
    app = FastAPI()

    @app.get("/api/ping")
    def ping():
        return {"pong": True}

    mount_frontend(app, tmp_path)
    return TestClient(app)


def test_serves_index_assets_and_spa_fallback(tmp_path):
    c = make(tmp_path)
    assert "app" in c.get("/").text
    assert c.get("/assets/a.js").text == "console.log(1)"
    assert "app" in c.get("/some/route").text


def test_api_routes_win_and_unknown_api_404(tmp_path):
    c = make(tmp_path)
    assert c.get("/api/ping").json() == {"pong": True}
    assert c.get("/api/nothing").status_code == 404


def test_no_path_traversal(tmp_path):
    c = make(tmp_path)
    assert "nope" not in c.get("/..%2fsecret.txt").text
    assert "nope" not in c.get("/../secret.txt").text


def test_missing_dist_is_noop(tmp_path):
    app = FastAPI()
    mount_frontend(app, tmp_path / "missing")
    assert TestClient(app).get("/").status_code == 404
