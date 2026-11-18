<!-- fable-status -->
> **Status (2026-11-18):** 10 finding(s): 10 fixed (TASK-111, TASK-133). Nothing open.
>
> **Action rule (RAW-00368):** check every finding against the code. A true positive is FIXED through a task; a warning or a note alone does not close it. A false positive is recorded with its reason in `docs/review/findings.tsv` and ignored. Update the Status line at each task transition.
<!-- /fable-status -->

# Phase 107 – CLI logic review (src/exam_engine/cli.py)

## Findings

### F001 – [MEDIUM] --write-recipe discards an unreadable recipe and overwrites it

- File: src/exam_engine/cli.py
- Lines: 662-666
- Issue: Every `ValueError` of `_load_recipe` (bad JSON, wrong version, one invalid exam entry) is treated like a missing file: `old = {}`, then the file is rewritten.
- Case: Recipe holds exams A, B, C; B has an invalid field. `rebuild-reports A --write-recipe` writes a recipe with only A.
- Fix: Use `old = {}` only when `os.path.exists(path)` is false; otherwise let the `ValueError` propagate (caller prints it, exit 2).

### F002 – [MEDIUM] run-stats ignores a failed --exam load and exits 0

- File: src/exam_engine/cli.py
- Lines: 1972-1975, 1978
- Issue: `_rs_compute` drops the error code of `_load_exam`; `exam` stays None and metrics are computed without it. `metrics.file_sha256` returns None for a missing file, so nothing else stops.
- Case: `run-stats stats DIR --exam missing.md` (or an invalid exam) prints `ERROR: input: ...` and still prints metrics, exit 0; `compare` skips the same-exam check.
- Fix: After each `_load_exam` call in `_rs_compute`, `raise ValueError("cannot load exam %s" % path)` when `exam is None`.

### F003 – [MEDIUM] solve: report build failure hides a finished run

- File: src/exam_engine/cli.py
- Lines: 232-236, 240-258
- Issue: `_build_default_report` runs inside the outer `try`; its `OSError`/`ValueError` returns 2 ("invalid input") after `engine.run` and `pw.finish` succeeded, skipping the result summary, metrics and `_append_history`.
- Case: `solve EXAM --real --line dev` with an unwritable `reports/` or a report_build error: paid run done, exit 2, no summary, no history line.
- Fix: Wrap line 233 in its own `try/except (OSError, ValueError)`: print `WARN: report not built: ...`, leave `result["reports"]` unset, continue to line 240 and return `code`.

### F004 – [LOW] ingest-refine: trace write in `finally` raises past the handled error

- File: src/exam_engine/cli.py
- Lines: 1237-1239, 1249-1254
- Issue: The `finally` block opens `a.out + ".trace.json"` unguarded; an `OSError` there replaces the `return 2` of the `except` branch with a traceback.
- Case: `ingest-refine doc.json --pages 1 --mock M --out nosuchdir/x.json`: calls run, the result write fails (handled), then the trace write raises `FileNotFoundError`.
- Fix: Wrap the trace write in `try/except OSError` printing `WARN: trace not written`; optionally check that `os.path.dirname(a.out)` exists before any call and return 2.

### F005 – [LOW] ingest --refined without a `refined` key raises KeyError

- File: src/exam_engine/cli.py
- Lines: 1036-1037, 1055-1060
- Issue: `json.load(fh)["refined"]` raises `KeyError` (or `TypeError` for a JSON list); only `IngestError`, `OSError`, `ValueError` are caught.
- Case: `ingest FILE --exam-out E.md --refined doc.json` where doc.json is a plain ingest document (no ingest-refine output): traceback, after `--out` was already written.
- Fix: Load into a variable; if it is not a dict or has no `"refined"` key, `raise ValueError("--refined %s: no refined block" % args.refined)`.

### F006 – [LOW] benchmark: missing --inputs dir is an uncaught OSError

- File: src/exam_engine/cli.py
- Lines: 1407-1411
- Issue: `benchmark.discover` calls `os.listdir(inputs)` with no guard and the call is outside any `try`; the `if not items` exit-2 branch is never reached.
- Case: `benchmark --dry-run --inputs nosuch` (or run from a cwd without `evals/inputs`): `FileNotFoundError` traceback instead of exit 2.
- Fix: Wrap line 1408 in `try/except OSError as exc`: print `ERROR: %s` to stderr and return 2.

### F007 – [LOW] lessons: output writes are outside the error handling

- File: src/exam_engine/cli.py
- Lines: 1559-1573
- Issue: The `try` covers only reading the summary; the two `open(..., "w")` calls on `out` are unguarded and `out` is never created.
- Case: `lessons --summary s.json --out newdir` (dir does not exist): `FileNotFoundError` traceback instead of exit 2.
- Fix: Before writing, `os.makedirs(out, exist_ok=True)`; put lines 1568-1573 in a `try/except OSError` that prints `ERROR: --out: ...` and returns 2.

### F008 – [LOW] `--help` exits 2 in subcommands that catch SystemExit

- File: src/exam_engine/cli.py
- Lines: 980-983, 1088-1091, 1172-1175, 1282-1285, 1382-1385
- Issue: `except SystemExit: return 2` maps argparse's `--help` exit (code 0) to 2. Same pattern in gen-exams, lessons, extract-eval, review-pack, review-apply, gold-pdf.
- Case: `exam.py ingest --help` prints help and exits 2 (usage error); `run-stats --help` exits 0.
- Fix: Use the form already at lines 1800-1801 and 2364-2365: `except SystemExit as exc: return 2 if exc.code else 0`.

### F009 – [LOW] run-stats backfill silently drops refs without result.json

- File: src/exam_engine/cli.py
- Lines: 2125-2131
- Issue: Refs that are not result dirs are filtered out with no message; an empty list still calls `metrics.backfill` and returns 0.
- Case: `run-stats backfill plans/typo-dir` (or no ref at all) prints `backfill: added 0 skipped 0` and exits 0.
- Fix: Compute the rejected refs; if any (or `a.refs` is empty), print `ERROR: not a result dir: ...` to stderr and return 2 before calling `metrics.backfill`.

### F010 – [LOW] run-list: unreadable plan.json of a foreign plan run is uncaught

- File: src/exam_engine/cli.py
- Lines: 1824-1833
- Issue: `settings.load_json(plan.json)` for a plan run of another exam runs outside the `try` at 1777-1804 and inside a `try` that guards only `plan_ref`; a `ValueError`/`OSError` propagates.
- Case: A report manifest links a plan run of another exam whose `plan.json` is truncated: `run-list EXAM` ends in a `JSONDecodeError` traceback.
- Fix: Load the plan in a `try/except (OSError, ValueError)` and use `None` on failure (as `_rl_stats` does for result.json).

## Summary

- Total findings: 10
- Critical: 0
- High: 0
- Medium: 3
- Low: 7
- More actionable findings exist (limit of 10 reached); another review batch is needed.
