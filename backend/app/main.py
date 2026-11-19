from fastapi import FastAPI

from .config import ffmpeg_available, get_settings

app = FastAPI(title="Shorts Clipper")


@app.get("/api/health")
def health():
    return {"ok": True, "ffmpeg": ffmpeg_available(), "llm": get_settings().llm_enabled}
