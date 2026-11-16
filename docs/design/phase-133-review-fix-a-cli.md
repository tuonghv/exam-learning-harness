# Phase 133 – Review leftovers fix A: cli.py + claude adapter (TASK-133, REQ-0140)

Source: re-triage work/TASK-131/handoff/design-cli.md (current lines, minimal fixes, repros);
docs/design/phase-131-review-leftovers-b1.md. All 9 rows IMPROVEMENT; 107-F003/F004 P2.

## Plan modes
CLI exit paths and the Claude adapter's decoding/classification only. solve: a report-build failure after a finished
run becomes a WARN, the run's exit code and summary stay. refine: `--out` dir checked before any paid call. No
prompt, cache key, result schema or engine logic change.

## Design (one item per id; fixes as in the handoff table)
- 133.1 107-F003 cli `_build_default_report` call in its own try: OSError/ValueError -> `WARN: report not built`.
- 133.2 107-F004 refine: `--out` parent dir must exist before the first call (exit 2); trace write guarded (WARN).
- 133.3 107-F005 ingest `--refined`: a doc without a `refined` dict -> ValueError -> exit 2.
- 133.4 107-F006 benchmark: `benchmark.discover` OSError -> exit 2.
- 133.5 107-F007 lessons: output writes inside try/except OSError -> exit 2 (also the default path next to
  `--summary`, D1); a non-dict summary -> exit 2 (D2, check genexam.lessons).
- 133.6 107-F009 run-stats backfill: `WARN: not a result dir: <ref>` per dropped ref; exit 2 only when no ref is valid
  (the review's exit-2-on-any-skip is NOT adopted: it breaks glob backfill).
- 133.7 107-F010 run-list: foreign plan.json via `runlayout._jload` (None on a bad file).
- 133.8 110-F004 adapter runner call: `encoding="utf-8", errors="replace"`.
- 133.9 110-F005 adapter: exit 0 with non-empty unparseable stdout -> `_bad("other", "unparseable output: ...")`.

## Verification ($0)
tests/unit/test_review_fix_a_133.py: one test per id from the handoff repros, each failing on old code; existing
cli/claude tests green; `--fast` NEW 0; ledger rows of the 9 ids `fixed TASK-133`.
