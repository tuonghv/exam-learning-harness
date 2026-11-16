# Phase 124 – P3-b refine hardening (TASK-124, REQ-0131)

Source: rows 114-F003, F006-F009 of work/TASK-113/handoff/design-ingest.md (traced, $0 repros). Only file:
src/exam_engine/ingest/refine.py. Designer waived: rows already designed; coordinator decisions below.

## Plan modes
Refine (page-image, paid) path only, used by both plan modes when `--refined` is chosen; no prompt or cache-key change.
A cached reply that the stricter validation now rejects is treated as a miss (refine.py `_ask` already does this) and
is re-asked once: bounded, only for prompt-violating replies.

## Design
- 124.1 F003 `validate_refined` (R:211-212, R:245-246): `figures` must be a list of strings (question, continuation
  and carry figures alike) -> otherwise the reply is invalid (`invalid_reply`, retried). Defence: `_native_tables`
  joins `str(f)` so it can never raise. Test: the repro -> validate returns an error; `_native_tables` no TypeError.
- 124.2 F006 `_native_tables` data-cell test (R:281, R:287): match a cell as a whole token (`\b` + re.escape, as the
  label test at R:293) instead of a substring. Test: repro -> table appended to q (figures gain it).
- 124.3 F007 label-less table (R:294-296): when the table has no labels, place it on the single question of that page
  whose figures mention a table (fold contains `bang` or `table`); zero or several candidates keep today's
  `native_table_unplaced` warning. Test: repro -> placed, no warning; two candidates -> warning stays.
- 124.4 F008 orphan advice (R:690-693): advise `add page(s) p-1` only when p > 1, kind is `no_owner` and p-1 is not in
  the selected pages; otherwise `check page p` (no page 0, no already-selected page). Test: repro -> no `page(s) 0`.
- 124.5 F009 `_why` (R:610, R:548-549): add code `order` when `_review` flags out-of-order questions in a window
  reply; `needs_review_why` carries it. Test: repro -> q14 `needs_review_why` contains `order`. Check metrics.py
  reason list (metrics.py:170) accepts the new code (add it there if reasons are enumerated).

## Verification ($0)
tests/unit/test_refine_hardening_124.py, one per item, each failing on HEAD; `--fast` NEW 0. Existing refine tests
must stay green; report any that pin old behaviour.
