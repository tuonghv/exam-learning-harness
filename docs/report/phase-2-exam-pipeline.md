# Report phase 2: exam-solving pipeline design (TASK-002; REQ-0008)

Verdict: adopted. `docs/design/phase-2-exam-pipeline.md` is the design the engine was built from; TASK-003..030 delivered the implementation (src/exam_engine, schemas/, tests/unit).

## Acceptance (REQ-0008), checked 2026-10-31 by an independent inspector audit and the coordinator
- AC1 reuse table, gaps, modules, stage flow, TASK split: met (design doc, `work/TASK-002/evidence/design_sections.txt`).
- AC2 per-question JSON schema fitting FORMAT.md: met; real schemas exist (`work/TASK-002/evidence/schemas_exist.txt`: result, solve_out, qa_out).
- AC3 cost and safety rules (mock-only tests, `--real` gated, key only in SCORE, no self-QA as proof): met (design :117-129).
- AC4 tests-first plan: met (19 mocked tests, design :149-168; built tests in tests/unit; suite `work/TASK-002/evidence/unit_suite.txt`: 531 run, 3 known unrelated failures).
- AC5 code-security-scanner unmodified: waived. No baseline `git status` was recorded, the design cites path:line only; the scanner repo's current modifications look like its own work. Honest status: unverifiable, not proven.
- AC6 solver.md reviewed: met (design :209).

## Limitations
The design named `tools/examples/` as module owner; the built code lives in `src/exam_engine` with `tools/examples` thin shims (documented in docs/guide/architecture.md). Design-only task: implementation, tests and verification were delivered under later TASKs and recorded as waivers.

User instructions honoured: RAW-00138.
