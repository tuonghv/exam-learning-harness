# Phase 138 – Scorer fixes from review batch 4 report (TASK-138, REQ-0145)

**Verdict: done.** 8 batch-4 scorer findings fixed (7 BUG, 1 IMPROVEMENT).

## Results
- Fraction keys compare exact values: `28/6` = `14/3`; a bare `14` is no longer correct (137-F001, HIGH; 4 eval keys).
  `4.67` for `14/3` stays wrong (open user question).
- A reply with a second value (`8 hoặc 9`, `8; 9`) no longer matches key `8` (137-F002).
- `19.975.000` reads as 19975000 (two or more groups only; `1.000` unchanged) (137-F003).
- `x = −3` with U+2212 matches `-3` (137-F004).
- An ordering key `b-d-a-e-c` is no longer counted as letter B in run-stats (137-F008).
- An `Open` answer is scored against a real key (`Open` vs `B` -> 0) and gap-fill `open` vs key `open` -> 1; only a
  missing or `Open (rubric)` key skips scoring (136-F004 + 137-F009, one change in `apply_key`).
- `exam.py score` reads legacy keys and marks a question without a final answer `manual` (137-F010).
- Integer half-unit tolerance (D1) unchanged: open user question.
- 8 tests (all fail on old code); `--fast` KNOWN 4, NEW 0; ledger 8 rows fixed.

Scores of earlier keyed runs can change for these answer shapes on the next report rebuild.

## Spend
$0. One coder run.
