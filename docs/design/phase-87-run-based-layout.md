PROGRESS: COMPLETE
SKILLS: design, token-efficiency
# Phase 87 - run-based plans and reports 
Task: TASK-087 · REQ-0095 (Q1 a, Q2 leave legacy, Q3 YYYYMMDD-HHMMSS UTC) · Status: draft
## Goal
New solves write `plans/<exam>/runs/<id>/`; every report build writes a new `reports/<exam>/run-<id>/` with
`run.json` naming its plan run(s); `exam run-list EXAM` shows plan runs -> report runs, cost, score; `exam run-compare A B`
compares two plan runs. Proof: two report runs of one plan run coexist, legacy folders still read, nothing moved.
## What the scanner does (read-only facts) and what we adopt
- `pipeline_lib.sh:16-17,48-65` plan runs at `<plan>/runs/<id>`, id `date +%Y%m%d-%H%M%S` (local time), collision `-N`
  (N from 2), `run.json` = {run_id, created_at, prev_run, status running|complete}; `runs/latest` symlink.
- `pipeline_lib.sh:58-63` toolkit stamp in a sidecar `toolkit.json`, never a run.json key (run.json is an engine input).
- `compare_runs.sh:85-105` `--run latest|dir --old prev|dir`; prev = run.json prev_run if complete, else last complete
  earlier id (string order = time order); report goes to `reports/<sys>/<plan>/run-<plan-run-id>/` (one per plan run).
- `tracking/history.py:2-14` history.md/json rebuilt from per-run cards, byte-stable, `--check` recounts from source.
- Adopt: `runs/<id>` + `-N`, `prev_*` link, status in manifest, id order = time order, deterministic history with a
  recount check. Change: UTC (Q3); report folder has its own id (Q1 a, scanner uses the plan id); provenance stays in
  run.json (our report run is output, not an engine input). Skip: `latest` symlink (computed instead: no symlink in
  git-ignored trees, `plan-import` already refuses symlinks), YAML registry, cards.
## Constraints
- $0, stdlib, no model. Solve cache stays `plans/<exam>/cache` (key = namespace+prompt, `replycache.py:19`, no path:
  cache answers unaffected). `plans/run-history.jsonl` path and line shape unchanged. No folder moved or rewritten.
- Generality: all exam kinds; ids are data; no exam literal. Golden: `report-index` on a legacy folder is byte-identical.
## Plan modes
- solve --real/--dry-run default out: new layout. `--out DIR`: unchanged (caller's dir, no run.json in plans).
- report / report-pack / solve default report: new report run. Explicit `--out`: as today plus run.json.
## Design
### 87.1 Layout resolver (owner: new `src/exam_engine/pipeline/runlayout.py`)
Constants `RUNS="runs"`, `CACHE="cache"`, `REPORT_PREFIX="run-"`, `RUN_JSON="run.json"`,
`NEW_ID=^\d{8}-\d{6}(-\d+)?$`. All ids pass `planrun.safe_id`.
- `plan_run_dir(root, exam_id, run_id)` -> `root/exam/runs/id` if it exists, else `root/exam/id` (legacy) if it exists, else the new path.
- `new_plan_run(root, exam_id, now=None)` -> claimed dir (`makedirs(exist_ok=False)` loop, as `planrun.py:46-58`).
- `list_plan_runs(root, exam_id)` -> `[{id, dir, layout:"runs"|"legacy", plan:dict|None}]`; legacy = direct child
  (not `runs`/`cache`) holding plan.json or result.json; sort key `(started_utc|imported_utc|id-time, id)`, never mtime.
- `exam_of_plan_dir(plan_dir)` -> parent name, or grandparent when parent is `runs`.
- `new_report_run(root, exam_id, run_id=None)` -> `root/exam/run-<id>`; given id (with or without `run-`) reuses the
  dir (AC3 overwrite), no id = fresh id, collision `-N`.
- `list_report_runs(root, exam_id)` -> `[{id, dir, layout:"run"|"incomplete"|"legacy", manifest}]`: `run-<NEW_ID>`
  with run.json = run; without = incomplete; any other subdir = legacy (plan link from its `result-data` json `plan_run_id`).
- `cache_dir(root, exam_id)` -> `root/exam/cache`.
### 87.2 Run id (owner: `runlayout.new_run_id(now=None)`)
`time.strftime("%Y%m%d-%H%M%S", time.gmtime(now))`; suffix `-2,-3..` added only by the claim loops. Old
`YYYYMMDDTHHMMSSZ` ids stay readable (parsed for sort only). Guide `docs/guide/report-kinds.md:8` gets one line on the format.
### 87.3 Manifest (owner: `runlayout.write_report_manifest(report_dir, plan_dirs, view, engine_git, cmd)`)
`run.json` (tmp+rename, sorted keys) written after a successful build: `{schema:1, report_run_id, exam_id, created_utc,
cmd:"report"|"report-pack"|"solve", view, plan_runs:[{exam_id, plan_run_id, dir (relative to repo root), result_sha256}],
prev_report_run, registry_sha256 (of config/report_kinds.json, no version key exists), engine_git}`. Plan dirs are never
written: the plan->report link is derived by `list_report_runs` (read-only plans). `report_kinds.write_index` skips
`run.json` like `INDEX.md` (`report_kinds.py:192`) and, when present, prints 3 header lines (plan runs, view,
registry/engine) from it; no clock. `report_pack.py:166` `have` also excludes `run.json`.
### 87.4 Writers and readers switched to the resolver
| Site | Change |
|---|---|
| `planrun.claim_run_dir` (`planrun.py:46`) | delegate to `runlayout.new_plan_run` (solve default `cli.py:120`, `import_dir` `:307`) |
| `planrun.last_solved` (`:164`) / `_already_imported` (`:209`) | iterate `list_plan_runs` (both layouts) |
| solve cache `cli.py:116` | `runlayout.cache_dir` (same path) |
| `_build_default_report` `cli.py:304` | `new_report_run` + manifest, cmd solve |
| `_report_plan` `cli.py:399-402` | exam id via `exam_of_plan_dir` (defect D1); out = `new_report_run(..., a.rid)`; manifest |
| `report_pack_main` `cli.py:424-426` | `--out` optional (default `new_report_run(reports, slug(--exam))`), `--run` optional (default `short_run(basename(out))`); manifest |
| `_rs_resolve` `cli.py:1316` | after dir and history id: try `EXAM/ID` via `plan_run_dir` |
| `tools/check_report_pack.py:96` | exclude run.json; if present check `len(plan_runs)==len(plans)` and each `result_sha256` |
| review-pack, scorer, `report_kinds.find`, run-history | path-agnostic (explicit paths): no change |
### 87.5 History and compare (owner: `cli.run_list_main`, `cli.run_compare_main`; commands `run-list`, `run-compare`)
- `exam run-list EXAM [--plans plans] [--reports reports]` prints, sorted as 87.1: `| plan run | layout | status | model |
  calls | cost_usd | report runs | score |`; score = `correct/total` from the newest linked report run's `score-summary`
  json (`report_kinds.find(dir,"score-summary",ext="json")`), else `-`. Plan runs of another exam that a report run of
  EXAM links (pack of subject plans) are listed as `EXAM2/ID`. Then a `## Report runs` table (id, layout, view, plan runs).
  Exit 0; 2 when EXAM has neither folder.
- `exam run-compare A B` = `_rs_compare` on refs resolved by `_rs_resolve` (87.4), same output and exit 0/1/2.
### 87.6 Exam runs index (owner: `report_kinds.write_index(folder)` + `runlayout.write_exam_index`)
When `folder` holds at least one new report run: write `INDEX.md` = runs table (report run -> plan runs, view, cmd,
created) + the existing file table limited to files outside new run dirs (each run dir has its own INDEX.md). Otherwise
the old output byte-identical. Called by report, report-pack and solve after each new report run, and by `report-index`.
### 87.7 Legacy
Nothing moved or renamed. Legacy plan/report folders appear with `layout legacy` in run-list and the exam INDEX.
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| Build fails mid-way | no run.json | run-list `incomplete`; rerun makes a new id |
| Two writers same second | `-N` suffix via exist_ok=False | two runs |
| run.json unreadable | treated as incomplete | WARN line in run-list |
| `--report-id` of existing run | overwrite in place (AC3) | same dir, new run.json |
| Legacy run named `run-f` | legacy (id not NEW_ID) | `legacy` row |
## Unit tests (tests/unit/test_runlayout.py + updates)
U1 new_run_id format/UTC with fixed `now`; U2 claim collision -> `-2`; U3 list_plan_runs mixes runs/ + legacy + skips
cache/runs/plain files, deterministic order; U4 last_solved finds a runs/ and a legacy plan; U5 two report runs of one
plan coexist, `--report-id` reuses; U6 run.json fields + check_report_pack passes with run.json, fails on sha mismatch;
U7 exam_of_plan_dir both layouts (D1); U8 run-list table on a synthetic non-DGNL exam; U9 write_index legacy folder
byte-identical golden; U10 run-compare EXAM/ID resolves. Update `test_solve_cache.py:84-86` `plans()` and
`test_planrun.py:129-134` to the runs/ layout.
## Verification (all $0)
| Item | Command -> expected |
|---|---|
| 87.1-87.4 | `python3 -I -m unittest discover -s tests/unit` -> OK |
| 87.3/QA | `exam report-pack <2 stored plan runs> --exam X` twice -> 2 `run-*` dirs; `python3 -I tools/check_report_pack.py <dir> <plans>` -> 0 FAIL; recount questions per subject = INDEX counts |
| 87.5 | `exam run-list dgnl2026f` -> legacy `out-*` rows + new runs, costs = plan.json sums |
| 87.7 | `git status --porcelain plans reports` before/after: no legacy path deleted |
## Decisions
- D-a (best, no user needed): no `latest` symlink; latest computed. D-b: exam INDEX = runs table + legacy file table.
## Defects
- D1 minor `cli.py:399`: exam id fallback `basename(dirname(plan))` gives `runs` for a runs/ plan without plan.json exam_id.
- D2 minor `tests/unit/test_solve_cache.py:86`: lists plans/<exam> children; returns `["runs"]` after the change.
## Out of scope
Moving legacy folders; per-subject exam id of subject files (`exam_id_of`); PDF of the history view.
Nova
