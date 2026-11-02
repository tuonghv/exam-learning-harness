PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency, crosscheck
## Result
- new tests/unit/test_image_qa.py: 13 tests (2a-c trigger/cap/key page, 3 shifted ids, 3b match by id, 4a-e reconcile/call fail/declined/call_cap/cost, 7a-c render failures incl. real refine.render_page on missing PDF).
- full suite: Ran 1024, FAIL 3 + ERROR 1, same names as work/TASK-058/evidence/baseline-failures.txt (lxml docx, check_examples x2, cwd_independence, scripts_exam). work/TASK-059/evidence/qa-full-suite.txt
## Checks
- (1) no --pdf byte identity vs 760fbac, 25 inputs: PASS (result/config/report/answers/run.log/calls identical; plan.json only timestamps+git; stdout/stderr equal modulo paths). work/TASK-059/evidence/qa-no-pdf-identity.txt
- (2) trigger set / cap / key page end-to-end: PASS (test_2a, 2b, 2c, existing 2, 4)
- (3) identity by id: PASS (test_3, 3b)
- (4) reconcile, G1, declined, call_cap, cost cap: PASS (existing 6-6d, 7, 7b + 4a-4e)
- (5) plan capture, schema old/new, report source, metrics: PASS (existing test_image_plan; not re-written)
- (6) mutations on scratch copy (9): all killed. M1 ids-by-position was killed ONLY by new test_3 (existing tests would have survived). M2 key guard off: 3 fail. M3 text overwritten: 2. M4 cap off: 2. M5 call_cap always +1: 2. M6 unflagged get pages: 3. M7 render exception uncaught: 3. M8 call failure ignored: 1 (test_4b, new). M9 declined reason lost: 2.
- (7) render failure: fake render raising OSError/RefineError and real refine.render_page on a missing PDF (RuntimeError subclass) -> no call, finding image_unavailable, text kept: PASS.
## Gaps
- No input exercises the pre-solve WARN in the CLI (0 WARN in the 25 runs); covered by unit test_1 only.
- Real fitz render of a valid PDF and the real image call are not run (paid/real).
- Design 59.5 says index gets `page_sha256` per page; code records only `pages`. Not tested.
## Defects
- D1 low, engine.py:189-193: image_check trusts render output; a render returning empty/non-PNG bytes would still be sent (real refine.render_page validates PNG/size itself, so only an injected render could hit it). No fix required.
- D2 info: design 59.5 `page_sha256` in calls index absent (see Gaps).
