# Purpose and architecture

## Purpose

An **exam/learning harness**: a small, checkable set of input/expected-output examples and the
tooling around them, used to teach and to evaluate an AI solver on Vietnamese high-school
graduation / university-entrance level questions in four subjects: Mathematics, Physics,
English and Literature.

It answers two questions:
1. **Few-shot:** which worked examples can be shown to a solver so it answers in the right format and depth?
2. **Eval:** how well does a solver do on questions it has never seen, scored against hidden keys?

Non-goals: not a security scanner (the repo was cloned from one; its scan rules are leftovers and
untrusted); no network, no external services, Python 3.8 stdlib only.

## Data model

| Set | Input (solver sees) | Key (expected) | Shown to solver? |
|---|---|---|---|
| Few-shot | `examples/<subject>/input-NNN.md` | `examples/<subject>/expected-NNN.md` | yes, both |
| Eval | `evals/inputs/<subject>/input-NNN.md` | `evals/keys/<subject>/expected-NNN.md` | input only; **key never exposed** |

`<subject>` = `math`, `physics`, `english`, `literature`. Target: 5 per subject (2 few-shot + 3 eval).
Exact file format: `examples/FORMAT.md` (approved standard).

## Components

Engine: one stdlib package `src/exam_engine/`, entry `scripts/exam.py` (always `python3 -I`).

```
src/exam_engine/
  cli.py engine.py settings.py   subcommands; solve loop -> result.json + reports; config loading
  core/       schema.py (validator) safe_eval.py decision.py (decide, evidence_kind)
  adapters/   claude.py          the ONLY module that runs the claude CLI
  pipeline/   parser router (subject policy, language) prompts solver verifier scorer
              reporter (answer sheet, learn view) examples_check cross benchmark genexam
  ingest/     api.py segment.py parts.py refine.py inspect.py schema.py optional.py
    adapters/ pdf.py docx.py markdown.py image.py     source file -> document -> exam .md
  utils/      md2html.py text.py (detect_lang)
config/       engine.json (defaults)  subjects.json (per subject: task, checks, score_basis, language, prompt)
schemas/      solve_out / qa_out / result  (*.schema.json)
prompts/      dev/ (editable)  releases/v1.0.0 v1.1.0 v1.2.0 (frozen, MANIFEST.json)
              each channel: system.md exam/ subjects/ verification/ lang/vi/ (+ genexam*.md in dev/)
examples/     few-shot pairs + FORMAT.md        evals/  inputs/ keys/ (+ generated*/ dgnl/)
tools/examples/*.py   thin shims to src (check_examples, score_eval, exam_run, ...)
tests/        unit/  integration/
docs/req/ (WHAT)  docs/design/phase-N-*.md (HOW, phases 1-30)  docs/guide/  .claude/ (workflow)
```

`exam.py` subcommands: `solve parse verify report check-examples score prompts check-prompts ingest
ingest-inspect ingest-refine cross-solve benchmark extract-eval gen-exams lessons`. Common `solve` flags:
`--out --key --mock|--dry-run|--real --max-attempts --max-cost-usd --timeout --model --lang vi|en|auto
--channel release|dev --prompt-version --no-pdf`. A new subject is a `config/subjects.json` entry plus an
optional `prompts/dev/subjects/<name>.md`; no engine code.

## Flow

1. **Author or ingest** an exam as `.md` per `examples/FORMAT.md`; `ingest` converts pdf/docx/md/image
   (`ingest-inspect` previews, `ingest-refine` AI-refines questions; see `docs/guide/ingest-usage.md`).
2. **Check** with `check-examples` (structure, verification lines, eval/few-shot separation).
3. **Solve** `exam.py solve EXAM.md --out DIR`: parse, route (subject policy), prompt (channel + language),
   call claude via the adapter, verify (checks per subject), QA review, decide, then score if `--key`.
   Writes `result.json` (validated by `schemas/result.schema.json`). Exit: 0 all PASS, 1 any
   FAIL/UNCERTAIN, 2 invalid input, 3 blocking stop (auth, rate limit, service, cost/call cap).
4. **Report** `exam.py report RESULT.json --out DIR [--view sheet|learn] [--no-pdf]`: `report.md`
   and `answers.md` always, `report.html`/`report.pdf` best effort. `sheet` = answer sheet (default),
   `learn` = study view (answer, why, steps) with labels in the explanation language.
5. **Evaluate**: `score --answers-dir D`; `benchmark` runs evals and `lessons --summary` distils
   them; `cross-solve` compares solves; `gen-exams` makes new exams.

Language precedence (`pipeline/router.py language()`): `--lang` > header `Language:` > subject policy
`language` > `vi`; `auto` is resolved by `detect_lang` from the question text, then pinned into the header.
Prompt variants for a language live under `prompts/<channel>/lang/<code>/`.

## Invariants

- Eval keys never appear in eval inputs, few-shot files or prompts; the key is opened only in
  `pipeline/scorer.py`, after every model call. No question is reused across sets.
- Nothing runs without `--mock`, `--dry-run` or `--real`; `--real` is capped by `--max-cost-usd`
  and `--max-attempts`. Every model call goes through `adapters/claude.py` (a test greps for others).
- Model text is data: escaped in reports, never executed (`core/safe_eval.py` for computed checks).
- Release prompts are frozen (MANIFEST.json, `check-prompts`); edit only `prompts/dev/`.
- Every key is verified by an independent method (Maths/Physics recompute; English rule check;
  Literature quotes verbatim). Items are original; English items in English, others in Vietnamese.
- English few-shot #1 (`examples/english/input-001.md`, `expected-001.md`) stays unchanged.
- Python >= 3.8 stdlib only; Bash 3.2 clean.

## Run and test

Always `python3 -I`. Tests (stdlib `unittest`):

```
python3 -I -m unittest discover -s tests/unit
python3 -I -m unittest discover -s tests/integration   # --real against a fake `claude` on a temp PATH, no network
```

- `python3 -I scripts/exam.py parse EXAM.md` prints the parsed exam as JSON; `verify EXAM.md SOLVE_OUT.json` runs code checks and a decision per question, no model call.
- `solve` needs exactly one of `--mock FILE`, `--dry-run`, `--real` and `--out DIR`.
- `workspace/` is runtime output (solve and report results), gitignored; never commit it.

## Workflow

Work is tracked in the requirement ledger (`docs/req`, EPIC-002) and delivered through TASKs
(TODO, DESIGN, IMPLEMENTING, UNIT_TESTED, VERIFIED, DONE) by the designer, coder, tester and verifier roles.
For content tasks the verifier's independent oracle run is the real verification (see `crosscheck`).
