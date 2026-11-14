# Phase 100 report: publish uses date-style run names

Task: TASK-100 · REQ-0107 (RAW-00315) · design `docs/design/phase-100-publish-date-run-names.md`

- Action: `cli.publish_main` default run part = the new main run folder id (`--run` still overrides); test `test_100_1`.
- Result: dgnl2026 → `run-20261114-082249`, dhqg2024 → `run-20261114-082256`; every file ends in that id; checker
  52/59 checks, 0 failed; suite 1918 tests NEW 0; previous main runs deleted, INDEX.md rebuilt.
- Decision: none open. Next: none.

Evidence: `docs/report/evidence/TASK-100/verify.md`
