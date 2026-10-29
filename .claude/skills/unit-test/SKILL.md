---
name: unit-test
description: Design and validate high-quality unit tests after implementation.
---

# Unit Test

Tests verify behavior, not implementation details. Consider: happy path, boundary conditions, invalid input,
error handling, empty values, dependency failure, regression scenarios. Prefer deterministic, isolated tests
with meaningful assertions; avoid meaningless coverage, duplicate tests and excessive mocking.

## What UNIT_TESTED means in this repo

There is no test framework; a unit test is a deterministic bash script that exercises one function or one
script in isolation:

- **Static:** `bash -n` + shellcheck on every touched shell file; `py_compile` on every touched `.py`.
- **Function-level:** source a side-effect-free file and call one function with fixture input.
- **Script-level:** copy what the script needs into `mktemp -d`, write a fixture, run it, assert exit code +
  output substring. Template: `.claude/tests/workflow_gates_test.sh` (`expect <name> <rc> <substr> <cmd...>`).
  Never touch the real `.claude/state/` or the exam content under test.
- **Prove the test bites:** run the new cases against the pre-change code (extract the base files to a temp
  dir) and record how many fail. A case that passes on the old code does not test the change.

Keep UNIT_TESTED and VERIFIED distinct: unit tests prove the code; the `verify` skill proves the behavior.

Before UNIT_TESTED run the whole suite once, `python3 -I -m unittest discover -s tools/examples/tests` (0 tests run is a failure). While iterating, add `-p 'test_<name>.py'`. Record
`unit_test.command` (the exact commands) and `unit_test.result` (per-suite pass/fail counts, plus the
bites-on-old-code count); 0 tests run is a failure, not a pass.

- For each failing suite, run it on the base commit and record pre-existing vs new before the handoff; save
  `test.md` as COMPLETE, not IN_PROGRESS.
- A detached test launcher's notification only means the launcher exited; read the saved evidence file
  for the verdict. Give detached suites `</dev/null` so a case reading stdin cannot hang.
