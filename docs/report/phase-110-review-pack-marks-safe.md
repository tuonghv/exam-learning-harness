# Phase 110 – Fix-C review pack report (TASK-110, REQ-0117)

**Verdict: adopted.** Review-triage bugs 111-F004, F005, F006, F007 fixed in `src/exam_engine/pipeline/review.py`.

## Results
- 110.1 a marked section with no number or a duplicate number is kept (routed to `.new.md` with
  `Q? / Qx unnumbered or duplicate heading`), never silently dropped on a re-run.
- 110.2 `review-apply` labels such a section `Q?` instead of raising TypeError.
- 110.3 an edited heading no longer produces a false "Answer changed"; a change line needs a known, different answer.
- 110.4 `S.old.md` backups are not listed as subjects.
- Tests: 11 `test_110_*` in tests/unit/test_review.py, 10 bite on the old code; --fast 2009 ran, NEW 0 (KNOWN 4).
- Oracle (observed by the coordinator) on a COPY of the user's real pack `review/dgnl-2026-sample`: parse,
  subject list and `review.apply` output identical old vs new; real files' md5 unchanged.

## What changed for the user
Marks you tick are now safe on a re-run even if a heading is edited or loses its number. The real pack has no
marks yet (all 120 blank), so nothing changes in it today.

## Spend
designer + coder + tester; no paid run.

## Needs your go
Fix-D (CLI: 107-F001 recipe overwrite, F002 run-stats exit 0, F008 --help exit 2) is next in the approved plan.
