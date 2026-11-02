# Toolkit reference

Full developer reference for this toolkit, moved out of `CLAUDE.md` to keep
per-session context small. Read the section you need before changing code.

## What this project is



## Commands

- `exam.py run-stats stats DIR | compare A B | trend | backfill DIR...` (TASK-056): run metrics from result.json + run.log; history `reports/run-history.jsonl` (`--history`; legacy `results/run-history.jsonl` still read), appended by `solve --real` or `solve --history`. `solve` prints a 3-line metrics block and report.md gets `## Metrics`. compare exit 2 on different exam, 1 on a regression signal.
