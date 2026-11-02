---
name: review-loop
description: When to stop loops of developer/tester/QA runs and hand the case to the human reviewer, and how to run the human review pack (review/ folder, review-pack, review-apply). Use after an engine change on exams, when a defect survives 2 fix rounds, or when correctness needs human judgment.
---

# Review loop

Many reruns by roles cost tokens and still cannot settle some questions (no answer key, flawed or ambiguous questions, extraction fidelity on a figure). Humans settle those quickly. So: **stop looping, ask the human.**

## Stop rule (user, RAW-00158)
Hand the case to the human instead of another run when ANY holds:
- the same defect survives 2 fix rounds, or a role needs a 3rd round;
- correctness depends on a judgment no script can make (answer key unknown, two defensible options, figure read, extraction fidelity);
- roles disagree and the evidence is the same on both sides;
- the next step would only re-run the same check with more tokens.
Then: write the case to the review pack (below), say in one line what was tried, give the options with a recommendation, ask the user, and keep working on other tasks.

## Pack (REQ-0055)
- `exam.py review-pack --exam-id ID --subject NAME --result RESULT.json --exam EXAM.md [--refined R.json] [--offset N]` -> `review/<exam-id>/<subject>.md` (one section per question) and `INDEX.md`; `review/` is user-visible and gitignored.
- The user fills `Your review:` per question (agree/disagree/unsure, correct, kind, note). `exam.py review-apply --exam-id ID` reads them: agreement with Wilson, disagreements by printed number and kind, `improvements.md`.
- Re-running a pack keeps typed marks (merged by printed number).

## After each engine change
Run each subject on its small slice (2-3 pages), rebuild the packs, tell the user which file to open and what changed, ask for review. Turn each human finding into a REQ with the question numbers as evidence; never tune the engine to one exam.

## Does not
Put human verdicts into solver inputs or eval keys (a human key file only when the user says so); copy question text outside `review/`.
