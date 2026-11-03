# Report phase 69: parsing accuracy apart from solving accuracy (TASK-069; REQ-0074)

Verdict: adopted. Brief: `tmp/Exam-Structure-Context.md` section 7. `metrics.structure_scores(exam, gold)` (pure) scores question extraction, boundary, hierarchy, instruction inheritance, shared-reference association and cross-page continuity; `run-stats board --structure-gold FILE --exam FILE` prints parsing accuracy beside solving accuracy with separate denominators. Without a gold file the board shows parse flags from `input/assembly.json` and splits wrong answers into parse-suspect (flagged question) and solver (unflagged); tokens per question is an estimate (bytes/4). Gold fixture: 11 synthetic cases (`tests/unit/fixtures/structure_gold.json`), each of the six metrics with a passing case and a labelled `known_miss`; known misses never count as regressions.

## Evidence (work/TASK-069/evidence/, not published)
1336 tests, only the 4 known baseline failures; independent recomputation of the six accuracies matches; output byte-identical without the new flags; 8/8 mutations killed (merged denominators, known_miss counted as failure, tokens unit, ignored flags).

## Limits
Gold is synthetic only; real runs have no gold, so they show flags only. The board's `solver` label means an unflagged wrong answer, not a proven solver error. The unit test T5 fails on a stale `known_miss` by design (update the label when the code improves). No `reference` gold case yet. 65.4 (section note) and 65.7 (restart-aware refs) stay unbuilt until a non-synthetic miss or a reviewed wrong answer justifies them.

User instructions honoured: RAW-00192.
