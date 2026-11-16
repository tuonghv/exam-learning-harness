# Phase 127 – Prompt release v1.3.0 as the default report (TASK-127, REQ-0134)

**Verdict: done.** User decisions: fix the diacritics retry (RAW-00346), promote v1.3.0 (RAW-00347).

## Results
- Cause: `config/engine.json` pinned prompt release v1.0.0 (phase 9); the vi diacritics rule (TASK-079), the
  `lang/vi` prompts, the group/sibling rules (TASK-055), the nearest-value rule (TASK-074) and the `missing_text`
  decline wording lived only in `prompts/dev`, so no default run since 2026-10-29 used them.
- `prompts/releases/v1.3.0` = frozen copy of dev (verify ok); it is the default release. v1.0.0-v1.2.0 unchanged;
  `--prompt-version v1.0.0` reproduces old runs.
- Paid check (DGNL 2025 English, 25 questions, $0.29): 24/25 correct (unchanged), diacritics fails 0 (was 5).
- 6 test files follow the new default; golden prompt-code guards are pinned to v1.0.0. `--fast` KNOWN 4, NEW 0.

## Effects
Every default solve/QA/retry prompt changes, so solve-cache entries from v1.0.0 runs are misses (one-time re-ask on
`--real`).

## Open
`test_assembly_qa` Golden.test_48_golden_refined_real_doc (outside `--fast`) fails before and after this task: stale
TASK-048 golden after the ingest changes of TASK-114..126.

## Spend
$0.29 (approved check run). Roles waived (release command + config value).
