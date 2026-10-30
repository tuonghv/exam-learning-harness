# Report phase 32: gated task advance (TASK-032; REQ-0037)

Verdict: adopted. `advance.sh <TASK> <STATE> --spec FILE [--dry-run]` does one gated TASK transition (fields, phase-log entry, view sync, linked REQ steps, workflow-check, gated commit) and `advance.sh req-catchup <REQ>` steps a lagging REQ; skill `advance` documents it.

## Quality of the product (REQ-0037 AC7)
- VERIFIED and DONE need existing non-empty evidence files; DONE needs a `quality` block; `n/a` is refused for crosscheck/content tasks; the tool never writes `verification.status` itself.
- Adversarial tester (Nemesis) found two real defects, both fixed with tests: concurrent runs corrupted state (now a whole-run non-blocking flock) and newlines in log fields could forge a phase-log heading (now one-line).
- Mutations caught: AC7 evidence check removed, snapshot restore made a no-op.

## Evidence (work/TASK-032/evidence/)
`final_advance_test.txt` 58/0, `final_advance_adv_test.txt` 32/0, `final_diff_protected.txt` (settings/hooks/agent_setup unchanged, empty), `final_force_grep.txt` (no `--force`), tester `qa_*.txt` (neighbour suites multi_task 205/0, workflow_gates 156/0, req_kit 38/0), verifier `work/TASK-032/handoff/verify.md` (AC2-AC7 PASS; coordinator checked AC1: gap list G1-G8 in design 32.1).

## Dogfooding
TASK-032 itself moved IMPLEMENTING, UNIT_TESTED, VERIFIED through `advance.sh`; its first dry-run caught a missing `roles.coder`.

## Limitations
Evidence is checked for existence and non-empty, not content; content-task detection uses scope, files and `crosscheck_required`; `lead_test.sh` is pre-existing broken (missing TASK-097 patch). The tool restores files outside req.py's lock (only main writes state).

User instructions honoured: RAW-00132, RAW-00133, RAW-00134, RAW-00136, RAW-00138.
