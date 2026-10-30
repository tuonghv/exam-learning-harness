# Phase 22: generated exams and lessons (REQ-0027, concept round)

## Goal
Test the engine on exams it has not seen: generate small Vietnamese-style math exams with keys, run the unchanged `benchmark`, and write each failure as a lesson. Concept first: 1 subject (math), 3 exams, one real round under $1.

## Design
- `exam.py gen-exams --subject math --n 3 --seed S --out evals/generated (--dry-run | --mock FILE | --real) [--max-cost-usd 0.5] [--model M]`. Never defaults to real; `--dry-run` and `--mock` cost $0.
- `pipeline/genexam.py`:
  - `build_prompt(subject, seed, n)`: template `docs/prompts/dev/genexam.md` (a dev prompt, not an exam prompt). Asks for one Grade 12 graduation-style Vietnamese question per call as JSON `{skill, question, final_answer, solution, check}`; `check` is a python-free arithmetic expression for the answer, so the key has a code oracle.
  - `generate(...)`: one call per exam through `adapters.claude` (retry once on bad JSON, cost cap). Reject when `check` evaluates (via `verifier.safe_eval`) to a value that differs from `final_answer` (`_answer_value`): a wrong key never enters the set.
  - `write(...)`: `evals/generated/inputs/math/input-1NN.md` and `evals/generated/keys/math/expected-1NN.md` in `examples/FORMAT.md` form, plus `evals/generated/manifest.json` (seed, prompt sha256, model, `generated: true`, `reviewed: false`).
  - `leak_check(input_text, key)`: error when the solution text or the `Final answer:` line appears in the input.
  - `lessons(summary)`: from a benchmark `summary.json`, one lesson per FAIL/UNCERTAIN question: item, cause class (`engine`, `bad_key`, `bad_exam`, `variance`; chosen by rule: key-match mismatch with a passing oracle = `bad_key`, check/QA finding = `engine`, otherwise `variance`; a human may reclassify), evidence. Writes `lessons.json` and `lessons.md`; `lessons --open` lists the unresolved.
- Generated set is separate from `evals/inputs`, so the hand-made numbers are never mixed; `benchmark --inputs evals/generated/inputs --keys evals/generated/keys` runs it unchanged. Engine, solver prompt and scorer are not changed; the key is opened only by `scorer.apply_key`.
- Exit: 0 ok, 1 rejected or leak, 2 usage, 3 call/budget failure.

## Tests ($0)
dry-run prints plan and bound, no files; mock writes paired files in the format, passes the format checker; wrong `check` rejected; leak detected; lessons classify a mock summary; CLI no-mode error.

## Limits
Same model generates and solves (shared blind spots); math keys have a code oracle, other subjects arrive only after this round shows value. The real round needs the user's go.
