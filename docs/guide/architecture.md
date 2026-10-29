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

```
examples/            few-shot pairs + FORMAT.md + README.md
evals/               eval inputs and hidden keys, kept in separate trees
tools/examples/      stdlib Python, run with `python3 -I`
  check_examples.py    $0 validator: layout, required sections, Verified status, quotes verbatim, no key leak
  score_eval.py        scores a solver's answers against evals/keys (objective exact match; Literature by rubric)
  tests/test_*.py      tests for the tools
docs/req/            requirement ledger (WHAT)      docs/design/   designs (HOW)
.claude/             workflow: roles designer/coder/tester/verifier, skills, hooks, state (TASK lifecycle)
```

## Flow

1. **Author** an item as an `input`/`expected` pair following FORMAT.md; keys are independently recomputed.
2. **Check** with `check_examples.py` (structure, answer verification lines, eval/few-shot separation).
3. **Solve** (outside this repo): the solver gets the few-shot set plus eval *inputs* only.
4. **Score** with `score_eval.py` using the hidden keys; report per subject.

## Invariants

- Eval keys never appear in eval inputs, few-shot files or solver prompts; no question is reused across sets.
- Every key is verified by an independent method (Maths/Physics recompute with units and rounding;
  English rule check; Literature quotes appear word for word in the passage).
- Items are original and self-contained; English items in English, others in Vietnamese.
- English few-shot #1 (`examples/english/input-001.md`, `expected-001.md`) stays unchanged.

## Workflow

Work is tracked in the requirement ledger (`docs/req`, EPIC-002) and delivered through TASKs
(TODO, DESIGN, IMPLEMENTING, UNIT_TESTED, VERIFIED, DONE) by the designer, coder, tester and verifier roles.
For content tasks the verifier's independent oracle run is the real verification (see `crosscheck`).
