from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import ffmpeg_available, get_settings
from .download import validate_url
from .jobs import JobStore
from .pipeline import run_analysis

app = FastAPI(title="Shorts Clipper")


def store() -> JobStore:
    return JobStore(get_settings().data_dir)


class JobIn(BaseModel):
    url: str
    notes: str = ""


@app.get("/api/health")
def health():
    return {"ok": True, "ffmpeg": ffmpeg_available(), "llm": get_settings().llm_enabled}


@app.post("/api/jobs")
def create_job(body: JobIn, bg: BackgroundTasks):
    try:
        url = validate_url(body.url)
    except ValueError as e:
        raise HTTPException(422, str(e))
    s = store()
    jid = s.create(url, body.notes)
    bg.add_task(run_analysis, jid, s, get_settings())
    return {"id": jid}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = store().get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


@app.get("/api/jobs/{job_id}/frame")
def get_frame(job_id: str):
    p = store().dir(job_id) / "frame.jpg"
    if not p.exists():
        raise HTTPException(404, "frame not ready")
    return FileResponse(p, media_type="image/jpeg")
