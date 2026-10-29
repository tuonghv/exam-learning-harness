PROGRESS: COMPLETE
SKILLS: verify, python

# TASK-006 / REQ-0012 verifier handoff (Argus)
Claim verdicts only; the task state is the coordinator's.

## Per-AC
- AC1 VERIFIED (static): docs/design/phase-6-engine-structure.md:30-43 maps all nine tools/examples/*.py, prompts, tests, schemas; :45-57 lists differences with reasons; :66-67 no open question. Map is by module group (no per-test-file rows), acceptable.
- AC2 VERIFIED: src/exam_engine/cli.py:20 COMMANDS = solve, parse, verify, report, check-examples, score; scripts/exam.py:9 sets sys.path explicitly. tools/examples/*.py are 6-9-line shims (e.g. exam_run.py:1-10); no duplicate logic left. evidence/old-vs-new.txt:9-12 old and new give identical summary lines and rc=2 for no mode (header rc 0); the same file shows the dry-run from cwd /tmp works. Tests: tests/unit/test_req0012_acs.py ShimParity.
- AC3 VERIFIED: subprocess "claude" argv only in src/exam_engine/adapters/claude.py:45-50. reporter.py uses subprocess only for the PDF renderer (reporter.py:136,207), not claude. Guard test test_req0012_acs.py:113. evidence/claude-sites.txt is weak (matches only a .pyc; filter drops .py hits), so I confirmed with my own Grep over src, scripts and tools.
- AC4 VERIFIED: settings.py:8-12,34-37 are the only path roots; prompts/ top-level, none under docs/prompts (grep of src found no such reference). Minor literals remain (see D2, D3). Prompts contain no expected-0/evals refs (Grep count 0; claude-sites.txt:11).
- AC5 VERIFIED: the test with a temp subject uses EXAM_ENGINE_CONFIG_DIR plus a temp prompts dir (test_req0012_acs.py:186-191); settings.py:3,15-16 supports this. Also tests/unit/test_router.py:62.
- AC6 VERIFIED: evidence/unit.txt:11-13 Ran 198 OK (rc 0); evidence/integration.txt:11-13 Ran 2 OK (rc 0). New tests: test_settings.py, test_req0012_acs.py, integration/test_fake_claude.py. README.md names exam_engine, prompts/, config/, schemas/ and scripts/exam (13 hits). 198 vs "108+": meaning unchanged is trusted from the tester's 3/3 mutation kills (test.md:20-23); I did not diff the moved tests individually (UNVERIFIED in detail).

## Other checks
- Key read only after DECISION and only in the scorer: engine.py:127-129 calls scorer.apply_key only when not stopped, after decide. solver.py:25-45 compares only the key path (realpath), never reads it; fewshot reads examples/, not evals/. The scorer reads keys at scorer.py:109-135 (score command) and in apply_key. Guard test_guards.test_only_scorer_reads_keys (test.md:21).
- Eval keys not in prompts: VERIFIED (grep above; the sentinel test in test_req0012_acs.py).
- Hardcoded paths: no /home or /tmp literals in src.

## Defects
- D1 low: CLAUDE.md and the unit-test skill still say `tools/examples/tests` (dir removed), so the documented test command fails. This is a coordinator-owned file (design :64 already lists it).
- D2 low: src/exam_engine/pipeline/scorer.py:109 builds the default keys dir as a literal "evals","keys" instead of via settings.
- D3 low: src/exam_engine/pipeline/examples_check.py:23 LEGACY has a literal "examples/english/expected-001.md" and solver.py:30 a literal "examples" (not in settings.py). This is cosmetic against AC4 "nothing hardcoded".
- D4 info: evidence/claude-sites.txt grep is ineffective as evidence (hits only a .pyc); rely on the guard test or re-run it with --include=*.py.

## Open
Not run by me: no real `claude` call (not needed; the integration test uses a fake claude). Everything else is judged from the saved files and the code.
