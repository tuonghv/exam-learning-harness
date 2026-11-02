PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency, crosscheck
## Files (tests only)
- tests/unit/test_group_e2e.py (4 tests, 1 expectedFailure = D1), tests/unit/fixtures/golden_rq.py, tests/unit/fixtures/golden_retry_qa.json
## Results
- golden_retry_qa: PASS. Hashes of retry_prompt + qa_prompt for 25 examples/evals inputs (5 NOPROMPT = subject prompt absent, same at baseline) generated from 083d0e4 (git archive) == current code. Existing test_clean_golden (solve + parse) still passes.
- e2e dry-run (work/TASK-055/evidence/qa-dryrun.txt): passage count 7, NOT 1 -> D1.
- e2e real round-1 prompt (engine.run + mock llm, test_55_4_round1_prompt_passage_once): passage 1, table 1, declined stems absent. PASS.
- e2e CLI --mock (test_55_5_mock_statuses): q11 (ref q99) UNCERTAIN solver_declined: missing_text (question 99); q13 (Read passage, empty) UNCERTAIN missing_text (passage); q12 ("the text") not declined, `group_link_uncertain: q 12` printed; q2 pages [1,2]. PASS.
- Full suite: work/TASK-055/evidence/qa-full.txt: 887 run, only known fails (lxml docx, check_examples x2 incl dgnl pairing, cwd_independence, scripts_exam).
- Mutations (scratch copy, all caught): no group context -> 4 fail; no sibling answers (solver) -> 1 fail (test_dependent_retry_has_sibling_answer only, thin); own-match broken -> 4; decline rule off -> 3; QA sibling_answers off -> 1 error; share-after-slice (api) -> 1 fail (test_slice_keeps_passage).
- Guard blocked a sed on core/refcheck.py (TASK-047 scope); decline mutation done by monkeypatch instead.
## Defects
- D1 (major) src/exam_engine/cli.py dry-run branch: `solver.solve_prompt(exam, text, <key>)` without ids -> prints the raw file (passage x7 for a 7-question group), not the group-rendered prompt a real run sends. Design Verification row "dry-run -> passage count 1" fails. Fix: pass ids of all questions. test_55_4_dry_run_passage_once_per_group is @expectedFailure; remove the decorator after the fix.
- D2 (minor) solver.py render_questions: `## Group a-a` header on single-question groups that have an instruction (confirmed, `## Group 1-1`). Harmless to answers, extra bytes; suggest header only when len(own) > 1 or a passage exists.
- D3 (minor-major) refcheck.missing_group_parts: "Read the following passage" + empty passage declines the question even when the passage text sits in the stem (confirmed: {1: ['passage']}). False UNCERTAIN on a solvable question. Suggest skipping the decline when the stem is long or main accepts as a known limit.
- Note: solve.md rule 5 not released (config pins v1.0.0); main decides.
