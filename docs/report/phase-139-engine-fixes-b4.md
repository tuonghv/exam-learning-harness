# Phase 139 – Engine image/adjudicate/retry fixes from review batch 4 report (TASK-139, REQ-0146)

**Verdict: done.** 4 batch-4 engine findings fixed (all BUG).

## Results
- A failed or malformed retry no longer triggers a second paid QA call on the unchanged answer, so an `agree` can no
  longer flip FAIL to PASS on it (136-F001).
- An adjudicated answer drops the replaced answer's review and gets fresh deterministic checks: a correct adjudicated
  answer is no longer FAIL `reviewer_disagrees` (136-F002).
- Image and adjudicated answers given as an option value (`12`) are mapped to the letter like solver answers
  (shared `solver.map_option`): no false `image_differs` and no extra adjudication call (136-F003).
- A marker-skipped question keeps its `missing_text (options cut)` reason after an image miss (136-F005).
- 4 tests (all fail on old code); no existing test changed; `--fast` KNOWN 4, NEW 0; ledger 4 rows fixed.

## Spend
$0. One coder run.
