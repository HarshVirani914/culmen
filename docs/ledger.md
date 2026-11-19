# SDD ledger — plan: docs/superpowers/plans/2026-11-19-shorts-clipper.md
Pre-flight: shared interfaces T2->T5, T3->T5, T4->T7, T6->T7 match plan signatures.
Ruling: project root is shorts-clipper/ (no extra clipper/ dir) — user's folder is already the project — none
Ruling: uv project (pyproject.toml) instead of requirements.txt — environment enforces uv — none
Task 1: complete (cd backend && uv run pytest → 1 passed; pytest pythonpath fix added)
Task 2: complete (uv run pytest tests/test_candidates.py → 6 passed)
Task 3: complete (uv run pytest tests/test_signals.py → 9 passed; chat fetch named _fetch_chat not _fetch_chat_times)
Task 4: complete (uv run pytest tests/test_layouts.py tests/test_render.py → 19 passed, real ffmpeg 1080x1920 h264 for all 4 layouts)
Task 5: complete (uv run pytest → 40 passed)
Task 6: complete (uv run pytest tests/test_captions.py tests/test_llm.py → 6 passed; transcribe.py not unit-tested, needs whisper model, covered in T10 e2e)
Ruling: restrict URLs to youtube.com/youtu.be + yt-dlp allowed_extractors youtube — security review flagged SSRF via generic extractor — non-YouTube sources (e.g. Twitch) rejected until allowlist extended
Security fix: complete (uv run pytest → 58 passed)
Task 7: complete (uv run pytest → 67 passed; ruling: GET missing profile returns 200 null not 404 — avoids console 404 noise in UI)
Task 8: complete (npm run build OK; ruling: removed tsconfig baseUrl, TS7 dropped it)
Task 9: complete (vitest 5 passed, npm run build OK; no browser check yet, done in T10)
Task 10 (partial): serve + run.sh + README committed, pytest 71 passed; e2e pending
Ruling: ffmpeg picked via FFMPEG_BIN or first build with libass (ffmpeg-full is installed, keg-only) — default brew ffmpeg lacks the ass filter — captions/credit return 422 and UI disables them if none found
Found by e2e: ass filter missing in default ffmpeg; fixed with real-render tests (77 backend tests passing)
Task 10: complete (backend pytest 78, vitest 5; real e2e on public video: analyze OK, 4 layouts 1080x1920 h264 OK, Whisper captions+credit OK). Ruling: transcribe feeds ffmpeg-decoded float32 to faster-whisper — installed PyAV rejects metadata_errors
