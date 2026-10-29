# Phase 15: DOCX adapter, ten-case spec tests, usage docs (REQ-0018, TASK-015; EPIC-005)

## Goal
`.docx` ingests into the same canonical document as PDF/Markdown; the ten cases of `tmp/input-exam-format.md` section 8 are covered by synthetic tests; usage docs list limits and risks. Free, local, no Claude call.

## Code
- `ingest/adapters/docx.py` `ingest(path, config)` (same signature as pdf.py; registered for `.docx` in `adapters/__init__.py`). Library `docx` via `optional.load("docx", "python-docx")`. Errors: not a zip / bad package -> `corrupt`; empty -> `empty`; password-protected (OLE header) -> `encrypted`; missing lib -> `missing_dependency`.
- Walk the body in order (`doc.element.body` children): paragraph -> block `paragraph`, style `Heading N`/`Title` -> `heading` with `level`; list styles -> `list_item`; table -> one `table` block (rows joined by `|`, cells by ` | `), merged cells deduped; inline image (`blip` rel) -> asset saved under `--assets` (name `docx-img-NNN.ext`, bytes unchanged, sha256) plus `image` block with `asset`; no image folder -> block `image` with warning `asset_not_saved`. Every block `origin: source`, one logical page (`n=1`, no bbox), `status native_text`, `extraction.method "python-docx"`.
- Text/OMML math: `m:oMath` text is kept as plain text in the paragraph with warning `math_possible` (page-level), never dropped; headers/footers, text boxes, footnotes are not read -> warning `unsupported_content` when present.
- Segmentation via `segment`; Markdown-style `Câu N` / `Question N` rules reused unchanged.
- Original file is only read; `source.sha256` of the bytes.

## Tests ($0, synthetic docx built with python-docx; skip with reason if lib absent)
`tests/unit/test_ingest_docx.py` for DOCX behaviour (headings, paragraph, table, image + bytes, math warning, corrupt, empty, non-zip, Vietnamese NFC, questions -> exam text, key-leak guard still applies via `parts`). `tests/unit/test_ingest_spec.py`: one test per spec section 8 case (digital PDF, scanned PDF (skip w/o tesseract), Vietnamese, math, table+diagram, multi-column, DOCX, Markdown, invalid input, backward compatibility: an exam-format `.md` still passes byte for byte and `solve --dry-run` works), referencing existing fixtures/helpers where they exist. Mutation: break heading level -> a test fails.

## Docs
`docs/guide/ingest-usage.md`: how to ingest PDF/DOCX/Markdown, `--pages`, `ingest-inspect`, key guard, OCR, exit/errors, limitations and unresolved extraction risks (math as text, OCR garbling, no header/footer, heuristic key detection). `ingest-setup.md` already covers setup (AC3b); add a link.

## Open questions
None (REQ-0018 has none).
