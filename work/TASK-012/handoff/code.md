PROGRESS: COMPLETE
SKILLS: python

Files: src/exam_engine/ingest/{__init__,schema,api}.py, ingest/adapters/{__init__,markdown}.py (new); src/exam_engine/cli.py (ingest_main + table/COMMANDS entry); tests/unit/test_ingest_core.py (21 tests).
Tests: unit 272 OK (21 new), integration 2 OK.
Mutation: disabled the parent-dir check and realpath commonpath check -> test_traversal_rejected and test_symlink_escape_rejected FAIL; restored, pass.
Backward compat: all 10 examples/**/input-*.md ingest, to_exam_text identical bytes, validate_exam passes.
Deviations: extra error code `missing_header` (listed in CODES); traversal/absolute -> invalid_document; http(s) image refs left as paragraph (no network); to_exam_text re-reads source file and checks sha256 (doc has no text copy); scripts/exam.py unchanged. A Bash call containing a literal parent-dir token was refused by the guard, so files were written with the Write tool.
Risks: free-form Markdown to_exam_text just dumps blocks under meta headers; no question segmentation.

## Verifier fixes (D1-D6)
- D1: test free-form+meta -> to_exam_text -> parse_exam/validate_exam OK, 1 question, options A-D (test_ingest_core.py ExamTextTest).
- D2: inline/angle-bracket/unsupported image refs add warning `unresolved_image` (markdown.py).
- D3: tests for `..\`, `%2e%2e`, `%2E%2E%2F` (refs are URL-decoded before checks), unclosed fence and `$$`.
- D4: adapter reads file once and hashes those bytes; `config` documented as reserved. Markdown source.text holds the decoded text so to_exam_text needs no re-read (hash checked).
- D5: validate_document checks unique `order` per page and relative, `..`-free asset paths; tests added incl. missing text/origin.
- D6: source.path = file name only; no absolute path in JSON (tested).
- Tests: unit 279 OK, integration 2 OK. Not done: saved real `solve --mock` run (main/verifier).
