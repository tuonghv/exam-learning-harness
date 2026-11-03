# Report phase 66: keyed regression set (TASK-066; REQ-0072, RAW-00188)

Verdict: adopted, and the first real baseline is recorded. `benchmark --set FILE --history F` scores a fixed keyed set and appends one `source=regset` history line per item (`set_id`, `key_basis`, git, prompt info). The board splits tiers by key basis: `official` only for human keys, `generated` (label `key (generated)`) for model-made keys, `exploratory` otherwise, so a kind never mixes the two. A skipped item is not a regression. Without `--set` all output is byte-identical. The set file lists paths, never key text (leak check: none). Tracked template: `evals/regset.example.json`; the working copy `evals/regset.json` is git-ignored.

## Real baseline (two paid runs, same commit, 1.20 USD in total, RAW-00186)
18 items: pass 14, fail 1, uncertain 3, 0.607 and 0.596 USD. All 18 items give the same verdict in both runs; answer wording differs on 4 items only in bracketed notes (noise band on verdicts: zero). Official rows (human keys): English 3/3, Physics 3/3, Mathematics 2/3 (95% CI 21%-94%), Literature unmeasured (open tasks have no auto key). Model-keyed rows: English, Mathematics, Vietnamese 2/2 each.

## Findings
- math/005 scores FAIL in both runs although the value is right: the engine answers `sqrt(2) (approx 1.4142)` and the key `sqrt(2)` does not match. A note turns a correct answer into a failure; this is REQ-0075 (the board counted it as a silent wrong answer, so the Mathematics figure is understated).
- The three informatics items cannot run: there is no `prompts/releases/v1.0.0/subjects/informatics.md`. They were removed from the set; informatics is unsupported by the engine.

## Evidence (work/TASK-066/evidence/, not published)
1294 tests, only baseline failures; 7/7 mutations killed; mock end to end wrote the history lines; paid runs in `paid-regset-runs.txt`.

## Limits
3 items per official kind and one commit: this is a baseline for later changes, not an accuracy claim. Generated keys are model-made. The informatics subject is unsupported.

User instructions honoured: RAW-00186, RAW-00188.
