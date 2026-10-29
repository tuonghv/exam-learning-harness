PROGRESS: COMPLETE
SKILLS: unit-test, python

# TASK-006 / REQ-0012 tester handoff (Nemesis)
New file: tests/unit/test_req0012_acs.py (12 tests, all green).

## AC map
- AC1 doc: not tested (docs; verifier).
- AC2: ShimParity x5 (every shim runs under -I; exam_run mock/dry-run/no-mode rc2 equal scripts/exam.py; check_examples and score_eval equal subcommands). Existing test_scripts_exam.py kept.
- AC3: ClaudeOnlyInAdapter (src+scripts scan for "claude"/-p outside adapters/claude.py), plus existing test_guards.
- AC4: prompts top-level, no "docs/prompts" or "docs" in src/scripts/tools, no schemas/config/prompts path literals outside settings.py, sentinel key text absent from solve_prompt and --dry-run output.
- AC5: temp subject via EXAM_ENGINE_CONFIG_DIR + temp prompts dir (settings.PROMPTS_DIR patched), addendum in solve prompt; unknown without entry. Existing router test also covers.
- AC6: README structure words + usage lines for solve/parse/verify/report. cwd independence: dry-run from temp cwd == from repo root; parse, check-examples from temp cwd.

## Results
- python3 -I -m unittest discover -s tests/unit: Ran 198, OK (186 + 12)
- python3 -I -m unittest discover -s tests/integration: Ran 2, OK
- tools/examples/tests no longer exists (stale path in CLAUDE.md/test instructions, see Defects).

## Mutations (temp copies under scratchpad/mut, repo untouched)
1. key read outside scorer (parse_expected in solver.py): FAIL test_guards.test_only_scorer_reads_keys (1 failure; my new tests do not catch it).
2. second claude call site in engine.py: 5 failures incl. test_req0012_acs.ClaudeOnlyInAdapter and test_guards x2.
3. router.subjects hardcoded (config lookup dropped): errors across test_exam_report/test_exam_run and test_router (mutation killed).

## Defects
- D1 low: CLAUDE.md and unit-test skill still name `tools/examples/tests` (dir gone); discover command errors "Start directory is not importable". Same as coder's stale-reference note.
- No production-code defects found.
