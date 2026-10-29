# Report: TASK-007 Math and Physics examples (REQ-0003)

**Verdict: adopted.** 10 items: math and physics, each 2 few-shot (`examples/<s>/001-002`) + 3 eval (`evals/inputs|keys/<s>/003-005`).

## Verification
- `check-examples` OK (11 pairs); `tests/unit/test_examples_oracle.py` (10 tests) recomputes every answer independently; a wrong key fails it. Suite 208 OK.
- Verifier re-solved all 10 by reasoning: all match; AC1-AC4 pass.
- Edge cases: math domain restriction (001), parameter boundary (003); physics unit conversion (001, 002, 004, 005), sign/direction (003).

## Limitations
- Oracle is a unit test, not a `check-examples` exit 1. Math keys carry the edge label only in the input `Skill:` line. Minor wording notes (verify.md D1-D4) accepted.
- Math and Physics solved answers are not yet measured on a real model (REQ-0009).

## Next
REQ-0004 (Literature and remaining English), then REQ-0009 benchmark (needs your go).
