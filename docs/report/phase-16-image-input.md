# Report: TASK-016 image input (REQ-0019, EPIC-005)

**Verdict: adopted on synthetic images; real `claude -p` image call not yet made.**

## What exists
- `ingest/adapters/image.py` (.png .jpg .jpeg .webp): stdlib magic and header parse (PNG, JPEG, WEBP VP8/VP8L/VP8X), extension-mismatch, truncated, empty errors; original bytes copied unchanged with sha256; > 5 MB resized via lazy Pillow into a referenced derived asset (else `missing_dependency`); one page, status `needs_review`, warning `image_only`; optional OCR (off by default, via PyMuPDF/tesseract) stored as extracted text, never replacing the image.
- `adapters/claude.py` `run_claude_images`: base64 image blocks on stdin as stream-json, tools off, empty cwd, no file paths sent; `run_claude` unchanged.
- Docs: `ingest-usage.md`, `ingest-setup.md`.

## Verification
387 unit tests OK; mutations (PNG magic, extension check, WEBP, VP8L, 5 MB limit) are caught. Verifier: AC1, AC2, AC4-AC6 verified; AC3 verified with a mock only.

## Limits (honest)
- D1: `--input-format stream-json` is paired with `--output-format json`; `claude --help` hints stream-json input may need stream-json output. Unverified until a paid image call; the fix would be small (parse the stream result).
- D2: `run_claude_images` has no caller yet; REQ-0021 (refine) is the first user.
- D3: no unit test for a missing asset.
- Math in images stays visual; no LaTeX yet (EPIC-006).

## Next
TASK-017: REQ-0021 refine (dry-run first; a real run needs your go).

User instructions honoured: auto your task, comment less, nothing run at cost.
