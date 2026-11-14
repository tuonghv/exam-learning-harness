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
| `solution_public-report` | `<exam>_<subject>_solution_public-report_<run>.<ext>` | md, pdf, html | both | - | student-facing report of one subject: question, answer, steps, explanation; no status, doubt, evidence, score or AI-review notes | - |
| `answer-table` | `<exam>_<subject>_answer-table_<run>.<ext>` | tsv | all | - | whole exam, one row per question: subject, printed no., answer, status, doubt, error, score | `answers.tsv` |
| `score-vs-key` | `<exam>_<subject>_score-vs-key_<run>.<ext>` | tsv | all | key | whole exam checked against the official answers: key, ours, correct/WRONG/declined, status, doubt, flag | - |
| `score-summary` | `<exam>_<subject>_score-summary_<run>.<ext>` | md, pdf, json | all | key | whole exam score: per subject correct/wrong/declined, cost, calls, items not correct, doubt vs outcome | - |
| `metrics` | `<exam>_<subject>_metrics_<run>.<ext>` | json | subject | retired | per-run metrics (calls, cost, coverage) of one subject; not written since TASK-101 (old runs only) | `metrics.json` |
| `result-data` | `<exam>_<subject>_result-data_<run>.<ext>` | json | subject | retired | provenance of a report: plan run id, result sha256, view, engine git; not written since TASK-101 (old runs only) | `report.json` |
| `run-log` | `<exam>_<subject>_run-log_<run>.<ext>` | log | subject | retired | copy of the plan run.log (call lines) kept with the pack; not written since TASK-101 (old runs only) | `run.log` |

`needs` = `retired`: the kind is no longer written (TASK-101, REQ-0108); it stays registered so old runs still classify as standard. The `json` of `score-summary` is optional (old runs only). A report run holds only .md/.pdf/.tsv + INDEX.md + run.json (provenance and `score` {total_correct,total} are in run.json).

## Superseded

| Path glob | Note |
| --- | --- |
| `dhqg2024/solutions*` | superseded 2026-11-05 by the dhqg2024 line t81 run, ALL-120/report.* (raw-JSON doubt, unaccented steps) |
| `dgnl2026-crosscheck/*` | superseded by the dgnl2026 line f pack run (standard names, hybrid solution-report) |

`score-summary` (TASK-098): accuracy = correct / scorable (nokey and keybad rows excluded); also sections Per question, Calibration (by doubt level), Mismatches (wrong/declined with the engine's reasoning) and Key issues (bad, duplicate or missing key entries, also on stderr). Registry names are unchanged.

## Run layout (TASK-087, REQ-0095; line layout TASK-090, REQ-0098)

- Plan runs: `plans/<exam>/<line>/runs/<YYYYMMDD-HHMMSS>[-<subject>][-N]/` (UTC; line default `main`, `solve --line NAME`; `<subject>` = lowercase tag of the exam file stem when `--exam-id` names another exam folder or the run was migrated; `-2`, `-3` only on a same-second collision, after the tag). REQ-0095 `plans/<exam>/runs/<id>/` and `plans/<exam>/<run>/` stay readable. The solve cache stays `plans/<exam>/cache/` for every line. New `plan.json` carries `line` and `plan_exam` (the folder; `exam_id` stays the file stem).
- Report runs: `reports/<exam>/<line>/run-<YYYYMMDD-HHMMSS>[-N]/` (mirrors the plan line; a plan run without a line keeps `reports/<exam>/run-<id>/`) with `INDEX.md` and `run.json` (not a registered kind; `write_index`, `report-pack` and `tools/check_report_pack.py` skip it). Every report build makes a new report run; the same `--report-id` overwrites that run. Many report runs may point to one plan run.
- `run.json`: `{schema, report_run_id, exam_id, created_utc, cmd, view, plan_runs:[{exam_id, plan_run_id, dir, result_sha256, line?}], prev_report_run, registry_sha256, engine_git, score? {total_correct,total} (pack with a key)}`. Plan dirs are never written; the plan -> report link lives here.
- Old layouts (`plans/<exam>/<run>/`, `reports/<exam>/<run>/<report-id>/`, `out-X`, old ids `YYYYMMDDTHHMMSSZ`) stay readable (`layout legacy`). `exam plans-migrate` (reviewed map `config/plans_migration.json`, backup, `plans/MIGRATION.json`, `--undo`) moves the old plan folders into `<exam>/<line>/`; the resolver maps every old path through the manifest and migrated `plan.json` files stay byte-identical (old `plan_run_id` = alias). No `latest` symlink: the newest run is computed.
- Migrated reports (TASK-091, REQ-0099): `exam plans-migrate --root reports` moves each old folder (`reports/dgnl2026f/`, `reports/dgnl2026/` pack, ...) to `reports/<exam>/<line>/run-<newest file mtime>/` (a `YYYYMMDDTHHMMSSZ` stamp dir is one run each; nothing stays directly in an exam folder). `run.json` adds `migrated_from`, `link` (`result_sha256` = plan runs found by result-data sha256, `name` = plan run of the same stamp, `line` = plan line known, run unknown, `unknown`), `plan_line`, `status` (`complete`|`superseded`) and `superseded` [{glob, note}] (globs relative to the run folder, added to the registry globs by `write_index`; moved from the registry paths `<old folder>/<glob>`). `run-list` shows `line <L> (run unknown)` / `unknown` for such runs.
- `reports/<exam>/INDEX.md` holds a report-runs table (run, layout, plan runs, view, cmd, created) plus the file table of files outside the run folders.

## Commands

- `exam report PLAN_RUN [--view V] [--report-id ID] [--out DIR]`: one plan run -> new `reports/<exam>/run-<id>/` (+ `run.json`), standard names.
- `exam report-pack PLAN... --exam N [--out DIR] [--run R] [--key FILE] [--no-pdf]`: whole-exam pack + `INDEX.md`, $0. Default out: a new run folder.
- Overlay (TASK-096, REQ-0103): `--overlay PLAN_DIR:PRINTED[,PRINTED...]` (repeatable) `--overlay-reason TEXT` (required) takes answer, solution, status, doubt and checks of the listed printed numbers from another plan run, in memory only (no result.json/plan.json is written). Refused (exit 2, before any file is written) when the overlay is another exam, its subject is not exactly one base part, a printed number is unknown or repeated, the stem+options hash differs (passage and instruction are not part of it), page sets are disjoint, the base question is answered and not unresolved, or the overlay has no letter. Each overlaid block gets one line `Answer source: plan run <id> of line <line> (<reason>)` (vi: `Nguồn đáp án: ...`) and shows the overlay passage; Totals are recounted; run.json `overlays` records plan run, ids, printed numbers, hashes, reason and the overlay cost. `tools/check_report_pack.py` reads `overlays` (sha256 of the overlay result, text equality, source-line counts, recounted answers). `exam publish` inherits the source pack's overlays .
- `exam run-list EXAM [--plans DIR] [--reports DIR]`: plan runs -> report runs, status, model, calls, cost, score (both layouts), $0.
- `exam run-compare A B`: compare two plan runs (`run-stats compare`); A, B = result dir, history run_id or `EXAM/PLAN_RUN_ID`.
- `exam report-index DIR...`: (re)write `INDEX.md` of existing folders.
- `python3 -I tools/check_report_pack.py PACK PLAN... [--key FILE] [--expect-correct N]`: independent recount; fails on an unregistered file or a registered kind with no file.

## Not covered yet

- Benchmark output: `pipeline/benchmark.py` writes a bare `report.md` (+ `summary.json`) into its out dir. It is a cost/benchmark summary, not an exam report; it keeps the old name and is outside REQ-0092 / TASK-085.
