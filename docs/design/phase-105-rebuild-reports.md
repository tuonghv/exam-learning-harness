# Phase 105: tracked recipe and exam rebuild-reports
Task: TASK-105 (REQ-0111 AC1-AC5)

## Goal
`exam rebuild-reports [EXAM...] [--dry-run]` rebuilds every published report from tracked recipe
`config/published_reports.json` at $0 (no model call), by calling the existing `report_pack_main` and
`publish_main`. Proof: normalized-identical report files vs today's runs, scores 113/120, 113/120, 105/119.

## Constraints
- Reuse: `cli.report_pack_main` (src/exam_engine/cli.py:478), `cli.publish_main` (cli.py:537),
  `overlay.resolve` (src/exam_engine/pipeline/overlay.py:64), `runlayout.list_report_runs` (runlayout.py:452),
  `runlayout.manifest_path` (:481), `runlayout._sha_file` (:474), `runlayout.new_report_run` (:376), `reporter.find_pdf_renderer`.
- Every refusal (exit 2) happens before the first delete. Keys stay git-ignored: recipe holds path + sha256 only.
- Generality: covers every exam with stored plan runs; recipe is data, no exam literal in code; unit test on a synthetic non-DGNL exam.
- Writes into line main: rebuild-reports is the user-run publish command, so it passes `--publish` internally.

## Plan modes
- None: reports are rebuilt from stored plan runs; no solve, no model call, no plan dir or cache key written. Single-source and pipeline plans unaffected.

## Design
### 105.1 Recipe schema (owner: config/published_reports.json, loader `cli._load_recipe(path)`)
```
{"version": 1, "exams": {"<exam>": {
   "line": "<source line>",          # "main" = pack straight into main; else pack on line, then publish --from line
   "view": "sheet", "pdf": true,
   "plan_runs": ["plans/<exam>/<line>/runs/<id>", ...],   # repo-relative, order = manifest plan_runs order
   "key": "input/dgnl/<file>.answer.txt", "key_sha256": "<hex>",
   "overlays": [{"dir": "plans/<exam>/<l>/runs/<id>", "printed": [64,65,66,67], "reason": "<text>"}]}}}
```
Loader: ValueError on unknown version, missing field, bad type, non-safe exam/line id (`planrun.safe_id`, `runlayout.safe_line`).
Seeded content: dgnl2025 line main; dgnl2026 line f; dhqg2024 line t81 + overlay t82/20261107-014525 printed 64-67, reason as in the manifest.
Test: test loads the tracked file, asserts 3 exams, dhqg2024 has 1 overlay with printed [64,65,66,67] and a non-empty reason (AC1).

### 105.2 Seed: `exam rebuild-reports --write-recipe [EXAM...]` (owner: cli.rebuild_reports_main)
Reads the newest main-line manifest per exam (`list_report_runs(reports, exam, line="main")`, cmd report-pack|publish):
line = `published_from` or "main"; plan_runs = manifest `plan_runs[].dir`; key/key_sha256; overlays
= `{dir, printed: [q.printed], reason}`; view; pdf = a `.pdf` exists in the run dir. Writes the whole file (indent=2,
sort_keys, trailing newline); git diff is the review. Chosen over a one-off script: reusable after the next publish.
Test: fixture with one publish manifest -> written recipe equals expected dict.

### 105.3 Pre-checks, all before any delete (owner: `_rebuild_plan(recipe, exams, plans, reports)` -> list of steps)
Per exam, refuse with `ERROR: <exam>: <reason>` exit 2 when: exam not in recipe; a plan_run dir missing or without
result.json; an overlay dir missing; key file missing; `_sha_file(key) != key_sha256`; `overlay.resolve(specs,
plan_dirs, reason)` raises; pdf true and `find_pdf_renderer()` is None. All named exams are checked before the first
exam is deleted (no half-done batch on a precheck failure).
Test: missing plan run -> exit 2, reports tree unchanged (file listing + manifests identical before/after); key with one
byte changed -> exit 2, nothing deleted (AC3).

### 105.4 Delete set + `--dry-run` (owner: `_rebuild_plan`, `_delete(step)`)
Delete set per exam: every report run of line main, plus report runs of the source line with manifest cmd
report-pack|publish; each = run dir under reports/ + its manifest (`manifest_path`). Other lines and `report` runs untouched.
`--dry-run` prints per exam: runs to delete, then the commands it will call (`report-pack ... --out <new> --publish
[--overlay ...]`, `publish <exam> --from <line> --key ...`), exit 0, writes nothing.
Test: dry-run on fixture -> exit 0, stdout names the delete set and both steps, tree byte-identical before/after (AC3).

### 105.5 Rebuild (owner: `rebuild_reports_main(argv)`, flags `[EXAM...] [--dry-run] [--write-recipe] [--recipe P] [--root DIR] [--plans P] [--reports P]`)
Per exam, after delete:
- line main: `report_pack_main(plan_runs + ["--exam", slug(exam), "--key", key, "--out",
  new_report_run(reports, exam, line="main", publish=True), "--publish", overlay args, "--no-pdf" if not pdf])`.
- other line: same with `--out new_report_run(reports, exam, line=<line>)` (no --publish), then
  `publish_main([exam, "--from", line, "--view", view, "--key", key, "--plans", plans, "--reports", reports, "--no-pdf"?])`;
  publish picks the fresh pack (the only pack left on the line) and inherits its overlays.
- After each exam: read the new main manifest; its plan_runs dirs must equal the recipe list, else exit 1 `MISMATCH`.
Prints `rebuilt <exam> main run-<id> score C/T`. Non-zero return of a reused function -> stop, exit 1 (plan runs are
intact; re-running the command recovers). Register in `cli.main` table (cli.py:1676) and the command list (cli.py:26).
Test: fixture exam (synthetic, line `x1`, 2 subjects, key, 1 overlay) -> exit 0, one main run + one x1 pack, old runs gone,
main manifest plan_runs == recipe, score line printed.

### 105.6 Docs (owner: docs/guide/report-kinds.md new `## How to rebuild reports` <=6 lines after `## Commands`; docs/guide/toolkit-reference.md one line)
Content: recipe path, `exam rebuild-reports --dry-run`, then without, `--write-recipe` after a new publish, exit 2 = nothing deleted.
Test: grep section exists and its body <= 6 lines (AC4). Main session writes docs (guard).

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| plan run / overlay dir / key missing, sha differs | exit 2 before delete | `ERROR: <exam>: ...` |
| no PDF renderer, recipe pdf true | exit 2 before delete | ERROR naming --no-pdf is not used silently |
| build fails after delete | exit 1; publish_main already removes its half run | ERROR + "re-run rebuild-reports" |
| publish selects other plan runs | exit 1 | `MISMATCH <exam>` |

## Verification (main runs; $0, no model call)
| Item | command -> expected |
|---|---|
| 105.1 | `python3 -I tools/run_tests.py --affected` -> schema test PASS |
| 105.2 | `exam rebuild-reports --write-recipe` on today's tree -> `git diff config/published_reports.json` empty vs the committed seed |
| 105.3/4 | unit tests PASS; `exam rebuild-reports --dry-run` -> 3 exams listed, `find reports plans -newer <stamp>` empty |
| 105.5 | backup first: `cp -a reports/<exam> plans/<exam>/*/report-runs work/TASK-105/before/`; run `exam rebuild-reports`; compare (below); scores 113/120, 113/120, 105/119 |
| 105.6 | grep section, `wc -l` of its body <= 6 |
Byte-identical proof (AC2): per exam, pair old/new run dirs by line; replace the exact old report run id (and old
`source_report_run`) with `RUNID` in names and contents of old files, the new id likewise in new files; then `cmp` every
`.md`/`.tsv`/INDEX.md. Exclude `.pdf` (embedded creation date; its `.md` source is compared). Manifests: compare
after dropping `created_utc`, `engine_git`, `report_run_id`, `source_report_run`. Never normalize by a date regex: plan
run ids (`20261107-005624-vietnamese`) share the shape. A stdlib compare script in work/TASK-105/ is enough (not tracked).

## Decisions
- Paths in the recipe are relative; they resolve against `--root DIR` (default: the current dir), and `--plans/--reports` default to `<root>/plans`, `<root>/reports`, so a restored backup tree can be dry-run in place (TASK-106 AC3).
- Mode derived from `line` (main = pack, else pack+publish); no `mode` field - one fewer thing to drift.
- Delete only main + source-line pack runs - deleting all report runs of the exam would drop dev experiments (t82 etc.).
- Call `*_main(argv)` in process - reuses arg checks and the publish half-run cleanup; rejected: calling build_pack directly (re-implements selection/overlay inheritance).
- `--write-recipe` over a one-off seed script - same code path, re-seeds after the next publish.

## Out of scope
Cache keys: not affected (no model query or cached rule changes). Rebuilding solve-time `report` runs.

## Defects
none
