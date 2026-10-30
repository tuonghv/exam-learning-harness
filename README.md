# exam-learning-harness

Checkable input/expected-output exam examples (few-shot and eval) plus a stdlib Python engine to solve, verify, report and score them.
- Layout: `src/exam_engine` (engine; `adapters/claude.py` is the only model call), `scripts/exam.py` (CLI), `prompts/`, `schemas/`, `config/` (`subjects.json`), `tools/examples` (thin shims), `tests/`, `examples/`, `evals/`.
- Run (always `python3 -I`): `scripts/exam.py solve`, `exam.py parse`, `exam.py verify`, `exam.py report [--view sheet|learn]`; real runs need `--real` (paid).
- Architecture, flow, invariants, test commands: `docs/guide/architecture.md`
- Example format standard: `examples/FORMAT.md`
- Requirements: `docs/req/`; design: `docs/design/`; guides: `docs/guide/`
