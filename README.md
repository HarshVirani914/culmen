# Shorts Clipper

Turn highlights from YouTube, Twitch and Kick gaming streams into 1080x1920 Shorts.

- **Replay tab:** paste a link (optionally a time range). The app finds the most reacted-to moments
  (chat spikes, audio peaks, YouTube's "most replayed" graph, optional LLM ranking and titles).
- **Live tab:** paste a live stream link. The app records it into a small rolling buffer and saves a
  moment whenever chat and audio spike, ready to frame and render.
- You frame the gameplay and facecam once per streamer, pick a layout, and render.

## Requirements
- ffmpeg. Captions and the source-credit line need a build with libass: `brew install ffmpeg-full`
  (the app finds it automatically; the default `brew install ffmpeg` has no libass).
- Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20+
- Apple Silicon Macs get fast GPU transcription (MLX Whisper). Other machines fall back to CPU
  (faster-whisper), which is much slower.

## Run
```bash
cp .env.example .env   # optional: add your OpenAI-compatible LLM
./run.sh               # opens on http://localhost:8000
```

## LLM (optional)
Any OpenAI-compatible API. Set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` in `.env`.
Without it the app still works using the signals alone.

## Supported links
YouTube, Twitch and Kick (`youtube.com`, `youtu.be`, `twitch.tv`, `kick.com`). Nothing else is accepted.

| | Replay chat | Live chat |
|---|---|---|
| YouTube | yes (via yt-dlp) | see "Verified status" |
| Twitch | not available (audio only) | yes (anonymous IRC) |
| Kick | not available (audio only) | best effort, unverified |

When chat is unavailable the app detects moments from audio alone and says so.

## Live clipping
- Records with ffmpeg stream copy (no re-encode, source quality) into 6-second segments.
- Keeps a rolling buffer (default 12 minutes, about 700 MB for a 1080p stream). Set
  `CLIPPER_LIVE_BUFFER_SECONDS` to change it.
- A spike needs both a loudness jump and (when chat is connected) a rise in distinct chatters.
  Limits: one moment per 45 s, at most 12 per hour.
- Each moment is cut from the buffer into a normal job, so the frame / trim / layout / render screens
  work unchanged. Saved moments are capped at 3 GB (`CLIPPER_LIVE_CAP_GB`); the oldest unopened ones go
  first, and any moment you opened or rendered is kept.
- One live session at a time. A session does not survive an app restart; saved moments do.
- Auto-posting and auto-render are not implemented.

## Long and slow videos
- Videos up to 4 hours are downloaded whole at full speed and the requested range is cut locally.
- Longer videos use a slow section download (at most 3 hours). Very long live-stream replays may
  fail to download a section; pick a shorter replay.
- Live-stream replays are stored by YouTube as thousands of small pieces and can download very slowly
  (the app uses 32 parallel pieces). Uploaded videos download much faster.
- Before downloading, the app checks free disk space and refuses if it is too low.

## Layouts
`stacked` (facecam on top), `facecam bubble`, `gameplay only` (blurred background), `facecam only`.
Final encode is x264 medium preset, CRF 18.

## Development
```bash
cd backend && uv run pytest          # backend tests
cd frontend && npx vitest run        # frontend tests
cd frontend && npm run dev           # dev UI on :5173, proxies /api to :8000
```

## Caution
Clipping other creators' streams can trigger copyright or reused-content problems
(strikes, demonetization). Captions, commentary and the source-credit option help but don't
remove the risk.
