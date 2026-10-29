# Phase 6: engine structure (REQ-0012, DRAFT until Q1-Q4 are answered)

Reference: `tmp/engine-architecture.md` (RAW-00038; `tmp/` is gitignored, so the reference is cited, not committed).
Goal: one package, grouped by responsibility, behaviour unchanged. Nothing is rewritten: each current module moves,
the 108+ tests are the regression net after every step.

## Target layout
```
README.md  pyproject.toml            (no dependencies; python>=3.8)
config/    engine.json  subjects.json
prompts/   system.md                 common rules (no key, plain-text math, output rules)   <- split from tools/examples/prompts/solve.md
           exam/solve.md             task wording
           subjects/{math,physics,english,literature}.md   subject addenda, loaded through config
           verification/verify_answer.md                   <- tools/examples/prompts/qa.md
schemas/   exam_input.schema.json  exam_output.schema.json (RESULT)  solve_out.schema.json  qa_out.schema.json
src/exam_engine/
  __init__.py  cli.py  engine.py     engine.run(...)  <- exam_run.run
  settings.py                        one place for paths and config loading
  core/      schema.py (mini validator) safe_eval.py decision.py (decide, evidence_kind)
  adapters/  claude.py               <- exam_llm.py (the ONLY claude -p caller)
  pipeline/  parser.py router.py solver.py verifier.py scorer.py reporter.py
  utils/     md2html.py text.py
tests/       unit/ (today's 108+)  integration/ (mock end to end, fake `claude` executable)
examples/<subject>/  evals/{inputs,keys}/<subject>/     unchanged (approved FORMAT.md)
scripts/     exam.py                 the single entry: solve | parse | verify | report | check-examples | score
workspace/   runs/ logs/ cache/      gitignored runtime output (default --out workspace/runs/<stamp>-<exam>)
work/        role handoffs (workflow), unchanged
```

## Map: today -> new
| Today | New |
|---|---|
| `exam_llm.py` | `adapters/claude.py` |
| `exam_schema.py` (dicts) | `schemas/*.json` + `core/schema.py` |
| `exam_checks.py` | `core/safe_eval.py`, `core/decision.py`, `pipeline/verifier.py` (det_checks), `pipeline/scorer.py` (score) |
| `exam_parse.py` | `pipeline/parser.py` (parse_exam, validate_exam, parse_expected) |
| `exam_run.py` | `engine.py` (run), `cli.py` (flags), `pipeline/solver.py` (prompt build + SOLVE) |
| `exam_report.py` | `pipeline/reporter.py` |
| `md2html.py` | `utils/md2html.py` |
| `check_examples.py`, `score_eval.py` | `pipeline/` helpers behind `exam.py check-examples` / `score` |
| `tools/examples/prompts/*.md` | `prompts/` as above |
| `tools/examples/tests/` | `tests/unit/` |
| `tools/examples/*.py` | 3-line shims calling the package, kept until the user says remove |

## Differences from the reference, and why
| Reference | Here | Why |
|---|---|---|
| `config/*.yaml` | `config/*.json` | stdlib only; Python 3.8 has no YAML/TOML parser (Q1) |
| `prompts/exam/parse.md` | none | parsing is code (`parser.py`), no model call; fewer calls |
| `src/exam_engine/subjects/` | subject policy in `config/subjects.json` + `prompts/subjects/*.md` | adding a subject must not add engine code; Literature = `{"task":"Open","checks":["quote"],"score_basis":"none"}` |
| `prompts/output/answer_format.md` | stays in `system.md`/`solve.md` | one reuse site, no split needed |
| `tests/evals/` | `evals/` data folder kept | approved FORMAT.md, eval keys must never sit beside code |
| `examples/input`, `examples/expected` | `examples/<subject>/` | approved format, pairs per subject |
| workflow designer -> coder -> verifier -> tester | designer -> coder -> tester -> verifier (current) | user rule: do not change the workflow |
| `pipeline/scorer.py` absent | added | SCORE runs after DECISION and is the only key reader |
| `workspace/` | added, gitignored; `work/` stays | `work/` is workflow state, not run output |
| a Python entry point | `scripts/exam.py` shim inserts `src/` into `sys.path` explicitly | repo rule: tools run as `python3 -I <script>` (no cwd on the path) |

## Rules kept
Key opened only in `scorer.py`; all `claude -p` through `adapters/claude.py` (a test greps for any other); `docs/prompts/` untouched; stdlib only, Bash 3.2; exit codes 0-3; the three run modes `--mock/--dry-run/--real` and the cost cap stay.

## Build (TASK-006, each step committed green, tests unchanged in meaning)
S1 package skeleton + `settings.py` + `adapters/claude.py` + shim; S2 schemas to JSON + `core/`; S3 `pipeline/` (parser, solver, verifier, scorer, reporter); S4 `engine.py` + `cli.py` + `scripts/exam.py`; S5 prompts split + `config/subjects.json` + subject test; S6 tests moved to `tests/unit`, integration test with a fake `claude`, README, `.gitignore` `workspace/`.
Needs the user's say (not done by me): CLAUDE.md lines naming `tools/examples/*` and `examples/*` commands, and any `.claude` hook path; I list them and ask.

## Open questions
Q1-Q4 in `docs/req/items/REQ-0012.md`.
