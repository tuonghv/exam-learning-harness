---
name: run-pipeline
description: Operate pipeline.sh safely on a real plan - resume after a usage limit, release a held unit, re-run ONE step by resetting its status, check cache reuse with a dry run before any paid call. Load before any pipeline.sh command other than status, on a plan that is reviewing real code. Never start a new run to fix one unit.
---

# Run the pipeline (harness rules)

Full guide: `docs/guide/pipeline-operations.md`. Review procedure: skill `run-security-review`.

1. `./pipeline.sh status` first. Read the hold and the held units, not the log.
2. **`./pipeline.sh new` is forbidden for repairs.** **Small problem = reset that step, run that step.** Never `./pipeline.sh new` (it wipes `steps_done`, units and approvals) and never start a whole run for one unit (user, 2026-10-26).
3. Before a paid call: `run --dry-run` and read the cache hits. Tell the user how many units will be called. Stop if the number is larger than the problem.
4. `release <unit>` only flips a held unit to pending; a step already in `steps_done` does not re-run. Reset the unit with the engine, never by hand: `PLAN=<p> ./pipeline.sh unit reset <ph>:<key> [--cascade]` (dry run), then `--yes`; check `./pipeline.sh status --units`; preview with `run --only <ph>:<key> --dry-run`, then `run --only <ph>:<key>` (calls only those units, pauses after the owner step). A unit whose output in this run is still valid self-heals to done at $0. Never re-call a whole phase and hope the cache covers it. Tail: `./pipeline.sh rebuild` (overlay, logreach, conclude, report; `--render` only redraws the report). `pipeline.sh new` refuses to wipe a running run with done units unless `--yes-wipe "<reason>"`.
5. Usage limit: wait for the reported reset; when the user says it is fixed, `rm` `.usage_hold.json`, `.scan_abort.json` (kit root) and the plan's `.scan_abort.json`, then resume. Keep a keeper script outside the kit. Stop on auth or service failures.
6. Never kill with `pkill -f`/`pgrep -f ... | kill` in a command line that also holds other work; use the PID. Background long runs and wait for the notification; a notification from a task I killed is not the user.
7. `plans/` is not in git: copy the file before editing state. Only `pipeline.sh` writes `.pipeline` normally; a hand edit is an exception to say out loud.
8. Close with `coverage_check.py <run_dir> --conclusion` (gaps=0) and `check_deliverables.sh --run latest`; end the reply with `Wait for ...` or `Your turn: ...`.
