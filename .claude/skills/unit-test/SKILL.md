---
name: unit-test
description: Design and validate high-quality unit tests after implementation.
---

# Unit Test

Tests must verify behavior, not implementation details.

Consider:
- happy path
- boundary conditions
- invalid input
- error handling
- empty/null values
- dependency failure
- regression scenarios
- security-sensitive behavior

Prefer deterministic, isolated tests and meaningful assertions.
Avoid meaningless coverage, duplicate tests and excessive mocking.

## What UNIT_TESTED means in this bash repo

There is no test framework; a unit test is a deterministic bash script that
exercises one function or one script in isolation:

- **Static:** `bash -n` + shellcheck on every touched file, no new findings.
- **Function-level:** source a side-effect-free file and call one function
  with fixture input — e.g. `scan_excludes.sh` (`scan_settings_json | jq`),
  `scheduler_common.sh` (`detect_reset_at <fake-log> <fake-envelope>`),
  `report_common.sh` (`enrich_findings`).
- **Script-level:** copy what the script needs into `mktemp -d`, write a
  fixture state, run it, assert exit code + output substring. Template:
  `.claude/tests/workflow_gates_test.sh` (`expect <name> <rc> <substr> <cmd…>`).
  Never touch the real `manifest.json`, `results/` or `.claude/state/`.
- **Both plan modes:** when the code path reads findings or writes reports, give the test one fixture per
  plan mode, a `results/` dir (single-source) and a run dir or `conclusion.json` (pipeline), and
  assert both. A mode left out needs the reason in the design's `Plan modes` section.
- **Prove the test bites:** run the new cases against the pre-change code
  (`git archive HEAD <paths> | tar -x -C <tmp>`) and record how many fail.
  A case that passes on the old code does not test the change.

Keep UNIT_TESTED and VERIFIED distinct: a fake-`claude` end-to-end run of
`scan_batch.sh` is verification (`verify` skill), not a unit test.

Before UNIT_TESTED run the whole suite once, `tests/run_all.sh` (fails if any
suite fails or none ran), plus `.claude/scripts/checks/shell.sh`. While
iterating, `tests/run_all.sh <name>` runs one suite. Record
`unit_test.command` (the exact commands) and `unit_test.result` (per-suite
pass/fail counts, plus the bites-on-old-code count); a result with 0 tests
run is a failure, not a pass.
A task becomes UNIT_TESTED only when relevant tests pass.
For each failing suite, run it on the base commit (`git archive` kit) and record pre-existing vs new before the handoff; save `test.md` COMPLETE, not IN_PROGRESS (TASK-109).
A detached `run_all` launcher's notification only means the launcher exited; read `evidence/full_run_all.txt` for the verdict (TASK-123).
- Background or detached runs: give suites `</dev/null`; a case that runs the session-start hook reads stdin and hangs on an open socket (TASK-124, workflow_gates).
