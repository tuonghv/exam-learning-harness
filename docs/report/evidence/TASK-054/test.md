PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency
## Added (tests only)
- tests/unit/test_clean_golden.py (3 tests), tests/unit/fixtures/golden_unlabelled.json
- Golden: sha256 of parse dict (new keys removed) and solve_prompt for all 25 examples/*/input-*.md + evals/inputs files, computed from baseline 2461f4f (git archive into scratchpad, run side by side): base vs HEAD identical (cmp SAME). Unlabelled files unchanged. Unit test also asserts sections==[] and instruction/passage empty.
- examples/informatics has no subject prompt in repo (solve_prompt FileNotFoundError at baseline and HEAD); golden records it as NOPROMPT (pre-existing, not from TASK-054).
- AC3: re-emit from work/dgnl-real/refined3.json (api.to_exam_text, no AI) for Vietnamese 1-30, English 31-60, Math 61-90, Science 91-120: 30 questions each, option dicts equal to old e3-*.md. Skips if work/ absent.
- AC5: slice 31-35 solve_prompt has "Instruction for this group" 5x, "1.2. TIẾNG ANH" 1x.
## Results
- golden: OK 3 tests (work/TASK-054/evidence/golden.txt)
- suite: 865 run; failures=3 errors=1 skipped=35: only the 4 known (lxml, examples/dgnl unknown subject dir x3) (work/TASK-054/evidence/suite.txt)
## Gaps
- Bite on old code: AC5/section assertions cannot pass on 2461f4f (no labels); not run mechanically.
## Defects
- none
