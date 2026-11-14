# Phase 103: plans-migrate reports map under plans
Task: TASK-103 (REQ-0110 AC1, AC2) · Supersedes: phase-91 map/stash location (reports/MIGRATION.json, reports/MIGRATION.index/)

## Goal
- reports/ holds only md/pdf/tsv/html + INDEX.md. Today the last machine files: reports/MIGRATION.json (state applied, 94 `orig` refs to `MIGRATION.index/...`) and reports/MIGRATION.index/ (11 INDEX.md stash copies; exists). Glob found no other json/png/log/txt under reports/.
- Proof: `find reports -type f ! -name '*.md' ! -name '*.pdf' ! -name '*.tsv' ! -name '*.html' | wc -l` = 0, and plans-migrate --verify/--undo of the reports root work from the new place.

## Plan modes
- plans root (`--root plans`): map stays plans/MIGRATION.json; only change = it skips the new `MIGRATION.reports.*` siblings (103.4). Reports root: map + stash relocated. No solve/eval/cache key touched.

## Design
### 103.1 location helpers (owner runlayout.py:23, next to manifest_path :451-465)
- `migration_map_path(root) -> str`: basename(abspath(root)) == "reports" -> `<parent>/plans/MIGRATION.reports.json`; else `root/MIGRATION.json`. Same sibling rule as manifest_path(a) and plansmigrate.section_of :57 (no `--plans-root` dependence, so readers without that flag agree).
- `migration_stash_dir(root) -> str`: reports -> `<parent>/plans/MIGRATION.reports.index`; else `root/MIGRATION.index`.
- `legacy_migration_files(root) -> [abs paths]`: reports root only: existing `root/MIGRATION.json`, `root/MIGRATION.index` (else []).
- Stored manifest strings unchanged: `generated[].orig` stays `MIGRATION.index/<rel>` (logical, root-relative); resolver `plansmigrate._stash_abs(root, orig)` = join(migration_stash_dir(root), orig[len(STASH)+1:]). The real map needs no rewrite.
### 103.2 plansmigrate uses the helpers (owner plansmigrate.py)
- Map: :600 dry_run, :680 _save, :869 verify, :928 apply, :1075 undo, :1168 main -> `runlayout.migration_map_path(root)`; messages :1077/:1170 print that path instead of "MIGRATION.json in root".
- Stash: :748-755 _stash dst, :788 _unwind copy source, :797 stash removal, :1095 undo hint -> `_stash_abs` / `migration_stash_dir`. `os.makedirs(parent)` before _dump_atomic (plans/ may not exist in tests).
- Legacy guard: dry_run, apply, verify, undo on a reports root with `legacy_migration_files(root)` non-empty -> `ERROR: old map at reports/MIGRATION.json[ + MIGRATION.index/]; run exam report-manifests-migrate --apply` exit 2 (found, never ignored; no read fallback, same as phase-102 D2).
### 103.3 runlayout readers (owner runlayout.py:143-146 _manifest)
- `_manifest(root)` reads `migration_map_path(root)`. Covers migrated_run_dirs :190 (report-index moved hint, cli.py:624), folder_alias :207, migration_folders :214. exam_line_of_plan_dir :230 probes `MIGRATION_JSON` exact name -> plans/MIGRATION.reports.json never matched (keep).
### 103.4 plans side ignores the new siblings (owner plansmigrate.py:141 build_moves loop, :451 _is_skipped)
- build_moves: `name.startswith("MIGRATION.")` -> keep (else plans/MIGRATION.reports.index = "UNMAPPED folder", plans dry-run exit 2).
- _is_skipped plans: `rel.startswith("MIGRATION.")` (superset of MIGRATION.json) so plans --verify counts stay equal to the baseline taken before the move.
### 103.5 one-shot move (owner runlayout.migrate_run_json :523 + cli.py:599-616 report-manifests-migrate; reuse, no new command)
- New `runlayout.migrate_migration_map(reports_root, apply) -> (moves, problems)`, called by report_manifests_migrate_main after migrate_run_json; rows printed `moved|would move src -> dst`, counted in the summary.
- Map: target missing -> makedirs + os.replace; target equal sha -> source removed; target differs -> problem, nothing moved.
- Stash: per file, same three cases (os.replace into the stash tree), then rmdir empty legacy dirs bottom-up. Map moved only after the whole stash moved OK (map is the index to the stash). Idempotent: re-run -> 0 to move.
### 103.6 leftover check (owner cli.py:599-616 same command)
- `runlayout.reports_leftovers(reports_root) -> [rel]`: files not ending .md/.pdf/.tsv/.html (skip symlinked dirs). Printed `LEFTOVER: <rel> (machine file in reports/)` to stderr; dry run and apply both; any leftover -> exit 2. tools/check_report_pack.py:139 already FAILs json in a pack (102.7), unchanged.

## Readers impact
| Reader | Path | Change |
|---|---|---|
| plans-migrate dry/apply/verify/undo (reports) | plansmigrate.py:600,680,869,928,1075,1168 | helper path + legacy guard |
| report-index moved hint | cli.py:624 -> runlayout.py:190 | via _manifest |
| run-list alias / list | cli.py:1546,1559 (plans root) | none (plans root keeps MIGRATION.json) |
| plans dry-run/verify | plansmigrate.py:141,451 | skip MIGRATION.* |

## Tests (tests/unit)
- test_plansmigrate.py reports fixture (:791-969): asserts on `join(self.rep, "MIGRATION.json")` :937 and `MIGRATION.index` :921,:969 -> new paths under the sibling plans/; add assert reports tree has no MIGRATION.* after apply and after undo.
- New: helper rule (reports vs plans root, custom root name); legacy map present -> dry_run/apply/verify/undo exit 2 with the move hint; apply -> undo round trip restores stashed INDEX.md from plans/MIGRATION.reports.index (bites if _unwind reads the old place).
- New: plans dry-run with plans/MIGRATION.reports.json + .index present -> 0 unmapped, tree_stats unchanged.
- New migrate_migration_map: dry (nothing written) / apply / re-apply 0 / equal-sha source removed / differing -> problem exit 2, stash moved before map; reports_leftovers flags a stray .json, ignores md/pdf/tsv/html.

## Verification (main; $0, no model call)
| Item | Command -> expected |
|---|---|
| 103.5 | `python3 -I exam.py report-manifests-migrate` -> would move 1 map + 11 stash files, LEFTOVER rows for them; `--apply`; re-run -> 0 to move, 0 LEFTOVER, exit 0 |
| AC1 | the `find reports -type f ! -name ...` above -> 0; `ls plans/MIGRATION.reports.json plans/MIGRATION.reports.index` ok; sha of moved map = old sha |
| 103.2 | `python3 -I exam.py plans-migrate --root reports --verify` -> 0 failed (same as before the move); `--root reports --dry-run` reads new map |
| 103.4 | `python3 -I exam.py plans-migrate --verify` (plans) -> 0 failed; `--dry-run` 0 unmapped |
| undo | scratch copy (tmp reports+plans) apply -> undo -> tree equal; never on the real tree |
| tests | `python3 -I tools/run_tests.py --fast`, main `--full` |

## Risks
- Verify on the real reports map before the move hits the legacy guard -> by design; run 103.5 first.
- plans/ gains 2 entries; any other plans scanner listing top-level dirs: solver.py:36, planrun.py:232 -> coder checks they filter by exam/run shape (dotted name fails `_safe`?) and adds the MIGRATION. skip if not.
- Cross-device os.replace (reports, plans same repo fs) -> OSError reported as problem, nothing lost (copy-free move).

## Newer features kept
- TASK-102: run manifests at plans/<exam>[/<line>]/report-runs/ and report-manifests-migrate unchanged; same sibling rule.
- TASK-101: no new json/metrics in reports; html fallback counted human-readable.

## Decisions (coordinator 2026-11-14: recommendations taken, consistent with TASK-102)
- D1 names: `plans/MIGRATION.reports.json` + `plans/MIGRATION.reports.index/` (rec) - rejected `plans/reports-migration/` (looks like an exam folder to scanners), reusing plans/MIGRATION.json (clash).
- D2 old map: hard error with move hint, no read fallback (rec, matches 102 D2) - rejected silent fallback read.
- D3 move entry: extend report-manifests-migrate (rec, existing one-shot) - rejected new plans-migrate `--move-map` mode (new flag, lifecycle).
- D4 leftover check: in report-manifests-migrate, exit 2 (rec) - rejected in report-index (per-folder, misses root files).

## Defects
- none (content). Note: plansmigrate.py:451 plans _is_skipped would count the new siblings without 103.4.
