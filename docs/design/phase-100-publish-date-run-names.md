# Phase 100: publish names files by the main run date id

Task: TASK-100 · REQ-0107 (RAW-00315)

## Goal
`publish EXAM --from LINE` without `--run` wrote `<exam>_all_<kind>_run-<LINE>` (e.g. `run-f`, `run-t81`) in a folder
named `run-YYYYMMDD-HHMMSS`. The user wants the date style in the file names too.

## Plan modes
No effect on single-source or pipeline plan files: only the run part of published report file names changes.

## Design
`cli.publish_main` (owner: src/exam_engine/cli.py): create the main run folder first, then
`run = a.run or os.path.basename(out)` (already `run-<id>`), passed to `report_pack.build_pack` as today.
`--run` still overrides. `report-pack` already defaults to the out-dir name. Docs: toolkit-reference `--run` default.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| bad `--run` | ValueError from report_kinds.name, half-built run removed (existing) | exit 2 + message |

## Unit tests
tests/unit/test_publish.py: a publish without `--run` writes files whose run part equals the folder name.

## Verification
Re-publish dgnl2026 (`--from f`) and dhqg2024 (`--from t81`), `tools/check_report_pack.py` passes, old main run deleted.
