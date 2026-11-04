# Report phase 75: discriminating confidence tier (TASK-075; REQ-0079)

Verdict: built and measured; the result is a hopeful signal, not a proven one. On DGNL every answer is UNCERTAIN (PASS needs an independent check, and a multiple-choice letter has none), so right and wrong answers looked the same. The PASS bar is unchanged; a separate, default-off `confidence` tier is added (`--confidence`, `--second-sample`).

## What was added
- Free signals (`--confidence`): option-distance for value answers, existing signals (malformed first round, retries, reviewer disagreement, image differs, solver uncertainty level) and a conservative structural check for an alternative reading the solver itself names (REQ-0082); a `format` failure whose value maps to exactly one option is not a warning.
- Second sample (`--second-sample`): re-solve ids with no independent check and doubtful ids with rotated options and reversed question order, batches of 15, compare in the original letters; agree gives `likely_ok`, differ gives `likely_wrong`; ids with a stem that names an option letter, "all or none of the above" options or a dependent stem are left out (`permutation_unsafe`); a cost or call stop leaves `second_skipped`, never `second_differs`; the second reply never changes the first answer or status.
- Metrics: `by_confidence` with Wilson intervals.

## Measured
- Free signals on the scored 2026 run 3: they caught 0 of the 4 real wrong answers (Science 112 is a rate-limit error, not a model error) and gave 7 false alarms: they do not separate.
- Paid second sample on Math and Vietnamese (2026, 1.11 USD, answers used for scoring only): 58 answered, 53 correct (91.4 percent [81.4, 96.3]); likely_ok 46 of 47 correct (97.9 percent [88.9, 99.6]); likely_wrong 3 with 1 wrong; 4 of the 5 wrong answers sit outside likely_ok, 1 of 5 is flagged likely_wrong.

## Limits
About 5 wrong answers against the about 20 a proof needs; the intervals overlap; the Math 65 wrong answer may be a key oddity; the older Vietnamese exam file gave 5 declines. The second proof (English, Science) was skipped on purpose: the 2025 sample (REQ-0081) will be pooled at no extra cost. Default-off output is byte-identical to the commit before the task (tester diff).

User instructions honoured: RAW-00188, RAW-00197.
