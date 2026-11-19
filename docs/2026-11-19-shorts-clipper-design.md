# Culmen: Stream-to-Shorts Design

## Intent
The user is starting a YouTube Shorts channel built from key moments of other creators' gaming live streams. They need to get from a stream link to ready-to-upload 9:16 clips quickly, with the most reacted-to moments found automatically. Speed to a working version matters more than polish.

## Goals
- Paste a YouTube video/stream-replay URL into a small local web UI.
- Auto-detect the best moments (viral/reaction peaks) and list them as ranked candidates with timestamps, score, and a thumbnail/preview.
- The user can also add focus notes (free text, e.g. "clutches and rage moments") and/or manual start/end times.
- Render each chosen moment to 1080x1920 MP4 using a selectable layout.
- Adjustable regions: the user drags/resizes two boxes on a sample frame, one for the gameplay region and one for the facecam region. Boxes are saved per streamer/channel and reused.
- Layouts (v1): Stacked (facecam on top, gameplay below), Facecam bubble (gameplay full-frame crop with facecam overlay in a corner), Gameplay only (blurred background fill), Facecam only.
- Burned-in captions (word-level, from Whisper) as an optional toggle.

## Non-goals (v1)
- Auto-detecting the facecam position (the user draws it once instead).
- Uploading to YouTube, scheduling, or multi-account management.
- Cloud hosting or multi-user support.
- Editing timelines, music, sound effects.

## Anti-goals
- A big framework or Docker stack that takes longer to understand than to rebuild.
- Detection that only works when live chat exists (many replays have chat disabled), so audio and transcript signals must work alone.

## Constraints
- Runs locally on the user's Mac. No git repo, no server hosting.
- Source is other creators' content. YouTube's reused-content and copyright rules apply and can lead to strikes or demonetization. The tool does not address this; the user has been told. Cheap mitigations that are in scope: caption/commentary overlays and a source-credit line option.
- Tool uses yt-dlp to download, so it depends on YouTube not breaking yt-dlp.

## Approaches considered
1. **Thin custom tool (chosen).** Python (FastAPI) backend plus a single-page HTML UI. Reuses yt-dlp, chat-downloader, FFmpeg, faster-whisper. Fastest to a working version and gives full control of layouts.
2. Fork OpenShorts: rich pipeline but heavy Docker codebase, no gaming facecam layout, slower to modify.
3. Run OpenShorts as-is plus a separate peak finder: least work, but lacks the facecam-plus-gameplay layouts that are the core need.

## Design
**Pipeline:** URL -> download video (yt-dlp, capped at 1080p) -> signals -> candidate windows -> user review -> render.

**Signals (combined into one score per time window, rolling baseline):**
- Live chat replay message rate and emote/caps density (chat-downloader), when available.
- Audio loudness and sudden-energy spikes (FFmpeg/librosa), always available.
- YouTube "most replayed" heatmap when the video exposes it (via yt-dlp metadata), a strong direct viewer-reaction signal.
- Transcript (faster-whisper) for caption text, and, when an LLM key is set, an LLM re-ranks the top candidates and writes a title and hook line, using the user's focus notes as guidance.
Without an LLM key, the tool still works using signals only.

**Candidate windows:** peaks are expanded to 20-60 s clips, with start/end snapped to speech pauses, then de-duplicated.

**UI:** one page. Steps: paste URL and notes, then Analyze; then a frame picker where the user drags the gameplay box and facecam box on a sample frame, with a Save for this streamer option; then a ranked candidate list with preview and trim handles; then per-clip layout choice and Render; then download links.

**Rendering:** FFmpeg filter graphs built from the saved boxes and chosen layout. Output 1080x1920, H.264/AAC. Captions via ASS subtitles.

**Stack:** Backend: Python 3.11+, FastAPI, FFmpeg, yt-dlp, chat-downloader, faster-whisper. Frontend (user's choice): React + Vite + Tailwind with shadcn/ui components and design; a canvas component for dragging the gameplay and facecam boxes. LLM (user's choice): any OpenAI-compatible API, configured by base URL, API key and model name in a `.env` file, called through the standard `openai` Python client with a custom `base_url`. In dev the Vite frontend proxies to FastAPI; for normal use FastAPI serves the built frontend, so it is one command to run.

## Left to the builder
Exact scoring weights, window lengths, caption styling, file layout, project name, and error handling for videos without chat.
