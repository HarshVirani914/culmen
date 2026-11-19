# Culmen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local web app that takes a YouTube video/replay URL, finds the most reacted-to moments automatically, and renders them as 1080x1920 Shorts in four layouts using user-drawn gameplay and facecam boxes.

**Architecture:** FastAPI backend runs a job pipeline (download, signals, candidates, optional transcript and LLM rank, render). A React + Vite + Tailwind + shadcn/ui frontend drives it. Pure logic (scoring, peak picking, layout filter building) is isolated in small modules and unit tested. FFmpeg does all video work. FastAPI serves the built frontend, so one command runs everything.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, pytest, numpy, yt-dlp, chat-downloader, faster-whisper, openai client (custom base_url), FFmpeg (system), React + Vite + TypeScript, Tailwind, shadcn/ui.

**Spec:** `docs/2026-11-19-shorts-clipper-design.md`

## Global Constraints

- Output: 1080x1920 MP4, H.264 video, AAC audio.
- Runs locally on macOS; no cloud hosting, no auth, single user.
- Download capped at 1080p.
- Clip length 20-60 seconds.
- Layouts, exactly these four ids: `stacked`, `bubble`, `game_only`, `face_only`.
- Boxes are normalized to the source frame: `{x, y, w, h}` each in 0..1.
- Box profiles are saved per streamer, keyed by YouTube channel id.
- LLM is optional. Configured only via `.env`: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`. Without them everything else still works.
- Detection must work with no live chat (audio and replay-graph signals alone).
- Frontend uses shadcn/ui components and its design conventions.
- All backend modules live in `backend/app/`, tests in `backend/tests/`.

## Review Focus

- Video with chat replay disabled or empty: analysis must still succeed using audio/heatmap, not crash.
- Video with no "most replayed" heatmap (short or low-view videos): `heatmap_signal` returns zeros, not an error.
- Silent video or video with no audio track: audio signal returns zeros; candidates may be empty and the UI shows an explicit "no moments found" state.
- Peak at the very start or end of the video: windows are clamped to `[0, duration]` and never negative or past the end.
- LLM returns invalid JSON, times out, or key is missing: ranking falls back to signal order with no exception reaching the user.
- Streamer with no saved profile, or boxes that touch the frame edge: render uses defaults and crop math never exceeds source bounds.

---

### Task 1: Project scaffold, config, health endpoint

**Files:**
- Create: `clipper/backend/requirements.txt`, `clipper/backend/app/__init__.py`, `clipper/backend/app/config.py`, `clipper/backend/app/main.py`, `clipper/backend/tests/test_health.py`, `clipper/.env.example`, `clipper/.gitignore`

**Interfaces:**
- Produces: `Settings` dataclass with `llm_base_url: str|None`, `llm_api_key: str|None`, `llm_model: str|None`, `data_dir: Path`, property `llm_enabled: bool`; `get_settings() -> Settings` (reads `.env` and env vars); FastAPI `app` in `app.main` with `GET /api/health -> {"ok": true, "ffmpeg": bool, "llm": bool}`.

- [ ] **Step 1: `git init` in `clipper/`, create venv, install requirements** (fastapi, uvicorn, pytest, httpx, numpy, yt-dlp, chat-downloader, faster-whisper, openai, python-dotenv).
- [ ] **Step 2: Write failing test `test_health_reports_flags`** using FastAPI `TestClient`: response 200, JSON has keys `ok`, `ffmpeg`, `llm`, and `llm` is `False` when `LLM_*` env vars are unset (monkeypatch).
- [ ] **Step 3: Run it, expect FAIL (import error).** `cd clipper/backend && pytest tests/test_health.py -v`
- [ ] **Step 4: Implement `get_settings`, `Settings`, and `/api/health`** (`ffmpeg` is `shutil.which("ffmpeg") is not None`).
- [ ] **Step 5: Run test, expect PASS.**
- [ ] **Step 6: Commit** `feat: backend scaffold and health endpoint`.

### Task 2: Candidate detection (pure logic)

**Files:**
- Create: `backend/app/candidates.py`, `backend/tests/test_candidates.py`

**Interfaces:**
- Produces: `@dataclass Candidate(start: float, end: float, score: float)`; `find_candidates(score: np.ndarray, duration: float, min_len: float = 20, max_len: float = 60, top_k: int = 10) -> list[Candidate]` where `score` is one value per second, already combined and normalized to 0..1.

- [ ] **Step 1: Write failing tests:**
  - `test_single_peak_gives_window_around_it`: score zeros with a bump at t=100..105, duration 600; assert one top candidate containing t=102 and `20 <= end-start <= 60`.
  - `test_peak_at_start_clamped`: bump at t=0..3; assert `start == 0`.
  - `test_peak_at_end_clamped`: bump at last 3 seconds; assert `end <= duration`.
  - `test_overlapping_peaks_deduplicated`: two bumps 10 s apart yield one candidate.
  - `test_flat_zero_score_returns_empty`.
  - `test_results_sorted_by_score_desc_and_capped_to_top_k`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement `find_candidates`.** Approach: smooth score with a 5 s moving average, pick local maxima above `mean + 1.5*std` (and above 0), greedily take highest first, window = peak - 0.35*L to peak + 0.65*L with L chosen as 30 s clamped to `[min_len, max_len]` and to the video bounds, skip peaks inside an already-chosen window, stop at `top_k`.
- [ ] **Step 4: Run, expect PASS. Commit** `feat: candidate window detection`.

### Task 3: Signals (audio, chat, replay heatmap, combine)

**Files:**
- Create: `backend/app/signals.py`, `backend/tests/test_signals.py`

**Interfaces:**
- Produces: `audio_energy(video_path: Path, duration: float) -> np.ndarray` (per-second loudness-spike score, 0..1; zeros if no audio stream); `chat_rate(url: str, duration: float) -> np.ndarray` (per-second message-rate-spike score, 0..1; zeros if chat unavailable or empty, never raises); `heatmap_signal(info: dict, duration: float) -> np.ndarray` (resamples yt-dlp `info["heatmap"]` list of `{start_time, end_time, value}` to per-second, zeros if absent); `normalize(a: np.ndarray) -> np.ndarray` (to 0..1, constant array -> zeros); `combine(parts: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray` (weighted sum over non-zero-signal parts, renormalized; default weights heatmap 0.4, chat 0.35, audio 0.25).

- [ ] **Step 1: Write failing tests (no network, no real video):**
  - `test_normalize_constant_is_zeros`, `test_normalize_range`.
  - `test_heatmap_signal_resamples`: given two heatmap segments, check per-second values and length equals `ceil(duration)`.
  - `test_heatmap_signal_missing_returns_zeros`.
  - `test_combine_skips_all_zero_parts`: chat all zeros does not dilute audio-only result (result equals normalized audio).
  - `test_audio_energy_detects_loud_burst`: generate a 10 s WAV with a loud 1 s burst at t=5 via ffmpeg (`sine` with volume enable), assert argmax within 1 s of 5; `test_audio_energy_no_audio_stream_returns_zeros` using `-an` video.
  - `test_chat_rate_unavailable_returns_zeros`: monkeypatch the chat-downloader call to raise; assert zeros, no exception.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** `audio_energy`: ffmpeg pipes mono 16 kHz PCM, compute RMS per second, score = RMS relative to a rolling 60 s median (spikes), normalize. `chat_rate`: use chat-downloader `ChatDownloader().get_chat(url)`, bin message timestamps (`time_in_seconds`) per second, add small weight for messages with caps ratio > 0.6 or emote-only text, smooth, spike vs rolling median, normalize; wrap everything in try/except returning zeros.
- [ ] **Step 4: Run, expect PASS. Commit** `feat: audio, chat and replay-heatmap signals`.

### Task 4: Layouts and rendering

**Files:**
- Create: `backend/app/layouts.py`, `backend/app/render.py`, `backend/tests/test_layouts.py`, `backend/tests/test_render.py`

**Interfaces:**
- Produces: `@dataclass Box(x: float, y: float, w: float, h: float)` with `clamped() -> Box` (clips into 0..1, enforces min size 0.02); `LAYOUTS = ("stacked", "bubble", "game_only", "face_only")`; `build_filter_complex(layout: str, game: Box, face: Box|None, src_w: int, src_h: int, ass_path: Path|None) -> str` (ends with output label `[out]`; raises `ValueError` for unknown layout or for a layout that needs a face box when `face is None`); `render_clip(src: Path, out: Path, start: float, end: float, layout: str, game: Box, face: Box|None, src_w: int, src_h: int, ass_path: Path|None = None) -> None`.
- Layout geometry on a 1080x1920 canvas: `stacked` = face slot 1080x700 on top, game slot 1080x1220 below, each filled by cover-fit crop of its box; `bubble` = game box cover-fit full canvas, face box scaled to 380x380 overlaid bottom-left at (40, 1380); `game_only` = blurred (boxblur 20) cover-fit background, game box fit-to-width centered; `face_only` = face box cover-fit full canvas.

- [ ] **Step 1: Write failing tests:**
  - `test_unknown_layout_raises`, `test_face_layout_without_face_raises` (for `stacked`, `bubble`, `face_only`).
  - `test_filter_ends_with_out_label` for all four layouts.
  - `test_crop_pixels_within_source`: box touching the frame edge (x=0.9, w=0.2 clamped) yields crop widths/offsets inside `src_w`/`src_h` (parse `crop=w:h:x:y` from the filter string).
  - `test_render_produces_1080x1920_mp4` (real ffmpeg): generate a 5 s 1280x720 `testsrc` + sine input, render with each layout, probe with `ffprobe` and assert width 1080, height 1920, codec h264, duration approx the requested 3 s.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Convert normalized boxes to even pixel ints; use `crop`, `scale=…:force_original_aspect_ratio=increase` then `crop` for cover-fit; `vstack`/`overlay` as needed; when `ass_path` is given append `ass=` filter to the final video stream; `render_clip` runs `ffmpeg -ss start -to end -i src -filter_complex … -map [out] -map 0:a? -c:v libx264 -preset veryfast -crf 20 -c:a aac -movflags +faststart`.
- [ ] **Step 4: Run, expect PASS. Commit** `feat: layouts and ffmpeg render`.

### Task 5: Download, analyze pipeline, job API

**Files:**
- Create: `backend/app/download.py`, `backend/app/jobs.py`, `backend/app/pipeline.py`, `backend/tests/test_jobs_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: Tasks 2 and 3 functions; `Settings.data_dir`.
- Produces: `download_video(url: str, dest_dir: Path) -> VideoInfo` where `@dataclass VideoInfo(path: Path, title: str, channel_id: str, channel: str, duration: float, width: int, height: int, info: dict)`; `JobStore` (`create(url, notes) -> str`, `get(id) -> dict`, `update(id, **fields)`, stored as `data/jobs/<id>/job.json`) with fields `status` in `queued|downloading|analyzing|ready|error`, `error`, `candidates`, `video` (title, channel_id, width, height, duration); `run_analysis(job_id, store, settings)` (download, compute signals, combine, find candidates, save a sample frame `frame.jpg` at 10% of duration, update status); endpoints `POST /api/jobs {url, notes}` (starts background task, returns `{id}`), `GET /api/jobs/{id}`, `GET /api/jobs/{id}/frame` (the jpg).

- [ ] **Step 1: Write failing API tests** with the pipeline's heavy functions monkeypatched (`download_video`, signals) to return a tiny fake video: `test_create_job_returns_id_and_reaches_ready` (poll `GET` until `ready`, candidates list present), `test_analysis_error_sets_error_status_with_message` (download raises), `test_zero_candidates_is_ready_with_empty_list`, `test_unknown_job_404`, `test_frame_endpoint_returns_jpeg`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** with FastAPI `BackgroundTasks`; yt-dlp via Python API with format `bestvideo[height<=1080]+bestaudio/best[height<=1080]` merged to mp4; frame via ffmpeg `-frames:v 1`.
- [ ] **Step 4: Run, expect PASS. Commit** `feat: download, analysis pipeline and job API`.

### Task 6: Transcription, captions, LLM ranking

**Files:**
- Create: `backend/app/transcribe.py`, `backend/app/captions.py`, `backend/app/llm.py`, `backend/tests/test_captions.py`, `backend/tests/test_llm.py`

**Interfaces:**
- Produces: `transcribe(video_path: Path, start: float, end: float) -> list[Word]` with `@dataclass Word(text: str, start: float, end: float)` (faster-whisper `small`, word timestamps, times relative to the clip start); `build_ass(words: list[Word], path: Path) -> None` (word-grouped 3-4 word captions, bottom-center, bold, outlined, 1080x1920 PlayRes); `rank_candidates(candidates: list[Candidate], transcripts: dict[int, str], notes: str, settings: Settings) -> list[RankedCandidate]` with `@dataclass RankedCandidate(candidate: Candidate, title: str, hook: str, llm_score: float|None)`; returns candidates in signal order with generic titles when `settings.llm_enabled` is false or any failure occurs.

- [ ] **Step 1: Write failing tests:**
  - `test_build_ass_groups_words_and_timing`: 8 words produce 2-3 Dialogue lines, times monotonic, file contains `PlayResX: 1080`.
  - `test_rank_without_llm_returns_signal_order`.
  - `test_rank_with_valid_json_reorders_and_titles`: mock `openai.OpenAI` client to return JSON `[{"index":1,"score":9,"title":"...","hook":"..."}, …]`; assert reorder by score and titles applied.
  - `test_rank_invalid_json_falls_back`, `test_rank_client_exception_falls_back`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** LLM call: `OpenAI(base_url=…, api_key=…)`, `chat.completions.create` with a system prompt giving the user's focus notes and asking for a JSON array only; parse with a tolerant extractor (first `[`…last `]`); 30 s timeout; any exception returns fallback.
- [ ] **Step 7: Run, expect PASS. Commit** `feat: transcription, captions and LLM ranking`.

### Task 7: Profiles and render endpoints

**Files:**
- Create: `backend/app/profiles.py`, `backend/tests/test_profiles_render_api.py`
- Modify: `backend/app/main.py`, `backend/app/pipeline.py` (rank step after candidates when LLM enabled)

**Interfaces:**
- Consumes: Tasks 4, 5, 6.
- Produces: `ProfileStore.get(channel_id) -> dict|None`, `ProfileStore.save(channel_id, game: Box, face: Box|None)` (JSON file `data/profiles.json`); endpoints `GET /api/profiles/{channel_id}`, `PUT /api/profiles/{channel_id} {game, face}`, `POST /api/jobs/{id}/render {start, end, layout, game, face, captions: bool, credit: bool}` returning `{render_id}`, `GET /api/renders/{render_id}` returning `{status, error, url}`, `GET /api/renders/{render_id}/file` (the mp4). When `credit` is true, the channel name is burned in as a small bottom text ("Source: <channel>") via the ass file.

- [ ] **Step 1: Write failing tests:** profile round trip, missing profile returns 404 body `null`-safe (frontend default), render with monkeypatched `render_clip` creates a file entry and reaches `done`, invalid layout returns 422, face layout with no face returns 422, `start >= end` returns 422, `end - start` over 90 returns 422.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Render runs as background task; captions step calls `transcribe` + `build_ass` only when `captions` is true.
- [ ] **Step 4: Run, expect PASS. Commit** `feat: profile storage and render API`.

### Task 8: Frontend scaffold with shadcn/ui

**Files:**
- Create: `clipper/frontend/` (Vite React TS app), `frontend/src/lib/api.ts`

**Interfaces:**
- Produces: typed API client in `api.ts` mirroring Tasks 5 and 7: `createJob`, `getJob`, `frameUrl`, `getProfile`, `saveProfile`, `startRender`, `getRender`, plus shared types `Box`, `Candidate`, `Job`, `Layout`.

- [ ] **Step 1: Scaffold** with `npm create vite@latest frontend -- --template react-ts`, set up Tailwind, run `npx shadcn@latest init`, add components: `button`, `input`, `textarea`, `card`, `select`, `slider`, `switch`, `badge`, `progress`, `sonner`, `tabs`.
- [ ] **Step 2: Configure Vite dev proxy** `/api` to `http://localhost:8000`.
- [ ] **Step 3: Write `api.ts`** with the types and functions above.
- [ ] **Step 4: Verify** `npm run build` succeeds. **Commit** `feat: frontend scaffold`.

### Task 9: Frontend flow

**Files:**
- Create: `frontend/src/components/UrlForm.tsx`, `BoxPicker.tsx`, `CandidateList.tsx`, `RenderPanel.tsx`, `frontend/src/lib/boxes.ts`, `frontend/src/lib/boxes.test.ts`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api.ts` from Task 8.
- Produces: pure helpers in `boxes.ts`: `dragToBox(start: {x,y}, end: {x,y}, rect: {w,h}) -> Box` (pixel drag to normalized, order-independent, clamped to 0..1), `moveBox(box, dx, dy) -> Box` (clamped), `resizeBox(box, handle, dx, dy) -> Box` (min size 0.02, clamped).

- [ ] **Step 1: Write failing vitest tests for `boxes.ts`:** drag in reverse direction gives positive w/h; drag past the frame edge clamps; `moveBox` cannot leave 0..1; `resizeBox` cannot go below min size.
- [ ] **Step 2: Run, expect FAIL.** Implement helpers, expect PASS.
- [ ] **Step 3: Build components with shadcn:** `UrlForm` (URL + notes + Analyze, progress via polling `getJob` every 2 s, error toast); `BoxPicker` (sample frame in a container with two draggable/resizable boxes, gameplay in one color and facecam in another, "Save for this streamer" button, loads saved profile on mount, sensible default boxes when none); `CandidateList` (ranked cards with score badge, title/hook, start/end sliders for trim, "no moments found" empty state); `RenderPanel` (layout tabs for the four layouts with a small live preview diagram, captions and credit switches, Render, progress, video player and download link).
- [ ] **Step 4: Wire `App.tsx` as a single page flow** (analyze, then boxes, then candidates, then render).
- [ ] **Step 5: Verify** `npm run build` and `npx vitest run` pass. **Commit** `feat: frontend flow`.

### Task 10: Serve frontend, run script, end-to-end check

**Files:**
- Create: `clipper/run.sh`, `clipper/README.md`
- Modify: `backend/app/main.py` (mount `frontend/dist` as static at `/` when present)

- [ ] **Step 1: Mount built frontend** with a catch-all to `index.html`, API routes under `/api` take priority.
- [ ] **Step 2: `run.sh`** builds the frontend if `dist` is missing, then starts `uvicorn app.main:app --port 8000`.
- [ ] **Step 3: README** covering prerequisites (ffmpeg, Python, Node), `.env` keys, one-command run, and the copyright caution from the spec.
- [ ] **Step 4: End-to-end check:** run the app, analyze a short real YouTube video (with replay heatmap preferably), confirm candidates appear, draw boxes, render one clip in each layout, and confirm each output plays at 1080x1920. Report results honestly, including anything that failed.
- [ ] **Step 5: Commit** `feat: serve frontend and docs`.

---

## Self-review notes

- Spec coverage: URL input and focus notes (T5, T9), auto detection with chat/audio/heatmap (T2, T3), LLM re-rank and titles with `.env` config (T6), adjustable gameplay and facecam boxes saved per streamer (T7, T9), four layouts (T4), captions toggle and credit line (T6, T7), one-command local run (T10). Manual start/end trim is covered by the candidate sliders (T9). Auto facecam detection and upload are non-goals.
- Type consistency: `Box`, `Candidate`, `Word`, `VideoInfo` are defined once and referenced by the same names across tasks.
