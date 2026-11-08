# Phase 92 - DHQG 2024 hybrid report pack (REQ-0094)

## Goal
Give the DHQG 2024 sample exam the same standard report pack as DGNL 2026, in the new report-run layout, at $0.

## Design
- 92.1 Source: the four stored plan runs of line t81, `plans/dhqg2024/t81/runs/<id>-{vietnamese,english,math,science}` (2026-11-07 run, moved by REQ-0098). Not merged: the corrected printed 64-67 from line t82 (REQ-0094 Q1 best: one run per pack); the pack's INDEX/run.json names the t81 plan runs, and a note says 64-67 were re-solved in line t82.
- 92.2 Command (existing, no code change): `python3 -I scripts/exam.py report-pack <the four plan dirs> --exam dhqg2024 --run t81` writing a new report run under `reports/dhqg2024/t81/run-<UTC stamp>/` via the run resolver; no `--key` (no official answers), so no score-vs-key; md -> pdf pairs (TASK-086), INDEX.md and run.json (plan runs linked by result_sha256).
- 92.3 Checks: `tools/check_report_pack.py` on the new run folder with its four plan dirs (keyless pack accepted), file counts per kind from `config/report_kinds.json`, 120 questions with text and options, zero raw `"level"` JSON lines, md count = pdf count, `report-index` and `run-list dhqg2024` show the new run beside the legacy t81 run.
- 92.4 Names: standard `dhqg2024_<subject>_<kind>_run-t81.<ext>`; the old `solutions.md` corresponds to kind `solution-report`.

## Plan modes
No impact on single-source or pipeline plans: a deterministic report built from stored results.

## Failure modes
A missing renderer stops the pack before writing (TASK-086). A keyless pack that the checker refuses is a defect to fix, not to bypass.

## Unit tests
None new (existing report-pack and checker tests cover the code); the evidence is the checker run and a recount.
