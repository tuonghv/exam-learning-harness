# Phase 113 – CLI logic review, batch 2 (src/exam_engine/cli.py)

## Findings

### F001 – [MEDIUM] solve claims the plan run dir before its inputs are checked

- File: src/exam_engine/cli.py
- Lines: 143-147, 211, 216-217, 234-236
- Issue: `claim_run_dir` creates the run dir first; `engine.mock_llm` / `_solve_image` then fail before `pw.start()`, exit 2, and the empty dir stays. `list_plan_runs` lists it, so `_publish_selection` (549-552) picks it as latest.
- Case: `solve E.md --mock nosuch.json --line dev`, then `publish E --from dev`: "has no result.json".
- Fix: In the `except` at 234, when `plan_only` and `a.out` has no `plan.json`, `shutil.rmtree(a.out, ignore_errors=True)`.

### F002 – [MEDIUM] report / report-pack leave a manifest-less report run on build failure

- File: src/exam_engine/cli.py
- Lines: 455, 468-470, 516-517, 523-525
- Issue: `new_report_run` creates `reports/<exam>/.../run-<id>/` before the build; on a build error the dir is kept and is listed as layout `incomplete`. Only `publish_main` (604-605) removes it.
- Case: `report-pack PLAN --exam x` with no PDF renderer: `build_pack` raises before any write, exit 2, empty run dir remains.
- Fix: In both `except` branches, when `--out` was not given and `runlayout.manifest_path(out)` is not a file, `shutil.rmtree(out, ignore_errors=True)`.

### F003 – [MEDIUM] run-stats uses the raw ref as a directory after resolving it

- File: src/exam_engine/cli.py
- Lines: 1990-1991, 1996, 2237, 2243
- Issue: `_rs_resolve` finds the run dir through a history `run_id`, but does not return it. `_rs_compute` keeps the run_id string, so `input/exam.md` is never loaded; `_rs_explain` joins `input/exam.md` and `calls` onto the raw ref.
- Case: `run-stats stats <run_id>` gives metrics without the exam; `run-stats explain EXAM/ID --key K` exits 2 "cannot read".
- Fix: Return the resolved dir from `_rs_resolve` and use it for the exam copy and `calls` paths.

### F004 – [LOW] compare --exam disables the same-exam check

- File: src/exam_engine/cli.py
- Lines: 2000, 2076-2078
- Issue: With `--exam`, `sha` is the hash of that file for both runs, so `sa != sb` is never true; the `exam_sha256` of each history line is ignored.
- Case: `run-stats compare A B --exam X.md` where B was solved from another exam: no error, flips are reported.
- Fix: In `_rs_compute`, when `a.exam` is set and `line` has an `exam_sha256` different from the file hash, raise `ValueError("<ref>: solved from another exam than --exam")`.

### F005 – [LOW] rebuild-reports --write-recipe ignores --dry-run

- File: src/exam_engine/cli.py
- Lines: 789, 800-802
- Issue: The `--write-recipe` branch runs before any `a.dry_run` test, although `--dry-run` is documented as "write nothing".
- Case: `rebuild-reports --write-recipe --dry-run` rewrites `published_reports.json` (unnamed mode replaces all exams).
- Fix: Before line 800, if `a.write_recipe and a.dry_run`, print a usage error to stderr and return 2 (or pass a flag to `_write_recipe` that skips lines 701-704).

### F006 – [LOW] --write-recipe without exams aborts on one non-id folder name

- File: src/exam_engine/cli.py
- Lines: 681-683
- Issue: In unnamed mode every sub-folder of `reports` goes through `planrun.safe_id`; one name with a leading dot or a space raises `ValueError` and no recipe is written.
- Case: `reports/.ipynb_checkpoints/` exists: `rebuild-reports --write-recipe` exits 2 "invalid exam id".
- Fix: When `exams` is empty, build `names` only from folders whose name passes `safe_id` (catch `ValueError` and skip); keep the raise for named exams.

### F007 – [LOW] ingest: --boundary-trace write is outside the error handling

- File: src/exam_engine/cli.py
- Lines: 1082-1085
- Issue: The trace file is opened after the `try/except` block, so an `OSError` is a traceback instead of exit 2, after `--out` and `--exam-out` were written.
- Case: `ingest F.pdf --boundary-ai haiku --mock M.json --boundary-trace nosuchdir/t.txt`.
- Fix: Wrap lines 1084-1085 in `try/except OSError as exc`: print `ERROR: ingest: --boundary-trace: %s` to stderr and return 2.

### F008 – [LOW] run-stats trend: negative --last drops the oldest rows

- File: src/exam_engine/cli.py
- Lines: 2122-2123
- Issue: `rows[-a.last:]` with a negative value is `rows[N:]`: it removes the first N rows instead of keeping the last N.
- Case: `run-stats trend --last -3` prints all rows except the 3 oldest, exit 0.
- Fix: In `_rs_trend`, if `a.last < 0`, print `usage: --last N (N >= 0)` to stderr and return 2.

### F009 – [LOW] board --baseline DIR without --exam reports "different exam"

- File: src/exam_engine/cli.py
- Lines: 2206-2207, 2303-2307
- Issue: A baseline dir that has no history line gets a synthetic line with `exam_sha256` None when `--exam` is absent; line 2304 then always fails with a wrong reason.
- Case: `run-stats board --baseline plans/E/dev/runs/ID` (run not in history): `ERROR: different exam (sha ? vs ?)`, exit 2.
- Fix: Before line 2304, if `base` has no `exam_sha256`, raise `ValueError("--baseline %s: exam sha unknown; pass --exam")`.

### F010 – [LOW] ingest: --refined and --questions are ignored without --exam-out

- File: src/exam_engine/cli.py
- Lines: 1051-1056
- Issue: `args.refined` and `args.questions` are read only inside `if args.exam_out`; `args.questions` also only inside `if args.refined`. Otherwise they have no effect and the exit code is 0.
- Case: `ingest F.pdf --refined doc.json --out D.json` writes the plain document; `--exam-out E.md --questions 61-90` writes all questions.
- Fix: After line 1012, return 2 with a usage message when `args.refined and not args.exam_out`, or `args.questions and not args.refined`.

## Summary

- Total findings: 10
- Critical: 0
- High: 0
- Medium: 3
- Low: 7
