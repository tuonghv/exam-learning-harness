# exam-learning-harness

Checkable input/expected-output examples (few-shot and eval) for Maths, Physics, English and
Literature at Vietnamese high-school graduation / university-entrance level, plus stdlib Python
tools to validate and score them.

- Purpose, data model, components, flow, invariants: `docs/guide/architecture.md`
- Example format standard: `examples/FORMAT.md`
- Requirements: `docs/req/` (EPIC-002); design: `docs/design/`

## Engine (`exam_engine`)

One package under `src/`, stdlib only (Python >= 3.8, no dependencies), entry `scripts/exam.py`.

```
src/exam_engine/  settings.py cli.py engine.py
  core/       schema.py (validator) safe_eval.py decision.py (decide, evidence_kind)
  adapters/   claude.py            the ONLY module that runs the claude CLI
  pipeline/   parser router solver verifier scorer reporter examples_check
  utils/      md2html.py text.py
config/       engine.json (defaults)  subjects.json (per subject: task, checks, score_basis, language, prompt)
prompts/      dev/ (editable: system.md exam/solve.md subjects/*.md verification/verify_answer.md)  releases/vX.Y.Z/ (frozen + MANIFEST.json)
schemas/      solve_out / qa_out / result  (*.schema.json)
tests/        unit/  integration/ (fake claude executable on a temp PATH)
workspace/    runtime output, gitignored
tools/examples/*.py   thin shims for the old commands
```

Usage (always `python3 -I`):

```
python3 -I scripts/exam.py solve EXAM.md --out DIR [--key KEY.md] (--mock FILE | --dry-run | --real)
python3 -I scripts/exam.py parse EXAM.md
python3 -I scripts/exam.py verify EXAM.md SOLVE_OUT.json
python3 -I scripts/exam.py report RESULT.json --out DIR [--no-pdf]
python3 -I scripts/exam.py check-examples
python3 -I scripts/exam.py score --answers-dir D
python3 -I -m unittest discover -s tests/unit        # and: -s tests/integration
```

Exit codes of `solve`: 0 all PASS, 1 any FAIL/UNCERTAIN/unresolved, 2 invalid input or usage,
3 blocking stop (auth, rate limit, service, cost or call cap). Nothing runs without `--mock`,
`--dry-run` or `--real`; `--real` is capped by `--max-cost-usd` and `--max-attempts`.

Safety rules: the answer key is opened only in `pipeline/scorer.py`, after every model call, and
never appears in a prompt; model text is data (escaped in reports, never executed); every model
call goes through `adapters/claude.py` (a test greps for others); a new subject is a
`config/subjects.json` entry plus an optional `prompts/dev/subjects/<name>.md`, no engine code.
