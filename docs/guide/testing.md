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

## Measured timings (2026-11-08, AC1; `python3 -I tools/run_tests.py --time`)
Full suite 1752 tests = 368.8 s at measurement time (today 1789 tests, gate 367.8 s). Six tests cost ~300 s; the other ~1,740 cost ~60 s together.
| Seconds | Test | Tier |
|---|---|---|
| 156.3 | test_window_golden.TestIngestGolden.test_existing_pdfs_unchanged_but_cut_warnings | slow |
| 49.5 | test_ocr_respace.TestOcrFamilies.test_glued_tokens_per_page | slow |
| 27.2 | test_ocr_respace.TestOcrFamilies.test_respacing_beats_bridge_text_with_vie | slow |
| 26.7 | test_completeness_measure_pdf.Families.test_chain_ocr_runs_on_a_scanned_family | slow |
| 20.8 | test_completeness_measure_pdf.Families.test_window_oracle_whole_questions_no_orphans | slow |
| 19.4 | test_completeness_measure_pdf.Families.test_chain_vision_mock_replies_all_families | slow |
Per file: test_window_golden 156 s, test_completeness_measure_pdf 77 s, test_ocr_respace 77 s, test_assembly_qa 9.5 s. Measured wall times: `--fast` about 50 s, `--affected` seconds, `--full` about 6 min in the background (a repeat on an unchanged tree prints REUSED). Counts: `--list` gives all = fast + slow (1789 = 1769 + 20); a plain grep of `def test` finds 1786 because some tests are generated at load time, so use `--list`.
Mutation proofs of the runner tests (3): dropping `_FailedTest` from the tier filter fails 1 test; removing the `cache_ignore` filter in `tree_key` fails 2; making `tier_of` always return fast fails 6.
