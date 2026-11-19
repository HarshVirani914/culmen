#!/usr/bin/env bash
# One command to run the app: ./run.sh  ->  http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")"

command -v ffmpeg >/dev/null || { echo "ffmpeg not found. Install it: brew install ffmpeg"; exit 1; }

if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm install && npm run build)
fi

ENV_ARGS=()
[ -f .env ] && ENV_ARGS=(--env-file ../.env)

cd backend
uv sync
exec uv run uvicorn app.main:app --port 8000 "${ENV_ARGS[@]}"
