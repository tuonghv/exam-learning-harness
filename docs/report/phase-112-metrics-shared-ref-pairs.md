# Phase 112 – Fix-E metrics report (TASK-112, REQ-0119)

**Verdict: adopted** (user decision RAW-00337). Review-triage bugs 109-F002 and 109-F004 fixed in
`src/exam_engine/pipeline/metrics.py`.

## Results
- 112.1 `shared_ref`: the expected linked set is the same-label gold ids that were extracted; a missing sibling is
  counted only by boundary/coverage, not twice. Supersedes the shared_ref row of phase-69. Real unlinks and
  overlinks among extracted ids still fail.
- 112.2 `board_delta` n = number of question ids in both runs (was: run B's n).
- Tests: t11, test_board_delta_n_pairs, test_board_delta_n_disjoint bite on old code; t12 + t4 guard AC2.
  --fast 2024 ran, NEW 0 (KNOWN 4).
- Oracle (observed by the coordinator): `structure_scores` on all 11 gold cases identical old vs new; no stored
  `shared_ref` values in plans/ or reports/, so history has no mixed formula.

## Spend
designer + coder; tester waived (two one-line edits); no paid run.

## Review-triage plan status
Fix-A..E done (TASK-108..112): 16 of 17 BUGs fixed. Left: 111-F002 (cosmetic INDEX count) and the 21
IMPROVEMENTs (P3, optional), plus an optional second review batch for cli.py and ingest/.
