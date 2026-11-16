# Phase 115 – Fix-G cli: empty run dir, clutter report dir, run-stats by id, write-recipe dry-run (TASK-115, REQ-0122)
Task: TASK-115 / REQ-0122. Source: phase-113-review-triage-b2.md rows 113-F001/F002/F003/F005; work/TASK-113/handoff/design-cli.md.
## Goal
Failed or dry-run CLI calls leave no new empty or partial dir; stats by run_id equals stats by dir. Proof: work/TASK-113/repro_cli.py prints the fixed lines (see Oracle).
## Constraints
Only `src/exam_engine/cli.py` changes. No change to success paths, prompts, result.json, manifests or cache keys (no cached query body touched). Stdlib only. No shell.
## Generality
CLI plumbing only; covers every exam kind; no exam literal. Tests use examples/english/input-001.md (non-DGNL).
## Known incidents
none
## Plan modes
- single-source solve (`solve_main`, plan_only): only the except at cli.py:234-236 changes, reached only when the run never got to `pw.start()` (no plan.json). Success path and failed-after-start path (plan.json kept, :229) unchanged.
- pipeline solve path: not touched (no change in engine.run, pipeline/*, report_build, report_pack, runlayout, planrun). Confirmed: triage holds.
## Design
### 115.1 F001 empty plan run dir (owner: cli.py `solve_main` :234-236)
- Change: in the `except (OSError, ValueError, _ingest_error())` at :234, before `return 2`: if `plan_only and a.out and not os.path.isfile(os.path.join(a.out, "plan.json"))`: `shutil.rmtree(a.out, ignore_errors=True)`.
- Minimal: one guard in the existing except; `a.out` was claimed by this call at :146 (plan_only means no user `--out`), so nothing user-owned is removed. `_solve_image` (:211, :217) never writes into `a.out`.
- Test (repro_cli.py §F001): tmp cwd, `solve_main([EX,'--mock','nosuch.json','--line','dev'])` -> rc 2 and `plans/input-001/dev/runs/*` is empty list (old: 1 empty dir). Plus AC1: mock-solve EX `--line dev --no-pdf` OK first, then the failing call, then `publish_main(['input-001','--from','dev'])` -> rc 0 (old: rc 2 "has no result.json").
- Risk: exceptions outside the tuple (KeyboardInterrupt, TypeError) still leave the dir - same as today; accepted.
### 115.2 F002 clutter report dir on build failure (owner: cli.py `_report_plan` :468-470, `report_pack_main` :510-525)
- `_report_plan`: in the :468 except, before `return 2`: if `not a.out and not a.rid and not os.path.isfile(runlayout.manifest_path(out))`: `shutil.rmtree(out, ignore_errors=True)`. `out` always exists here (:455 succeeded).
- `report_pack_main`: set `out = None` before the try (:510); in the :523 except: `if out and not a.out and not os.path.isfile(runlayout.manifest_path(out))`: rmtree. (`report_pack_main` has no `--report-id`, so `new_report_run` always claims a fresh dir via `_claim_dir`, runlayout.py:389.) The except also catches `overlay.resolve` :512 / `exam_line_of_plan_dir` :513 before `out` exists, hence the `None`.
- Minimal: same shape as `publish_main` :604-605; never touches `--out` or a `--report-id` reuse (runlayout.py:383-388 reuses an existing dir; removing it would lose a previous complete run).
- Test (new; repro_cli.py has no F002 case, built from the triage repro): tmp cwd, mock-solve EX `--line dev --no-pdf`, delete `result.json` of that plan run, snapshot `reports/input-001/dev/run-*`; (a) `_report_plan([plan])` -> rc 2, set of run dirs unchanged (old: one extra `run-<id>` without manifest); (b) mkdir `reports/input-001/dev/run-keep/` with file `x`, `_report_plan([plan,'--report-id','keep'])` -> rc 2, `run-keep/x` still exists (passes on old code too; it guards the fix); (c) `report_pack_main([plan,'--exam','input-001','--no-pdf'])` -> rc 2, run dirs unchanged (old: one extra).
- Risk: a build that wrote some files then failed loses them - intended (a manifest-less run is `incomplete`, no consumer, triage F002).
### 115.3 F003 run-stats by run_id drops the exam copy (owner: cli.py `_rs_resolve` :1966-1983, `_rs_compute` :1986-1997)
- `_rs_resolve` returns a 4th value `path` (the resolved dir, already computed at :1969-1979). `_rs_compute` :1987 unpacks 4; delete the re-resolve at :1990-1991 and use `path` at :1996-1997. Callers :2012, :2241, :2274 take `[0]` - unchanged.
- Minimal: reuses the resolution already done; one return value added, one unpack changed, two lines removed.
- Test (repro_cli.py §F003b): tmp cwd, mock-solve EX `--line dev --no-pdf --history H`, `rid` = last history `run_id`, plan dir `d`; `run_stats_main(['stats',rid,'--history',H,'--json'])` stdout == `['stats',d,...,'--json']` stdout, both rc 0 (old: DIFFERS 1184 vs 1299 chars). Keep §F003 (`--out` layout, `o@<ts>`): still equal (regression guard).
- Risk: low; a ref that is a dir keeps `path = ref` (:1969).
- 115.3b (in scope, user 2026-11-16) `_rs_explain` :2236-2243: same root cause (raw `d` for exam default :2237 and `calls` :2243). Change: call `_rs_resolve` first, use its `path` for the :2237 default (keep `e`/`a.exam` precedence) and :2243. Test: `explain rid` rc 0 like `explain d` (old: rc 2 "cannot read").
### 115.4 F005 --write-recipe --dry-run (owner: cli.py `rebuild_reports_main` :796-802)
- Change: after `parse_args` (:796): if `a.write_recipe and a.dry_run`: print `ERROR: --write-recipe and --dry-run cannot be combined` to stderr, `return 2`.
- Minimal: one guard before any write; no preview mode (fixed decision). Uses the file's `print ERROR / return 2` style (no `ap.error` in cli.py).
- Test (repro_cli.py §F005): copy config/published_reports.json to T/r.json, mkdir T/rep, `rebuild_reports_main(['--write-recipe','--dry-run','--recipe',T/r.json,'--reports',T/rep])` -> rc 2 and T/r.json byte-identical (old: rc 0, `"exams": {}`).
- Risk: a script using the combination now fails loudly; it was silently destructive before.
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| solve fails before start | rc 2, claimed dir removed | `ERROR: ...` |
| report/report-pack build fails (fresh dir) | rc 2, fresh dir removed | `ERROR: ...` |
| build fails with `--report-id`/`--out` | rc 2, dir kept (manifest dropped as today) | `ERROR: ...`, run listed `incomplete` |
| `--write-recipe --dry-run` | rc 2, nothing written | `ERROR: ... cannot be combined` |
## Unit tests
New `tests/unit/test_cli_fix_g_115.py`, one test per AC (115.1-115.4) from the cases above; each in a tmp cwd (`os.chdir` restored in tearDown) with stdout/stderr captured; each except 115.2(b) fails on the old src.
## Verification ($0 oracle)
| Item | command -> expected | tier |
|---|---|---|
| 115.1-115.4 | `python3 -I work/TASK-113/repro_cli.py` on new src -> `113-F001 solve rc 2 run dirs left 0`; `113-F003 ... same output`; `113-F005 ... rc 2 unchanged`; `113-F003b ... same` (old src output = work/TASK-113/repro_cli.out) | $0 |
| AC5 | `python3 -I tools/run_tests.py --fast` -> NEW 0; new test file fails on `git stash`-ed src (main runs) | $0 |
## Decisions
- 115.2 supersedes the phase-87 failure row "Build fails mid-way -> run-list incomplete" for a fresh dir only; `incomplete` remains for kill/crash and `--report-id`/`--out` reuse. test_runlayout test_87_3_failed_build_leaves_no_complete_run_json updated to expect no run.
- F002 cleanup only for a dir this call created (not `--out`, not `--report-id`) - rejected review Fix (rmtree when manifest missing at :456) - deletes a reused complete run.
- F005 usage error - rejected preview mode - new feature.
- F003 4th return value - rejected re-resolving in `_rs_compute` - duplicate logic was the bug.
## Out of scope
113-F004, F006..F010 (IMPROVEMENT, triage T).
## Open questions
- [x] Q1: include 115.3b (`explain <run_id>`)? -> yes, as AC3b (user, 2026-11-16)
## Defects
- none new (code defects are the four findings above).
