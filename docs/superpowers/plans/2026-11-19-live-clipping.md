# Live Clipping and Twitch/Kick Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record a live stream into a small rolling buffer, auto-detect reaction spikes from chat and audio, pin each spike as a "moment" the user can render with the existing layouts, and accept Twitch and Kick links.

**Architecture:** A `LiveSession` owns an ffmpeg stream-copy recorder writing 10 s segments, a detector fed by per-second audio and chat scores, and a moment pinner that cuts footage out of the buffer into ordinary jobs (`status: ready`, one candidate), so the existing box picker, trim and render flow works unchanged. Pure logic (detector, buffer pruning, cap enforcement, chat parsing) is isolated and unit tested; ffmpeg and network parts are covered by integration tests with a local file standing in for a live stream.

**Tech Stack:** Python 3.12, FastAPI, ffmpeg (stream copy), yt-dlp (stream URL), websockets, numpy, React + shadcn/ui.

**Spec:** `docs/2026-11-19-live-clipping-design.md` (extends `docs/2026-11-19-shorts-clipper-design.md`)

## Global Constraints

- Recorder never re-encodes: `-c copy`, 10-second MPEG-TS segments.
- Rolling buffer default 12 minutes; pinned-moments cap default 3 GB; one live session at a time (second start returns 409).
- Moment window: 25 s before the spike start to 15 s after the post-roll, total 30-60 s; post-roll wait 12 s; cooldown 45 s between moments; max 12 moments per hour.
- Adaptive trigger threshold: mean + 2 standard deviations of the last 10 minutes of scores, with a floor.
- Hosts allowed: `youtube.com`, `youtu.be`, `twitch.tv`, `kick.com` (and subdomains). Nothing else.
- Final render encode: `-preset medium -crf 18`.
- Auto-render defaults to off. Auto-posting is out of scope.
- All backend code under `backend/app/` (live code in `backend/app/live/`), tests in `backend/tests/`.
- Existing tests keep passing at every commit.

## Rulings from reading the PeakCut reference repo (MIT, `studio/live.py`)

- Segment length 6 s (not 10): finer clip boundaries, same cost. Reconnect flags `-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 10`; re-resolve the URL when ffmpeg exits while the stream is live.
- Twitch chat: raw TLS socket to `irc.chat.twitch.tv:6697`, `NICK justinfan<number>`, `JOIN #channel`, answer `PING` with `PONG :tmi.twitch.tv`, nick regex `^:([A-Za-z0-9_]{2,25})!`. No websocket library needed for Twitch.
- Loudness is read from saved segments (not a separate audio pipe) because PeakCut documents about 4 s per hour of clock drift between a live audio feed and the video segments.
- Detector baseline excludes the most recent 10 s; chat counts as a jump only when it passes `max(1.5, 1.6 x baseline)`.
- Cutting: pad 8 s, wait until the buffer reaches the window end, fail with a clear message if the window start already rolled off.
- PeakCut has no YouTube or Kick chat and no Twitch ad handling, so those unknowns remain open and are checked in Task 10.

## Review Focus

- ffmpeg dies or the HLS URL expires mid-session: the recorder retries with a re-resolved URL and ends the session cleanly when the stream is over.
- Chat unavailable for a platform: session runs on audio alone and the status reports `chat: false`, never an error.
- Spike in the first seconds of a session (buffer shorter than the pre-roll): window is clamped to what exists.
- Buffer rolls while a moment is being cut: segments needed by a pending moment are protected from the janitor.
- Pinned-moment cap reached while the user is viewing or rendering one: that moment is never deleted.
- Start while a session runs, stop twice, or stop before first segment: clean 409 / no-op / no crash.
- Silent stream (no audio) or a very loud ad break: no crash; cooldown and per-hour cap prevent a flood.

---

### Task 1: Twitch and Kick link support

**Files:**
- Modify: `backend/app/download.py` (`ALLOWED_HOSTS`, `allowed_extractors`), `backend/tests/test_url_validation.py`

**Interfaces:**
- Produces: `validate_url(url) -> str` now accepts `twitch.tv` and `kick.com`; `ALLOWED_EXTRACTORS: list[str]` module constant used by every yt-dlp call (`download.py`, `chat.py`, later `live/recorder.py`).

- [ ] **Step 1: Write failing tests:** `test_twitch_and_kick_urls_valid` (`https://www.twitch.tv/videos/123`, `https://twitch.tv/somechannel`, `https://kick.com/somechannel`, `https://m.twitch.tv/x`); `test_lookalike_hosts_rejected` (`https://twitch.tv.evil.com/x`, `https://kick.com.evil.com`, `https://evilkick.com`); `test_extractor_list_covers_platforms` asserting `ALLOWED_EXTRACTORS` contains regex patterns matching `twitch:stream`, `twitch:vod`, `kick:live`, `youtube`.
- [ ] **Step 2: Run, expect FAIL.** `cd backend && uv run pytest tests/test_url_validation.py -q`
- [ ] **Step 3: Implement** the allowlist and `ALLOWED_EXTRACTORS` (yt-dlp `allowed_extractors` entries are regexes). Replace the inline list in `download.py` and `chat.py`.
- [ ] **Step 4: Run full suite, expect PASS. Commit** `feat: accept Twitch and Kick links`.

### Task 2: Higher quality final render

**Files:**
- Modify: `backend/app/render.py`, `backend/tests/test_render.py`

**Interfaces:**
- Produces: `render_clip` signature unchanged; `ENCODE_ARGS: list[str]` constant (`-preset medium -crf 18 -pix_fmt yuv420p`).

- [ ] **Step 1: Write failing test** `test_render_uses_quality_preset`: monkeypatch `subprocess.run` in `app.render`, call `render_clip`, assert the command contains `medium` after `-preset` and `18` after `-crf`.
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement** using `ENCODE_ARGS`. **Step 4: Run render tests, expect PASS** (existing real-render tests still produce 1080x1920). **Commit** `feat: higher quality final encode`.

### Task 3: Live detector (pure logic)

**Files:**
- Create: `backend/app/live/__init__.py`, `backend/app/live/detector.py`, `backend/tests/test_live_detector.py`

**Interfaces:**
- Produces: `@dataclass MomentWindow(start: float, end: float, score: float)` (seconds on the session clock); `class LiveDetector` with `__init__(self, pre_roll: float = 25, post_roll: float = 12, tail: float = 3, cooldown: float = 45, max_per_hour: int = 12, history: float = 600, floor: float = 0.35)`, `feed(self, t: float, score: float) -> MomentWindow | None` (called once per second with the combined 0..1 score at session time `t`; returns a window when a trigger fires and its post-roll has elapsed), and `available_start: float` attribute the recorder updates (earliest second still in the buffer) so windows are clamped.

- [ ] **Step 1: Write failing tests** (feed second by second): `test_quiet_stream_never_triggers`; `test_spike_triggers_after_post_roll` (spike at t=100..104; no window before t=100+post_roll, one window after containing 100..104 with `end - start` in 30..60); `test_cooldown_blocks_second_moment` (second spike 20 s later ignored, spike 60 s later accepted); `test_max_per_hour_cap`; `test_window_clamped_to_available_start` (spike at t=5, `available_start=0`, `start == 0`); `test_adaptive_threshold_ignores_constant_loud_stream` (score constantly 0.9 for 10 min, no triggers); `test_all_zero_scores_no_crash`.
- [ ] **Step 2: Run, expect FAIL. Step 3: Implement** with a rolling deque for the baseline (mean + 2 std, never below `floor`), a pending-trigger state that fires `post_roll` seconds after the first over-threshold second, and window = `[trigger_start - pre_roll, trigger_end + tail]` clamped to `[available_start, t]` and to a 60 s maximum. **Step 4: PASS. Commit** `feat: live moment detector`.

### Task 4: Segment buffer and storage cap

**Files:**
- Create: `backend/app/live/buffer.py`, `backend/app/live/storage.py`, `backend/tests/test_live_buffer.py`, `backend/tests/test_live_storage.py`

**Interfaces:**
- Produces: `class SegmentBuffer(dir: Path, max_seconds: float = 720, seg_seconds: float = 10)` with `list() -> list[Segment]` (`Segment(index: int, path: Path, start: float)` sorted, start on the session clock), `prune() -> list[Path]` (deletes segments older than `max_seconds` except protected ones), `protect(start: float, end: float) -> Callable[[], None]` (returns a release function; protected segments survive pruning), `available_start() -> float`, `extract(start: float, end: float, out: Path) -> None` (ffmpeg concat demuxer, stream copy, trimmed to the exact window; raises `ValueError` if the window is not fully inside the buffer after clamping empties it); `enforce_cap(moments_dir: Path, cap_bytes: int, keep: set[str]) -> list[str]` in `storage.py` (deletes oldest job directories first until under the cap, never any id in `keep`, returns deleted ids).

- [ ] **Step 1: Write failing tests:** `test_prune_removes_old_segments_keeps_recent`; `test_protected_segments_survive_prune_until_released`; `test_available_start_after_pruning`; `test_extract_has_expected_duration` (real ffmpeg, 6 generated 10 s `.ts` segments, extract 15-40 s, probe duration about 25 s); `test_extract_outside_buffer_raises`; `test_enforce_cap_deletes_oldest_first_and_never_keep` (temp dirs with sized files).
- [ ] **Step 2: FAIL. Step 3: Implement.** Segments are named `%06d.ts` and parsed by index; session time = index * seg_seconds. **Step 4: PASS. Commit** `feat: segment buffer and storage cap`.

### Task 5: Recorder

**Files:**
- Create: `backend/app/live/recorder.py`, `backend/tests/test_live_recorder.py`

**Interfaces:**
- Consumes: `SegmentBuffer` (Task 4), `ALLOWED_EXTRACTORS` (Task 1), `ffmpeg_bin()`.
- Produces: `resolve_stream_url(url: str) -> str` (yt-dlp, best up to 1080p, returns one playable URL; raises `ValueError` if the stream is not live); `class Recorder(source: Callable[[], str], buffer_dir: Path, on_segment: Callable[[Segment], None] | None = None, seg_seconds: float = 10, retries: int = 5)` with `start() -> None`, `stop() -> None` (idempotent), `status: Literal["starting","recording","ended","error"]`, `error: str | None`. `source` is called again on every reconnect to re-resolve the URL. ffmpeg runs `-c copy -f segment -segment_time 10 -reset_timestamps 1` with HTTP reconnect flags.

- [ ] **Step 1: Write failing tests using a local file as the live source** (`source=lambda: str(local_mp4)` with ffmpeg `-re` in the test config): `test_records_segments_and_reports_recording` (30 s source yields at least 2 segments within the time limit, `on_segment` called); `test_ends_when_source_finishes` (status `ended`); `test_retries_then_errors_on_bad_source` (nonexistent URL, status `error` after the retries, no exception raised to the caller); `test_stop_is_idempotent_and_kills_ffmpeg`; `test_stop_before_first_segment_is_safe`.
- [ ] **Step 2: FAIL. Step 3: Implement** with a background thread that spawns ffmpeg, watches the buffer directory (or ffmpeg's segment list) to call `on_segment` for each newly completed segment, and applies backoff (2, 4, 8, 16, 32 s; shortened via a module constant in tests). **Step 4: PASS. Commit** `feat: stream-copy recorder`.

### Task 6: Live signals (audio per segment, chat parsers)

**Files:**
- Create: `backend/app/live/signals.py`, `backend/app/live/chat_live.py`, `backend/tests/test_live_signals.py`, `backend/tests/test_chat_live.py`

**Interfaces:**
- Produces: `segment_audio_scores(path: Path, seg_seconds: float = 10) -> np.ndarray` (per-second raw RMS for one segment, zeros if no audio); `class ScoreTracker(history: float = 600)` with `add_audio(t: float, rms: float)`, `add_chat(t: float, author: str)`, `score(t: float) -> float` (0..1: audio spike vs rolling median combined with unique chatters per second, reusing `signals.combine`/`normalize`), `has_chat: bool`; parsers `parse_twitch_irc(line: str) -> tuple[str, str] | None` (returns `(author, text)` for a PRIVMSG), `parse_kick_event(raw: str) -> tuple[str, str] | None`, `parse_youtube_live_chat(json_obj: dict) -> list[tuple[str, str]]`; async `class ChatSource` with `async run(on_message: Callable[[str, str], None]) -> None` and `close()`; factory `chat_source_for(url: str) -> ChatSource | None` (None when the platform has no supported chat).

- [ ] **Step 1: Write failing tests:** `test_segment_audio_scores_detects_burst` (generated segment with a loud second); `test_segment_without_audio_returns_zeros`; `test_tracker_chat_crowd_beats_single_user_spam`; `test_tracker_audio_only_when_no_chat` (`has_chat` False, score still works); `test_parse_twitch_privmsg_and_ignores_ping_join_notice`; `test_parse_kick_chat_message_event_and_ignores_others`; `test_parse_youtube_live_chat_actions`; `test_chat_source_for_unknown_host_is_none`.
- [ ] **Step 2: FAIL. Step 3: Implement.** Twitch: anonymous `justinfan` IRC over websocket (`wss://irc-ws.chat.twitch.tv`), JOIN `#channel`, answer PING. Kick: public chat websocket subscription for the channel's chatroom id, event `App\Events\ChatMessageEvent`. YouTube: poll the live chat endpoint using the continuation token from the watch page. **The three network clients are manual-checked in Task 10; unit tests cover parsing only.** **Step 4: PASS. Commit** `feat: live audio and chat signals`.

### Task 7: Live session, moments as jobs, API

**Files:**
- Create: `backend/app/live/session.py`, `backend/tests/test_live_api.py`
- Modify: `backend/app/main.py`, `backend/app/jobs.py` (helper `create_ready(...)`)

**Interfaces:**
- Consumes: Tasks 3-6, `JobStore`, `render_clip` flow.
- Produces: `JobStore.create_ready(url: str, notes: str, video: dict, candidates: list[dict]) -> str`; `class LiveSession` with `id`, `start()`, `stop()`, `snapshot() -> dict` (`status`, `started_at`, `buffer_seconds`, `disk_mb`, `signals: {"chat": bool, "audio": bool}`, `recent_scores: list[float]` (last 120), `moments: list[str]` job ids, `error`), and an `on_moment(window)` that: protects the segments, extracts `data/jobs/<id>/video.mp4`, creates a ready job whose single candidate spans the clip, extracts a sample frame, releases protection, runs `storage.enforce_cap` (keeping the newest and any opened moment). Module-level `get_manager()` holds at most one session. Endpoints: `POST /api/live {url, notes}` (validates URL, 409 if running, 422 for a non-live URL), `GET /api/live/{id}`, `POST /api/live/{id}/stop`. `Settings` gains `live_buffer_seconds=720`, `live_cap_gb=3`, `live_auto_render=False`.

- [ ] **Step 1: Write failing API tests with a fake recorder and fake chat** (inject via `get_manager` factory): `test_start_returns_id_and_status_recording`; `test_second_start_returns_409`; `test_stop_is_idempotent_and_keeps_moments`; `test_spike_creates_moment_as_ready_job` (feed synthetic audio so the detector fires; the new job id appears in `moments`, `GET /api/jobs/{id}` is `ready` with one candidate and a video file of about the window length); `test_non_live_url_422`; `test_cap_never_deletes_moment_being_rendered`; `test_session_without_chat_reports_chat_false`.
- [ ] **Step 2: FAIL. Step 3: Implement.** One scoring loop per session: each completed segment adds its per-second audio to `ScoreTracker`, then `detector.feed(t, tracker.score(t))` for each second. **Step 4: Full suite PASS. Commit** `feat: live session, moments and API`.

### Task 8: Moment titles in the background

**Files:**
- Modify: `backend/app/live/session.py`, `backend/tests/test_live_api.py`

**Interfaces:**
- Consumes: `transcribe.transcribe_text`, `llm.rank_candidates`, `JobStore.update`.

- [ ] **Step 1: Write failing tests:** `test_moment_gets_llm_title_and_hook` (LLM enabled, transcribe and LLM monkeypatched, job's candidate title replaced); `test_titling_failure_keeps_generic_title`; `test_titling_does_not_block_new_moments` (slow fake transcribe, a second spike still produces its moment).
- [ ] **Step 2: FAIL. Step 3: Implement** titling on a single background worker thread fed by a queue; no-op when `settings.llm_enabled` is false. **Step 4: PASS. Commit** `feat: live moment titles`.

### Task 9: Live tab UI

**Files:**
- Create: `frontend/src/components/LivePanel.tsx`, `frontend/src/lib/live.ts`, `frontend/src/lib/live.test.ts`
- Modify: `frontend/src/lib/api.ts`, `frontend/src/App.tsx`

**Interfaces:**
- Produces: API client `startLive(url, notes)`, `getLive(id)`, `stopLive(id)` and type `LiveSnapshot` mirroring Task 7; helper in `live.ts` `sparklinePoints(scores: number[], w: number, h: number) -> string` (SVG polyline points; empty or constant input yields a flat line, never NaN).

- [ ] **Step 1: Write failing vitest tests for `sparklinePoints`:** empty input, single value, all equal, values scaled into the box, no `NaN` in output. **Step 2: FAIL. Step 3: Implement the helper. Step 4: PASS.**
- [ ] **Step 5: Build `LivePanel`** with shadcn components: start form (URL, notes), running card (status badge, buffer length, disk used, chat/audio indicators, sparkline), moment cards (each loads that job into the existing flow: box picker, candidate trim, layout, render), Stop button, polling every 2 s. Add a Tabs switcher in `App.tsx` between "Replay" and "Live". Show the "chat unavailable, using audio only" notice when `signals.chat` is false.
- [ ] **Step 6: `npm run build` and `npx vitest run` pass. Commit** `feat: live tab`.

### Task 10: Verification on real streams and docs

**Files:**
- Modify: `README.md`, `docs/ledger.md`

- [ ] **Step 1: Manual run on a live YouTube stream** (user picks or I search): start a session, watch for at least 10 minutes, confirm segments rotate (disk stays near the 12 minute size), moments appear, a moment previews, and rendering one produces a 1080x1920 Short. Record chat status.
- [ ] **Step 2: Same check on a live Twitch channel and a live Kick channel,** noting whether chat connected and whether ad breaks caused false triggers.
- [ ] **Step 3: Stop the session and confirm no ffmpeg process remains and the buffer directory is cleaned.**
- [ ] **Step 4: Update the README** (live clipping, supported platforms, storage settings) and the ledger with anything that failed or was verified only partially. Report honestly. **Commit** `docs: live clipping`.

---

## Self-review notes

- Spec coverage: live URL start/stop and moment feed (T5, T7, T9); detection from chat and audio with adaptive threshold, cooldown, cap, pre/post-roll (T3, T6); rolling buffer, protection and storage cap (T4, T7); moments reuse the existing job flow (T7); titles (T8); Twitch/Kick links (T1); quality preset (T2); auto-render stays off and is deferred as a setting only (T7 `live_auto_render`, no behavior in v1); audio-only fallback and chat indicators (T6, T7, T9). Unknowns (YouTube/Kick chat, ad breaks) are checked in T10.
- Types: `MomentWindow`, `Segment`, `SegmentBuffer`, `ScoreTracker`, `Recorder`, `LiveSession` are each defined once and used with the same names.
- Auto-render: the setting exists but is intentionally a no-op in this plan to keep scope small; flagged here so it is not mistaken for a gap.
