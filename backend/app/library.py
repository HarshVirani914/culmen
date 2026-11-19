"""Saved clips: permanent copies of rendered Shorts, kept apart from jobs and renders so cleanup never touches them."""
import json
import shutil
import time
import uuid
from pathlib import Path

from .jobs import ID_RE, JobStore, RenderStore


class LibraryStore:
    def __init__(self, data_dir: Path):
        self.root = data_dir / "library"
        self.root.mkdir(parents=True, exist_ok=True)

    def dir(self, lid: str) -> Path:
        return self.root / (lid if ID_RE.match(lid) else "_invalid")

    def get(self, lid: str) -> dict | None:
        p = self.dir(lid) / "meta.json"
        return json.loads(p.read_text()) if p.exists() else None

    def video(self, lid: str) -> Path:
        return self.dir(lid) / "short.mp4"

    def list(self) -> list[dict]:
        items = []
        for d in self.root.iterdir():
            m = d / "meta.json"
            if m.exists():
                try:
                    items.append(json.loads(m.read_text()))
                except ValueError:
                    continue
        return sorted(items, key=lambda i: i["created_at"], reverse=True)

    def add(self, rs: RenderStore, js: JobStore, render_id: str, title: str | None) -> str:
        render = rs.get(render_id)
        if render is None:
            raise LookupError("render not found")
        if render["status"] != "done" or not (rs.dir(render_id) / "out.mp4").exists():
            raise ValueError("this render is not finished")
        for it in self.list():  # saving the same render twice returns the existing entry
            if it.get("render_id") == render_id:
                return it["id"]
        job = js.get(render["job_id"]) or {}
        video = job.get("video") or {}
        req = render.get("request") or {}
        cs, ce = float(req.get("start", 0)), float(req.get("end", 0))
        name = (title or "").strip()
        if not name:
            best, best_overlap = None, 0.0
            for c in job.get("candidates", []):
                ov = min(ce, c["end"]) - max(cs, c["start"])
                if ov > best_overlap:
                    best, best_overlap = c, ov
            name = (best or {}).get("title") or video.get("title") or "Short"
        lid = uuid.uuid4().hex[:12]
        d = self.dir(lid)
        d.mkdir(parents=True)
        shutil.copyfile(rs.dir(render_id) / "out.mp4", d / "short.mp4")
        meta = {
            "id": lid, "title": name, "created_at": time.time(), "render_id": render_id,
            "job_id": render["job_id"], "source_url": job.get("url", ""), "stream_title": video.get("title", ""),
            "channel": video.get("channel", ""), "layout": req.get("layout", ""),
            "captions": bool(req.get("captions")), "credit": bool(req.get("credit")),
            "clip_start": cs, "clip_end": ce, "stream_start": cs + float(video.get("offset") or 0),
            "duration": ce - cs, "size_bytes": (d / "short.mp4").stat().st_size,
        }
        (d / "meta.json").write_text(json.dumps(meta))
        return lid

    def rename(self, lid: str, title: str) -> bool:
        meta = self.get(lid)
        if meta is None:
            return False
        meta["title"] = title
        (self.dir(lid) / "meta.json").write_text(json.dumps(meta))
        return True

    def delete(self, lid: str) -> bool:
        if self.get(lid) is None:
            return False
        shutil.rmtree(self.dir(lid), ignore_errors=True)
        return True
