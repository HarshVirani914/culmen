# Live Clipping and Twitch/Kick Links: Design

Extends `2026-11-19-shorts-clipper-design.md`. Auto-posting is explicitly out of scope for now.

## Intent
The user clips gaming streams from other creators for a Shorts channel. Replays are handled today. They now want to clip a stream while it is live, so a moment can be turned into a Short minutes after it happens, and to paste Twitch and Kick links as well as YouTube. Chosen approach (user picked "A"): a rolling recording buffer, live detection, and an approval step. Quality must stay high and disk use small.

## Goals
- Paste a live URL (YouTube, Twitch or Kick), press Start, and see "live moments" appear as the stream goes on, each with a playable preview.
- A moment is created automatically when chat and audio spike, from footage taken out of a rolling buffer. The user then picks a layout, trims, and renders it with the facecam and gameplay boxes saved for that streamer (the existing flow).
- Source quality is preserved: the recorder never re-encodes, and each Short is encoded once, at the end.
- Disk use is bounded and visible: buffer length, pinned-moments cap, and a clear "disk used" readout.
- Twitch and Kick URLs also work for normal (non-live) analysis.
- Optional "auto-render" switch: every new moment is rendered with the saved boxes and the last-used layout and left in a folder for review. Off by default.

## Non-goals
- Auto-posting (deferred by the user).
- Several simultaneous live sessions (v1 runs one at a time).
- Surviving an app restart mid-session. Pinned moments persist, the live session does not.
- Transcoding or recording the whole stream.
- Judging gameplay quality visually. Detection uses chat and audio.

## Anti-goals
- Filling the disk. A forgotten session must not grow without limit.
- Missing the start of a moment because the buffer rolled too soon.
- A flood of low-quality moments: unlimited triggering is a failure even if it technically works.

## Constraints
- Runs on the user's Mac, only while the app is open. Apple Silicon: MLX Whisper is available for transcription.
- YouTube HLS stream URLs expire (about 6 hours), so the recorder must re-resolve them.
- Only YouTube, Twitch and Kick hosts are accepted (SSRF allowlist already in place for YouTube).
- Reuses: `render_clip`, layouts, box profiles, signals scoring, the LLM titler, the job/candidate data shapes.

## Approaches considered
- **A. Rolling buffer with approval (chosen).** Small disk footprint, user stays in control.
- B. Auto-render every spike: more clutter and needs saved boxes up front. Kept only as the opt-in switch on top of A.
- C. Record the whole stream and analyze in chunks: 8-10 GB for a 4 hour stream and late clips. Rejected.

## Design

### 1. Recorder (new `live/recorder.py`)
- Resolve a direct stream URL with yt-dlp (`best` up to 1080p, HLS), uniformly for YouTube, Twitch and Kick.
- ffmpeg reads the URL with reconnect flags and writes 10-second segments with stream copy (`-c copy`, MPEG-TS) to `data/live/<session>/buffer/NNNNNN.ts`. No re-encode, so quality equals the source.
- A janitor deletes segments older than the buffer length. Default buffer 12 minutes. At 6-8 Mbps source bitrate that is roughly 550-720 MB.
- If ffmpeg exits while the stream is still live, retry with backoff (5 tries), re-resolving the URL each time. When the stream is over, the session ends with status `ended`.

### 2. Live signals and detector (new `live/detector.py`)
- Audio: as each segment completes, compute per-second RMS (existing `audio_energy` logic) and keep a rolling 10-minute history.
- Chat: Twitch via anonymous IRC over websocket, Kick via its public chat websocket, YouTube via polling YouTube's live chat endpoint. Messages feed the existing unique-chatter-per-second score. If chat is unavailable for a platform, the session runs on audio alone and the UI says so.
- Score per second = existing `combine` of the available signals, normalized against the rolling baseline.
- Trigger when the smoothed score exceeds an adaptive threshold (mean + 2 standard deviations over the last 10 minutes, with a floor), then wait 12 seconds of post-roll so the reaction is included. At most one moment per 45 seconds (cooldown) and a configurable cap per hour (default 12).
- Moment window: 25 s before the spike start to 15 s after the post-roll, 30-60 s total, clamped to what the buffer holds.

### 3. Moments (new `live/moments.py`)
- On trigger, the needed segments are concatenated with stream copy into `data/jobs/<moment-job>/video.mp4`, so they survive the buffer rolling.
- Each moment becomes an ordinary job (`status: ready`, one candidate) with `video` metadata, a sample frame, and the streamer's channel id. The existing box picker, trim slider, layouts and render API work on it unchanged.
- Titles and hooks: after the moment is pinned, `transcribe_text` (MLX) plus the LLM add a title and hook in the background. Failure leaves the generic "Moment N" title.
- Storage rules: pinned moments are capped (default 3 GB). When the cap is hit, the oldest un-rendered moments are deleted first. A moment the user opened or rendered is kept until they remove it.

### 4. API
- `POST /api/live {url, notes}` starts a session. Returns `{id}`. Rejects if one is already running (409).
- `GET /api/live/{id}` returns `{status, started_at, buffer_seconds, disk_mb, signals: {chat: bool, audio: bool}, recent_scores: [...], moments: [job ids]}`.
- `POST /api/live/{id}/stop` stops recording and keeps pinned moments.
- Moments are read and rendered through the existing `/api/jobs/...` endpoints.

### 5. UI
- A "Live" tab beside the existing flow. Start form (URL, focus notes). A running panel: status dot, buffer length, disk used, and a small live signal sparkline. A feed of moment cards (preview player, score, generated title) that opens the existing frame/layout/render screens. A Stop button.

### 6. Twitch and Kick links for normal analysis
- Extend the allowlist (`twitch.tv`, `kick.com`) and yt-dlp `allowed_extractors`. Replay chat for Twitch and Kick VODs is not available through yt-dlp, so those start with audio-only detection; chat is added if a reliable source is verified.

### 7. Rendering quality
- Final encode changes from `-preset veryfast -crf 20` to `-preset medium -crf 18`, the one place re-encoding happens. Slower by about 2x, visibly cleaner.

## Testing approach
- Detector and window logic: unit tests with synthetic score arrays (spike, cooldown, cap, edges, no data).
- Janitor and storage cap: unit tests on temporary directories.
- Recorder: integration test using a local file as a fake live source (`ffmpeg -re`), asserting segments appear, old ones are deleted, and a moment's concatenated clip has the expected duration.
- Chat clients: unit tests on message parsing with recorded sample frames; real-network checks are manual.
- A real-stream manual check on a live YouTube and a live Twitch channel before calling it done.

## Open unknowns to verify in the first build step
- Whether YouTube live chat polling works reliably today (the old chat library does not).
- Kick's chat websocket details and whether Kick streams resolve through yt-dlp.
- Twitch ad breaks inside the HLS stream (they may appear in the buffer and trip the audio detector).

## My calls (flag any you disagree with)
- Buffer 12 minutes, pinned cap 3 GB, one session at a time.
- Moment cooldown 45 s, max 12 moments per hour, adaptive threshold.
- Final render preset medium, crf 18.
- Auto-render is off by default.

## Left to the builder
Exact threshold constants, sparkline styling, file layout under `backend/app/live/`, websocket library choice.
