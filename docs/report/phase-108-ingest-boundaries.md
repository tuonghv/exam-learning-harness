# Phase 108 – Fix-A ingest boundaries report (TASK-108, REQ-0115)

**Verdict: adopted.** Five review-triage ingest bugs fixed (108-F001, F002, F004, F005, F010).

## Results
- 108.1 a cut page reply with <4 options passes validation; refine no longer aborts (`invalid_reply`).
- 108.2 group intros `Câu 31-35:`, `câu 31 đến câu 35`, `and`/list forms are context, not a question (`_INTRO` reuses the GROUP_RE span; `_q_start`).
- 108.3 an empty `unreadable` question is kept.
- 108.4 `split_part` strips only heading-shaped lines; `Phần I của ...` stems keep their text.
- Tests: 8 new (tests/unit/test_ingest_triage_fixes.py), 5 bite on the old code; affected NEW 0, --fast NEW 0 (KNOWN 4 pre-existing).
- Real-data oracle (observed by the coordinator): old vs new `segment` on 22 example files = 0 changed;
  `split_part` on 21 stored refined DGNL stems = 0 changed. `test_generality_golden.py` pattern pin updated for 108.2.

## Spend
designer + coder (one resume after the usage limit) + tester; no paid run.

## What changed for the user
Exams with group intros or page-cut questions now ingest whole; nothing else changes. No prompt or cache-key change.

## Needs your go
Fix-B (Claude adapter: 110-F001 classify, 110-F002 JSON extract) is next in the approved plan.
