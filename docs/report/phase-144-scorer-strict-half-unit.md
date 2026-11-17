# Phase 144 – Scorer: strict half-unit tolerance, no decimal for fraction keys report (TASK-144, REQ-0151)

**Verdict: done.** User decision RAW-00360 (D1 strict, no decimals) applied.

## Results
- A numeric answer must differ from the key by strictly less than half a unit of the key's last digit: for key `5`,
  `5.49` is correct, `5.5` and `4.5` are wrong; `3.465` vs `3.46` and `1.85e-19` vs `1.8e-19` are wrong. Applies to
  the main compare and to keys with a note `(…)`.
- A decimal answer for a fraction key stays wrong (`4.67` vs `14/3`); exact fractions (`28/6`) stay correct. Pinned
  by a test (behaviour since TASK-138).
- 4 tests (3 fail on old code, 1 pins current behaviour); `--fast` KNOWN 4, NEW 0.
- Re-score of the 95 stored keyed answers old vs new: 0 flips; no published score changes.

## Spend
$0. One coder run.
