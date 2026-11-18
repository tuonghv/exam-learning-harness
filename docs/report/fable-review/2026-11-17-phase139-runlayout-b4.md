<!-- fable-status -->
> **Status (2026-11-18):** 3 finding(s): 3 fixed (TASK-140). Nothing open.
>
> **Action rule (RAW-00368):** check every finding against the code. A true positive is FIXED through a task; a warning or a note alone does not close it. A false positive is recorded with its reason in `docs/review/findings.tsv` and ignored. Update the Status line at each task transition.
<!-- /fable-status -->

# Phase 139 – Code review batch 4: runlayout.py

Scope: src/exam_engine/pipeline/runlayout.py (all 736 lines; callers in cli.py, planrun.py, report_pack.py read only to prove or drop findings)

## Findings

### F001 – [MEDIUM] --out into a no-line run folder of a protected root skips the publish guard

- File: src/exam_engine/pipeline/runlayout.py
- Lines: 111-113
- Type: BUG
- Trigger: normal input
- Reached via: `exam report PLAN --out DIR` (cli.py:473), `solve --out` (cli.py:117), `report-pack --out` (cli.py:537) -> require_publish(None, ...)
- Issue: with line None the line is taken from `parts[1]`, which for the layouts without a line is the run folder (`run-<id>`) or `runs`, not a line. It is then judged a dev line.
- Case: `exam report PLAN --out reports/ex/run-20260101-000000` (no --publish) passes and overwrites a published report run; `solve --out plans/ex/runs/<id>` likewise.
- Fix: after line 112, set `line = None` when `parts[1] == RUNS` or `parts[1].startswith(REPORT_PREFIX)`.
- Fix risk: none found; tests/unit/test_publish.py:127-132 only use `<exam>`, `<exam>/main/run-a`, `<exam>/v3/run-a`, which keep today's result.
- Test: require_publish(None, False, "x", join(reports, "ex", "run-a")) must raise PublishRequired; today returns None.

### F002 – [LOW] Line or exam named `reports` puts the report manifest inside the reports tree

- File: src/exam_engine/pipeline/runlayout.py
- Lines: 79, 488-490
- Type: BUG
- Trigger: normal input
- Reached via: `exam solve --line reports` -> _build_default_report -> finish_report_run -> write_report_manifest -> manifest_path
- Issue: manifest_path stops at the nearest ancestor named `reports`; safe_line does not reserve that name, so the line folder is taken for the reports root.
- Case: report dir `reports/ex/reports/run-<id>` -> manifest `reports/ex/plans/report-runs/run-<id>.json`: a machine file under reports/, and scan_report_runs(`reports/ex`) lists `plans` as a legacy report run.
- Fix: in safe_line (line 79) add `"reports"` and `"plans"` to the reserved tuple. The same case for an exam id `reports` stays open (exam ids are checked in planrun.safe_id, outside this scope).
- Fix risk: an existing line folder with one of these names would be refused; none is used in tests (grep `line="reports"` before applying).
- Test: safe_line("reports") must raise ValueError; today returns "reports".

### F003 – [LOW] Report runs with a -10 or higher suffix sort before -2: wrong prev_report_run and Latest

- File: src/exam_engine/pipeline/runlayout.py
- Lines: 448, 536, 705
- Type: BUG
- Trigger: normal input
- Reached via: `exam report` / `report-pack` -> finish_report_run -> write_report_manifest -> scan_report_runs; rk.write_index -> lines_table
- Issue: scan_report_runs sorts by `(id_time, id)`; the id is compared as text, so `...-10` comes before `...-2`. Callers take `[-1]` as the newest.
- Case: ten or more report runs claimed in one second (scripted rebuild): for run `S-11` the earlier list ends with `S-9`, so `prev_report_run` is `S-9`, not `S-10`; the lines table shows `run-S-9` as Latest.
- Fix: line 448 key: `(id_time(r["id"]), _suffix(r["id"]), r["id"])` for non-legacy rows, `("", 1, r["id"])` for legacy rows.
- Fix risk: none; order is unchanged for suffixes below 10.
- Test: dirs run-S, run-S-2 .. run-S-10 with manifests: scan_report_runs(...)[-1]["id"] must be "S-10"; today "S-9".

## Summary

- Total findings: 3 (CRITICAL 0, HIGH 0, MEDIUM 1, LOW 2; BUG 3, HARDENING 0)
- Cap hit: no
- Not reviewed: none. Checked and dropped (not reported): empty `--line` (rejected by safe_line at cli.py:83); report ids that do not match NEW_ID such as `--report-id fix` (tests rely on them); manifest dropped before a same-id rebuild (documented `incomplete` state); malformed MIGRATION.json entries (machine-written file, no concrete trigger); exam_line_of_plan_dir fallback for a line-layout run without a readable plan.json (no safe fix without the plans root); finish_report_run exam-INDEX refresh when the report line differs from the first plan line (rebuild-reports recipe path not verified).
