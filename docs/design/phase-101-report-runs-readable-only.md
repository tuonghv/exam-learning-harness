# Phase 101: report runs hold only human-readable reports
Task: TASK-101 · REQ-0108 (AC1, AC2)

## Goal
- publish / report-pack / report (and solve default report) write no `*_metrics_*.json`, `*_result-data_*.json`, `*_run-log_*.log` into reports/; only .md/.pdf/.tsv + INDEX.md + run.json.
- Provenance already in run.json (runlayout.py:460-478): plan_runs[{exam_id, plan_run_id, dir, line, result_sha256}], view, engine_git, overlays (report_pack.py:243). result-data held nothing more -> no new field needed.

## Plan modes
No effect on single-source or pipeline plan files: plan runs under plans/ keep result.json, run.log and metrics; only the report-run copies are no longer written.

## Design
### 101.1 stop writing metrics/result-data (owner report_build.build, report_build.py:66-76)
- Delete `_dump(path("metrics"))`, the result.json sha and `_dump(path("result-data"))` (+ `path()` helper, `hashlib`/`_dump` if unused). Return dict unchanged (`metrics` still returned; still rendered in solution-report "## Metrics", reporter.py:187).
- Callers needing provenance get it from run.json: cli.py:338 (solve), 447/449 (report), report_pack.py:248 (pack/publish) all write it.
### 101.2 stop copying run.log (owner report_pack.build_pack, report_pack.py:196-198)
- Delete the copy; drop `shutil` import if unused; fix module docstring lines 3-4.
### 101.3 registry: kinds retired, not removed (config/report_kinds.json:26-34, docs/guide/report-kinds.md:22-24)
- Keep `metrics`, `result-data`, `run-log` so old runs still classify `standard` in INDEX and `name()/parse()` keep working for legacy readers.
- Set `"needs": "retired"` on the three: `expected()` (report_kinds.py:153) and check_report_pack.py:164 then skip them with no code change (no view/key is ever "retired").
- Descriptions get suffix "; not written since TASK-101 (old runs only)". Guide table `needs` column = `retired` (asserted by test_report_kinds.py:131) + one line explaining `retired`.
- Cache: registry change alters `registry_sha256` in new run.json only; it is a record, not a cache key (no reader compares it). OK.
### 101.4 score-summary json (D1 = drop, user 2026-11-14)
- Drop `json` from score-summary ext (`["md","pdf"]`); stop writing it (report_pack.py:227-229); add `score: {total_correct, total}` to pack meta before finish_report_run (report_pack.py:241-247).
- `_rl_score` (cli.py:1450-1460): read run.json `score` of the dir first, fall back to the score-summary json (old runs).
### 101.5 checker (tools/check_report_pack.py:204-206, 241-245)
- Replace "log copy" + "result-data plan_run_id" with: `json/log files in pack` = 0 (any file not run.json with ext json/log), and per subject plan.json plan_run_id in run.json plan_runs ids (run.json is already loaded at :128).
- With D1: compare `score-summary` total_correct to run.json `score.total_correct` instead of the json.

## Readers impact (no change needed)
- runlayout.legacy_plan_link (runlayout.py:366-379), plansmigrate._result_shas (plansmigrate.py:222-235): legacy folders/old runs only; new runs have run.json. Keep.
- INDEX (report_kinds.render_index) lists files present -> new runs show only md/pdf/tsv; old runs still index the retired kinds as standard.
- run-list/run-compare: only `_rl_score` reads a report json (D1). publish/_publish_selection reads run.json plan_runs (cli.py:520), unaffected.

## Tests (tests/unit)
- test_report_build.py:78 -> assert metrics/result-data absent; :96 compare `info["metrics"]` to metrics.compute or check md "## Metrics" block instead of the file.
- test_plan_qa.py:124-125 -> compare solution-report md Metrics block (or returned metrics) of solve vs report.
- test_overlay.py:233-234 -> metrics reflected in solution-report md / answer-sheet, not json.
- test_plan_import.py:75 -> check rk.find(...,"metrics") is None if `d` is a report dir (verify which dir).
- test_report_kinds.py:67 (expected contains metrics) -> assertNotIn; :144 score-summary json -> NotIn (D1); :425 metrics kind loop -> use a live kind; :94/:251/:278 classify/legacy stay (kinds retained).
- test_key_score_98.py:181 -> read run.json `score` (D1).
- test_runlayout.py:547-570 legacy fixtures stay (old-run fallbacks).
- New: pack of 2 plans has no `.json`/`.log` except run.json; run.json plan_runs names both plans with result_sha256; check_report_pack exits 0 on it and non-0 when a stray `*_metrics_*.json` is added.
- New: synthetic non-DGNL exam pack (Generality). Iterate `--affected`, finish `--fast`.

## Verification (main runs; $0, no model call)
| Item | Command -> expected |
|---|---|
| 101.1-101.4 | `exam publish dgnl2026 --from f` and `exam publish dhqg2024 --from t81` -> new reports/<exam>/main/run-<date>/ |
| 101.1/101.2 | `find reports/dgnl2026/main/run-<new> reports/dhqg2024/main/run-<new> -name '*.json' ! -name run.json -o -name '*.log'` -> empty |
| 101.5 | `python3 -I tools/check_report_pack.py <new run> <plan dirs> [--key ...]` -> all PASS |
| provenance | `jq '.plan_runs[]|.plan_run_id,.result_sha256' run.json` -> one per subject; INDEX.md Kind column has no metrics/result-data/run-log |
| AC2 | delete old main runs (run-20261114-082249 and the dhqg2024 main one), `exam report-index` the line folder -> runs table lists only new run |

## Risks
- A missed test/reader expecting metrics json in a report dir -> `--fast` catches; grep `rk.find(.*"metrics"` done (test_plan_qa, test_plan_import only).
- run-list score for new runs blank if D1 done without the run.json fallback -> test for `_rl_score` on run.json.
- Deleting old main runs is irreversible (git-ignored); main confirms the new runs pass the checker first.

## Newer features kept
- TASK-100 date run names (`run-YYYYMMDD-HHMMSS`, cli.py:539 default) untouched: only file kinds change.
- TASK-099 public report default (`solution_public-report`, report_build.py:64, report_pack.py:209) untouched.

## Decisions
- D1 resolved (user, 2026-11-14): drop score-summary json too; score into run.json, run-list falls back to the old json for old runs.
- Retire via `needs: "retired"` - rejected: delete kinds (old runs turn `unregistered`), new flag key (code change in two places).

## Out of scope
- Plan-run side files under plans/ (result.json, run.log, metrics in history) unchanged.

## Defects
- none
