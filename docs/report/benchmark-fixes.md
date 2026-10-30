# Report: benchmark check fixes (REQ-0009 AC4, TASK-021)

Measured on the same 15 `evals/inputs` items, prompts v1.2.0, sonnet. Before: `work/exam-runs/2026-10-30-v120` ($0.567). After: `work/exam-runs/2026-10-30-v120-fix` ($0.534).

| Item | Before | Change | After |
|---|---|---|---|
| math/004 (37/42) | FAIL, computed read "37" | `computed` reads fractions | PASS |
| math/005 (sqrt(2)) | FAIL, computed read "2" | `computed` reads sqrt | PASS |
| physics/005 (1.8e-19 J) | FAIL, computed + key | sci notation in `computed` and key match | PASS |
| english/004 (b-d-a-e-c) | FAIL, quote with "b:" label | label stripped before the verbatim test | PASS |
| physics/004 (9 điểm) | FAIL, key remark | key remark in (...) ignored | PASS |
| informatics/005 (62 host) | FAIL, key unit words | unit words contained in the other side accepted | PASS |
| physics/003 (B) | PASS | none (not touched) | FAIL: solver's evidence quote was not verbatim this run, answer B unchanged |

Totals: pass 6 -> 11, fail 6 -> 1, uncertain 3 -> 3 (literature, open). physics/003 is a run-to-run change of the model's quote, not caused by the fixes (the quote check only got looser); one run each, so it may flip again.

Guards: tests/unit/test_benchmark_fixes.py keeps wrong answers failing (36/42, sqrt(3), 1.8e-18 J, 5 m vs 5 s, 63 host, 10 vs 9). 474 unit tests OK, check-examples OK.
Limits: n=15, one run each, no accuracy claim; the unit rule accepts a bare or contained unit, so a key without a unit does not check units.

User instructions honoured: change cited the measured items and was re-measured on the same items; cost within the approved $0.60 rerun; solver prompts and output schema unchanged; keys never shown to the solver.
