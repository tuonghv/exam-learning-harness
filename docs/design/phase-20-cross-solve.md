# Phase 20: cross-solve, answer-level agreement of two input routes (REQ-0023, TASK-020; EPIC-006)

## Goal
An extraction error matters only if it changes the answer. Solve the exam twice through independent inputs and compare final answers: route A = the exam Markdown (native/refined text, same input as `solve`), route B = the page images, no transcript. Equal -> `agree`; anything else -> `needs_review` with both answers. Agreement is evidence, not proof (both routes use the same model family). The solving engine, prompts and output schema are not changed: both routes reuse `solver.base_prompt` and `SOLVE_OUT`.

## Command
`scripts/exam.py cross-solve EXAM.md --pdf FILE.pdf|doc.json --pages SPEC --out DIR (--dry-run | --mock FILE | --real) [--max-cost-usd 1.00] [--model sonnet] [--timeout S] [--allow-key-pages]`. Never defaults to real. Pages are checked like refine (`check_key_pages`: answer-guide pages refused). Calls: one per route, one retry each on a malformed reply (<= 4); cost cap checked before each call. Dry run prints call bound, cap, both prompts, the page list; no call.

## Code (`pipeline/cross.py`, CLI in `cli.py`)
- `route_a_prompt` = `solver.solve_prompt(exam, text, None)`; `route_b_prompt` = `solver.base_prompt` + "the exam is in the attached page images; number the questions 1..N in reading order across the pages (ignore restarts at a new part); N = <count>; do not guess unreadable content".
- `same_answer(a, b)`: canonical forms: single letter A-D; Part II four verdicts (T/F); first number as float (exact, no tolerance guess); else folded text.
- `compare`: per exam question id: `agree` | `needs_review` with reason `differ`, `missing_a`, `missing_b`, `declined_a`, `declined_b`; if route B returns a different number of questions than N, every question gets `count_mismatch` (alignment not trusted).
- Outputs: `cross.json` ({routes, questions[{id, answer_a, answer_b, status, reason}], summary, calls, cost_usd}) and `review.md` (needs_review list).
- Exit: 0 all agree, 1 any needs_review, 2 usage/input, 3 call/cost stop.

## Tests ($0, mock list [reply A, reply B])
agree; seeded different letter / sign / number; missing id; declined; count mismatch; Part II verdict forms; numbers `3,46` vs `3.46`; malformed then valid (retry); two malformed -> error; dry-run no call; no mode -> usage; key pages refused; solving engine files untouched (hash of solver/engine unchanged in the diff, checked by test of `solve --mock` regression suite staying green).

## Real measurement (REQ-0023 AC5, needs the user's go)
Trial PDF vs answer-guide key: accuracy of A, of B, of "A and B agree"; report n and no accuracy claim.

## Open questions
None (REQ-0023 Q1, Q2 accepted; lean plan accepted RAW-00074).
