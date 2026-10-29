# Examples and evals

Few-shot examples and evaluation items for the exam solver. The file format is the standard in
[FORMAT.md](FORMAT.md); this page only says where files go and how to check and use them.

## Layout

| Set | Input | Key |
|---|---|---|
| Few-shot (may be shown to the solver) | `examples/<subject>/input-NNN.md` | `examples/<subject>/expected-NNN.md` |
| Eval (never shown with its key) | `evals/inputs/<subject>/input-NNN.md` | `evals/keys/<subject>/expected-NNN.md` |

`<subject>` is `math`, `physics`, `english` or `literature`. Numbering is shared per subject:
few-shot items are 001-002, eval items start at 003, so one (subject, NNN) never lives in both sets.
Create a subject dir only when its first file exists (no empty dirs, no `.gitkeep`).
`examples/english/input-001.md` and `expected-001.md` are the original pair and are never edited;
the checker accepts the old layout of `expected-001.md` only while its sha256 matches.

## Add an item

1. Write `input-NNN.md` and `expected-NNN.md` per FORMAT.md (four options A-D, a Verification
   block with a `- Check:` line, literature quotes word for word from the Passage).
2. An eval pair goes under `evals/inputs/` and `evals/keys/`; never copy key text into any input or
   few-shot file (the checker compares lines of 40 or more characters).
3. Run the check; fix every `ERROR:` line.

## Check

```
python3 -I tools/examples/check_examples.py [--root DIR]
```

Exit 0 prints `OK: <n> pairs (<f> few-shot, <e> eval)`; exit 1 prints
`ERROR: <path>: <check>: <message>` per defect (pairing, header, sections, options, verification,
literature, disjoint-id, disjoint-text, input-key, key-leak); exit 2 is a usage error.

## Few-shot use

A solver prompt may include `examples/<subject>/*.md` pairs. It never includes anything under `evals/`.

Limit: `input-key` flags answer markers at the start of a line and `key-leak` flags copied Solution/Explanation lines (>= 40 chars). A short answer written mid-line in prose is not caught, so a human reads every new eval input once.

## Eval run (main session only)

1. For each file in `evals/inputs/<subject>/`, make one fresh solver call: empty temp cwd, no tools,
   and never expose `evals/keys`.
2. Save each reply as `work/eval-runs/<ts>/<subject>/answer-NNN.md` in the expected layout (`## Question N`
   and `Final answer:` are enough).
3. Score: `python3 -I tools/examples/score_eval.py --answers-dir work/eval-runs/<ts> [--keys-dir evals/keys]`.
   It prints `<subject>/NNN Q<n>: correct|wrong|missing|manual` and `TOTAL <correct>/<objective>`,
   never key values. Open (rubric) items are `manual`. It exits 2 if the answers dir overlaps the keys dir.

## See also

Skills `verify` and `crosscheck`; `docs/design/phase-2-exam-pipeline.md`; `docs/design/phase-3-example-checker.md`.
