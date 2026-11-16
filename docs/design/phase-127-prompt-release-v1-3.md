# Phase 127 – Prompt release v1.3.0 as the default (TASK-127, REQ-0134)

## Cause (traced from the approved DGNL English run, work/dgnl-text/run-English/calls)
5 of 25 answers failed the diacritics check: the retry reply (call 3) wrote unaccented Vietnamese. Neither the solve
nor the retry prompt holds the "full diacritics" rule: `config/engine.json` pins `prompt_channel` release /
`prompt_release` v1.0.0 (phase 9), and the rule (TASK-079) lives only in `prompts/dev`. v1.0.0 also lacks `lang/vi`
(Vietnamese variants), the group/sibling rule (TASK-055), the nearest-value rule (TASK-074) and the `missing_text`
decline bullet. The retry notes already carry the diacritics finding (solver.retry_prompt); no engine code change.

## Design
- 127.1 `python3 -I scripts/exam.py prompts release v1.3.0` (the phase-9 freeze: copy of dev + MANIFEST), then
  `prompts verify v1.3.0`. Releases are never overwritten; v1.0.0-v1.2.0 stay for old runs/compare.
- 127.2 `config/engine.json` `prompt_release` v1.0.0 -> v1.3.0 (channel stays `release`).
- 127.3 Tests that assert the default version (test_metrics etc.) follow the config or are updated.

## Plan modes
Every default `solve`, `cross-solve`, QA and retry uses v1.3.0. Solve cache keys include the prompt, so cached
replies of v1.0.0 runs are misses (one-time re-ask, paid only on `--real`). `--prompt-version v1.0.0` reproduces old runs.

## Verification
`--fast` NEW 0; `solve --dry-run` on a vi exam shows the rule; paid check approved (RAW-00346): the 25-question DGNL
2025 English file, default settings, expect 0 diacritics fails, accuracy vs the key (was 24/25).
