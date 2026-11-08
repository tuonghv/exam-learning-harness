PROGRESS: COMPLETE
SKILLS: design, token-efficiency
# Phase 91 - reports run layout 
Task: TASK-091 · REQ-0099 · Status: draft · Supersedes: phase-90 §90.8 phase 2 (report_folders map)
## Goal
Every report file lives in `reports/<exam>/<line>/run-<YYYYMMDD-HHMMSS[-N]>/` with run.json + INDEX.md; nothing sits
directly in an exam folder (AC4). Proof: reviewed dry-run (0 UNMAPPED), apply, `--verify` PASS, sha256 of every moved
file equal, `--undo` restores the tree byte for byte (tmp tree).
## Real tree facts (read-only, 2026-11-08; Glob, reports/ is git-ignored)
- 10 folders, 122 files (10 INDEX.md + 112 content files), 0 run.json, 0 run-<id> dirs, 0 loose root files.
- dgnl2026 36 (35 standard `_run-f` + INDEX; 4 result-data json carry `plan_run_id` out-* + `result_sha256`);
  dgnl2026-crosscheck 17 (16 + INDEX; registry superseded `dgnl2026-crosscheck/*`); dgnl2026f 13 (English|Math|Science|
  Vietnamese/{report.md,answers.md,report.pdf}); dgnl2026-t80 2 (answers.tsv); dgnl2025 2 (answers.tsv); dhqg2024 17
  (sheet-*/ x4 =12, solutions.{md,html,pdf} superseded `dhqg2024/solutions.*`, solutions-weasy.pdf not matched);
  dhqg2024-t81 16 (ALL-120 + 4 subjects); dhqg2024-t82 4 (Math-64-67/); cacheproof-en 9 (stamp dirs 20261107T035802Z,
  20261107T035827Z, each sheet/ x4); input-001 6 (`20261102T103714Z/` 5 files; no plans/input-001).
- plans/MIGRATION.json applied (TASK-090): plan lines dgnl2026/{f,t80,v2}, dhqg2024/{main,t81,t82}, dgnl2025/{main,..},
  cacheproof-en/main/runs/20261107-035802|035827.
## Why today's `--root reports --dry-run` is not the target
plansmigrate.py:43-46 maps 5 folders, keeps 5; :175-176 moves each child to `<exam>/<line>/<child>` (32 'file' rows =
INDEX+children of dgnl2026f 5, t80 2, t81 6, t82 2, crosscheck 17). Result: no run-<id> dir, so runlayout.py:325-331
does not see `dgnl2026/f` as a line folder (it lists as a legacy dir "f"); no run.json; the pack stays flat in
reports/dgnl2026 (AC4 fail); 5 folders unmapped in effect (AC1 fail); crosscheck loses its superseded status (glob keyed on
the old folder name, report_kinds.py:102-105); line `crosscheck` has no plan line; tree_stats hashes only plan.json (AC3).
## Constraints
os.rename inside reports/ only; no report content byte changes (INDEX.md and run.json are generated, outside the
content sha set); backup tar outside reports/; plans/ untouched; registry config/report_kinds.json unchanged.
## Generality
Any exam: map is data (config/plans_migration.json), rules use names/stamps/sha only; tests use synthetic exam ids.
## Plan modes
- report / report-pack / solve report (new runs): unchanged (already `reports/<exam>/<line>/run-<id>`, phase 90.8).
- `--out DIR`: unchanged. plans-migrate `--root plans`: unchanged (golden: its dry-run output byte-identical).
## Design
### 91.1 Target map (every folder; ids computed by --write-map, then hand-reviewed)
| old folder | target run folder | link -> run.json |
|---|---|---|
| dgnl2026 (pack) | dgnl2026/f/run-<id> | result_sha256: 4 plan runs (science vs science2 by sha) |
| dgnl2026-crosscheck | dgnl2026/f/run-<id> (Decision 2) | line f; status superseded, `superseded:[{"glob":"*"}]` |
| dgnl2026f | dgnl2026/f/run-<id>/{English,Math,Science,Vietnamese}/ | line f |
| dgnl2026-t80 | dgnl2026/t80/run-<id> | line t80 |
| dgnl2025 | dgnl2025/main/run-<id> | line main |
| dhqg2024 | dhqg2024/main/run-<id>/ (sheet-*/ + solutions*) | line main; `superseded:[{"glob":"solutions.*"}]` |
| dhqg2024-t81 / -t82 | dhqg2024/t81/run-<id>/ (ALL-120 + 4) / dhqg2024/t82/run-<id>/Math-64-67 | line t81 / t82 |
| cacheproof-en | cacheproof-en/main/run-20261107-035802, -035827 (stamp dir = one run each) | name: plan run same stamp |
| input-001 | input-001/main/run-20261102-103714 | unknown (no plans) |
- Totals: 10 folders, 11 report runs, 0 keep, 0 UNMAPPED. Line = the plan line of the same old folder name
  (plans/MIGRATION.json `folders`), else `main`.
- Run id rule: a child dir named `YYYYMMDDTHHMMSSZ`/NEW_ID = its own run, id = that stamp. Otherwise the whole old folder
  = one run, id = newest st_mtime (UTC) of its files excluding INDEX.md/run.json. Taken id in the same line (map or disk)
  -> `-2`, `-3` in old-folder name order (NEW_ID allows -N). A hand-edited id in the map wins (validated NEW_ID, unique).
- Old INDEX.md moves with its folder (split folders: into the line folder) and is regenerated after the moves.
### 91.2 Map schema (config/plans_migration.json, written by `--root reports --dry-run --write-map`)
- `report_folders` {old: {exam,line}|"keep"} (DEFAULT_REPORT_FOLDERS replaced by the table above).
- `report_runs` [{id, exam, line, from (old folder or old stamp dir), id_source mtime|name, link
  result_sha256|name|line|unknown, plan_runs [plan dir rel], plan_line, status complete|superseded, superseded
  [{glob, note}]}]; superseded seeded from registry globs `<old>/<g>` -> run-relative `<g>` with the registry note.
- `report_moves` [{old, new, kind run|file, exam, line, run}]: stamp dirs kind run (whole dir), others kind file with
  new = `<exam>/<line>/run-<id>/<child>`. Stale check compares the regenerated moves using the map's report_runs ids.
### 91.3 plansmigrate.py changes (reports section only)
- build_moves: run grouping (91.1), child == line folder holding run-<id> dirs -> skipped (rerun safe).
- tree_stats(section="reports"): sha256 of every file; INDEX.md/run.json under a target run/line folder and
  `MIGRATION.*` excluded from the content set.
- apply: baseline (all-file sha) -> backup tar (existing make_backup, map in extra) -> copy each old INDEX.md to
  `reports/MIGRATION.index/<old rel>` -> manifest applying -> renames -> rmdir emptied old folders (old != exam) ->
  run.json per run (runlayout.write_report_manifest(dir, plan_dirs, view, None, "plans-migrate", now=id time) +
  new `extra` kwarg: exam_id, migrated_from, link, plan_line, status, superseded) -> write_index each run then each
  line folder -> verify -> applied. Generated files recorded with sha in MIGRATION.json `generated`.
- undo: generated INDEX/run.json removed or restored from MIGRATION.index only when sha == recorded (else refuse that
  path), reverse renames, rmdir created dirs, recreate removed old dirs, state undone; tree == baseline.
- verify: content files: count, bytes, per-file sha at mapped path equal; every run folder has run.json + INDEX.md;
  INDEX bytes == fresh render (report_kinds.render_index); targets exist, olds gone.
### 91.4 Readers
- report_kinds.classify/superseded_note: optional `extra` globs; write_index reads `folder/run.json` `superseded`
  (split write_index -> render_index + write). No run.json superseded -> output byte-identical (golden).
- runlayout.list_report_runs/scan_report_runs: no change (run.json with empty plan_runs = layout run).
- run-list (cli.py:1445-1451): plan runs cell `line <plan_line> (run unknown)` / `unknown` when link != exact; links
  (cli.py:1395-1401) unchanged. cli.py:1377-1380 legacy old-folder scan kept (empty after apply).
- report-index on a moved path: `migrated(reports, path)` hint "moved to X", exit 2.
- check_report_pack.py: no code change; QA passes new pack path + the 4 linked plan dirs (run.json sha check applies).
- run-stats/run-compare: read plans/history only; tests prove unchanged.
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| mtime tie / taken id | -N suffix | id column in dry-run |
| result-data sha matches no plan run | link line, plan_runs [] | `link line` row + NOTE |
| hand-edited id invalid/duplicate | apply refuses before backup | REFUSED row, exit 2 |
| regenerated INDEX edited after apply | undo refuses that file | path + MIGRATION.index copy |
| rename/run.json/INDEX failure | existing rollback + remove generated | `rolled back k moves`, exit 1 |
## Unit tests (tests/unit/test_plansmigrate.py, tmp trees, synthetic exams `ex1`, `ex1-t9`, `zz-legacy`)
- id rule: mtime newest (os.utime), stamp-dir name, tie -N, map override; line from plans manifest else main.
- dry-run writes nothing; write-map shape; 0 UNMAPPED over a 10-folder fixture; flat exam folder -> run folder.
- apply: content sha equal, run.json fields (link exact via result_sha256, line, unknown), INDEX superseded rows,
  no file directly in an exam folder; apply twice no-op; injected failure -> tree == before; undo -> tree == before.
- list_report_runs sees the line folders; run-list cells; check_report_pack on a migrated pack PASS.
- goldens: plans-mode dry-run and write_index without run.json superseded byte-identical.
## Verification ($0; main runs)
| Item | command -> expected |
|---|---|
| 91.1-91.4 | `python3 -I tools/run_tests.py --fast` -> 0 failed |
| 91.1 | `exam plans-migrate --root reports --dry-run --write-map` -> 11 runs, 0 keep, 0 UNMAPPED; user reviews |
| 91.3 | `--apply --backup-dir <outside>` -> applied; `--verify` PASS: 112 content sha equal, 11 run.json, 19 INDEX (11 run + 8 line) |
| 91.4 | `check_report_pack.py reports/dgnl2026/f/run-<id> plans/dgnl2026/f/runs/<4 ids>` -> 0 FAIL; `run-list dgnl2026 --line f` 3 report runs |
## Decisions (best picks taken by main under the user's standing "best" rule; user may veto in the dry-run review)
1. Report run id = newest file mtime (best) - rejected: plan run start time (dgnl2026f, crosscheck and pack all derive
   from line f: 3 ids collide, -N order arbitrary, prev_report_run chain wrong; a report id means build time).
2. crosscheck -> dgnl2026/f, superseded via run.json (best; sits beside the pack that supersedes it) - rejected: line
   `crosscheck` (phase 90.8; no plan line, run-list --line shows no plans) and line `legacy` (status lives in INDEX).
## Out of scope
Registry edits; plans/ changes; time-based plan links; exam-level INDEX.md (none after the move).
## Defects
- DS1 medium plansmigrate.py:43-46: 5 report folders "keep" -> AC1/AC4 unmet.
- DS2 medium plansmigrate.py:175-176 + runlayout.py:325-331: reports moved without run-<id> are not seen as line folders.
- DS3 medium report_kinds.py:102-105 + config/report_kinds.json:34-35: superseded globs keyed on old folder; any move
  turns crosscheck files "standard" in a regenerated INDEX.
- DS4 low plansmigrate.py:241-242: tree_stats hashes plan.json only; AC3 needs every report file.
- DS5 low runlayout.py:416: run.json exam_id fallback = basename(dirname) = line name for a line run with no plans.
- DS6 info config/report_kinds.json:35: note cites reports/dgnl2026/ (stale after move); :34 glob misses solutions-weasy.pdf.
- DS7 info: file mtimes not read (no Bash); ids appear first in the dry-run.
Nova
