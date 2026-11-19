import json
import re
import uuid
from pathlib import Path


ID_RE = re.compile(r"^[0-9a-f]{12}$")


class JobStore:
    def __init__(self, data_dir: Path):
        self.root = data_dir / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)

    def dir(self, job_id: str) -> Path:
        if not ID_RE.match(job_id):
            return self.root / "_invalid"
        return self.root / job_id

    def create(self, url: str, notes: str, range_start: float | None = None,
               range_end: float | None = None) -> str:
        jid = uuid.uuid4().hex[:12]
        self.dir(jid).mkdir(parents=True)
        self._write(jid, {"id": jid, "url": url, "notes": notes, "status": "queued",
                          "error": None, "candidates": [], "video": None,
                          "range_start": range_start, "range_end": range_end, "progress": None})
        return jid

    def get(self, job_id: str) -> dict | None:
        p = self.dir(job_id) / "job.json"
        return json.loads(p.read_text()) if p.exists() else None

    def update(self, job_id: str, **fields) -> None:
        job = self.get(job_id)
        job.update(fields)
        self._write(job_id, job)

    def _write(self, job_id: str, job: dict) -> None:
        p = self.dir(job_id) / "job.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(job))
        tmp.replace(p)


class RenderStore:
    def __init__(self, data_dir: Path):
        self.root = data_dir / "renders"
        self.root.mkdir(parents=True, exist_ok=True)

    def dir(self, rid: str) -> Path:
        if not ID_RE.match(rid):
            return self.root / "_invalid"
        return self.root / rid

    def create(self, job_id: str) -> str:
        rid = uuid.uuid4().hex[:12]
        self.dir(rid).mkdir(parents=True)
        self._write(rid, {"id": rid, "job_id": job_id, "status": "queued", "error": None})
        return rid

    def get(self, rid: str) -> dict | None:
        p = self.dir(rid) / "render.json"
        return json.loads(p.read_text()) if p.exists() else None

    def update(self, rid: str, **fields) -> None:
        r = self.get(rid)
        r.update(fields)
        self._write(rid, r)

    def _write(self, rid: str, r: dict) -> None:
        p = self.dir(rid) / "render.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(r))
        tmp.replace(p)
