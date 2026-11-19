# Contributing

Thanks for helping improve Shorts Clipper.

## Setup
```bash
git clone <this repo> && cd shorts-clipper
./run.sh                          # builds the UI, installs the backend, serves http://localhost:8000
```
You need ffmpeg (`brew install ffmpeg-full` for captions), Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node 20+.

## Tests
```bash
cd backend && uv run pytest       # backend (about 2 minutes; some tests run real ffmpeg)
cd frontend && npx vitest run     # frontend helpers
cd frontend && npm run build      # type-checks the UI
```
Write the failing test first. Pure logic (detector, buffer, section planner, layouts, parsers) lives in small modules
with unit tests; anything that touches ffmpeg or a network is covered with local fixtures (a local HTTP server, a local
file standing in for a live stream) rather than real services.

## Guidelines
- Keep modules small and single-purpose (see "Project layout" in the README).
- Don't commit anything from `data/` or `.env`. Never commit cookies or API keys.
- Platform code that can't be unit tested (live chat clients) should fail soft: a missing signal must never crash
  a session, it just changes what the detector uses.
- If you change detection thresholds, say what stream you tested on and what you saw.
- Be careful with other people's content in screenshots and test fixtures: use videos you have the rights to.

## Reporting problems
Include the video platform, whether it was a replay or live, the time range, and the relevant server log lines
(remove any URLs with tokens).
