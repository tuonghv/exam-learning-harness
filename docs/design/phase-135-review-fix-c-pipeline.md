# Phase 135 – Review leftovers fix C: metrics, report_kinds, review pack (TASK-135, REQ-0142)

Source: re-triage work/TASK-131/handoff/design-ingest.md (rows 109-F003, F005, F006; 111-F001, F002, F008, F009).

## Plan modes
Reporting/metrics/review-pack only (run-stats, report INDEX, review-pack/review-apply); no solve, prompt or cache
change. Report numbers change only for the proxy label (109-F003) and the INDEX with_text count (111-F002).

## Design
- 135.1 109-F003 metrics classify: set `proxy=True` when a fixed/regressed id was QA-judged; `pool` ORs it; the
  verdict prints `better (proxy)` when basis is QA or proxy (no `mixed` basis: it would break `verdict`/`pool`).
- 135.2 109-F005 causes_text: skip rows without `primary`.
- 135.3 109-F006 backfill: unreadable/non-dict result.json -> skipped, loop continues.
- 135.4 111-F001 report_kinds supersede note: `sup.get("note") or ""` (both places).
- 135.5 111-F002 `_has_text`: break only after a run of >= 2 option letters; a single-letter run resets.
- 135.6 111-F008 review `_guard`: also prefix `QA: ` and `Answer changed:` lines of exam text.
- 135.7 111-F009 review `_check_name`: refuse reserved subject names (SUBJECT_SKIP, `.new`/`.old`) case-insensitively.

## Verification ($0)
tests/unit/test_review_fix_c_135.py, one test per id failing on old code; existing metrics/report/review tests
green; `--fast` NEW 0; 7 ledger rows fixed.
