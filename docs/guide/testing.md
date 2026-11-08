# Testing modes (TASK-088, REQ-0096)

One runner, `tools/run_tests.py` (stdlib, run as `python3 -I tools/run_tests.py ...`), one registry, `config/test_tiers.json`.
Tests are never edited: tiers are a load-time filter on test ids.

| Mode | When | Command | Cost |
|---|---|---|---|
| affected | development loop | `--affected [--base REV] [--files F...] [--with-slow]` | seconds |
| fast | before each commit | `--fast` | about a minute |
| full (gate) | once per task before VERIFIED | `--full [--wait] [--force]` | ~6 min, detached |
| list | check the registry | `--list` | seconds |
| time | re-measure the slow tests | `--time [--fast]` | one run |
| clean | stale worktrees/locks | `--clean` | seconds |

## Registry (`config/test_tiers.json`)
- `slow`: test ids (module, class or method; an entry matches `id == e` or `id` starting `e.`). A test with no entry is fast (default), so a new test always runs in `--fast`.
- `known_failures`: pre-existing failures; reported as `KNOWN`, never as `NEW`. Exit code is 1 only for a NEW failure/error.
- `affected_map`: `{path glob: [test modules]}` extra source->test overrides. `affected_ignore`: globs of changed files that need no test (docs, state, inputs). `cache_ignore`: path prefixes left out of the `--full` tree key.
- `threshold_s`: `--time` prints `SUGGEST: <id>` for an untagged test slower than this.
- `--list` ends with `COUNT all=A fast=F slow=S` and exits 1 when F+S != A (or a registry entry matches no test: `STALE <entry>`).

## `--affected`
Changed = `git diff --name-only <base|HEAD>` plus untracked files, minus `affected_ignore`. Per file the reason is printed (`<test_module>\t<file>: <why>`):
test file itself (and tests importing it), `affected_map`, `src/<pkg>/a/b.py` -> `test_b*.py` by name or tests that import `pkg.a.b` (direct imports only), `tools/**.py` -> tests mentioning the path or file name.
A changed file with no hit prints `FALLBACK --fast (<file> unmapped)` and runs `--fast`. Nothing changed prints `NOTHING CHANGED`.
Slow tests are skipped (`SKIPPED_SLOW <id> (gate covers)`) unless `--with-slow`. Transitive imports are not followed; the gate covers that gap.

## `--full` (gate)
Runs `python3 -I -m unittest discover -s tests/unit` in a throwaway detached worktree of HEAD (`mkdtemp` outside the repo), in the background; the main tree is not touched.
- Result `work/test-runs/<key>.json`: `status, key, head, rc, ran, summary, failed, known, new, skipped, dirty, duration_s, cmd, worktree_removed, gate_ok`. Raw output `<key>.out`.
- `key` hashes `git ls-tree -r HEAD` (minus `cache_ignore` prefixes), the Python version and the runner version: state commits and design/report docs do not change it, code, tests and the registry do. An unchanged key prints `REUSED <file>` instead of running; read the file, do not re-run.
- Only committed files are gated: uncommitted tracked changes print `DIRTY: n files not in the gate (commit first)`.
- Gate passes when `new == []` (exit 0). Data-dependent tests that need git-ignored `work/` data skip in the worktree; the `skipped` count is recorded.
- One run at a time (`work/test-runs/.full.lock/pid`; a dead pid is broken, a live one exits 3). Stale `elh-test-*` worktrees are removed on each run and by `--clean`; the worktree is removed in `finally`.
