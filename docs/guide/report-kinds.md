# Report kinds (REQ-0092)

Single source: `config/report_kinds.json` (loaded by `src/exam_engine/pipeline/report_kinds.py`). The table below is generated from it and a unit test checks they match; add a kind by adding one registry entry (writers, `INDEX.md` and `tools/check_report_pack.py` read it).

File name: `<exam>_<subject>_<kind>_<run>.<ext>`

- `<exam>`, `<subject>`, `<kind>`: `[a-z0-9-]+`; `_` only separates the four parts. `<subject>` = `all` for the whole exam.
- `<run>` = `run-<short>` (e.g. `run-f`; a run folder made by the engine: `run-<YYYYMMDD-HHMMSS>[-N]`, UTC, see Run layout). Plan dirs (`plans/**`: result.json, run.log, input/exam.md) are not reports and keep their names.
- Scope: `subject` = one per subject, `all` = one for the exam, `both` = both. Needs: condition for the kind to apply (`sheet`/`learn` view, `key` = an answer key was given).
- Rule `pdf_with_md` (registry flag): every md of a pack has a pdf of the same name and every pdf has an md; `tools/check_report_pack.py` checks it (legacy folders and `report-index` do not enforce it).
- Legacy names (old folders, never renamed) are still read; `INDEX.md` marks them `legacy`. Superseded paths are marked `superseded`.

| Kind | Pattern | Ext | Scope | Needs | Description | Legacy |
| --- | --- | --- | --- | --- | --- | --- |
| `answer-sheet` | `<exam>_<subject>_answer-sheet_<run>.<ext>` | md, pdf | subject | - | one subject's answers as a bubble grid (letters only, a dash for a declined question) | `answers.md` |
| `solution-report` | `<exam>_<subject>_solution-report_<run>.<ext>` | md, pdf, html | both | sheet | hybrid full report: question and options, answer, status, doubt in words, steps, explanation, checks (html only when no PDF renderer) | `report.md`, `report.pdf`, `report.html` |
| `learning-report` | `<exam>_<subject>_learning-report_<run>.<ext>` | md, pdf, html | subject | learn | study view of one subject (answer, why, steps) written for --view learn | - |
| `answer-table` | `<exam>_<subject>_answer-table_<run>.<ext>` | tsv | all | - | whole exam, one row per question: subject, printed no., answer, status, doubt, error, score | `answers.tsv` |
| `score-vs-key` | `<exam>_<subject>_score-vs-key_<run>.<ext>` | tsv | all | key | whole exam checked against the official answers: key, ours, correct/WRONG/declined, status, doubt, flag | - |
| `score-summary` | `<exam>_<subject>_score-summary_<run>.<ext>` | md, pdf, json | all | key | whole exam score: per subject correct/wrong/declined, cost, calls, items not correct, doubt vs outcome | - |
| `metrics` | `<exam>_<subject>_metrics_<run>.<ext>` | json | subject | - | per-run metrics (calls, cost, coverage) of one subject | `metrics.json` |
| `result-data` | `<exam>_<subject>_result-data_<run>.<ext>` | json | subject | - | provenance of a report: plan run id, result sha256, view, engine git | `report.json` |
| `run-log` | `<exam>_<subject>_run-log_<run>.<ext>` | log | subject | - | copy of the plan run.log (call lines) kept with the pack | `run.log` |

## Superseded

| Path glob | Note |
| --- | --- |
| `dhqg2024/solutions.*` | superseded 2026-11-05 by dhqg2024-t81/ALL-120/report.* (raw-JSON doubt, unaccented steps) |
| `dgnl2026-crosscheck/*` | superseded by reports/dgnl2026/ (run-f pack, standard names, hybrid solution-report) |

## Run layout (TASK-087, REQ-0095)

- Plan runs: `plans/<exam>/runs/<YYYYMMDD-HHMMSS>[-N]/` (UTC; `-2`, `-3` only on a same-second collision). The solve cache stays `plans/<exam>/cache/`.
- Report runs: `reports/<exam>/run-<YYYYMMDD-HHMMSS>[-N]/` with `INDEX.md` and `run.json` (not a registered kind; `write_index`, `report-pack` and `tools/check_report_pack.py` skip it). Every report build makes a new report run; the same `--report-id` overwrites that run. Many report runs may point to one plan run.
- `run.json`: `{schema, report_run_id, exam_id, created_utc, cmd, view, plan_runs:[{exam_id, plan_run_id, dir, result_sha256}], prev_report_run, registry_sha256, engine_git}`. Plan dirs are never written; the plan -> report link lives here.
- Old layouts (`plans/<exam>/<run>/`, `reports/<exam>/<run>/<report-id>/`, `out-X`, old ids `YYYYMMDDTHHMMSSZ`) stay readable (`layout legacy`) and are never moved. No `latest` symlink: the newest run is computed.
- `reports/<exam>/INDEX.md` holds a report-runs table (run, layout, plan runs, view, cmd, created) plus the file table of files outside the run folders.

## Commands

- `exam report PLAN_RUN [--view V] [--report-id ID] [--out DIR]`: one plan run -> new `reports/<exam>/run-<id>/` (+ `run.json`), standard names.
- `exam report-pack PLAN... --exam N [--out DIR] [--run R] [--key FILE] [--no-pdf]`: whole-exam pack + `INDEX.md`, $0. Default out: a new run folder.
- `exam run-list EXAM [--plans DIR] [--reports DIR]`: plan runs -> report runs, status, model, calls, cost, score (both layouts), $0.
- `exam run-compare A B`: compare two plan runs (`run-stats compare`); A, B = result dir, history run_id or `EXAM/PLAN_RUN_ID`.
- `exam report-index DIR...`: (re)write `INDEX.md` of existing folders.
- `python3 -I tools/check_report_pack.py PACK PLAN... [--key FILE] [--expect-correct N]`: independent recount; fails on an unregistered file or a registered kind with no file.

## Not covered yet

- Benchmark output: `pipeline/benchmark.py` writes a bare `report.md` (+ `summary.json`) into its out dir. It is a cost/benchmark summary, not an exam report; it keeps the old name and is outside REQ-0092 / TASK-085.
