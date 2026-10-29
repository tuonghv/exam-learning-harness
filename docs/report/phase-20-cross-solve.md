# Report: TASK-020 cross-solve (REQ-0023, EPIC-006)

**Verdict: built and mock-verified; real value of "A and B agree" unmeasured (AC5 waits for the user's go).**

## What exists
- `scripts/exam.py cross-solve EXAM.md --pdf FILE|doc.json --pages SPEC (--dry-run | --mock FILE | --real) --out DIR`: never defaults to real. Route A = the exam text through the unchanged solver prompt; route B = the rendered page images with the same prompt and an image rule (number questions 1..N in reading order). Answers are compared per question: letter, four Part II verdicts, or number plus unit; anything else folded text.
- Output `cross.json` and `review.md`; statuses `agree` or `needs_review` with reason `differ`, `missing_a/b`, `declined_a/b`, `count_mismatch` (route B returning another question count never agrees).
- Calls <= 4 (one retry per route), cost cap checked before each call; answer-guide pages refused unless `--allow-key-pages`; pages must exist in the document.
- Solving engine, prompts and schemas unchanged.

## Verification
452 unit tests OK (11 new); mutation (always-agree) is caught; seeded sign, digit, letter, verdict and unit corruptions are each detected. Dry run on the real trial document works and refuses answer-guide pages (exit 3). Evidence: `work/TASK-020/evidence/`.

## Limits
- AC5 not done: no real call yet (about 2 calls, cap $1.00). Until then agreement is unmeasured as a correctness signal; both routes use the same model, so a shared error can agree.
- Route B ids rely on reading-order numbering; a wrong count flags everything (conservative, no silent mis-pairing).
- The text route needs an exam Markdown for the trial PDF (from refine output); that conversion is not automated yet.

## Next
Build the trial exam Markdown from the refined questions, then the real measurement with your go.

User instructions honoured: lean plan accepted, comment less, cost gate kept, no engine change.
