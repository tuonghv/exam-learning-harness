PROGRESS: COMPLETE
SKILLS: design, token-efficiency

# Phase 111 - cli exit codes (draft for docs/design/phase-111-<slug>.md)
Task: TASK-111 · REQ-0118 · Status: draft · Source: phase-107-review-triage.md Fix-D, work/TASK-107/handoff/design-cli.md F001/F002/F008

## Premise
- Three exit/IO bugs in `src/exam_engine/cli.py`, all confirmed against the current source (not only the review).
- Smallest fix per bug; no new flags, no new inputs, no change to any successful run's output.
- Suggested slug: `cli-exit-codes`.

## Goal
- AC1 `rebuild-reports --write-recipe` refuses (exit 2, file byte-identical) when the existing recipe is unreadable/invalid.
- AC2 `run-stats stats|compare --exam <missing|invalid>` exits 2 after the input error; no metrics printed, no history write.
- AC3 `--help` exits 0 in all 11 subcommands that catch SystemExit; an argparse usage error still exits 2.

## Constraints
- Python stdlib only; trust boundary unchanged (local files only).
- `run_stats_main` :2375 and `rebuild_reports_main` :791 already map `(OSError, ValueError)` to `ERROR: ...` + exit 2; both fixes reuse that path.
- No cache key / cached query body touched.

## Generality
CLI-generic; no exam-, subject- or language-specific literal. Tests use existing fixtures (examples/english/input-001.md, mock_english_001.json) and synthetic recipe JSON.

## Known incidents
none

## Plan modes
- solve / plan runs: not affected (no exit path touched).
- run-stats on a good run (stats, compare, trend, board, explain, gain, backfill, recheck): unchanged; only the `--exam` failure branch changes.
- rebuild-reports without `--write-recipe`: unchanged (`_load_recipe` already strict).
- `--write-recipe` with no recipe file yet: unchanged, still creates it.

## Design
### 111.1 `--help` exits 0 (owner: new `_argparse_exit` in cli.py, near `_load_exam` :359)
- Add `def _argparse_exit(exc) -> int: return 2 if exc.code else 0` (one-line docstring: argparse exits 0 on --help, 2 on a usage error).
- Exception mapper, not a parse wrapper: site :1563 (`lessons_main`) wraps parse + file read in one `try`, so a parse wrapper would not fit every site uniformly.
- At each site, change `except SystemExit:` / `return 2` to `except SystemExit as exc:` / `return _argparse_exit(exc)`:

| line | function | subcommand |
|---|---|---|
| 982 | ingest_main | ingest |
| 1090 | inspect_main | ingest-inspect |
| 1174 | refine_main | ingest-refine |
| 1284 | cross_main | cross-solve |
| 1384 | benchmark_main | benchmark |
| 1494 | genexam_main | gen-exams |
| 1563 | lessons_main | lessons |
| 1591 | extract_eval_main | extract-eval |
| 1632 | review_pack_main | review-pack |
| 1652 | review_apply_main | review-apply |
| 1681 | gold_pdf_main | gold-pdf |

- The correct inline forms at :1800 (run_list_main) and :2364 (run_stats_main) stay as they are (no churn).

### 111.2 `--write-recipe` never overwrites an unreadable recipe (owner: `_write_recipe` cli.py:660-665)
- Replace `try: old = _load_recipe(path)["exams"] except ValueError: old = {}` with:
  `old = _load_recipe(path)["exams"] if os.path.exists(path) else {}`.
- Missing file -> `{}` (create path unchanged). Present but bad JSON / failed `_recipe_check` / unreadable -> `ValueError` from `_load_recipe` :655-657 propagates before any write (:688) -> caller :791 prints `ERROR: recipe <path>: ...`, returns 2.
- Applies with and without named exams (AC1 says "refuses"); a full re-seed over a corrupt file now needs the user to restore or delete it first (see Decisions D1).
- Only caller: `rebuild_reports_main` :787.

### 111.3 `run-stats --exam` input error exits 2 (owner: `_rs_compute` cli.py:1972-1973)
- After `exam, _code = _load_exam(a.exam)` add: if `exam is None`: `raise ValueError("--exam %s: invalid or unreadable exam" % a.exam)`. `_load_exam` :359-369 already printed the `ERROR: input:` lines.
- `run_stats_main` :2375 catches it -> `ERROR: ...`, return 2. Raised before `metrics.compute` and before any print in `_rs_stats` :2026 / `_rs_compare` :2052; `stats`/`compare` write no history (only `backfill` does, which does not call `_rs_compute`).
- Plan-run copy branch :1974-1975 (no `--exam`, `input/exam.md` beside the result) keeps today's fallback (D2).

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| `<cmd> --help` | help printed, exit 0 | help text, `$?`=0 |
| `<cmd> --bogus` | usage error, exit 2 | argparse usage + error |
| corrupt recipe + `--write-recipe` | no write, exit 2 | `ERROR: recipe <path>: ...` |
| `run-stats stats DIR --exam nosuch.md` | no metrics, exit 2 | `ERROR: input: cannot read ...` + `ERROR: --exam ...` |

## Unit tests
- `test_cli_help_exit.py::test_help_exits_0_all_sites`: for each of the 11 `*_main` above, `fn(['--help'])` (stdout captured) == 0. Also assert `run_list_main`, `run_stats_main` stay 0.
- `test_cli_help_exit.py::test_bad_flag_exits_2`: same 11 with `['--no-such-flag']` == 2.
- `test_rebuild_reports.py::test_write_recipe_refuses_corrupt`: T/r.json = `{bad`; patch `cli.runlayout.list_report_runs` to one A row (as design-cli.md F001 repro); `rebuild_reports_main(['A','--write-recipe','--recipe',T/r.json,'--reports',T])` == 2; file bytes unchanged. Variant: valid JSON failing `_recipe_check` -> same.
- `test_rebuild_reports.py::test_write_recipe_merges_valid`: valid recipe with exam B + same A row -> 0, file holds A and B (guards the merge path).
- `test_rebuild_reports.py::test_write_recipe_creates_missing`: no file -> 0, file created with A.
- `test_run_stats.py::test_stats_missing_exam_exits_2`: mock solve to T/o (fixture from F002 repro), `run_stats_main(['stats',T/o,'--exam','nosuch.md','--history',T/h])` == 2, stdout empty, `T/h` has no history line. Same for `compare T/o T/o`.
- `test_run_stats.py::test_stats_good_exam_unchanged`: same run with `--exam examples/english/input-001.md` == 0 and output equal to the pre-change expectation (existing tests already cover it if present; else assert exit 0 + metrics block).
- Coder: check exact flag names (`--recipe`, `--reports`) by `--help`, not this doc.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 111.1 | `python3 -I exam.py lessons --help; echo $?` -> help, `0`; `... lessons --x; echo $?` -> `2` | free |
| 111.2 | copy recipe to scratch, write `{bad`, `exam.py rebuild-reports A --write-recipe --recipe <scratch>` -> `ERROR: recipe`, `2`, `cmp` identical | free |
| 111.3 | `exam.py run-stats stats <mock run> --exam nosuch.md --history <scratch>; echo $?` -> `2`, no history file | free |
| AC4 | `run_tests.py --affected` then `--fast` NEW 0; mock solve + `run-stats stats` on a good run: same stdout/exit old vs new | free |

## Decisions
- D1 111.2 refuse also without named exams - rejected: tolerate corruption on a full re-seed - AC1 has no exception; a deleted/restored file is a one-step recovery.
- D2 111.3 only explicit `--exam` - rejected: also raise for an invalid plan-run `input/exam.md` - AC2 names `--exam`; old plan runs whose copy fails newer validation would stop giving stats (normal-run regression). Main may widen if wanted.
- D3 111.1 exception-mapper helper - rejected: `_parse_args(ap, argv)` wrapper (does not fit :1563) and 11 inline copies (duplication).

## Out of scope
- Other 107 IMPROVEMENT rows (F010 `_jload` reuse etc.); unifying :1800/:2364 to the helper.

## Defects
- none new (F001/F002/F008 confirmed at the cited lines).

## Coordinator addendum (2026-11-15): 111.1 covers 16 entry points, not 11
Oracle `work/TASK-111/evidence/cli_oracle.py` on HEAD: `--help` returns 2 in 16 `*_main`: benchmark, cross,
extract_eval, genexam, gold_pdf, ingest, inspect, lessons, parse, refine, report_index, report, review_apply,
review_pack, run_compare, verify. The 5 not in the 11-site list (parse, verify, report, report_index, run_compare)
reach exit 2 by another path; the coder finds each path and routes it through `_argparse_exit`. AC3 = all 16
return 0 on `--help`, and a real argparse error (unknown flag) still returns 2.
Decisions: D1 accepted (a corrupt recipe blocks the re-seed too: never overwrite unread data). D2 accepted
(only `--exam` changes; plan-run exam.md copies keep today's behaviour).
