# Phase 12: ingestion core (REQ-0016, TASK-012; EPIC-005)

## Goal
One boundary `ingest_document(path, config, meta)` -> validated canonical document or structured error, then `to_exam_text(doc)` -> the existing exam file text, so `solve` is unchanged. Core and Markdown adapter are stdlib only. Spec: `tmp/input-exam-format.md` (read-only). PDF, DOCX and image adapters (REQ-0017/18/19) plug into the same registry later.

## Current input contract (documented here)
`solve` reads an exam `.md` (`parser.parse_exam`): header lines (`Subject:`, `Level:`, `Language:` ...), `## Instructions`, optional `## Passage`, `## Question N` with options `A.`-`D.`. `validate_exam` checks it. Existing files stay valid and are passed through byte for byte.

## Canonical document v1 (JSON dict, `schema_version: "1"`)
- `source`: `{path, name, format, sha256, size}` (original is never modified).
- `status`: `native_text | ocr | mixed | needs_review` (how it was extracted, never a correctness claim); `extraction`: `{method, tool}`.
- `meta`: exam header fields (Subject, Language ...) from the file or the caller's `meta`.
- `pages`: `[{n, width, height, blocks:[{id, order, type, text, level, bbox, origin, asset}]}]`; `type` = heading|paragraph|list|table|code|math|image; `origin` = source|extracted|normalized|ai (ai content is never written over source text).
- `assets`: `[{id, path, mime, sha256, page, bbox}]`; `questions` (optional): `[{id, text, options}]` only when reliable; `warnings`: `[{level, code, message, page}]`.
Markdown has one logical page; blocks keep file order.

## Code (new package `src/exam_engine/ingest/`)
- `schema.py`: `SCHEMA_VERSION`, `validate_document(doc) -> list[str]` (reuse `core/schema.py` validator style), `IngestError(code, message)` with codes `unsupported_format, empty, decode, missing_asset, missing_dependency, invalid_document, corrupt`.
- `adapters/__init__.py`: registry by extension `{".md": markdown}` and `register(ext, fn)`; each adapter is `fn(path, config) -> doc`; lazy imports raise `missing_dependency` with the pip command.
- `adapters/markdown.py`: UTF-8 read, split into heading, list, table, fenced code, math (`$$`), image refs; local image refs resolve only inside the file's folder (no `..`, no absolute path, no symlink escape); a missing asset is an error with the name, never dropped.
- `api.py`: `ingest_document(path, config=None, meta=None)` (pick adapter, run, add source hash, validate) -> doc; raises `IngestError`. `to_exam_text(doc)`: a Markdown source already in exam format returns the source text unchanged; otherwise builds headers from `meta` + sections, error `missing_header` listing absent required fields. No subject logic, no prompt, no Claude call.
- CLI: `scripts/exam.py ingest <file> [--out doc.json] [--meta K=V ...] [--exam-out exam.md]`; `solve` stays as is (a later step lets it take any supported file through `to_exam_text`; minimal change, tested for backward compatibility).

## Tests ($0, no external call)
Schema accepts a good doc and rejects: missing version, bad status, duplicate block id, asset not in assets. Markdown: headings/lists/table/code/math/image refs; Vietnamese diacritics intact; traversal and absolute image path rejected; missing asset error; empty file, invalid UTF-8, unsupported extension -> structured errors. Backward compat: every `examples/**/input-*.md` ingests, `to_exam_text` returns identical bytes, `validate_exam` passes. Mutation: break the traversal check, the test must fail.

## Limits
No PDF/DOCX/image here. Free-form Markdown needs `--meta` for the exam headers. No question segmentation beyond the exam format.

## Open questions
None: REQ-0016 Q1-Q2 accepted (RAW-00050).
