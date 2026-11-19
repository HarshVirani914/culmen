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
- Sensitivity (Low / Normal / High) sets how far above the stream's own baseline a spike has to rise. Use High for
  streams that are loud all the time.
- Auto-posting and auto-render are not implemented.

## Time ranges and long videos
- **Fast section download:** for processed YouTube videos, only the requested time range is fetched, using the
  video's segment index (`sidx`) and many parallel chunked requests. A 5 minute 1080p60 section of a 9 hour video
  took 34 s (the old ffmpeg section download ran at about 0.6x realtime, 25+ minutes for 30 minutes). The cut
  snaps outward to segment boundaries (a few seconds); timestamps in the app account for that.
- If that is not possible (no mp4/avc1 formats, no index), it falls back to downloading videos up to 4 hours whole
  and cutting locally, and for longer ones to the slow ffmpeg section download (at most 3 hours).
- **Replays of streams that just ended** (`post_live`) can't be cut until YouTube finishes processing them, usually
  a few hours. The app says so instead of failing cryptically.
- Live-stream replays are stored by YouTube as thousands of small pieces and can download very slowly whole
  (the app uses 32 parallel pieces). Uploaded videos download much faster.
- Before a whole-file download the app checks free disk space and refuses if it is too low.

## YouTube "confirm you're not a bot" (optional cookies)
If YouTube blocks requests, export the login cookies of a **throwaway** account (never your main one):
sign in to youtube.com in a browser profile, quit that browser completely, then run
`cd backend && uv run python -m app.cookies brave "Profile 6"` (browser and profile name as in your browser).
Only YouTube/Google cookies are saved, to `data/youtube_cookies.txt` (private, git-ignored). Each request uses a
private copy, so YouTube's cookie rotation never damages the saved file. Don't use that account in a browser while
the tool runs.

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
