import asyncio
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .. import llm, transcribe
from ..candidates import Candidate
from ..config import Settings, ffmpeg_bin
from ..download import _probe_duration
from ..jobs import JobStore
from . import storage
from .buffer import Segment, SegmentBuffer
from .chat_live import chat_source_for
from .detector import LiveDetector, MomentWindow
from .recorder import Recorder, StreamInfo, resolve_stream
from .signals import ScoreTracker, segment_audio_scores

SEG = 6  # seconds per segment
REALTIME = False  # tests set True to replay a local file at real speed
default_resolver = resolve_stream
default_chat_source = chat_source_for


def _probe_size(path: Path) -> tuple[int, int]:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=width,height", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=30).stdout.strip().split(",")
        return int(out[0]), int(out[1])
    except Exception:
        return 1920, 1080


class LiveSession:
    def __init__(self, url: str, notes: str, settings: Settings, store: JobStore):
        self.url, self.notes, self.settings, self.store = url, notes, settings, store
        self.id = f"{int(time.time())}{id(self) % 1000:03d}"
        self.started_at = time.time()
        self.moments: list[str] = []
        self.info: StreamInfo | None = None
        self.error: str | None = None
        self._first_urls: list[str] | None = None
        self._scores: list[float] = []
        self._lock = threading.Lock()
        self._stopped = False
        self._seg_end = 0.0
        self._seg_wall = time.monotonic()
        self._n = 0
        self._chat = None
        self._chat_loop: asyncio.AbstractEventLoop | None = None
        self._chat_thread: threading.Thread | None = None
        self.dir = settings.data_dir / "live" / self.id
        self.buffer = SegmentBuffer(self.dir / "buffer", settings.live_buffer_seconds, SEG)
        self.detector = LiveDetector()
        self.tracker = ScoreTracker()
        self.recorder: Recorder | None = None
        self._title_q: queue.Queue = queue.Queue()
        self._title_thread: threading.Thread | None = None

    # ---- lifecycle
    def start(self) -> None:
        self.info = default_resolver(self.url)  # raises ValueError when the stream is not live
        self._first_urls = self.info.urls
        self.dir.mkdir(parents=True, exist_ok=True)
        self.recorder = Recorder(self._source, self.dir / "buffer", self._on_segment, SEG, realtime=REALTIME)
        self._chat = default_chat_source(self.url)
        if self._chat:
            self._chat_thread = threading.Thread(target=self._run_chat, daemon=True)
            self._chat_thread.start()
        if self.settings.llm_enabled:
            self._title_thread = threading.Thread(target=self._title_worker, daemon=True)
            self._title_thread.start()
        self.recorder.start()

    def _source(self) -> list[str]:
        if self._first_urls is not None:
            urls, self._first_urls = self._first_urls, None
            return urls
        self.info = default_resolver(self.url)  # re-resolve: stream URLs expire
        return self.info.urls

    def _run_chat(self) -> None:
        try:
            self._chat_loop = asyncio.new_event_loop()
            self._chat_loop.run_until_complete(self._chat.run(self._on_chat))
        except Exception:
            pass

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        if self.recorder:
            self.recorder.stop()
        if self._chat:
            self._chat.close()
            if self._chat_loop and self._chat_loop.is_running():
                self._chat_loop.call_soon_threadsafe(self._chat_loop.stop)
        self._title_q.put(None)
        shutil.rmtree(self.dir, ignore_errors=True)

    @property
    def status(self) -> str:
        if self._stopped:
            return "stopped"
        return self.recorder.status if self.recorder else "starting"

    @property
    def running(self) -> bool:
        return self.status in ("starting", "recording")

    # ---- signals
    def _on_chat(self, author: str, text: str) -> None:
        with self._lock:
            t = self._seg_end + (time.monotonic() - self._seg_wall)
            self.tracker.add_chat(t, author)

    def _on_segment(self, seg: Segment) -> None:
        rms = segment_audio_scores(seg.path, SEG)
        windows: list[MomentWindow] = []
        with self._lock:
            self._seg_end, self._seg_wall = seg.start + SEG, time.monotonic()
            self.detector.available_start = self.buffer.available_start()
            for i, v in enumerate(rms):
                t = seg.start + i
                self.tracker.add_audio(t, float(v))
                score = self.tracker.score(t)
                self._scores.append(score)
                w = self.detector.feed(t, score)
                if w:
                    windows.append(w)
        for w in windows:
            try:
                self._moment(w)
            except Exception as e:  # noqa: BLE001
                self.error = f"moment failed: {e}"
        self.buffer.prune()

    # ---- moments
    def _moment(self, w: MomentWindow) -> None:
        release = self.buffer.protect(w.start, w.end)
        try:
            jid = self.store.create(self.url, self.notes)
            d = self.store.dir(jid)
            video = d / "video.mp4"
            self.buffer.extract(w.start, w.end, video)
            dur = _probe_duration(video)
            width, height = (self.info.width, self.info.height) if (self.info and self.info.width) \
                else _probe_size(video)
            subprocess.run([ffmpeg_bin(), "-y", "-loglevel", "error", "-ss", f"{dur * 0.3:.2f}", "-i", str(video),
                            "-frames:v", "1", str(d / "frame.jpg")], check=True)
            self._n += 1
            info = self.info or StreamInfo([])
            self.store.update(
                jid, status="ready", progress=None,
                video={"title": info.title, "channel_id": info.channel_id, "channel": info.channel,
                       "width": width, "height": height, "duration": dur, "offset": 0, "path": str(video)},
                candidates=[{"start": 0.0, "end": dur, "score": w.score, "title": f"Live moment {self._n}",
                             "hook": "", "llm_score": None}])
            self.moments.append(jid)
            self._title_q.put((jid, dur, w.score))
        finally:
            release()
        self._enforce_cap()

    def _enforce_cap(self) -> list[str]:
        ids = list(self.moments)
        if not ids:
            return []
        keep = {ids[-1]} | {i for i in ids if (self.store.dir(i) / "used").exists()}
        deleted = storage.enforce_cap(self.store.root, ids, int(self.settings.live_cap_gb * 1e9), keep)
        self.moments = [i for i in ids if i not in deleted]
        return deleted

    def _title_worker(self) -> None:
        """Adds an LLM title and hook to each moment without blocking the recorder."""
        while True:
            item = self._title_q.get()
            if item is None:
                return
            jid, dur, score = item
            try:
                job = self.store.get(jid)
                if job is None:  # deleted by the storage cap
                    continue
                text = transcribe.transcribe_text(Path(job["video"]["path"]), 0, dur)
                cand = Candidate(0.0, dur, score)
                ranked = llm.rank_candidates([cand], {0: text}, self.notes, self.settings)[0]
                if ranked.llm_score is None:  # the LLM failed; keep the generic title
                    continue
                job = self.store.get(jid)
                if job is None:
                    continue
                c = dict(job["candidates"][0])
                c.update(title=ranked.title, hook=ranked.hook, llm_score=ranked.llm_score)
                self.store.update(jid, candidates=[c])
            except Exception:  # noqa: BLE001 - keep the generic title
                continue

    # ---- status
    def _disk_mb(self) -> float:
        total = 0
        for p in [self.dir] + [self.store.dir(i) for i in self.moments]:
            if p.exists():
                total += sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        return round(total / 1e6, 1)

    def snapshot(self) -> dict:
        return {
            "id": self.id, "status": self.status, "started_at": self.started_at, "url": self.url,
            "buffer_seconds": round(self.buffer.available_end() - self.buffer.available_start(), 1),
            "disk_mb": self._disk_mb(),
            "signals": {"chat": self.tracker.has_chat, "chat_source": self._chat is not None, "audio": True},
            "recent_scores": [round(s, 3) for s in self._scores[-120:]],
            "moments": list(self.moments),
            "title": self.info.title if self.info else "",
            "error": self.error or (self.recorder.error if self.recorder else None),
        }


class Manager:
    def __init__(self) -> None:
        self.sessions: dict[str, LiveSession] = {}
        self._last: LiveSession | None = None

    def current(self) -> LiveSession | None:
        return self._last

    def get(self, sid: str) -> LiveSession | None:
        return self.sessions.get(sid)

    def start(self, url: str, notes: str, settings: Settings, store: JobStore) -> LiveSession:
        if self._last and self._last.running:
            raise RuntimeError("a live session is already running")
        s = LiveSession(url, notes, settings, store)
        s.start()
        self.sessions[s.id] = s
        self._last = s
        return s

    def reset(self) -> None:
        self.sessions.clear()
        self._last = None


_manager = Manager()


def get_manager() -> Manager:
    return _manager
