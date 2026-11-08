PROGRESS: COMPLETE
SKILLS: design, token-efficiency
# Phase 94 - main is the published line 
Task: TASK-094 · REQ-0101 AC1-AC5 · Q1-Q3 answered best (RAW-00286)
## Goal
`plans|reports/<exam>/main` change only on an explicit publish: writes into main without `--publish` exit 2 with a hint; `exam publish EXAM --from LINE` builds a NEW main report run ($0) from a dev line; run-list and the exam INDEX.md show main as `published`, other lines as `dev`. Proof: 94.1-94.8 rows; DGNL 2026 + DHQG 2024 published from f / t81.
## Constraints
- Default line stays `main` for reading (run-list, last_solved, plan_run_dir). No change to result.json, cfg, cache keys (cache_dir is per exam, line-agnostic, runlayout.py:91: a main re-solve reuses the dev cache).
- Protected roots = realpath(<repo>/plans), realpath(<repo>/reports) (repo = 4x dirname of runlayout.py). Tests chdir to tmp (29 files, ~115 call sites write tmp/plans/<exam>/main): exempt by root, zero test edits.
- plans-migrate (apply/undo/verify) never calls new_plan_run/new_report_run (plansmigrate.py:764 uses write_report_manifest): stays unguarded.
## Generality
All exam kinds; no exam/subject literal in code; line name `main` = existing LINE_DEFAULT.
## Known incidents
none
## Plan modes
- real/mock without --out: write plans/<exam>/<line> + reports -> guarded. dry-run: writes nothing -> never guarded. --out DIR: guarded only if DIR resolves inside a protected root's `main` (or legacy no-line) area.
## Design
### 94.1 Guard (owner: runlayout.require_publish, new, after safe_line)
`require_publish(line, publish, what, root)` -> None or raises `PublishRequired(ValueError)`.
- root realpath not under a protected root -> return (tmp/test/other cwd).
- line None: derive from path: rel = relpath(realpath(root), protected); parts[1] if len>=2 else None (--out paths).
- main-equivalent: line in ("main", None, "-") (legacy reports/<exam>/run-x counts as main, cli.py:1380). Dev line -> return.
- publish True -> return. Else raise: "<what>: line 'main' of <exam> is the published line; tests/experiments use --line <name> (e.g. --line v3); pass --publish only when the user asked for a main run."
Callers already map ValueError to "ERROR: ..." + exit 2 (cli.py:81,137,424,463,508).
### 94.2 Entry points call the guard
- runlayout.new_plan_run(..., publish=False) :230 and new_report_run(..., publish=False) :307 call require_publish(line, publish, "new plan run"/"new report run", root) before mkdir.
- planrun.claim_run_dir(..., publish=False) :46 and import_dir(..., publish=False) :260 pass it through.
- cli: `--publish` (store_true) on solve :43, report (_report_plan :404), report-pack :449, plan-import :496; threaded to the calls at :135, :324 (_build_default_report gets a.publish), :423, :458, :504.
- Early check in solve_main after the mode check (:106), before the "already solved" prompt: plan_only -> require_publish(a.line, a.publish, "solve", DEFAULT_OUT_ROOT); a.out -> require_publish(None, a.publish, "solve --out", a.out). _report_plan/report-pack with --out: require_publish(None, publish, cmd, out).
- `--publish` on a dev line: no-op. Default `solve X --mock M` at repo root -> exit 2 with the --line hint.
- Exempt (no call): run-list, run-compare, run-stats, report-index, plans-migrate (moves history by the reviewed map, backup + --undo), report RESULT.json --out (legacy free path), all tmp roots.
### 94.3 exam publish (owner: cli.publish_main, new; COMMANDS :23 + dispatch :1478)
`exam publish EXAM --from LINE [--view sheet|learn] [--run NAME] [--key FILE] [--no-pdf] [--plans DIR] [--reports DIR]`
- Refuse (exit 2): LINE == main; safe_line fails; no plan runs in LINE; a selected plan dir without result.json.
- Selection (see D1): plan runs of LINE's latest complete `report-pack`/`publish` run.json in reports/<exam>/LINE whose plan_runs all lie in LINE and exist; else latest plan run per subject tag (list_plan_runs(root, exam, line=LINE), last per `subject`). Print the chosen list before building.
- Build: out = new_report_run(reports, EXAM, line="main", publish=True); report_pack.build_pack(plans, out, exam=EXAM, run=--run or LINE, key, pdf, view, cmd="publish", extra={"published_from": LINE, "source_report_run": <id or null>}). Plans stay in LINE; run.json plan_runs keep line=LINE; prev_report_run links the earlier main run (write_report_manifest :429). Earlier main runs untouched (fresh _claim_dir id).
- build_pack gains view="sheet", cmd="report-pack", extra=None, passed to report_build.build :130 and finish_report_run :171 (finish_report_run gains extra=None -> write_report_manifest(extra=)). Defaults keep current report-pack byte-identical.
- --key: default = `key` recorded in the source run.json (new: report-pack/publish record extra {"key": repo-rel path, "key_sha256"}); old packs lack it -> pass --key (see D3).
### 94.4 solve --line main --publish (no new code beyond 94.2)
New plan run id in plans/<exam>/main/runs, report into reports/<exam>/main; cache hits cost $0; non-tty still needs --yes.
### 94.5 run-list + exam INDEX (owner: cli.run_list_main :1439/:1450, runlayout.lines_table new)
- Plan table: new column `publish` after `line` = published (line main or "-") | dev. Report table: add `line` and `publish` columns. Existing `status` column (plan status) kept (D2).
- `lines_table(exam_folder)`: | Line | Publish | Report runs | Latest |, main first, then dev lines sorted. render_index (report_kinds.py:207) appends it for an exam folder holding line dirs; finish_report_run :454 also rewrites reports/<exam>/INDEX.md when the run sits in a line folder.
### 94.6 Docs (main writes)
workflow-roles.md §12 "Lines: main is published": tests/experiments always `--line <dev>`; main only when the user asks; publish = `exam publish EXAM --from LINE` ($0); real main re-solve = `solve --line main --publish`. toolkit-reference + report-kinds.md:45: publish entry, --publish flag, run-list publish column.
### 94.7 First publication (main, after VERIFIED code)
`exam publish dgnl2026 --from f --key <dgnl2026 key>` and `exam publish dhqg2024 --from t81 --key <dhqg2024 key>`: new main runs, $0; dhqg2024/main/run-20261105-110545 kept. Kinds/files equal source packs f/run-20261108-061114, t81/run-20261108-061132 (same --run name -> same file names).
### 94.8 Tests (tmp roots; patch runlayout.PROTECTED_ROOTS to the tmp roots for guard cases)
## Failure modes
| Failure | System response | Operator sees |
| --- | --- | --- |
| write to main w/o --publish | exit 2, nothing created | ERROR + --line/--publish hint |
| publish --from main | exit 2 | "LINE must be a dev line" |
| duplicate pack subject (science/science2) | build_pack ValueError, exit 2; empty claimed run dir removed | chosen list + error |
| key missing on old pack | pack without score files | WARN "no key: score files skipped; pass --key" |
| plans/ symlinked | realpath compare | guard still applies |
## Unit tests
- guard: main+no publish raises; publish ok; dev ok; None/"-" = main; tmp root (unpatched) exempt; --out inside protected main refused, outside ok.
- solve mock at protected root w/o --line -> 2, no dir; with --line v3 -> 0; --line main --publish -> 0 new id; dry-run -> 0. plan-import/report/report-pack same pattern.
- plans-migrate apply into main under patched roots still passes.
- publish: new reports/<exam>/main/run-<id>, run.json cmd=publish, published_from=LINE, plan_runs line=LINE; earlier main run bytes unchanged; LINE==main -> 2; empty line -> 2; selection from latest pack vs fallback.
- run-list publish column (main/"-" published, f dev); exam INDEX.md lists main first. Existing report-pack golden unchanged.
## Verification
| Item | command -> expected | tier |
| --- | --- | --- |
| 94.1/94.2 | `python3 -I scripts/exam.py solve examples/<x>.md --mock <m> --no-pdf` at repo root -> exit 2, hint; no new plans/ dir | $0 |
| 94.3 | `exam publish dgnl2026 --from f --no-pdf --plans <tmp copy>` -> run.json published_from f | $0 |
| 94.5 | `exam run-list dhqg2024` -> main rows `published`, t81 `dev` | $0 |
| 94.7 | `python3 -I tools/check_report_pack.py <main run> <plan dirs> --key K` PASS; kinds == source pack | $0 |
| 94.8 | `python3 -I tools/run_tests.py --fast`, main `--full` | $0 |
## Decisions (best picks taken; answer keys: DGNL 2026 = input/dgnl/De-thi-minh-hoa-2026-Final.answer.txt, DHQG 2024 has none) (best, from Q1-Q3)
- Guard scope by protected root (best) - env var or editing ~115 test calls (rejected: invasive).
- Selection from LINE's latest pack, fallback latest per subject (best) - pure latest-per-tag (breaks dgnl2026/f).
- --run default = LINE (file names equal the source pack) - "main" (loses diff-ability).
## Out of scope
Changing LINE_DEFAULT; moving plan runs into main; tools/check_report_pack.py (read-only, unchanged).
## Defects
- D1 (high, brief rule): plans/dgnl2026/f/runs has both `-science` and `-science2`; "latest plan run per subject" picks both -> build_pack :138 duplicate subject error. Fixed by the 94.3 selection.
- D2 (low): run-list already has a `status` column (plan status, cli.py:1439); new column named `publish`.
- D3 (medium): run.json does not record the --key file (report_pack.py:125); 94.7 needs the key paths from main (TASK-093 notes).
- D4 (medium): new_report_run(line=None/"-") writes reports/<exam>/run-x, which run-list counts as main (cli.py:1380); guard treats it as main.
- D5 (low): build_pack hardcodes view "sheet" and cmd "report-pack" (report_pack.py:130,171); publish --view learn needs rk.expected to hold for learn - coder must confirm, else restrict --view to sheet.
Nova
