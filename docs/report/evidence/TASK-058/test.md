PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency, crosscheck
## Added
- tests/unit/test_plan_qa.py (6): crash at call 2 keeps call 001 + plan.json status failed, no result/reports (58.2/D-4); KeyboardInterrupt same; plan.json exists before first call; 3 solves in a frozen second -> 3 distinct plan + report ids (D-2); flat solve vs `report` vs default solve give identical report.md, answers.md, metrics.json (D-3); token in reply masked in calls/ through the engine, sha stored.
- Already covered by the coder's suites (reviewed, not duplicated): determinism, adapter/subprocess/socket blocked, AST import guard (test_report_build), git status clean (test_planrun), mask+sha, idempotent import, missing run.log, not-captured replies, trace + --ingest-cache pickup (test_plan_import).
## Results
- test_plan_qa: PASS 6/6. Full suite: 985 run, only known failures (lxml docx, check_examples x2, cwd_independence): work/TASK-058/evidence/qa-full-suite.txt
- Item 7 recount (fixture run-small, scratch cwd): old dir vs imported plan -> result.json byte-identical; calls=2, questions=1 (jq); run-stats stats lines identical; compare unchanged:1; replies all "not captured"; second import skipped: work/TASK-058/evidence/qa7-import-stats.txt
## Mutations (scratch copy /tmp/scratch-kit.Q5FwA8, suites *plan*.py + test_report_build)
- M1 report_build imports adapters -> killed (test_report_build AST guard, 1 fail)
- M2 sink disabled (calls not written during run) -> killed (2 fail 4 err: test_plan_qa crash, test_planrun)
- M3 masking off -> killed (2 fail, test_planrun + test_plan_qa)
- M4 metrics computed without exam -> killed by test_report_build stored-exam test only; my parity test survives (english fixture metrics do not differ), no extra test needed.
## Gaps
- Real work/dgnl-real import not re-run (coder's plan-import-real.txt taken as is); parity uses the english fixture only.
## Defects
none
