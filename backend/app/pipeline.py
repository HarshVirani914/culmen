import subprocess
from dataclasses import asdict

from . import download, signals
from .candidates import find_candidates
from .config import Settings
from .jobs import JobStore


def run_analysis(job_id: str, store: JobStore, settings: Settings) -> None:
    try:
        job = store.get(job_id)
        store.update(job_id, status="downloading")
        vi = download.download_video(job["url"], store.dir(job_id))
        store.update(job_id, status="analyzing", video={
            "title": vi.title, "channel_id": vi.channel_id, "channel": vi.channel,
            "width": vi.width, "height": vi.height, "duration": vi.duration,
            "path": str(vi.path)})
        parts = {
            "heatmap": signals.heatmap_signal(vi.info, vi.duration),
            "chat": signals.chat_rate(job["url"], vi.duration),
            "audio": signals.audio_energy(vi.path, vi.duration),
        }
        cands = find_candidates(signals.combine(parts), vi.duration)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{vi.duration * 0.1:.2f}",
                        "-i", str(vi.path), "-frames:v", "1", str(store.dir(job_id) / "frame.jpg")],
                       check=True)
        store.update(job_id, status="ready", candidates=[
            {**asdict(c), "title": f"Moment {i + 1}", "hook": ""} for i, c in enumerate(cands)])
    except Exception as e:  # noqa: BLE001
        store.update(job_id, status="error", error=str(e))
