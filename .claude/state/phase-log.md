# Phase Log

Append-only. One entry per phase transition, oldest first.
Never edit or delete a previous entry.
Inherited sample history (security harness template): docs/templates/sample-state/state/phase-log.md


## DESIGN - TASK-001 - 2026-10-29T10:00:00Z
- Action: designer (Nova) wrote docs/design/phase-1-harness-exam-fit.md r3: 31-row audit table, exam-brief-override, crosscheck oracle, compression targets (<=1,446 lines), CLAUDE.md rewrite (A), strip list (B), delete list (C); agent_setup files and settings.json out of plan (AC11/AC12).
- Result: design committed (0838404); settings.json dead ask rules already removed (e37cc92).
- Decision: coder steps A, B, C in order, each closed by its grep check; user answers Q6 A+B+C, D not done.
- Next: brief coder on step A (CLAUDE.md rewrite) with the override block.

## IMPLEMENTING - TASK-001 - 2026-10-29T10:20:00Z
- Action: state DESIGN -> IMPLEMENTING; scope CLAUDE.md; coder launched for step A (design 2.7, CLAUDE.md rewrite <= 4 KB).
- Result: coder running; steps B and C not started.
- Decision: three coder steps in order A, B, C, each closed by its grep check; agent_setup files and settings.json stay out (AC11).
- Next: review coder step A handoff and run its checks, then brief step B.

## UNIT_TESTED - TASK-001 - 2026-10-29T03:01:29Z
- Action: tester (Nemesis) ran AC1-AC13 as read-only deterministic checks at HEAD fa21894.
- Result: all PASS, 0 FAIL; skills 794 lines (<=1033), role bodies 57-71 (<=75), CLAUDE.md 3967 B; minor D1: tools/examples/* named before REQ-0002 creates it.
- Decision: advance to verifier; the agent-setup project-block text edit stays (not generated, not forbidden by AC11/AC13).
- Next: verifier evidence, then VERIFIED.

## VERIFIED - TASK-001 - 2026-10-29T03:07:35Z
- Action: verifier (Argus) checked AC1-AC13 independently; coordinator ran the git-based AC4, AC5, AC11 checks.
- Result: no REFUTED; AC5 grep empty; agent_setup files, hooks, settings.json unchanged.
- Decision: advance to DONE; agent-setup project-block text edits stay (not generated, not forbidden).
- Next: report, backlog complete, DONE.

## DONE - TASK-001 - 2026-10-29T03:08:03Z
- Action: report written (docs/report/phase-1-harness-exam-fit.md), backlog complete.
- Result: REQ-0005 AC1-AC13 met; skills 794 lines, roles 57-71, CLAUDE.md 3,967 B.
- Decision: adopted; coder waiver and limitations recorded in the report.
- Next: TASK for REQ-0008 (exam pipeline design), then REQ-0006 hook caps and REQ-0002.

## DESIGN - TASK-002 - 2026-10-29T03:13:11Z
- Action: designer (Nova) wrote the exam pipeline design; installed as docs/design/phase-2-exam-pipeline.md (209 lines).
- Result: 6 modules, 19 mocked tests; code-security-scanner git status unchanged (0 files); blind solve of English Q1 with docs/prompts/exam/solver.md gave A, matching the key.
- Decision: Q4-Q6 go to the user; solver.md review (RAW-00027) added as REQ-0008 AC6.
- Next: user answers Q4-Q6, then fold the solver.md review into the design.

## DESIGN - TASK-003 - 2026-10-29T03:26:59Z
- Action: designer (Nova) wrote the example checker design; installed as docs/design/phase-3-example-checker.md (128 lines).
- Result: 5 modules/files, 15 unit tests; 4 low defects (expected-001 not in FORMAT form, Skill/Language optional, eval ids start at 003, rewording not machine-checkable).
- Decision: Q1-Q5 go to the user (Q5 touches the approved FORMAT.md).
- Next: user answers, then IMPLEMENTING.

## IMPLEMENTING - TASK-003 - 2026-10-29T03:31:10Z
- Action: user accepted Q1-Q5 (RAW-00030); FORMAT.md marks Skill and Language optional; state DESIGN -> IMPLEMENTING.
- Result: coder step 1 (exam_parse.py, check_examples.py, score_eval.py, README) launching; tests follow with the tester.
- Decision: coder writes tools/examples/*.py and examples/README.md only; coordinator owns FORMAT.md and design.
- Next: coder handoff, run the design's verification commands.
