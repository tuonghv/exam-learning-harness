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

## UNIT_TESTED - TASK-003 - 2026-10-29T03:35:58Z
- Action: tester (Nemesis) wrote 28 unittest cases (tests 1-15 of the design plus extras); coordinator re-ran them and mutated disjoint-text, header, options checks in a temp copy.
- Result: 28 OK; every mutation made its matching test fail. No tool defects.
- Decision: advance to verifier (real repo run, AC1-AC5 evidence).
- Next: verifier handoff, then VERIFIED.

## VERIFIED - TASK-003 - 2026-10-29T03:38:07Z
- Action: coordinator ran 13 injected-defect cases on isolated copies (evidence.md); verifier judged AC1-AC5 from files.
- Result: AC1-AC5 PASS; 28 tests OK; limitation L1 (mid-line key leak) documented in examples/README.md; no defects.
- Decision: VERIFIED; security not_applicable (read-only file tools).
- Next: report, crosscheck waiver, DONE.

## DONE - TASK-003 - 2026-10-29T03:38:25Z
- Action: report written (docs/report/phase-3-example-checker.md); crosscheck waived with reason; backlog completed.
- Result: REQ-0002 AC1-AC5 ticked; 28 tests OK; limitation L1 documented.
- Decision: DONE.
- Next: EPIC-003 engine build (resume TASK-002 or new TASK), REQ-0003/0004 examples, REQ-0009 benchmark after the user's go.

## DESIGN - TASK-004 - 2026-10-29T04:21:56Z
- Action: RAW-00036 accepted (start REQ-0010); wrote docs/design/phase-4-engine-core.md from phase-2 design; aligned SOLVE_OUT with tools/examples/prompts/solve.md.
- Result: 4 modules + qa.md + validate_exam, 14 mock tests; decisions D1-D8; designer waived (architecture done in TASK-002).
- Decision: no open questions; go to IMPLEMENTING.
- Next: coder step A.

## IMPLEMENTING - TASK-004 - 2026-10-29T04:22:11Z
- Action: state DESIGN -> IMPLEMENTING; coder step A launching (exam_schema, exam_llm, validate_exam, exam_checks).
- Result: pending coder handoff.
- Decision: coder B (exam_run, qa.md) follows after A.
- Next: coder A handoff, review, commit.

## UNIT_TESTED - TASK-004 - 2026-10-29T04:35:31Z
- Action: coder A and B committed; tester wrote 4 test files (73 new tests) with mocked replies only; coordinator ran an extra mutation (key appended to the solve prompt).
- Result: 101 tests OK (28 old + 73 new); tester mutations 17/17 killed; coordinator mutation killed by 3 tests; no real claude call reachable.
- Decision: UNIT_TESTED; retry set skips no_independent_check (a re-solve cannot create an independent check).
- Next: coordinator mock end-to-end on examples/english/input-001.md with a key-leak grep, evidence.md, verifier.

## VERIFIED - TASK-004 - 2026-10-29T04:40:41Z
- Action: coordinator ran mock end-to-end, the --real path against a fake claude executable and a key-sentinel grep; verifier reviewed AC1-AC6 statically, found safe_eval overflow/hang (D1-D3), coder A fixed, tester added 7 regression tests, verifier re-checked.
- Result: 108 tests OK; AC1-AC6 PASS; no sentinel or key line in any prompt or output; no real claude call; D4 (extra ids ignored) accepted and AC2 reworded.
- Decision: VERIFIED; model accuracy is not claimed here (REQ-0009 needs the user's go).
- Next: report, crosscheck waiver, DONE, backlog complete.

## DONE - TASK-004 - 2026-10-29T04:41:16Z
- Action: report docs/report/phase-4-engine-core.md written; crosscheck waived with reason; backlog item completed.
- Result: REQ-0010 AC1-AC6 ticked, 108 tests OK, verifier PASS after the safe_eval fix; no real claude call made.
- Decision: DONE; model accuracy stays unclaimed until REQ-0009 (needs the user's go).
- Next: REQ-0011 report stage; then REQ-0009 dry-run and call-count/cap proposal for the user.

## DESIGN - TASK-005 - 2026-10-29T05:15:22Z
- Action: RAW-00037 triaged into REQ-0011 (PDF follows code-security-scanner: copy md2html.py, rewrite md_to_pdf in Python); design docs/design/phase-5-report.md written; scanner md2html.py read in full (stdlib, escapes, scheme allowlist).
- Result: design complete, no open questions; designer waived (coordinator wrote it).
- Decision: go to IMPLEMENTING with one coder; renderer is Chrome (present at /usr/bin/google-chrome).
- Next: coder (md2html copy, exam_report, exam_run hook, evidence_kind), then tester.

## IMPLEMENTING - TASK-005 - 2026-10-29T05:15:29Z
- Action: state DESIGN -> IMPLEMENTING; one coder launched (md2html copy, exam_report, exam_run hook, evidence_kind).
- Result: pending coder handoff.
- Decision: tester follows the coder; no Chrome needed for unit tests.
- Next: coder handoff, review, commit.

## UNIT_TESTED - TASK-005 - 2026-10-29T05:23:00Z
- Action: tester wrote test_exam_report.py (41) and test_md2html.py (16), fakes only; 6 mutations; coordinator fixed D1 (invalid pdf removed) and added an assertion.
- Result: 165 tests OK; mutations killed 6/6.
- Decision: advance to UNIT_TESTED; real Chrome evidence is the VERIFIED step.
- Next: coordinator evidence.md, then verifier.

## VERIFIED - TASK-005 - 2026-10-29T05:26:02Z
- Action: coordinator real runs (mock end to end, no-renderer PATH, real Chrome Vietnamese PDF) saved under work/TASK-005/evidence; verifier read code, tests and evidence.
- Result: AC1-AC4 verified; verifier D1 (markdown structure injection) and D2 (fake verdict pill) fixed with a test; 166 tests OK.
- Decision: advance to VERIFIED.
- Next: report, crosscheck waiver, DONE.

## DONE - TASK-005 - 2026-10-29T05:26:33Z
- Action: wrote docs/report/phase-5-report.md; crosscheck waived with reason; backlog complete.
- Result: REQ-0011 AC1-AC4 verified, 166 tests OK, real Chrome PDF with Vietnamese.
- Decision: close TASK-005.
- Next: TASK-006 engine restructure (REQ-0012).

## DESIGN - TASK-006 - 2026-10-29T05:27:43Z
- Action: design doc docs/design/phase-6-engine-structure.md (final, Q1-Q4 decided); designer waived.
- Result: file map, differences from the reference and 6 build steps recorded.
- Decision: enter DESIGN; build in small green steps.
- Next: IMPLEMENTING, coder step S1.

## IMPLEMENTING - TASK-006 - 2026-10-29T05:27:51Z
- Action: REQ-0012 Design section points to the phase-6 doc; implementation pending.
- Result: ready to build S1.
- Decision: enter IMPLEMENTING; coder does S1 then each step is committed green.
- Next: coder S1.

## UNIT_TESTED - TASK-006 - 2026-10-29T06:07:23Z
- Action: tester added 12 AC tests (shims, single claude site, prompt isolation, temp subject, cwd independence); 3 mutations.
- Result: 198 unit + 2 integration OK; mutations 3/3 killed.
- Decision: advance.
- Next: coordinator evidence, verifier.

## VERIFIED - TASK-006 - 2026-10-29T06:09:04Z
- Action: raw evidence saved; verifier read code, tests, evidence.
- Result: AC1-AC6 verified; defects low (stale CLAUDE.md path needs the user).
- Decision: advance.
- Next: report, DONE.

## DONE - TASK-006 - 2026-10-29T06:09:15Z
- Action: report written; crosscheck waived; backlog complete.
- Result: REQ-0012 AC1-AC6 verified, 198+2 tests OK.
- Decision: close TASK-006.
- Next: user decides CLAUDE.md/skills path edits; REQ-0003/0004, REQ-0009.

## DESIGN - TASK-007 - 2026-10-29T06:11:30Z
- Action: phase-7 plan; designer waived.
- Result: 2+3 items per subject, edge cases, checker proof.
- Decision: enter DESIGN.
- Next: IMPLEMENTING, coders.

## IMPLEMENTING - TASK-007 - 2026-10-29T06:11:30Z
- Action: start content writing.
- Result: ready.
- Decision: two coders.
- Next: coders.
