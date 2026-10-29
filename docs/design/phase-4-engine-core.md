# Phase 4: engine core + QA (TASK-004, REQ-0010)

Build plan for the part of `docs/design/phase-2-exam-pipeline.md` (the architecture; read 2.1-2.4 there)
that REQ-0010 covers. This file only records what changed and how the build is split. It does not repeat
the stage flow, the result schema (2.3) or the cost and safety rules (2.4).

## Goal
`python3 -I tools/examples/exam_run.py <exam.md> --out DIR` builds the call from
`tools/examples/prompts/solve.md` + the exam text, sends it to `claude -p`, validates the JSON, runs code
checks and a separate QA call, decides PASS/FAIL/UNCERTAIN with retries, and scores against a key only
after the decision. All tests use mocked replies ($0); a real call needs `--real` and the user's go.

## Scope
In: `exam_schema.py`, `exam_llm.py`, `exam_checks.py`, `exam_run.py`, `prompts/qa.md`, `validate_exam` added
to `exam_parse.py`, tests `test_exam_*.py`. Out: `exam_report.py` (REQ-0011), real benchmark (REQ-0009).
`exam_run` writes a schema-valid `result.json` itself (validate, then `json.dump`); REQ-0011 adds the
Markdown and PDF on top.

## Changes against phase 2 (decided here)
| # | Phase 2 said | Now | Why |
|---|---|---|---|
| D1 | `SOLVE_OUT` has `computed:[{expr, expect}]` | `SOLVE_OUT` = what `solve.md` emits: `schema_version`, `questions[{id, type, answer, answer_status, solution, explanation, checks, expr, evidence, uncertainty{level,reason}, reasoning_status, issues}]`, `input_issues` | `solve.md` was written after the design (RAW-00027/28); one source of truth |
| D2 | `computed` check from `computed.expect` | a `computed` check is `safe_eval(expr)` compared with the numeric part of `answer` (tolerance 0.5% of the rounding stated, default 1e-6 relative); `independent=true`, detail "arithmetic only" (Q4) | the model gives the expression, code recomputes it |
| D3 | `reasoning_status` | solver always sends `not_independently_verified`; any other value is a schema error; only `decide` can produce `PASS` | fix 8 of the prompt review |
| D4 | `answer_status` absent | `uncertain` or `unanswerable` or `answer:null` -> UNCERTAIN with finding `solver_declined`, no code check run | prompt rule 6 |
| D5 | `validate_exam` in `exam_parse.py` | not there yet; coder adds it (errors list, no raise) | only `parse_exam` exists |
| D6 | PASS needs one independent pass | independent kinds are only `computed` (code recompute) and `key_match`. `quote` (evidence is a verbatim substring) and `format` (valid letter / ordering) are sanity checks with `independent=false`: a wrong answer can quote a real line or be a valid letter. Without a key, an item with no `computed` check ends UNCERTAIN (honest: not proven) | decided in review of step A |
| D9 | call isolation | `run_claude` runs with `cwd` = an empty temp dir and `--tools "" --disable-slash-commands --no-session-persistence --strict-mcp-config`, so a real call cannot read `evals/keys` or the repo | README rule "empty temp cwd, no tools"; flags checked against `claude --help` |
| D7 | Literature | `answer = Open`, only `quote` checks, `score.basis = none`, status always UNCERTAIN, never PASS (Q5: no rubric means no independent proof); quote results and QA findings are shown | no key to compare |
| D8 | summary counts | computed in code from `questions[]` | prompt rule: model never counts |

## Modules (interfaces; phase 2 table 2.1 is the base)
- `exam_schema.py`: `SOLVE_OUT`, `QA_OUT`, `RESULT` dicts; `validate(obj, schema) -> list[str]` (subset: type, required, enum, properties, items, additionalProperties, minimum).
- `exam_llm.py`: `run_claude(prompt, *, model, timeout_s, runner=subprocess.run) -> Call`; the argv is a list (no shell), prompt on stdin, `--output-format json`; the answer is the envelope field `result`; `extract_json(text) -> (obj, err)`; `mask(s)`; an exit != 0, a timeout, an empty `result` or `is_error` becomes a `Call` with `ok=False` and a class (`auth`, `rate_limit`, `service`, `timeout`, `empty`, `other`).
- `exam_checks.py`: `safe_eval(expr)` (ast whitelist: numbers, + - * / ** %, unary -, parentheses, `sqrt log ln exp sin cos tan pi e abs round`; anything else raises); `det_checks(q, ans, exam)`; `decide(checks, review, ans) -> (status, reason)`; `score(ans, key_q)` reusing `score_eval.match`.
- `exam_run.py`: CLI (`--out`, `--key`, `--mock FILE`, `--dry-run`, `--real`, `--max-attempts` 2, `--max-cost-usd` 1.00, `--timeout` 300, `--model` sonnet) and `run(exam_path, out_dir, cfg, llm) -> (result, exit_code)`.
- `prompts/qa.md`: the reviewer prompt (question + answer + checks, never a key); output `{"reviews":[{"id","verdict":"agree|disagree|unsure","findings":[]}]}`.

## TASK steps
1. coder A: `exam_schema.py`, `exam_llm.py`, `validate_exam`, `exam_checks.py` (safe_eval, det_checks, decide, score).
2. coder B: `exam_run.py`, `prompts/qa.md`, dry-run printing the call count and the exact prompts.
3. tester: `test_exam_*.py` (list below), mocked only; mutation notes.
4. coordinator + verifier: mock end-to-end on `examples/english/input-001.md`; key-leak grep; no real call.

## Tests (mock only; each maps to REQ-0010 AC)
| # | Case | AC |
|---|---|---|
| 1 | `extract_json`: strict, fenced, outer braces, malformed, empty | 1 |
| 2 | `run_claude` with a fake runner: argv list, prompt on stdin, no shell, timeout, error classes | 1 |
| 3 | schema: missing question, wrong type, extra id, `reasoning_status: verified` rejected | 2 |
| 4 | retry: malformed twice -> UNCERTAIN, `attempts` = limit; call count never above 1 + 2*max_attempts | 2, 5 |
| 5 | `safe_eval`: `2*sqrt(3)` ok; `__import__('os')`, names, attributes, power bomb `9**9**9` refused | 3 |
| 6 | `computed` pass and fail; `format` (letter, ordering); `quote` present and absent | 3 |
| 7 | decide: AI agree alone -> UNCERTAIN; independent pass + agree -> PASS; any code fail -> FAIL; disagree -> FAIL | 3 |
| 8 | answer_status uncertain/unanswerable -> UNCERTAIN, no code check | 3 |
| 9 | Literature: Open, quote checks only, always UNCERTAIN, `score.basis = none` | 3 |
| 10 | sentinel string in the key appears in no captured prompt (solve, QA, retry) | 4 |
| 11 | key mismatch -> FAIL `differs_from_key`, no retry call afterwards | 4 |
| 12 | `--mock` and `--dry-run` never call the real runner; `--real` prints count and cap first | 5 |
| 13 | missing question in the output -> FAIL `missing_in_output`; summary counts from code | 2, 6 |
| 14 | exit codes 0/1/2/3, partial result valid on a blocking stop | 6 |

## Verification
- `python3 -I -m unittest discover -s tools/examples/tests` -> OK (28 old + new), $0.
- `python3 -I tools/examples/exam_run.py examples/english/input-001.md --mock <fixture> --out work/exam-runs/mock` -> exit 0 or 1 as the fixture says, `result.json` valid.
- `--dry-run` prints prompts; grep of the key lines in them is empty.
- Real run: not in this task (REQ-0009, user's go).

## Open questions
None: Q1-Q6 of phase 2 are accepted; D1-D8 are consequences of the already accepted prompt review.
