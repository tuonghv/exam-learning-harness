PROGRESS: COMPLETE
SKILLS: coding, token-efficiency, python
Files
- src/exam_engine/ingest/refine.py (new): pick_pages, check_key_pages, validate_refined, similarity, refine, render_page (lazy fitz), make_real_llm (only real call site, via claude.run_claude_images; stream_format error), mock_llm.
- src/exam_engine/cli.py: refine_main + `ingest-refine` command (mode gate like solve; exit 0/1/2/3; real needs source PDF next to .json, hash-checked).
- prompts/dev/ingest/refine.md (new; check-prompts OK 7 files; ingest/ not in contract so unchecked; will be copied by a future release).
- tests/unit/test_ingest_refine.py (24 tests, mock only; run_claude_images patched to fail if reached).
- docs/guide/ingest-usage.md: "Optional AI refine" section. toolkit-reference.md has no ingest rows, untouched.
Tests: full suite 411 OK (387 + 24). Real mode unreachable from tests.
Mutation: `if allow:` -> `if True:` in check_key_pages: 2 tests fail (test_key_pages_refused_unless_allowed, test_key_pages_exit_3); restored.
Notes/risks
- test_guards allows only reporter/claude.py to import subprocess: refine.py avoids it (runner=None default).
- no_question_numbering warning has no page, so it does not flag pages (design says "warnings with page"); OCR status and page warnings do.
- Real render_page and stream-json behaviour untested (real run is out of scope).
## Defects
None.
