PROGRESS: COMPLETE
SKILLS: design, token-efficiency
# Phase 90 - line-based plans layout 
Task: TASK-090 · REQ-0098 (Q1-Q4 best) · Supersedes: phase-87-run-based-layout §87.1 (writer path), §87.7 ("never moved")
## Goal
New plan runs go to `plans/<exam>/<line>/runs/<YYYYMMDD-HHMMSS>[-<subject>][-N]` (line default `main`); the old sibling
folders are moved there by a reviewed, backed-up, reversible `exam plans-migrate`; history, run-list, run-compare,
run-stats and last_solved keep resolving every old path. Proof: dry-run table approved, then QA recount equal (90.7).
## Current tree facts (read-only, 2026-11-08)
- plans/: 19 folders + run-history.jsonl (158 lines) + scratch-history.jsonl. 50 plan.json, all legacy layout
  (`<folder>/<run>/`); 0 REQ-0095 `runs/`; 0 INDEX.md under plans/; 0 run.json under reports/.
- History: 50 lines carry `plan_dir`+`result_path` (abs) of exactly those 50 runs; 108 lines `result_path` into plans/regset.
- plan.json keys: exam_id (= file stem: English, e-Math, slice-pages ...; NOT the folder), plan_run_id (= old dir name),
  started_utc/finished_utc, source=solve (all 50), status done (2 stopped). No subject key: tag comes from the dir name.
- Caches: dgnl2025/cache 15, dhqg2024-t81/cache 16, -t82/cache 1 (page-* ingest caches), dgnl-window/cache 9, cacheproof-en/cache 3 (solve-*).
- Loose files in migrating folders: 76 (dgnl2025 13, -fix 6, -fix2 3, -v2 12, -noise 5, -noise2 5, dgnl2026-v2 9, dhqg2024 1, -t81 16, -t82 6).
- 19 docs files cite old plan paths (historic, never rewritten; MIGRATION.json answers them). reports/: 10 folders, legacy only.
## Proposed move table (run id = started_utc stamp + subject tag; dates 2026-11-0x)
| old folder | target | runs (old dir -> new id) |
|---|---|---|
| dgnl2025 | dgnl2025/main | out-Vietnamese 20261104-033012-vietnamese, out-English -033245-english, out-Math -033551-math, out-Science -033731-science |
| dgnl2025-fix | dgnl2025/fix | out-English 20261104-060728-english, out-Science -060956-science |
| dgnl2025-fix2 | dgnl2025/fix2 | out-Science 20261104-062141-science |
| dgnl2025-noise | dgnl2025/noise | out-Math 20261104-085845-math, out-Vietnamese -090059-vietnamese, out-English -090407-english, out-Science -090627-science |
| dgnl2025-noise2 | dgnl2025/noise2 | out-English 20261104-103812-english, out-Science -104104-science |
| dgnl2025-v2 | dgnl2025/v2 | out-Vietnamese 20261104-063756-vietnamese, out-English -064054-english, out-Math -064414-math, out-Science -064600-science |
| dgnl2026f | dgnl2026/f | out-Vietnamese 20261105-100541-vietnamese, out-English -100543-english, out-Math -100543-math, out-Science -100543-science (stopped), out-Science2 -144607-science2 |
| dgnl2026-t80 | dgnl2026/t80 | out-Vietnamese 20261106-232221-vietnamese, out-English -232448-english, out-Math -232619-math, out-Science -232816-science |
| dgnl2026-v2 | dgnl2026/v2 | out-Vietnamese 20261104-065600-vietnamese, out-English -065821-english, out-Math -065910-math |
| dhqg2024 | dhqg2024/main | out-English 20261105-104103-english, out-Math -104103-math, out-Science -104103-science (stopped), out-Vietnamese -104650-vietnamese, out-English-t79 20261106-213444-english-t79 |
| dhqg2024-t81 | dhqg2024/t81 | run-Vietnamese 20261107-005624-vietnamese, run-English -005812-english, run-Math -005940-math, run-Science -010203-science |
| dhqg2024-t82 | dhqg2024/t82 | run 20261107-014525 (no subject) |
| cacheproof-en | cacheproof-en/main | 20261107T035802Z -> 20261107-035802, 20261107T035827Z -> 20261107-035827 (exam_id = folder; cache stays) |
Loose files -> `<exam>/<line>/<name>`; dhqg2024-t81/cache, -t82/cache -> `dhqg2024/t81/cache`, `/t82/cache` (line-level ingest
caches, kept whole, no merge); dgnl2025/cache stays (it is already exam level). Emptied old folders: `os.rmdir` only.
Keep (not moved): confidence (experiment, exam_id e3-*), trial-image (exam_id "exam"), dgnl-window (slice experiment + own cache),
dgnl-retry (different exam file: Math sha 411d5a.. vs dgnl2025 864cfc..), crosssolve-070 (no plan runs), regset (own runN tree,
108 history refs), run-history.jsonl, scratch-history.jsonl. input-001 exists only in reports/ (keep).
Totals: 41 runs move (39 exam + 2 cacheproof), 9 stay; 50 history lines rewritten.
## Plan modes
- solve --real/--dry-run default out: `<exam>/<line>/runs/<id>`. `--out DIR`: unchanged. plan-import: same as solve.
- report/report-pack/solve report: `reports/<exam>/<line>/run-<id>/`. Explicit `--out`: unchanged. Cache path unchanged.
## Design
### 90.1 Layout writer (owner: runlayout.py:15-87, planrun.py:46, cli.py:42-120,467-475)
- `LINE_DEFAULT="main"`; `PLAN_ID=re(r"^(\d{8}-\d{6})(?:-([a-z][a-z0-9._-]*?))?(?:-(\d+))?$")` (NEW_ID kept for reports);
  `id_time`/`_suffix` accept PLAN_ID. `subject_tag(s)`: lowercase, `[^a-z0-9._-]`->`-`, must start with a letter, else None.
- `new_plan_run(root, exam, line=LINE_DEFAULT, subject=None, now=None)` -> claimed `root/exam/line/runs/<stamp>[-tag][-N]`
  (`_claim_dir` appends -N after the tag). `claim_run_dir(root, exam, line=..., subject=None)` passes through.
- solve/plan-import: `--line NAME` (safe_id, not runs/cache) and solve `--exam-id ID` (default exam_id_of(file), as today;
  see Decision 1); subject tag = subject_tag(file stem) when --exam-id differs from the stem, else none.
- New plan.json gets `"line"` and `"plan_exam"` keys (new runs only; migrated plan.json never touched).
### 90.2 Resolver (owner: runlayout.list_plan_runs/plan_run_dir/exam_of_plan_dir/plan_ref)
- `list_plan_runs(root, exam, line=None)`: rows `{id, dir, layout 'line'|'runs'|'legacy', line, subject, alias, plan}`;
  scans `exam/<L>/runs/*` (every child L with a runs/ dir), `exam/runs/*` (line "-"), legacy children; `alias` = plan.json
  plan_run_id when it differs from id. Sort key unchanged (`_plan_key`).
- `plan_run_dir(root, exam, run_id, line=None)`: line given -> that path; else unique hit in line dirs, then `exam/runs`,
  then legacy, then `migrated(root, exam+"/"+run_id)`; two lines hold the id -> ValueError naming them; nothing -> main path.
- `migrated(root, path)`: loads `root/MIGRATION.json` (state applied only), longest-prefix old->new on the path relative
  to abspath(root) (abs history paths and `OLD/ID` refs). `exam_line_of_plan_dir(d)`: plan.json line -> (GG, G);
  manifest entry -> its exam/line; else REQ-0095 (G, "-"). `exam_of_plan_dir` = first item.
### 90.3 plans-migrate (owner: new src/exam_engine/pipeline/plansmigrate.py; cli `plans-migrate`)
- Map `config/plans_migration.json`: `folders` {old: {"exam","line"} | "keep"} hand-written = table above; `moves`
  [{old,new,kind run|file|cache,line,subject,plan_run_id,plan_sha256}] generated by `--dry-run --write-map` (refuses
  overwrite without --force). Any child of a mapped folder not covered -> listed `UNMAPPED`, apply refuses.
- `--dry-run` (default): validate + print the move table, keep list, history lines/paths to rewrite; writes nothing.
- `--apply --backup-dir DIR` (required): (1) validate: sources exist, no symlinks, safe ids, targets unique and absent,
  same st_dev as plans root, target not under its own source; (2) baseline: file count, bytes, sha256 of every plan.json
  and of the history; (3) free space of DIR >= bytes of sources+history + 64 MiB, DIR realpath outside plans/;
  (4) tar.gz of sources+history+map -> `DIR/plans-backup-<stamp>.tar.gz`, reopen, member count and sizes == baseline,
  sha256 recorded; (5) MIGRATION.json `state:"applying"` with all moves + baseline + backup (tmp+os.replace);
  (6) per move makedirs parent (record created dirs), `os.rename`, mark done, rewrite manifest; (7) history rewrite
  (90.4); (8) rmdir emptied old folders (recorded); (9) QA check (90.7); (10) `state:"applied"`.
  Failure in 6-9: reverse renames of done moves, restore history from .bak, rmdir created dirs, `state:"rolled_back"`, exit 1.
  Rollback failure: state stays applying, print backup path + `--undo`.
- Idempotence: applied + same map sha -> "nothing to do", exit 0; applied + other map -> refuse; applying -> resume
  (new exists & old gone = done; old exists & new absent = todo; both = refuse).
- `--undo`: needs applied/applying/rolled_back-partial; checks new exists & old absent per move, renames back in reverse,
  recreates removed folders, reverse-maps history (90.4), rmdirs created dirs, `state:"undone"` (manifest kept).
- `--verify`: read-only 90.7 checks against the manifest.
### 90.4 References (owner: plansmigrate.rewrite_history)
- run-history.jsonl: copy to `.bak` (copy2), textual replace of `"<abs old>` followed by `"` or `/` -> abs new, per line;
  untouched lines byte-identical; each changed line must json-load and equal the original with mapped plan_dir/result_path;
  tmp+os.replace. Undo applies the reverse map (keeps lines appended after apply). Resolver fallback (90.2) also covers
  scratch-history, legacy history files and docs paths. Reports run.json links: 0 today; plan_ref falls back via 90.2.
  plans INDEX.md: none exist; nothing generated.
### 90.5 run-list / run-compare / run-stats (owner: cli.py:1321-1386, 1427-1450)
- `run-list EXAM [--line L]`: columns `plan run | line | subject | layout | status | model | calls | cost_usd | report runs | score`,
  rows grouped by line. Old folder name (dgnl2025-fix) -> manifest alias to exam+line, stderr note.
- Report links match on (line, id or alias); legacy reports of `reports/<old folder>` link only to the line that folder
  migrated to; report folders read: `reports/<exam>/<line>/`, `reports/<exam>/` (main), `reports/<old folder>/`.
- `_rs_plan_ref`: accepts `EXAM/ID`, `EXAM/LINE/ID`, `OLD/OLDID` (via migrated); `_rs_resolve` maps old abs result_path.
### 90.6 Cache and last_solved (owner: runlayout.cache_dir, planrun.last_solved/_already_imported)
- cache stays `plans/<exam>/cache` for every line (key = model+prompt text, replycache.py:19; path change only, key holds
  the body). last_solved/_already_imported scan all lines (list_plan_runs line=None).
### 90.7 QA (owner: plansmigrate.verify; work/TASK-090/qa/ by main)
- Before==after: file count and total bytes of plans/ (excl. MIGRATION.json, *.bak); per-plan.json sha256 at new path;
  50/50 history plan_dir+result_path exist; run-list rows (alias id, status, model, calls, cost, reports, score) per old
  folder before == `run-list <exam> --line <line>` after; 9 kept folders untouched (sha of plan.json, counts).
### 90.8 Reports mirror (owner: runlayout.new_report_run(root, exam, run_id=None, line=None), finish_report_run)
- New: `reports/<exam>/<line>/run-<id>/` (line from exam_line_of_plan_dir; report-pack: line of first plan dir);
  INDEX of run dir and of its line folder.
- Phase 2 (same task, after 90.3 applied+verified): `plans-migrate --root reports` with map section `report_folders`:
  dgnl2026f->dgnl2026/f, dgnl2026-t80->dgnl2026/t80, dhqg2024-t81->dhqg2024/t81, -t82->dhqg2024/t82,
  dgnl2026-crosscheck->dgnl2026/crosscheck; dgnl2025, dgnl2026, dhqg2024 loose legacy stay at exam level; cacheproof-en,
  input-001 keep. Own `reports/MIGRATION.json`, same backup/undo/verify; write_index of moved folders regenerated.
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| target exists / unmapped child / symlink | apply refuses before backup | table row marked, exit 2 |
| backup dir inside plans, low space, archive listing mismatch | refuse, nothing moved | reason + needed bytes, exit 2 |
| rename fails at move k | reverse k-1 renames, restore history | `rolled back k-1 moves`, exit 1 |
| crash mid-apply | manifest state applying | next --apply resumes, --undo restores |
| id in two lines | ValueError | `ambiguous: use EXAM/LINE/ID` |
| history line appended after apply | undo reverse-maps only matching paths | lines kept |
## Unit tests (tests/unit/test_runlayout.py, new test_plansmigrate.py; tmp trees, synthetic non-DGNL exam ids)
- new_plan_run: main default, --line, subject tag, -N after tag; PLAN_ID parse; list_plan_runs over 3 layouts.
- plan_run_dir: line, REQ-0095, legacy, migrated, ambiguity error. last_solved finds a run in a non-main line.
- dry-run writes nothing (tree sha equal); write-map refuses overwrite; unmapped child refused.
- apply: tree moved, counts/bytes/sha equal, MIGRATION.json shape, history rewritten + .bak, untouched lines identical.
- apply twice = no-op; injected rename failure at move 3 -> tree and history equal to before; resume from applying.
- undo -> tree, history byte-identical to before; backup inside plans / low space (patched disk_usage) refused.
- run-list old-folder alias rows == pre-migration rows; run-stats EXAM/LINE/ID and old abs path resolve.
- golden: solve --out DIR unchanged; report-index on a legacy folder byte-identical.
## Verification (all $0)
| Item | command -> expected |
|---|---|
| 90.1-90.6, 90.8 | `python3 -I tools/run_tests.py --fast` -> 0 failed |
| 90.3 dry-run | main: `exam plans-migrate --dry-run --write-map` -> 41 runs, 76 files, 2 caches, 7 keep, 0 UNMAPPED; user approves |
| 90.3 apply | main after approval: `--apply --backup-dir <outside>` -> state applied; `--verify` -> PASS |
| 90.7 | before/after counts, bytes, 50 sha, 50/50 history, run-list diff empty (work/TASK-090/qa/) |
| 90.8 phase 2 | same three steps with `--root reports` |
## Decisions
1. Solve exam folder: add `--exam-id` to solve (best; default unchanged = file stem, so `solve dgnl2025/English.md --exam-id
   dgnl2025 --line fix` lands in plans/dgnl2025/fix and the tag is english) - rejected: infer from the file's parent dir
   (silent change of every default path). Taken as the best pick by main (a CLI flag, default unchanged; user rule 'best'); user may veto.
2. migrated plan.json untouched (sha equality, check_report_pack.py:150) - aliases carry old plan_run_id.
3. cacheproof-en migrated to cacheproof-en/main (exam_id = folder, no doc refs); other non-exam folders keep. User may veto in the dry-run review.
## Defects
- DS1 medium cli.py:116,120 + planrun.py:23: plan exam folder = file stem; plan.json exam_id is the subject stem, so
  without Decision 1 `solve --line` cannot reach plans/dgnl2025/<line> (REQ AC1 gap).
- DS2 low: stamp-only ids collide (dgnl2026f 3 runs at 10:05:43; dhqg2024 3 runs at 10:41:03); the subject tag is required.
- DS3 low cli.py:1349,1359: run-list matches report links by dir name; migrated dir names differ from plan_run_id -> alias match needed (90.5).
- DS4 info: REQ AC3 names reports run.json links and plans/*/INDEX.md; real tree has 0 of each (fallback only).
- DS5 info: input-001 is not in plans/ (reports/input-001 only).
## Out of scope
Rewriting DONE docs paths; merging line caches; regset layout.
Nova
