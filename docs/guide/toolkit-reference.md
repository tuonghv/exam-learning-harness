# Toolkit reference

Full developer reference for this toolkit, moved out of `CLAUDE.md` to keep
per-session context small. Read the section you need before changing code.

## What this project is



## Commands

- `exam.py run-stats stats DIR | compare A B | trend | backfill DIR...` (TASK-056): run metrics from result.json + run.log; history `plans/run-history.jsonl` (`--history`; legacy `reports/` and `results/run-history.jsonl` still read), appended by `solve --real` or `solve --history`. `solve` without `--out` writes a plan run `plans/<exam-id>/<run-id>/` (git-ignored: plan.json, config.json, input/exam.md, calls/NNN-{prompt,reply}.txt + index.jsonl written per call, result.json, run.log, report); `--out DIR` puts the same files in DIR. `solve` prints a 3-line metrics block and report.md gets `## Metrics`. compare exit 2 on different exam, 1 on a regression signal.
