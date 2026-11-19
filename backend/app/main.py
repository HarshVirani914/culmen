from fastapi import BackgroundTasks, FastAPI, HTTPException
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, captions_available, ffmpeg_available, get_settings
from .download import MAX_SECTION, validate_url
from .jobs import JobStore, RenderStore
from .layouts import LAYOUTS
from .live.session import get_manager
from .pipeline import run_analysis, run_render
from .profiles import ProfileStore

app = FastAPI(title="Shorts Clipper")


def store() -> JobStore:
    return JobStore(get_settings().data_dir)


class JobIn(BaseModel):
    url: str
    notes: str = ""
    range_start: float | None = Field(default=None, ge=0)
    range_end: float | None = Field(default=None, gt=0)


class BoxIn(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)


class ProfileIn(BaseModel):
    game: BoxIn
    face: BoxIn | None = None


class RenderIn(BaseModel):
    start: float = Field(ge=0)
    end: float
    layout: str
    game: BoxIn
    face: BoxIn | None = None
    captions: bool = False
    credit: bool = False


@app.get("/api/health")
def health():
    return {"ok": True, "ffmpeg": ffmpeg_available(), "captions": captions_available(),
            "llm": get_settings().llm_enabled}


@app.post("/api/jobs")
def create_job(body: JobIn, bg: BackgroundTasks):
    try:
        url = validate_url(body.url)
    except ValueError as e:
        raise HTTPException(422, str(e))
    rs, re_ = body.range_start, body.range_end
    if rs is not None and re_ is not None:
        if re_ <= rs:
            raise HTTPException(422, "range end must be after range start")
        if re_ - rs > MAX_SECTION:
            raise HTTPException(422, f"time range too long (max {MAX_SECTION // 3600} h)")
    s = store()
    jid = s.create(url, body.notes, rs, re_)
    bg.add_task(run_analysis, jid, s, get_settings())
    return {"id": jid}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = store().get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


def _mark_used(job_id: str) -> None:
    """A moment the user opened or rendered is exempt from the live storage cap."""
    d = store().dir(job_id)
    if d.exists():
        (d / "used").write_text("1")


@app.get("/api/jobs/{job_id}/frame")
def get_frame(job_id: str):
    p = store().dir(job_id) / "frame.jpg"
    if not p.exists():
        raise HTTPException(404, "frame not ready")
    _mark_used(job_id)
    return FileResponse(p, media_type="image/jpeg")


class LiveIn(BaseModel):
    url: str
    notes: str = ""


@app.post("/api/live")
def start_live(body: LiveIn):
    try:
        url = validate_url(body.url)
    except ValueError as e:
        raise HTTPException(422, str(e))
    try:
        session = get_manager().start(url, body.notes, get_settings(), store())
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"could not open the stream: {e}")
    return {"id": session.id}


@app.get("/api/live/{session_id}")
def get_live(session_id: str):
    s = get_manager().get(session_id)
    if s is None:
        raise HTTPException(404, "live session not found")
    return s.snapshot()


@app.post("/api/live/{session_id}/stop")
def stop_live(session_id: str):
    s = get_manager().get(session_id)
    if s is None:
        raise HTTPException(404, "live session not found")
    s.stop()
    return s.snapshot()


@app.get("/api/profiles/{channel_id}")
def get_profile(channel_id: str):
    return ProfileStore(get_settings().data_dir).get(channel_id)


@app.put("/api/profiles/{channel_id}")
def put_profile(channel_id: str, body: ProfileIn):
    ProfileStore(get_settings().data_dir).save(
        channel_id, body.game.model_dump(), body.face.model_dump() if body.face else None)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/render")
def start_render(job_id: str, body: RenderIn, bg: BackgroundTasks):
    js = store()
    job = js.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if job["status"] != "ready":
        raise HTTPException(409, "job is not ready")
    if body.layout not in LAYOUTS:
        raise HTTPException(422, f"layout must be one of {LAYOUTS}")
    if body.layout != "game_only" and body.face is None:
        raise HTTPException(422, "this layout needs a facecam box")
    if body.end <= body.start:
        raise HTTPException(422, "end must be after start")
    if (body.captions or body.credit) and not captions_available():
        raise HTTPException(422, "captions and credit line need an ffmpeg built with libass (brew install ffmpeg-full)")
    if body.end - body.start > 90:
        raise HTTPException(422, "clip too long (max 90 s)")
    _mark_used(job_id)
    rs = RenderStore(get_settings().data_dir)
    rid = rs.create(job_id)
    bg.add_task(run_render, rid, rs, js, job_id, body.model_dump())
    return {"render_id": rid}


@app.get("/api/renders/{render_id}")
def get_render(render_id: str):
    r = RenderStore(get_settings().data_dir).get(render_id)
    if r is None:
        raise HTTPException(404, "render not found")
    return {**r, "url": f"/api/renders/{render_id}/file" if r["status"] == "done" else None}


@app.get("/api/renders/{render_id}/file")
def get_render_file(render_id: str):
    p = RenderStore(get_settings().data_dir).dir(render_id) / "out.mp4"
    if not p.exists():
        raise HTTPException(404, "not ready")
    return FileResponse(p, media_type="video/mp4", filename="short.mp4")


def mount_frontend(app: FastAPI, dist: Path) -> None:
    if not (dist / "index.html").exists():
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "not found")
        f = (dist / path).resolve()
        if path and f.is_file() and dist.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(dist / "index.html")


mount_frontend(app, ROOT / "frontend" / "dist")
