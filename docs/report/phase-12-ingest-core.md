# Report: TASK-012 ingestion core (REQ-0016, EPIC-005)

**Verdict: adopted.** `ingest_document(path, config, meta)` returns a validated canonical document v1 or a structured `IngestError`; Markdown is the first adapter; `to_exam_text` bridges to the existing exam format; `solve` is unchanged.

## What exists
- Schema v1 and `validate_document` (versioned, status native_text|ocr|mixed|needs_review, blocks with origin source|extracted|normalized|ai, assets, warnings, unique ids and order, relative asset paths): `src/exam_engine/ingest/schema.py`.
- Adapter registry plus Markdown adapter (headings, lists, tables, code, math, images; local image refs safe inside the file folder: no `..`, absolute, symlink escape, `..\`, `%2e%2e`): `ingest/adapters/`.
- `ingest/api.py`: ingest, `to_exam_text` (exam-format Markdown passes through byte for byte; free-form needs `--meta` headers, else `missing_header`).
- CLI: `python3 -I scripts/exam.py ingest <file> [--out doc.json] [--exam-out exam.md] [--meta K=V]`.

## Verification
Suite 279 unit + 2 integration OK; all 10 examples round-trip identical; mutation of the path checks fails tests; verifier: AC1, AC3-AC5 verified. AC2 (its major defect) closed by a parse_exam + validate_exam test and a saved ingest then `solve --dry-run` run (`work/TASK-012/evidence/free-md-ingest-solve-dryrun.txt`); a full `solve --mock` run was not made.
Minor defects D2-D6 fixed (unresolved-image warning, extra traversal cases, single read and hash, order and path checks, file name only in `source.path`).

## Limits
No PDF, DOCX or image yet (REQ-0017/18/19). Free-form Markdown needs `--meta`. No question segmentation beyond the exam format. Inline images get a warning, not an asset.

## Next
REQ-0017 PDF adapter (needs `pip install pymupdf python-docx` by the user for real tests).
