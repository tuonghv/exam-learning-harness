# Report: TASK-004 engine core + QA (REQ-0010)

**Verdict: adopted for plumbing, isolation and decision logic.** Model accuracy is not claimed; no real `claude` call was made.

## Task and requirement
REQ-0010: Python builds `prompts/solve.md` + the exam, sends it to `claude -p`, validates the JSON, runs code checks and a separate QA call, decides PASS/FAIL/UNCERTAIN with bounded retries, and scores against a key only after the decision. Architecture: `docs/design/phase-2-exam-pipeline.md`; build plan and decisions D1-D9: `docs/design/phase-4-engine-core.md`.

## Implementation (commits)
- `76bd55b`: `exam_schema.py`, `exam_llm.py` (isolated argv, empty cwd, prompt on stdin, no shell), `exam_checks.py` (`safe_eval`, checks, decide, score), `validate_exam` in `exam_parse.py`.
- `ccf6567`: `exam_run.py` (CLI, retry, QA, SCORE after DECISION, exit codes 0-3, partial result), `prompts/qa.md`, mock fixture.
- `a258418`, `9bee23b`: 80 new tests; `safe_eval` hardened after the verifier's findings.

## Decisions that matter
- Only `computed` (code recompute) and `key_match` count as independent. `quote` and `format` are sanity checks, so a multiple-choice item without either ends UNCERTAIN (`no_independent_check`) and is not retried (a re-solve cannot create an independent check).
- Literature: Open, quote checks only, always UNCERTAIN, `score.basis=none`.
- Extra ids in the model output are ignored and never scored (AC2 reworded; verifier D4 accepted).

## Tests and verification
- 108 unit tests OK (28 old + 80 new), mock only; tester mutations 17/17 killed, coordinator mutation (key appended to the solve prompt) killed by 3 tests, `safe_eval` mutations killed by 5 and 1 tests.
- Real-path check at $0 (`work/TASK-004/handoff/evidence.md`): `--real` against a fake `claude` executable showed the isolated flags, an empty cwd that is removed afterwards, and a key sentinel present in no prompt or output.
- Verifier (`verify.md`): AC1-AC6 PASS. Found `safe_eval` overflow (`(10**100)**4`) and two hangs (pow tower, `round(5,-999999999)`); fixed with float-only evaluation, a 1e100 cap, a depth cap and a round-digits cap, regression-tested and re-verified.

## Limitations
- The mock replies are recorded fixtures: this proves plumbing and decisions, not accuracy. That is REQ-0009 and needs the user's explicit go.
- With `--real`, the retry cost is bounded by `calls <= 1 + 2*max_attempts` and `--max-cost-usd`, but the real cost per exam is unmeasured.
- The coder's Bash `cp` into `.claude/agents/*` passing the context guard (earlier task) is still an open item.

## Next
REQ-0011 (result.json to Markdown/PDF report), then REQ-0009 real benchmark (after the user's go), REQ-0003/0004 examples.
