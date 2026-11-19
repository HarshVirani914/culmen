# SDD ledger — plan: docs/superpowers/plans/2026-11-19-shorts-clipper.md
Pre-flight: shared interfaces T2->T5, T3->T5, T4->T7, T6->T7 match plan signatures.
Ruling: project root is shorts-clipper/ (no extra clipper/ dir) — user's folder is already the project — none
Ruling: uv project (pyproject.toml) instead of requirements.txt — environment enforces uv — none
Task 1: complete (cd backend && uv run pytest → 1 passed; pytest pythonpath fix added)
Task 2: complete (uv run pytest tests/test_candidates.py → 6 passed)
