# Shorts Clipper

Turn highlights from YouTube gaming streams into 1080x1920 Shorts.

Paste a YouTube link, the app finds the most reacted-to moments (chat spikes, audio peaks,
YouTube's "most replayed" graph, optional LLM ranking), you frame the gameplay and facecam
once per streamer, pick a layout, and render.

## Requirements
- ffmpeg (`brew install ffmpeg`)
- Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20+

## Run
```bash
cp .env.example .env   # optional: add your OpenAI-compatible LLM
./run.sh               # opens on http://localhost:8000
```

## LLM (optional)
Any OpenAI-compatible API. Set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` in `.env`.
Without it the app still works using the signals alone.

## Layouts
`stacked` (facecam on top), `facecam bubble`, `gameplay only` (blurred background), `facecam only`.

## Development
```bash
cd backend && uv run pytest          # backend tests
cd frontend && npx vitest run        # frontend tests
cd frontend && npm run dev           # dev UI on :5173, proxies /api to :8000
```

## Caution
Clipping other creators' streams can trigger copyright or reused-content problems on YouTube
(strikes, demonetization). Captions, commentary and the source-credit option help but don't
remove the risk. Only YouTube URLs are accepted.
