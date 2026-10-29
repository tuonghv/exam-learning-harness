# Phase 16: image input (REQ-0019, TASK-016; EPIC-005)

## Goal
PNG/JPG/JPEG/WEBP files ingest into the canonical document as one page that is an image asset; the image can later be sent to `claude -p` (base64, tools off, empty cwd). Ingestion is free; no Claude call here.

## Code
- `ingest/adapters/image.py` `ingest(path, config)`, registered for `.png .jpg .jpeg .webp`. Stdlib header parse: magic bytes (PNG `\x89PNG\r\n\x1a\n`, JPEG `\xff\xd8\xff`, WEBP `RIFF....WEBP`) -> format, width/height (PNG IHDR, JPEG SOF scan, WEBP VP8/VP8L/VP8X). Extension must match magic (`format_mismatch`), unreadable/truncated -> `corrupt`, empty -> `empty`, > `max_image_bytes` (default 5 MB) -> resize via lazy PIL (`optional.load("PIL","pillow")`) into `--assets` as a referenced derived asset (`origin: normalized`, original untouched, both listed); without PIL -> `IngestError("missing_dependency")` for oversized only, never a silent drop. Small images untouched. Document: one page `n=1` with width/height, one block `type: image`, `asset` = original copy under `--assets` (bytes unchanged, sha256) or source ref; `status needs_review` with warning `image_only` (no text unless OCR); `extraction.method "image"`.
- Optional OCR (`--ocr on`, default off): tesseract text as `origin: extracted` block after the image, never replacing it (reuse pdf.py OCR helpers `pick_ocr_language`; if tesseract missing -> warning `ocr_unavailable`).
- `adapters/claude.py`: `run_claude_images(text, images, *, model, timeout_s, runner, cwd)`: same argv plus `--input-format stream-json`, stdin one JSON line `{"type":"user","message":{"role":"user","content":[{"type":"image","source":{"type":"base64","media_type":...,"data":...}},...,{"type":"text","text":...}]}}`; same cwd/tools isolation and result handling (reuse `_bad`, classification). Images validated (type, size) before send; no file paths ever sent.
- `to_exam_text` of an image-only document -> `IngestError("no_text")` explaining that the image goes to the solver as a visual (refine/solve with images arrive in REQ-0021); no guess.
- CLI: `ingest photo.png [--assets DIR --out --ocr on|off]` through the existing registry; `ingest-inspect` works unchanged.

## Tests ($0)
Synthetic images generated with stdlib (zlib PNG writer) and PIL if present (JPEG/WEBP, skip otherwise): each format ingests, original bytes unchanged, sha/size/dims; truncated, wrong extension, empty, text file named .png -> structured errors; oversize with PIL -> derived asset listed, without PIL (mock `optional.load`) -> missing_dependency; OCR off by default; mock-runner test for `run_claude_images`: argv has stream-json, stdin is one JSON line with image block and base64, cwd is passed, no key text, tools off; unsupported media type reported. Mutation: break magic check -> failure.

## Open questions
None (REQ-0019 Q1-Q2 accepted).
