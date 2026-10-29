# Report: TASK-017 optional Claude refine stage (REQ-0021, EPIC-005)

**Verdict: built and mock-verified; real accuracy unmeasured (AC5 waits for the user's go).**

## What exists
- `scripts/exam.py ingest-refine <file|doc.json> --pages SPEC (--dry-run | --mock FILE | --real)`: never defaults to real. Dry run prints pages, call bound (<= 2 per page) and the cap, no call. Only pages that are selected and flagged are sent; detected answer-guide pages are refused unless `--allow-key-pages`.
- `ingest/refine.py`: page render, vision call through `run_claude_images` (base64, tools off, empty cwd), validation (schema, consecutive ids, no answer/solution fields), one retry, similarity vs OCR/native text with `needs_review` threshold, stored under `refined` as `origin: ai`; source blocks unchanged. Prompt `prompts/dev/ingest/refine.md` (transcribe only, no solving, no keys).

## Verification
423 unit tests OK; mutations (key guard, retry, similarity flag, render cap) are caught. Verifier: AC1-AC4 verified on mocks. `render_page` tests use a fake fitz.

## Limits
- AC5 not done: no real call yet. It needs your go (about 4 calls, cap $1.00) and settles the unverified stream-json flag pairing.
- Cost cap can overshoot by one page's retry; `--real` is guarded by the flag only.
- Similarity is a heuristic, not an accuracy claim.

## Next
Your go for the real run on trial pages 1-4; then EPIC-006 (REQ-0022 first).

User instructions honoured: auto your task, comment less, cost gate kept.
