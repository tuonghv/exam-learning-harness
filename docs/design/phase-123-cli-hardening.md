# Phase 123 – P3-a CLI hardening (TASK-123, REQ-0130)

Source: rows 113-F004, F006-F010 of work/TASK-113/handoff/design-cli.md (traced with repros, batch-2 triage
docs/design/phase-113-review-triage-b2.md). Only file: src/exam_engine/cli.py. Designer waived: rows already designed.

## Plan modes
None of the solve paths change; run-stats, rebuild-reports and ingest argument checks only.

## Design (each: smallest change; usage errors use the file's `print("usage: ...") / return 2` style)
- 123.1 F004 `run-stats compare` (cli.py ~2000, ~2076): take each ref's `exam_sha256` from its history line when present;
  only when a ref has none, fall back to `file_sha256(a.exam)`. A mismatch then reports "different exam" as for refs
  without `--exam`. Test: two history lines with different exam_sha256 + `--exam EX` -> exit 2 "different exam" (old 0).
- 123.2 F006 `_write_recipe` (cli.py ~681-685): a sub-folder whose name fails `safe_id` is skipped with a one-line
  `note: skipped <name> (not a report exam id)` on stderr; exit unchanged. Test: `.ipynb_checkpoints` dir -> exit 0, recipe written.
- 123.3 F007 `ingest --boundary-trace` (cli.py ~1084): open the trace path inside the existing try / check the parent dir
  before ingest so an unwritable path is `ERROR: ...` exit 2, not a traceback. Test: `/nonexistent/t.txt` -> exit 2, no traceback.
- 123.4 F008 `run-stats trend --last` (cli.py ~2122, ~2374): `--last` < 1 is a usage error (exit 2). Test: `--last -3` -> 2 (old: 1 row, exit 0).
- 123.5 F009 `run-stats board --baseline DIR` (cli.py ~2206, ~2303): when a side's exam sha is None, the message is
  "exam sha unknown for <ref>; pass --exam" (exit 2 unchanged). Test: message text.
- 123.6 F010 `ingest` (cli.py ~1051-1056): `--questions` without `--refined`, or `--refined` without `--exam-out`, is a
  usage error (exit 2) before any work. Test: `--exam-out e.md --questions 1-2` -> 2 (old: 0, all questions written).

## Verification ($0)
New tests/unit/test_cli_hardening_123.py, one per item, each failing on HEAD; `--fast` NEW 0. If an existing test or
documented usage relies on an old behaviour (e.g. `--refined` alone), report it (main decides).
