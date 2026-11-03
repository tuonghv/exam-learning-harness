# Phase 66 - Keyed regression set (TASK-066)
Task: TASK-066 (REQ-0072) · Status: designed. Full design: `docs/design/phase-63-engine-scoreboard.md` item 63.6; statistics: `docs/design/phase-64-eval-stats-robustness.md` (tiers, `source=regset` = official tier).

## Goal
After an engine change, re-score a fixed keyed set with `benchmark --set FILE --history F` and append `source=regset` history lines so `run-stats board` compares quality on keyed data, per exam kind, with an official tier that exploratory runs cannot change.

## Constraints
Keys reach only the scorer (cfg["key"]); the set file lists ids and paths, never key text; stdlib only; defaults unchanged (no `--set` = old `discover()`).

## Generality
No exam-specific literal: the set is data (`evals/regset.json`, git-ignored, `v:1`, items `{id,input,key,key_basis}`); kinds come from the exam header; `key_basis` separates `official` from `generated: ...` keys (a kind with only generated keys never claims "official").

## Plan modes
Benchmark path only; solve/cross-solve unchanged. Mock mode proves plumbing at $0; real mode is the coordinator's paid run.

## Design
- 66.1 (= 63.6) `--set` loads the file, validates it (bad file fails naming it), runs each item with its key, appends one history line per item (`source=regset`, `set_id`, `key_basis`, git, prompt_info; fixes D4).
- 66.2 board labels generated-key kinds `key (generated)`; official needs `key_basis: official`.
- 66.3 skipped item counts as skipped, not as a regression (benchmark G9, D8 of phase 64): a pass drop is only counted for items that ran in both runs.
- 66.4 regset content: committed `evals/inputs` + `evals/keys` pairs (human keys) plus 2 items from each generated set (math, english, vietnamese), fixed; paths relative to the repo.

## Unit tests
Synthetic set with 2 kinds and mock replies: history lines carry `source=regset`; bad set file fails by name; a skipped item is not a regression; the key text never appears in prompts or in the history.

## Verification
Free: unit suite, `benchmark --set ... --mock`. Paid (coordinator, cap 1.00 USD): one real run, then a second run at the same commit for the noise band; board output recorded.

## Failure modes
Missing input or key file: item reported `missing`, run continues; budget reached: remaining items `skipped (budget)`; mixed key bases in one kind: board prints both labels.

## Decisions
Generated keys stay labelled; the official tier needs human keys; the set is never re-generated (fixed ids).

## Out of scope
New exam generation; changing the scorer; threshold tuning.
