# Phase 111 – Fix-D CLI exit codes report (TASK-111, REQ-0118)

**Verdict: adopted.** Review-triage bugs 107-F001, F002, F008 fixed in `src/exam_engine/cli.py` (auto mode, RAW-00336).

## Results
- 111.1 `--help`/`-h` exits 0 in all 16 entry points (review listed 5, triage 11; the oracle found 16: 11 argparse
  sites via `_argparse_exit`, 5 hand-parsed usage branches via `_help_asked`). An unknown flag still exits 2.
- 111.2 `--write-recipe` refuses (exit 2) a corrupt or wrong-type recipe and leaves the file untouched; a missing
  file is still created.
- 111.3 `run-stats --exam <missing>` exits 2 with no metrics or history (was: ERROR printed, exit 0).
- Tests: tests/unit/test_cli_exit_codes_111.py (48 subtests fail on old code); --fast 2020 ran, NEW 0 (KNOWN 4).
- Oracle (observed by the coordinator): only the intended exit codes changed; mock solve and run-stats on a good
  exam give the same exit codes and output files.

## Spend
designer + coder + tester; no paid run.

## What changed for the user
Scripts that check exit codes now see failures as failures and help as success. Plan-run `exam.md` copies keep
today's behaviour (D2).
