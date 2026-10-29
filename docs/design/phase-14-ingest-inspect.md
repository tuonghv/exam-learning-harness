# Phase 14: ingest-inspect, answer-guide detection, --pages, key guard (REQ-0020, TASK-014; EPIC-005)

## Goal
A local, free (no Claude call) way to read what ingestion produced and to keep an answer guide away from the solver. Motivated by the trial on `input/exam/math/math_12_graduation_2026_001.pdf`: pages 1-4 are the scanned exam, pages 5-12 an AI-written solution guide in the same file.

## Code (`src/exam_engine/ingest/`)
- `parts.py`: `find_parts(doc) -> [{kind: "exam"|"answer_key", pages:[first,last]}]`. A page starts an answer key when one of its first 6 blocks matches (fold-insensitive, via `utils.text.fold`) `huong dan giai|dap an|loi giai|answer key|solutions?|marking scheme`; every later page stays in the key until the end (a key is never followed by exam pages in the formats we see). `select_pages(doc, spec) -> doc'`: spec `1-4`, `1,3,5-6`; keeps `n` of the original pages, filters assets and blocks, re-runs `segment`, adds warning `pages_selected`, recomputes `parts`; bad spec or page out of range -> `IngestError("invalid_pages")`.
- `inspect.py`: `suspicious(doc) -> [{page, block, code, detail}]`: `split_formula` (block with >=6 lines of <=2 chars), `option_without_text` (`^[A-D]\.\s*[-—.]?$`), `numbering_gap` (exam part only), `stray_chars` (>3% not letters/digits/punct/space), plus the adapter warnings. `report(doc) -> str` Markdown: summary header (source, status, pages, per-page status, counts, parts, answer key notice, questions found), then per page the blocks (`[type]`, origin, text or asset+bbox), warnings and suspicious spots; ends with "heuristics, not proof of correctness".
- `schema.py`: optional top-level `parts` validated. `api.py`: `ingest_document` computes `parts` for every document and applies `config["pages"]`; `to_exam_text` raises `IngestError("answer_key_present", ...)` when the document still contains answer_key pages, unless `config["allow_key_pages"]`.
- CLI: `ingest --pages SPEC --allow-key-pages`; new `ingest-inspect <doc.json|file> [--out report.md] [--pages SPEC]` (a `.json` argument is loaded and validated, anything else is ingested first). Read-only: source and document are never altered.

## Tests ($0)
Synthetic PDFs built with fitz (skip if absent): exam pages + guide pages -> parts detected, `to_exam_text` refuses, `--pages` exam range passes, `--allow-key-pages` passes; page spec parsing and errors; suspicious detection on crafted blocks (split formula, empty option, gap); report contains header, notice, warnings and the disclaimer; document unchanged after inspect (hash/dict equality). Markdown/exam files: no parts, backward compatible. Mutation: disable the guard -> a test fails.

## Limits
Guide detection is by heading words (vi/en); an unlabelled key is not found. No answer-text comparison.

## Open questions
None: REQ-0020 Q1-Q2 accepted (RAW-00061).
