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
Final review: self-review (no fresh reviewer dispatched). Final: hardening — job/render ids validated (test passed before change too: defence in depth, no RED). Suite 82 backend + 5 frontend.
Range feature: complete (backend 91 passed, vitest 8 passed). Guard: sections >3h refused before download (24h stream nearly downloaded whole)
Real-stream test (a streamer 24h live replay, range 2:00:00-2:30:00): ranged download returned empty file; works on normal video. Added clear error. Needs a normal-length replay to test LLM end to end.
Live T1: complete (pytest 117 passed; also fixed youtu.be short links being blocked by extractor allowlist)
Live T2: complete (render tests 9 passed)
Live T3: complete (pytest tests/test_live_detector.py → 9 passed)
Live T4: complete (buffer+storage tests 9 passed). Ruling: enforce_cap(root, ids oldest-first, cap_bytes, keep) so it only touches moment jobs, never normal replay jobs
Live T5: complete (recorder tests 6 passed, real ffmpeg with local file as fake live source)
Live T6: complete (live signals + chat parser tests 12 passed). Twitch IRC client, YouTube/Kick chat clients are best-effort and unverified until T10
Live T7: complete (full pytest green incl. 7 live API tests with real recorder on a local source). Ruling: moments created via store.create + update (no create_ready helper); 'used' marker file exempts opened/rendered moments from the cap
Live T8: complete (live API tests 11 passed incl. titles; LLM fallback never overwrites title)
Live T9: complete (vitest 11 passed, npm build OK, backend live API 12 passed; UI not yet checked against a real live stream)
Live T10 partial: Twitch live (a Twitch streamer, 1080p): recording OK, buffer rolled (~1 MB/s), IRC chat OK (451 msgs/4min), clean stop. YouTube live (a streamer): recording OK; chat was broken (bare UA got stub page) FIXED, 1080 msgs/75s. English replay (an uploaded VOD): ranking 10 clips in 67s (was ~20 min). Not yet seen: a real moment from a live stream; Kick (no live channel found); Twitch ads
Range UX: replaced free-text range with hh:mm:ss fields; backend rejects ranges <20 s (user typed 1 to 2 meaning hours, got 1 s); replay find_candidates now guarantees >=3 non-overlapping moments (174 backend + 17 frontend tests)
Sensitivity + cookies: live sensitivity presets (low/normal/high) in detector, API and Live tab; post_live replays refuse ranged download with a wait message; optional YouTube/Google-only cookie file (python -m app.cookies <browser> <profile>), wired into download, chat and recorder yt-dlp calls. 187 backend + 17 frontend tests. NOT yet exported any cookies: waiting for user to name the throwaway profile. Cut problem root cause (yt-dlp #9968): replays of just-ended streams are 'post-live manifestless'; wait hours
Fast section download (app/sections.py): sidx index + parallel chunked ranges + local join. Real: 60 s of an uploaded VOD in 14 s; 5 min 1080p60 of 9h45m 9h45m VOD in 34 s (old path ~25 min for 30 min). Cookies: each yt-dlp call uses a private copy (rotation wrote back bad cookies and broke the saved file). long-video analysis 1:00-1:30 completed earlier via slow path: 10 moments with LLM titles. 200 backend tests.
Facecam off-centre bug: not a render bug; sample frame (10% into section) showed overlay at a different place than at the chosen moment (a streamer overlay y 0.34 vs 0.44). Fix: frame endpoint ?t=, frame step now after moment pick with scrubber. Library: save finished renders to data/library (copy), list/play/rename/download/delete; Library tab. 209 backend + 17 frontend tests. NOTE saved profile for a streamer has a facecam box from the wrong scene: re-frame and Save again.
