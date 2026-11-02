---
name: solve-qa
description: Senior-solver QA of exam answers without API cost: independent reads from the source, adjudication of differences, merged into the review pack as the QA line. Use after a solve run on an exam subject, or when answers are disputed.
---

# Solve QA

The user reviews EXTRACTION; answer correctness is QA's job (REQ-0056). QA = in-session subagents (verifier role), no `claude -p` spend.

## Steps (per subject, small slices)
1. Independent read: a verifier solves each question from the SOURCE pages (PDF/image Read), never from the engine output or exam file. Output table `n | answer | conf | note` by printed number, 12 words per note.
2. Compare with the engine (`work/<TASK>/compare.py` pattern): agree / differ / engine declined.
3. Adjudicate each difference, each decline and each low-confidence item with a second independent read: per option one clause, final answer, confidence, `flawed?` (two defensible options, misspelt/impossible option, missing information). Prefer the key an exam setter would give.
4. Write one QA table per subject: `n | answer | conf | flawed | reasoning` (adjudication overrides the read).
5. `exam.py review-pack ... --qa FILE` merges it: QA line and verdict (agrees / differs / flawed / qa-only / unresolved) per question, counts in INDEX.md.

## Rules
- QA split or low confidence with two defensible options: `unresolved`, both options in the reasoning; never guess.
- Same model family as the engine: agreement is not accuracy; say so in the pack header; only differences and flaws carry information.
- Printed numbers and statuses only outside `review/`; question text never in reports.
- Small slices (2-3 pages); the full exam once at the end.

## Does not
Use the engine's answer as input to QA, put QA into solver inputs or eval keys.
