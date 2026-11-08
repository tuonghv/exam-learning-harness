# Phase 97: small fixes (REQ-0104, TASK-097)

## Goal
Two leftovers from TASK-096, both reporting-only, no model call, no change to plans or report content.

## Fix 1: exam INDEX and run-level `superseded`
- Problem: `render_index` read `superseded` globs only from `run.json` of the folder being indexed and from the registry.
  The exam-level INDEX therefore listed 3 files of `dgnl2026/f/run-20261107-133501` and 4 of
  `dhqg2024/main/run-20261105-110545` as `unregistered`, although the run's own `run.json` says `superseded`.
- Change: `report_kinds.nested_superseded(folder, rel, cache)` walks the parent folders of a file, reads
  their `run.json` `superseded` list (cached) and matches each glob against the path inside that run folder.
  First match wins; the row becomes `superseded` with the run.json note. Registry/folder-level rules stay first.
- Side effect (intended, stated): all files of a run whose `run.json` says `glob: "*"` become `superseded`
  (dgnl2026 f/run-20261107-133501: 16 files, 13 of them were listed `standard` before).

## Fix 2: checker usage error
- Problem: passing an overlay plan dir as a PLAN_DIR gave 17 spurious failures.
- Change: `tools/check_report_pack.py` reads `run.json` overlays first; a PLAN_DIR equal to an overlay `dir` ends with
  exit 2 and one line naming the dir. Other inputs behave as before.

## Tests
`test_overlay.test_104_1_*` (exit 2, message, no FAIL rows), `test_report_kinds.test_104_2_*` (run.json glob applies,
stray file stays unregistered, totals). Gate `--full`.

## Verification
Recount the two INDEX files with grep/awk against the run.json globs; `report-index` of the two exam folders;
checker on the published DHQG run (60 checks, 0 failed) and with the overlay dir (exit 2); sha256 of `plans/` unchanged.

## Plan modes
No effect on single-source or pipeline plans: only `report-index` rendering and the report-pack checker's argument handling change; solve, ingest and plan files are untouched.
