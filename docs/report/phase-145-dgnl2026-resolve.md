# Phase 145 – Re-solve DGNL 2026 report (TASK-145, REQ-0091)

**Verdict: done.** Paid re-solve approved (RAW-00361): 112/120, $1.65; the published 113/120 run stays published.

## Results
- Already solved before the run: line f (published), sonnet, 2026-11-05, 113/120, $1.37.
- Re-solve on dev line `r4`, model `claude-sonnet-5-5`, cap $0.80/subject, current code (batch-4 fixes), same refined
  inputs (sha256 equal): Vietnamese $0.49, English $0.26, Math $0.34, Science $0.56 = **$1.65**, 16 calls.
- Score vs `input/dgnl/De-thi-minh-hoa-2026-Final.answer.txt`: **112/120**. Not correct: Vietnamese 21, 24;
  English 38; Math 63, 65, 66 (declined); Science 112, 120.
- Versus the published run: q43 fixed (WRONG -> correct), q21 and q120 lost (correct -> WRONG). Net -1: model noise
  on two hard items, not a code regression (no scorer verdict changed on stored answers, TASK-138/144 re-score).
- Cache: a second Math run made 0 calls, $0 (4 hits).
- Reports generated: 34 files under `reports/dgnl2026/r4/` (4 subject report runs x 6 files; full pack
  `run-r4pack`: solution report, public report, score summary, score-vs-key, answer table, INDEX).
- Not done: re-refine (the TASK-143 table-row fix only reaches the solve after a paid re-refine).

## Spend
$1.65 (approved).
