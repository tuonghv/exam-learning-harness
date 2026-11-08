PROGRESS: COMPLETE
SKILLS: design, token-efficiency
# Phase 88 - fast test tiers (draft for docs/design/phase-88-fast-test-tiers.md)
Task: TASK-088 / REQ-0096 (AC1-AC8, Q2 = --full once per task before VERIFIED, --fast before each commit)
## Goal
Dev loop checks a change in <70 s (`--fast`) or seconds (`--affected`); the 369 s full suite runs once per task, detached, in a throwaway worktree of HEAD, result persisted by tree key and reused.
## Scanner reference (`_code-security-scanner/tests/run_worktree.sh`, `worktree_sync.py`, `run_worktree_test.sh`)
- Worktree pinned to a commit (`git worktree add --detach <root>/test-run <sha>`), root = sibling `<repo>.worktrees`, refused inside repo (exit 2). ADOPT (outside-repo rule; we use `tempfile.mkdtemp(prefix="elh-test-")`).
- Lock dir `.run.lock/pid` via mkdir, stale lock broken when pid dead, exit 3 when live. ADOPT.
- housekeeping: `git worktree prune`, drop trees > 7 days / commit gone, cap 3 kept failed trees. ADOPT prune+stale; SKIP keeping failed trees (we always remove in finally).
- `worktree_sync.py` copies git-ignored data into the tree (deny list: work/, secrets, caches). SKIP: our data tests skip cleanly when data is absent; skip count is recorded instead (88.4).
- env scrubbed (`env -u TASK -u CTXGUARD_TASK ...`, `CLAUDE_PROJECT_DIR=<wt>`). ADOPT.
- byproducts diff (`git status --porcelain --ignored` before/after). SKIP (tree is deleted).
- Result: summary line tagged `(tested @<short>)`, logs to `work/<T>/evidence/worktree-<short>`. ADOPT as JSON result file.
## Constraints
stdlib, `python3 -I`, Python 3.10 (no new unittest flags). Tests are not edited; selection is a load-time filter. Never writes in the main tree except `work/test-runs/`. `--full` command == today's `python3 -I -m unittest discover -s tests/unit` (cwd = worktree).
## Plan modes
Not affected (no engine/exam path; dev tooling only).
## Design
### 88.1 Timing report (owner: `tools/run_tests.py --time [--full|--fast]`) - AC1
TestResult subclass timing startTest/stopTest (+ setUpClass time charged to the class via a per-class clock). Writes `work/test-runs/timing-<key>.json` `{tests:{id:s}, files:{module:s}, total_s}`; prints top 15 ids, per-file totals, total, and `SUGGEST: <id>` for ids > `threshold_s` not in the slow list. Main commits a short summary (numbers only) to docs/report.
### 88.2 Registry (owner: `config/test_tiers.json`) - AC2, AC7
`{"threshold_s":2.0, "note":"measured 2026-11-08, 369 s total, see report", "slow":[ids], "known_failures":[ids], "affected_map":{"<path glob>":["test_mod",...]}, "affected_ignore":["docs/*","*.md",".claude/state/*"], "cache_ignore":[".claude/state/",  "docs/req/","docs/design/","docs/report/"]}`.
- An entry matches a test id when `id == e or id.startswith(e + ".")` (module, class or method). Seed slow = the 6 measured methods + `test_completeness_measure_pdf.Families` + `test_assembly_qa.Golden` (exact ids from 88.1 output). known_failures = the 4 ids in the brief.
- Untagged test = fast (AC5). Loader: `unittest.defaultTestLoader.discover("tests/unit")` (top = start dir, ids like `test_x.Cls.test_y`), flatten, keep by tier, rebuild `TestSuite`; `_FailedTest`/import errors always kept.
### 88.3 Fast / list (owner: `run_tests.py --fast | --list`) - AC2, AC5
- `--fast`: run kept suite in-process (TextTestRunner, cwd = repo root, `sys.path[0]=tests/unit`), print `Ran`, `FAILED/OK`, `KNOWN: n NEW: m`, `SKIPPED_SLOW: k`, duration; rc 0 iff no NEW failure/error.
- `--list`: `<tier>\t<id>` per test, then `COUNT all=A fast=F slow=S`; rc 1 if `F+S != A`, or a slow/known entry matches no test (stale registry, prints it).
### 88.4 Full gate (owner: `run_tests.py --full [--wait] [--force]`) - AC4, AC7, AC8
- key = sha256(`git ls-tree -r HEAD` lines minus `cache_ignore` prefixes + python version + RUNNER_VERSION)[:16]. State commits and design/report docs do not invalidate; config/test_tiers.json and any code/test/tool does.
- Tree = HEAD only (decision D1). Dirty tracked files outside `cache_ignore` -> warning `DIRTY: n files not in the gate (commit first)` and `dirty:n` in the result.
- Result exists with `status:"done"` and same key -> print `REUSED <file>` + its summary, rc = stored rc; no run. `status:"running"` with live pid -> print `RUNNING pid`, rc 0.
- Else parent writes `{status:"running", pid, key, head, started}` and spawns itself detached (`Popen([...,"--full","--child"], start_new_session=True, stdin=DEVNULL, stdout=work/test-runs/<key>.log)`), prints the result path, exits 0. `--wait` runs the child step in the foreground.
- Child: lock `work/test-runs/.full.lock/pid` (mkdir; break if pid dead, else exit 3); cleanup 88.5; `git worktree add --detach <mkdtemp> HEAD`; run the gate command with env minus TASK/CTXGUARD_TASK, timeout 1800 s; parse; write result; `finally`: `git worktree remove --force` + rmtree fallback + `git worktree prune` + release lock.
- Result `work/test-runs/<key>.json`: `{status:"done", key, head, rc, ran, summary:"FAILED (failures=a, errors=b, skipped=c)"|"OK...", failed:[ids], known:[ids], new:[ids], skipped:c, dirty, duration_s, cmd, worktree_removed:true}`. Parser handles 3.10 `FAIL: test_x (mod.Cls)` and 3.11+ `(mod.Cls.test_x)`. Gate pass = `new == []` (known failures reported, not counted).
### 88.5 Safety (owner: `run_tests.py`, helpers) - AC5, AC8
- Worktree path asserted outside repo root (realpath) else exit 2.
- Stale cleanup on each `--full` and `--clean`: `git worktree prune`; every `git worktree list --porcelain` entry with basename `elh-test-*` and no live lock pid -> `worktree remove --force`.
- Main tree untouched: unit test asserts `git status --porcelain` identical before/after a `--full --wait` on a scratch repo.
### 88.6 Affected (owner: `run_tests.py --affected [--base REV]`) - AC3
- Changed = `git diff --name-only <base or HEAD>` + `git ls-files -o --exclude-standard`; drop `affected_ignore` matches.
- Per file, reasons printed `<test_mod>\t<why>`: (1) `tests/unit/test_*.py` -> itself; (2) `affected_map` glob hit; (3) `src/<pkg>/a/b.py` -> dotted `pkg.a.b`: test modules named `test_b*.py`, and test files whose import lines (regex scan of `^\s*(from|import)\s`) name `pkg.a.b` or `from pkg.a import ...b...`; (4) `tools/**.py` -> test files containing the path or basename string.
- Any changed non-ignored file with no hit -> `FALLBACK --fast (<file> unmapped)`, run --fast. Empty change set -> `NOTHING CHANGED`, rc 0.
- Slow tests in the set are skipped by default and listed `SKIPPED_SLOW <id> (gate covers)`; `--with-slow` runs them (D2). Direct imports only (transitive gap is covered by the gate; documented).
### 88.7 Docs and briefs (owner: main) - AC6
Mode rule: loop = `--affected`, before commit = `--fast`, gate = `--full` once per task before VERIFIED (detached; read the result file, do not re-run).
- docs/guide/workflow-roles.md (new section "Test modes") + docs/guide/architecture.md:97 command.
- `.claude/agents/coder.md:42`, `tester.md:21,42`, `verifier.md:35`, designer.md:35 (project block: edit its generator source if `agent-setup:project` is generated), `.claude/skills/unit-test/SKILL.md:27`, `verify/SKILL.md:37`, `coding/SKILL.md:27`, workflow skill pointer, CLAUDE.md project rules line.
- NOT in scope: settings/hooks (e.g. a gate hook requiring a result file) -> needs user confirmation (opt-in blocking rule).
### 88.8 Timings (measure, do not guess)
Expected fast ~60-70 s (369 - ~300 slow). Proof: `run_tests.py --time --fast` total and `--list` counts recorded in the report; full via the result file `duration_s`.
## Failure modes
| Failure | Response | Operator sees |
|---|---|---|
| registry id stale / typo | `--list` rc 1 | `STALE <entry>` |
| new test untagged and slow | runs in fast | `SUGGEST <id>` from `--time` |
| child killed / host reboot | lock pid dead -> broken next run; status stays running w/ dead pid -> re-run | `STALE RUN <key>, restarting` |
| worktree add fails | result `status:"error"`, rc 2 | error text in json + log |
| gate timeout | kill process group, `status:"timeout"` | `TIMEOUT 1800 s` |
| dirty tree | gate on HEAD, warns | `DIRTY: n` |
| data-dependent test skips in worktree (work/ data absent) | counted in `skipped` | skipped count vs main run |
## Unit tests (`tests/unit/test_run_tests.py`, fast, scratch git repo with 3 tiny test files in a tempdir)
1 matching: module/class/method entries; untagged -> fast. 2 `--list` counts F+S==A; stale entry -> rc 1. 3 known vs new classification from canned unittest output (3.10 and 3.11 formats). 4 key: unchanged after a `.claude/state/` commit, changed after a src commit. 5 reuse: second `--full --wait` prints REUSED, no worktree created. 6 worktree removed + `git worktree list` back to 1 + main `git status` unchanged, also when the test run raises. 7 stale `elh-test-*` worktree and dead-pid lock cleaned. 8 affected: test file, src import scan, tools path string, unmapped -> FALLBACK, docs-only -> NOTHING CHANGED. 9 path outside repo assert.
## Verification
| Item | command -> expected |
|---|---|
| 88.1 | `python3 -I tools/run_tests.py --time --full` -> total ~369 s, top ids match brief |
| 88.2/88.3 | `--list` -> `COUNT` F+S==A (A=1752+new), rc 0; `--fast` -> duration < 90 s, NEW 0 |
| 88.4 | `--full` twice -> 2nd `REUSED`; json has rc, ran, known=4, new=[] |
| 88.5 | after run: `git worktree list` 1 line, no `elh-test-*` in tmp |
| 88.6 | touch one src module -> chosen tests + reasons printed |
## Decisions (best picks taken; none blocking; user RAW-00272 "best" rule)
- D1 gate tree: HEAD worktree (best; matches AC8 "committed tree", transitions are committed) - rejected `git stash create` snapshot (misses untracked files, gives a tree nobody committed).
- D2 `--affected` skips slow by default (best; productivity, gate covers) - rejected always-run (156 s on any core edit).
- D3 worktree in `mkdtemp` (best; outside repo, no ruff/compileall recursion) - rejected scanner sibling dir (extra housekeeping) and `work/` (inside repo).
## Out of scope
Hooks/settings gate enforcement (user confirmation); tests/integration; syncing ignored data into the worktree.
## Defects
- D-1 low, `.claude/scripts/checks/python.sh:26-31`: quality-check runs pytest, not the unittest command used everywhere else; unaffected here, note only.
- D-2 medium, `tests/unit/test_assembly_qa.py:114,217`: tests depend on git-ignored `work/dgnl-real/...`; they skip in the worktree gate, so `--full` (worktree) skips more than a main-tree run. Recorded as `skipped`; consider listing them as `needs_data` in the registry later.
Nova (designer)
