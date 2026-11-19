import json
import uuid
from pathlib import Path


class JobStore:
    def __init__(self, data_dir: Path):
        self.root = data_dir / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)

    def dir(self, job_id: str) -> Path:
        return self.root / job_id

    def create(self, url: str, notes: str) -> str:
        jid = uuid.uuid4().hex[:12]
        self.dir(jid).mkdir(parents=True)
        self._write(jid, {"id": jid, "url": url, "notes": notes, "status": "queued",
                          "error": None, "candidates": [], "video": None})
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
