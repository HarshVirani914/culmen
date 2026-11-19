import subprocess
from dataclasses import asdict
from pathlib import Path

from . import download, llm, render, signals, transcribe
from .candidates import find_candidates
from .captions import build_ass
from .config import Settings
from .jobs import JobStore, RenderStore
from .layouts import Box


def _rank(job_id: str, store: JobStore, job: dict, vi_path: Path, cands, settings: Settings) -> list[dict]:
    if not settings.llm_enabled:
        ranked = llm.rank_candidates(cands, {}, job["notes"], settings)
    else:
        transcripts: dict[int, str] = {}
        for i, c in enumerate(cands):
            store.update(job_id, progress={"step": "transcribing", "done": i, "total": len(cands)})
            try:
                transcripts[i] = transcribe.transcribe_text(vi_path, c.start, c.end)
            except Exception:  # noqa: BLE001
                transcripts[i] = ""
        store.update(job_id, progress={"step": "ranking", "done": len(cands), "total": len(cands)})
        ranked = llm.rank_candidates(cands, transcripts, job["notes"], settings)
    return [{**asdict(r.candidate), "title": r.title, "hook": r.hook, "llm_score": r.llm_score}
            for r in ranked]


def run_analysis(job_id: str, store: JobStore, settings: Settings) -> None:
    try:
        job = store.get(job_id)
        store.update(job_id, status="downloading")
        rs, re_ = job.get("range_start"), job.get("range_end")
        vi = download.download_video(job["url"], store.dir(job_id), rs, re_)
        offset = float(vi.actual_start if vi.actual_start is not None else (rs or 0))
        store.update(job_id, status="analyzing", video={
            "title": vi.title, "channel_id": vi.channel_id, "channel": vi.channel,
            "width": vi.width, "height": vi.height, "duration": vi.duration, "offset": offset,
            "path": str(vi.path)})
        parts = {
            "heatmap": signals.heatmap_signal(vi.info, vi.duration, offset),
            "chat": signals.chat_rate(job["url"], vi.duration, offset),
            "audio": signals.audio_energy(vi.path, vi.duration),
        }
        cands = find_candidates(signals.combine(parts), vi.duration)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{vi.duration * 0.1:.2f}",
                        "-i", str(vi.path), "-frames:v", "1", str(store.dir(job_id) / "frame.jpg")],
                       check=True)
        ranked = _rank(job_id, store, job, vi.path, cands, settings)
        store.update(job_id, status="ready", candidates=ranked, progress=None)
    except Exception as e:  # noqa: BLE001
        store.update(job_id, status="error", error=str(e), progress=None)


def run_render(rid: str, rstore: RenderStore, jstore: JobStore, job_id: str, req: dict) -> None:
    try:
        rstore.update(rid, status="rendering")
        video = jstore.get(job_id)["video"]
        out = rstore.dir(rid) / "out.mp4"
        ass = None
        if req["captions"] or req["credit"]:
            words = transcribe.transcribe(Path(video["path"]), req["start"], req["end"]) if req["captions"] else []
            ass = rstore.dir(rid) / "captions.ass"
            build_ass(words, ass, credit=f"Source: {video['channel']}" if req["credit"] else None,
                      clip_len=req["end"] - req["start"])
        game = Box(**req["game"])
        face = Box(**req["face"]) if req["face"] else None
        render.render_clip(Path(video["path"]), out, req["start"], req["end"], req["layout"],
                           game, face, video["width"], video["height"], ass)
        rstore.update(rid, status="done")
    except Exception as e:  # noqa: BLE001
        rstore.update(rid, status="error", error=str(e))
