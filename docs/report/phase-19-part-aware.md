# Report: TASK-019 part-aware refine and Part II/III format checks (REQ-0026, EPIC-006)

**Verdict: built and verified on mocks and on the saved real replies; part I is not detected on the trial pages.**

## What exists
- `refine.split_part`: a leading "PHẦN I-V" heading line is removed from a question's text, heading-only items are dropped, `part` is stored per refined question and carried across pages. Numbering gaps are judged per part (restart at 1 on a new part is fine).
- `verifier._part_format` (math/physics, no options): Part II shape (a-d lines) needs 4 true/false verdicts; Part III shape (no a-d lines) needs a number. Tolerant: only clearly wrong shapes fail. Solver prompt and output schema unchanged.

## Verification
441 unit tests OK (9 new); a mutation per rule is caught; `check-examples` OK (25 pairs). Replay on the saved real refine replies (TASK-017 run, no new call): Part II questions 2-4 and Part III questions 1-6 get the right part; the heading no longer sits in question 1's text. Evidence: `work/TASK-019/evidence/`.

## Limits
- The page-1 questions (Part I) stay `part: null`: the "PHẦN I" heading was not in the reply text. A later step can infer the part from the first heading found.
- The Part II/III checks use heuristics on question text (a-d lines, no options); a Part III question that prints "a)" lines would be treated as Part II.
- Real accuracy of these checks on solver answers is unmeasured (needs a solve run).

## Next
REQ-0023 (cross-solve: text route vs page-image route).

User instructions honoured: lean plan accepted, comment less, no solving-engine change.
