PROGRESS: COMPLETE
SKILLS: design, token-efficiency
# Phase 95 - publish badge from main links 
Task: TASK-095 / REQ-0102 · Supersedes: phase-94 §94.5 (plan-run publish column only) · fixes D-V1, D-V2

## Goal
- run-list plan-run `publish` = `published` only if a complete main report run lists it in run.json `plan_runs`; else `dev` (AC1).
- Exam-level INDEX.md stops listing generated `<line>/INDEX.md` and `<line>/run-*/INDEX.md` as `unregistered`; any other unknown file is still flagged (AC2).

## Current behaviour
- cli.py:1449 `_rl_publish(line)` -> badge by line name; used for plan rows (cli.py:1540) and report rows (cli.py:1557).
- So dhqg2024/main plan runs from 2026-11-05 show `published` (no main report links them); dgnl2026 f plan runs show `dev` although main run-20261108-072344 links them.
- report_kinds.py:223 skips only the top-level `INDEX.md`/`run.json` (`rel not in (...)`); nested INDEX.md files fall to `unregistered` (reports/dgnl2026/INDEX.md:16,20,31,49,86,123,124,161,162; dhqg2024/INDEX.md:16,17,35,68,75,86,119,152,153).

## Plan modes
- Display only: no model call, no plan/report file written; publish/solve/report write paths unchanged. Generality: all exams (no exam literal).

## Design
### 95.1 plan-run badge (owner: cli.py run_list_main)
- Publications P = `runlayout.list_report_runs(a.reports, exam)` (always the whole exam, independent of `--line`), keep rows with `line in ("-", "main")`, `layout == "run"`, `manifest.status == "complete"`.
- Build `pub_links` from P with the same key rule as `links` (cli.py:1493-1514: `(pr.line, pr.plan_run_id)`, other-exam ids as `exam/id`). Extract that key loop into `_rl_plan_keys(man, exam) -> [(line, key)]` and reuse it for both dicts (row-append side effect stays in run_list_main).
- `linked(label, r)` (cli.py:1523) gets a `links` parameter (default the current dict); badge = `published` if `linked(label, r, pub_links)` else `dev`. Alias match via MIGRATION.json is the existing `r.get("alias")` term.
- Main plan run with no link: `dev` (REQ text; the `line` column already says main). Rejected: `unpublished` (third word, no need).
- Legacy main report run with `link: line|unknown` (`plan_runs: []`, e.g. dhqg2024 run-20261105-110545): links nothing, gives no badge. Rejected: mark all `plan_line` runs older than it (guess; migration recorded "run unknown").
- Legacy flat report folders (layout `legacy`, legacy_plan_link) do not count: not a run.json `plan_runs` link.
- Unchanged: report-runs table publish column (cli.py:1557, line-based), `lines_table` (runlayout.py:505-522, AC1 "Lines table unchanged"); `_rl_publish` stays for those.
- Doc (main): docs/guide/workflow-roles.md:141 says "`published` for main"; reword to "plan run: linked by a main report run's plan_runs; report run: by line".
### 95.2 INDEX scan (owner: report_kinds.render_index, report_kinds.py:217-224)
- New `_generated_index(path) -> bool`: basename == `INDEX_NAME` and first line starts with `"# Reports index: "` (header written at report_kinds.py:258).
- Line 223: also skip when `_generated_index(os.path.join(dp, fn))`. A hand-written INDEX.md (other first line) and any other unknown file stay `unregistered`. Applies at every level (exam, line, legacy dirs).
- Nested `run.json` rows stay `unregistered` (out of AC2 scope; see Decisions).

## 95.3 Expected real output (reasoned from run.json files, not run)
| Item | before | after |
|---|---|---|
| dgnl2026 f plan runs 20261105-100541-vietnamese, -100543-english, -100543-math, -144607-science2 | dev | published |
| dgnl2026 other plan runs (f/t80/...) | dev | dev |
| dhqg2024 t81 plan runs 20261107-005624-vietnamese, -005812-english, -005940-math, -010203-science | dev | published |
| dhqg2024 main plan runs 20261105-104103-{english,math,science}, 20261105-104650-vietnamese, 20261106-213444-english-t79 | published | dev |
| report-runs table, Lines table (both exams) | - | unchanged |
| reports/dgnl2026/INDEX.md | unregistered 18 | 9 (9 INDEX.md rows gone, total -9) |
| reports/dhqg2024/INDEX.md | unregistered 19 | 10 (total -9) |
- INDEX files change only after main runs `report-index` (real write under reports/: main's call).

## Unit tests (tmp trees, tests/unit/test_publish.py / test_report_kinds.py)
- 95.1a: plans ex/main/A, ex/f/B; main report run.json (status complete) plan_runs=[{exam_id ex, line f, plan_run_id B}] -> B `published`, A `dev`; Lines table rows equal before/after.
- 95.1b: main run.json `link: line`, `plan_runs: []` -> main plan runs `dev`.
- 95.1c: run.json status != complete (or unreadable) in main -> linked run stays `dev`.
- 95.1d: `run-list ex --line f` still shows B `published` (P scanned regardless of --line).
- 95.1e: alias: plan_runs id = old id mapped by MIGRATION.json -> `published`.
- 95.2a: exam folder with generated `f/INDEX.md` + `f/run-X/INDEX.md` -> no row; `f/notes.txt` and an `f/x/INDEX.md` without the header still `unregistered`.
- Regression: test_publish.py:342 (main plan run reported into main -> still `published`), test_runlayout.py:494,528 (`unregistered: 0`) pass unchanged.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 95.1 | exam CLI `run-list dhqg2024` and `run-list dgnl2026` (cli.py run_list_main entry main uses) -> table 95.3 | $0, read-only |
| 95.2 | `report-index reports/dgnl2026` / `reports/dhqg2024`, grep `unregistered: ` -> 9 / 10 | $0, writes INDEX only |

## Decisions (no user decision needed)
- Badge = linked by ANY complete main report run (best; REQ text, smallest). Rejected: only the latest main run = `published`, older = `superseded` (a single-subject main report would mark other subjects superseded; AC1 does not need it). Effect: after a later publish from another line, older linked plan runs still read `published`.
- Nested run.json `unregistered` rows (9 per exam): out of scope (best), follow-up if wanted; same skip rule would fix it.

## Risks
- Exams whose main publication exists only as legacy flat folders: main plan runs flip `published` -> `dev` (per REQ; none seen besides dhqg2024's link:line run).
- `--line X` now also reads the main report runs (cheap).

## Defects
- none new (D-V1, D-V2 in work/TASK-094/handoff/verify.md:42-43 are the scope; D-V3 doc gap not in REQ-0102).

Nova (designer)


## Main's addition (accepted scope)
Also skip the generated `run.json` manifests of report runs in the exam-level INDEX scan (they are generated files like the INDEX.md, listed `unregistered` today: 9 rows per exam after the INDEX.md fix); a truly unknown file is still flagged.
