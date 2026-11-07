PROGRESS: COMPLETE
SKILLS: design, token-efficiency
# Phase 85 - standard report names 
Task: TASK-085 · REQ-0092 AC1-AC9 · Status: draft
## Goal
Every report file is `<exam>_<subject>_<kind>_<run>.<ext>`, one registry defines kinds, each exam folder has a generated INDEX.md, solution-report is hybrid, DGNL 2026 pack regenerated at $0 and recounted by a checker.
## Constraints / Generality
- Plan dirs (`plans/**`: result.json, run.log, input/exam.md) are NOT reports: names unchanged (planrun.load planrun.py:201, metrics.load_log cli.py:459,1288, engine.py:517 keep reading them).
- Name parts `[a-z0-9-]+`, `_` only as separator; subject `all` = whole exam; run = `run-<short>`; labels from reporter.LABELS (reporter.py:87), no exam literal in code. Synthetic non-DGNL test exam.
- Old folders never renamed (AC4); readers accept both via one resolver.
## Plan modes
- single-source: config/report_kinds.json is the only list; writers, INDEX, checker, doc test all load it.
- pipeline: solve (engine.py:523 -> write_reports), `report PLAN_RUN` (cli.py:383 -> report_build.build), `report RESULT.json` (cli.py:438), new `report-pack`; benchmark.py:182 not affected (out of scope).
## Design
### 85.1 registry (owner: config/report_kinds.json + src/exam_engine/pipeline/report_kinds.py)
- JSON: `{"pattern": "<exam>_<subject>_<kind>_<run>.<ext>", "kinds": {kind: {"ext": [...], "scope": "subject|all", "description": str, "count": "questions|rows|none", "legacy": [basenames]}}, "superseded": [{"glob": "solutions.*", "note": str}]}`.
- Kinds/legacy: answer-sheet[md; answers.md], solution-report[md,pdf,html; report.md/.pdf/.html], learning-report[md,pdf], answer-table[tsv; answers.tsv], score-vs-key[tsv], score-summary[md,json], metrics[json; metrics.json], result-data[json; report.json provenance], run-log[log; run.log copy in pack only].
- Functions: `load()`, `name(exam, subject, kind, run, ext) -> str` (ValueError on bad part/kind/ext), `parse(basename) -> dict|None`, `slug(s)`, `short_run(plan_run_id)`, `find(dir, kind, subject=None, ext="md") -> path|None` (new name first, then legacy), `classify(basename) -> (kind, "standard"|"legacy"|"superseded"|None)`.
- docs/guide/report-kinds.md: table kind/pattern/ext/description/legacy; a unit test checks it equals the JSON (no second source).
### 85.2 writers emit standard names (owner: reporter.write_reports reporter.py:350, report_build.build report_build.py:39)
- `write_reports(..., names=None)`: names = `{"exam","subject","run"}`; default from result (`slug(exam.path stem)`, `slug(exam.subject) or "all"`, `run-` + short of out dir). Writes `_solution-report_` (view sheet) or `_learning-report_` (view learn) .md/.pdf/.html and `_answer-sheet_`.md. Return keys md/answers/html/pdf unchanged so cli.py:216,409,465 print paths as-is.
- build(): `_metrics_`.json, `_result-data_`.json (was report.json), names from new `exam_name=, run_name=` kwargs; cli `report PLAN_RUN` gains `--exam-name`, `--run-name` (needed: plan exam_id is per subject, e.g. `e-Math`). Defaults keep today's dirs.
- Readers: run-stats/report paths that look for a report go through `report_kinds.find`; nothing in src parses report.md today (grep), so the resolver is used by INDEX, checker and the pack.
### 85.3 INDEX.md (owner: report_kinds.write_index(folder) -> path)
- Walk folder recursively, sorted; per file: relative path, kind, standard|legacy|superseded, description, count (questions: `^#{2,3} \S+ \d+` headings in md, rows in tsv minus header; else `-`). Footer: totals per kind and grand total. Superseded rows show the registry note (dhqg2024/solutions.* -> dhqg2024-t81/ALL-120/report.*) (AC6). Unknown files listed as `unregistered`. Deterministic: no clock, no abs paths. CLI: `exam report-index DIR`.
### 85.4 hybrid solution-report (owner: reporter.build_markdown reporter.py:159)
- Per question: `### <Câu|Question> <id>`, question text, options `A. ...` one per line, `**<Đáp án>: X**`, `<status>: PASS|FAIL|UNCERTAIN (<reason>)`, `<doubt>: <low|medium|high in words> - <reason>` (never raw JSON), steps numbered, explanation, checks as one compact line each, QA findings, error. Top: title, totals, metrics, answer sheet; `## <subject>` heading per subject.
- Text source: result.json has NO question text; it comes from plan `input/exam.md` via report_build._exam (report_build.py:27) -> parser.parse_exam fields text/options/passage (parser.py:131). Passage printed once per run of questions sharing it. Pass `exam` to build_markdown(result, metrics, exam=None).
- Missing (no input/exam.md, parse error, id absent, or `report RESULT.json` path): one line `<label: question text not stored in this run>`, rest unchanged; count reported as `with_text n/N` in INDEX and checker.
- New LABELS keys: status, doubt, levels{low,medium,high}, no_text (vi + en).
### 85.5 pack regeneration (owner: new src/exam_engine/pipeline/report_pack.py, CLI `exam report-pack`)
- `build_pack(plan_dirs, out_dir, exam, run, key=None, pdf=True)`: per plan dir report_build.build into out_dir with names; copy run.log as `_run-log_`; `<exam>_all_solution-report_<run>.md/.pdf` (subjects in plan order, `## <subject>`); `_all_answer-table_<run>.tsv` (subject, printed, answer, status, doubt, error, score); with key: `_all_score-vs-key_<run>.tsv` via scorer.key_letters (scorer.py:228) + printed = id + exam offset (same offset as explain/metrics), `_all_score-summary_<run>.md/.json` (per subject correct/wrong/declined/cost/calls, not-correct list, doubt-vs-outcome). Then write_index(out_dir).
- Run (main, $0): `report-pack plans/dgnl2026f/out-{Vietnamese,English,Math,Science2} --out reports/dgnl2026 --exam dgnl2026 --run f --key input/dgnl/De-thi-minh-hoa-2026-Final.answer.txt`; then `report-index` on reports/dgnl2026-crosscheck, dgnl2026f, dhqg2024, dhqg2024-t81.
### 85.6 QA checker (owner: new tools/check_report_pack.py, stdlib, crosscheck oracle)
- Independent of report_kinds code: reads config/report_kinds.json + plan result.json + key with re/json only. Checks: every file name parses and kind/ext registered; per-kind file counts = expected (4 subjects x kinds); questions per solution-report/answer-sheet = len(result.questions); sum 120; answer letters in answer-table = result answers; score-vs-key correct count recomputed = score-summary total and = old pack (113/120); INDEX totals = directory listing; raw-JSON doubt lines = 0; with_text = N. Output TSV `check\texpected\tgot\tok`, exit 1 on any mismatch.
### 85.7 announcement (owner: main reply + INDEX header; text)
"Report format changed (REQ-0092). Old: report.md / answers.md / solutions.md / answers.tsv per folder. New: <exam>_<subject>_<kind>_<run>.<ext>, kinds in docs/guide/report-kinds.md, INDEX.md per exam folder. Current: reports/dgnl2026/ (run-f). Superseded: reports/dgnl2026-crosscheck/, reports/dhqg2024/solutions.* (kept, marked in INDEX). Solution-report is now hybrid: question + options, answer, status, doubt in words, steps. Cross-check: INDEX counts, 120 questions, score 113/120 vs score-vs-key."
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| bad name part (`_`, empty) | name() ValueError | report ERROR exit 2 |
| exam.md missing / id absent | no-text line | `with_text 0/30` in INDEX |
| PDF renderer missing | md kept, html kept under standard name | `PDF skipped` (as today) |
| unknown file in folder | listed `unregistered` | INDEX row; checker fails |
| key absent | score files skipped | INDEX lacks score kinds |
## Unit tests
- registry: name/parse round trip; bad parts raise; doc table == JSON; legacy find returns old file when new absent.
- AC5: build() + mock solve output dir: every file parses (`parse()` not None) except plan files; fails on a stray report.md.
- hybrid: question text + options + doubt words present, no `{"level"` text; no-text line when exam None; subject heading; synthetic non-DGNL exam.
- INDEX: fixed tmp tree -> byte-identical INDEX; superseded and unregistered rows; totals.
- pack: 2 synthetic plans + key -> expected file list, score counts; checker exit 0, and exit 1 after deleting one file (test bites).
- Update tests naming report.md/answers.md: test_exam_report, test_report_build, test_run_stats:189, test_solve_gate:170, test_planrun:82, test_plan_import:71, test_plan_qa:118, test_scripts_exam:66.
## Verification
| Item | command -> expected | tier |
|---|---|---|
| 85.1-85.4 | `python3 -I -m unittest discover -s tests/unit` -> OK | $0 |
| 85.5 | report-pack command above -> 30 files + INDEX.md | $0 |
| 85.6 | `python3 -I tools/check_report_pack.py reports/dgnl2026 plans/dgnl2026f/...` -> all ok, 113/120 | $0 |
## Decisions (user, RAW-00260 "accept all", 2026-11-07)
1. (a) new flat `reports/dgnl2026/` with run in names; old `reports/dgnl2026-crosscheck` kept and marked superseded.
2. (a) also write a combined `_all_solution-report_` (4 subjects) besides per-subject files.
3. (a) pack is run-f only; the t80 answer table stays legacy in its own folder.
4. AC10 (RAW-00259): the QA checker also fails when a registered kind has no generated file (not only unregistered files).

## Out of scope
benchmark summary.json/report.md; renaming old folders; accent fixing of model text (only measured).
## Defects
- D1 low, reports/dgnl2026-crosscheck/INDEX.md:26: says the engine writes `answers.tsv`; no src writer exists (grep), t80 table was hand-made.
- D2 low, same INDEX:16-19: score-summary/score-vs-key names lack `<run>` (Q2 says run in every name).
- D3 medium, plans/dgnl2026f/*/plan.json:10: exam_id is per subject (`e-Math`), so default names would give exam `e-math`; pack needs `--exam`.
- D4 known (AC7), reports/dhqg2024/solutions.md:31: doubt printed as raw JSON.
