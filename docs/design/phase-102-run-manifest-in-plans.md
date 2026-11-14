# Phase 102: run manifest under plans, no run.json in report runs
Task: TASK-102 · REQ-0109 (RAW-00316/317/318) · Supersedes: phase-87 run.json-in-folder, phase-101 §101.5 run.json exception

## Goal
- A report run `reports/<exam>[/<line>]/run-<id>/` holds only .md/.pdf/.tsv + INDEX.md; `find reports -name run.json` = 0.
- Same manifest dict (keys unchanged) lives at `plans/<exam>[/<line>]/report-runs/run-<id>.json`; every reader goes through one runlayout helper.

## Plan modes
- solve (no --out), report, report-pack, publish: manifest path changes only; build output byte-identical except no run.json.
- explicit `report --out DIR`: manifest beside DIR (102.1 rule b), never inside it. Plan runs / solve cache: unaffected.

## Design
### 102.1 manifest location + helpers (owner runlayout.py:17-23, 446-486)
- `REPORT_RUNS = "report-runs"`; reserved: `safe_line` (runlayout.py:77), `line_dirs` (:138), `list_plan_runs` legacy loop (:337).
- `manifest_path(report_dir) -> str`: (a) nearest ancestor `R` with basename `reports` -> `<dirname(R)>/plans/<dirname(rel)>/report-runs/<basename>.json`, rel = relpath(report_dir, R) (same sibling rule as plansmigrate.py:285); (b) no such ancestor -> `<dirname(report_dir)>/<basename>.run.json` (sibling, outside the run folder).
- `read_report_manifest(report_dir) -> dict|None` (= `_jload(manifest_path(..))`); `drop_report_manifest(report_dir)` (unlink, missing ok).
- `write_report_manifest` (:480): path = `manifest_path`, `os.makedirs(dirname, exist_ok=True)`, tmp + `os.replace` as now. Returns dict unchanged.
- `RUN_JSON` stays only as the legacy name for the migration (102.4) and the guard in 102.5.
### 102.2 half-built detection (owner scan_report_runs runlayout.py:404-408, new_report_run :352-356, cli.py:581)
- Rule unchanged in meaning: a `run-<id>` dir is `run` iff its manifest is readable; dir without manifest = `incomplete`; unreadable = `warn`. Manifest is still written last (finish_report_run :493, after the build), so a crash leaves `incomplete`.
- New: `new_report_run` with a given run_id (dir reuse, overwrite) calls `drop_report_manifest` first, so a rebuild in progress is not seen as complete with the old manifest.
- publish error path cli.py:581 tests `os.path.isfile(manifest_path(out))`; cli.py:586 uses `read_report_manifest(out)`.
- Orphan manifest (run folder deleted by hand): ignored by every scanner (they iterate report dirs); no cleanup.
### 102.3 INDEX.md provenance (owner report_kinds.py:97-104, 212-222, 262-265)
- `run_superseded(folder)` and `_manifest_lines(folder)` read `runlayout.read_report_manifest(folder)`; header lines (Plan runs / View / Registry) byte-identical.
- render_index: drop the `RUN_JSON` skips (:262 `rel in (...)`, :264-265) and `_generated_run_json` (:236-243): after migration a run.json in a report folder is a stray file and shows as `unregistered` (visible, not hidden).
### 102.4 one-shot migration (new `exam report-manifests-migrate [--reports reports] [--apply]`, cli.py:1633 table; logic `runlayout.migrate_run_json(reports_root, apply=False) -> (moves, problems)`)
- Walk reports_root; each `run.json` in a dir whose parent dir name starts `run-` and that parses as a dict with a `plan_runs` list -> move to `manifest_path(dir)`.
- Target missing: `os.replace` (same filesystem, no copy). Target exists, same sha256: remove source. Different sha: problem, nothing moved for that run, exit 2.
- After moves: `rk.write_index` of each touched run folder, its parent and (line folder) the exam folder - text must not change (assert in test).
- Dry run (default) prints `N to move, M already migrated, K problems`; second `--apply` -> `0 to move` (idempotent). Covers `run-key-baseline` style ids (basename rule, no NEW_ID needed).
- No reader fallback to in-folder run.json (D2). Instead `scan_report_runs` sets `warn="unmigrated"` when `<dir>/run.json` exists and no plans manifest; `_publish_selection` (cli.py:514) raises `ValueError("... run exam report-manifests-migrate --apply")` on such a run, so publish never silently drops to "latest per subject".
### 102.5 plans-migrate (owner plansmigrate.py:34, 718-772, 775-798, 827-850)
- `_gen_targets` keeps kind `run.json` with key `<run dir>/run.json`; `_generate`/`_stash`/`_unwind_generated`/check resolve that kind via `runlayout.manifest_path(_abs(root, d))` (outside the reports root), not `_abs(root, rel)`. Check "run.json per run" uses `read_report_manifest`.
- GEN_NAMES keeps `RUN_JSON` so legacy trees still exclude old run.json from the content set.
### 102.6 writers (owner report_pack.py:3,228,242; cli.py:332,416,446-449)
- report_pack :228 drop `RUN_JSON` from the exclusion (nothing to skip); docstring :3 "provenance is the plans manifest". cli.py:446 comment/help text: "manifest beside --out"; :416 help "... with its manifest under plans/".
- `_rl_score` cli.py:1453-1460: `read_report_manifest(d).get("score")`, old score-summary fallback kept (TASK-101 D1).
### 102.7 checker (owner tools/check_report_pack.py:104-137, 123, 206-207)
- Standalone (no exam_engine import): add `manifest_path(pack)` copy of rule 102.1 (a)/(b); test asserts both agree.
- :123 exclude only `INDEX.md`; so "json/log files in pack" (:207) = 0 with no exception (a run.json in a pack FAILs).
- :105, :125-137 read the manifest from `manifest_path(pack)`; new row `run manifest present` exp True (FAIL when missing). Row names `run.json ...` renamed `manifest ...`.

## Readers impact
| Reader | Path | Change |
|---|---|---|
| publish / _publish_selection | cli.py:514-586 | via scan rows + 102.2/102.4 guard |
| run-list, _rl_score, pubs status | cli.py:1453, 1531-1581 | scan rows; _rl_score helper; WARN text `manifest` |
| run-compare | cli.py:1622 | none (plan runs only) |
| report-index, runs_table, lines_table | report_kinds.py:212,246; runlayout.py:505-549 | via helper / scan rows |
| plan_ref, legacy_plan_link | runlayout.py:366,525 | none |

## Tests (tests/unit; ~84 refs in 16 files, main ones test_runlayout 31, test_plansmigrate 11, test_report_kinds 8, test_overlay 8, test_publish_badge 6)
- Fixtures: tmp `reports/` + sibling `plans/`; replace `join(run, "run.json")` reads/writes with `runlayout.manifest_path`/`read_report_manifest`.
- New: manifest_path rule (a) line, exam-level, non-NEW_ID id; rule (b) outside reports; reserved `report-runs` line rejected and not listed as plan run.
- New: finish_report_run leaves the run folder with only report files + INDEX.md (AC1); manifest dict keys unchanged.
- New: dir without manifest = incomplete; reuse id drops old manifest; publish failure removes the half-built folder.
- New: migrate dry/apply/re-apply (0), same-sha target -> source removed, diff-sha -> problem exit 2, INDEX.md text unchanged.
- New: unmigrated in-folder run.json -> scan warn + publish ValueError.
- New: checker FAILs on a run.json in the pack and on a missing manifest; checker/runlayout manifest_path agree.
- Golden: INDEX.md header of a run equal before/after migration.

## Verification (main runs; $0, no model call)
| Item | Command -> expected |
|---|---|
| 102.4 | `python3 -I exam.py report-manifests-migrate` -> 23 to move, 0 problems; `--apply`; re-run -> 0 to move |
| AC1 | `find reports -name run.json \| wc -l` -> 0; `ls plans/*/*/report-runs/*.json \| wc -l` -> 23 |
| 102.4 guard | publish dry check on a temp copy with one run.json put back -> ValueError text |
| AC3 | `publish dgnl2026 --from f --publish`, `publish dhqg2024 --from t81 --publish` -> "pack run-<id>" source found (not "latest per subject"), score line |
| 102.7 | `python3 -I tools/check_report_pack.py <new main run> <plan dirs>` -> 0 FAIL, "json/log files in pack 0" |
| 102.3 | new run INDEX.md has Plan runs / View lines; `run-list dgnl2026` shows score + published runs |
| tests | `python3 -I tools/run_tests.py --fast`, then main `--full` |

## Risks
- New code before migration: all old runs read `incomplete` -> mitigated by 102.4 unmigrated warn + publish refusal; run migration in the same verification step.
- Rule (a) keys on a dir named `reports`: a custom `--reports` root not named so uses rule (b) sibling files inside that root's line folder. Acceptable (outside the user's reports/); documented in help.
- plans-migrate undo of an old migration now removes manifests under plans/ -> covered by test_plansmigrate.
- No solve cache key or prompt body touched.

## Newer features kept
- TASK-101: no metrics/result-data/score-summary json, no run.log; score stays in the manifest `score`, run-list fallback kept.
- TASK-100: date run names `run-YYYYMMDD-HHMMSS` (cli.py:574) unchanged; manifest file named after the run folder.
- TASK-099: public report default untouched.

## Decisions (coordinator 2026-11-14: recommendations taken, all follow the user rule RAW-00317/318)
- D1 location: `plans/<exam>[/<line>]/report-runs/run-<id>.json` (recommended: next to the line's `runs/`, mirrors reports path) - rejected `plans/report-runs/<exam>/...` (looks like an exam id to plan scanners), one jsonl index (rewrite races).
- D2 fallback: none; unmigrated in-folder run.json -> warn + publish refusal (recommended) - rejected read fallback (keeps two sources of truth).
- D3 migration entry: new small `report-manifests-migrate` (recommended) - rejected extending plans-migrate (map/MIGRATION.json/undo lifecycle overhead for a pure move).

## Out of scope
- Plan-run files under plans/ (result.json, run.log, history); report kinds registry.

## Defects
- none
Nova
