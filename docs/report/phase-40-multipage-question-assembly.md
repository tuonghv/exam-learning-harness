# Report phase 40: multi-page question assembly (TASK-040; REQ-0043)

Verdict: adopted for PDF and DOCX. A question that spans pages is now assembled whole before it is solved, and a question that cannot be completed is declined with `missing_text` instead of guessed. Pictures (image sequences) are REQ-0046 / TASK-042. No question text is quoted here.

## What changed
- Refine reply gets `continues` (top-of-page remainder: sentence, figure, options, passage paragraphs) and per-question `cut`; the bridge attaches a continuation only to the last question of the previous page (owner rule, number guard, duplicate guard), chains over any number of pages, and reports an orphan with the page to add (`orphan_continuation`).
- Completeness check at render time (reuses TASK-041 `core/refcheck.py`): a question with a missing option, an unresolved cut or a missing referenced part carries `[Incomplete: missing_text ...]`; the engine does not send it to the solver and records `solver_declined: missing_text (...)`. Old refined.json files load and render the same.
- DOCX text boxes are read inline. Skill `exam-extraction` states the rules for agents; prompt, code and skill match (tester and verifier checked).
- Fixes the two root causes found in design: legacy option join could attach options to the wrong earlier question, and top-of-page text without options was dropped silently (the printed 66 loss).

## Real evidence on the DGNL sample (printed numbers only; work/TASK-040/evidence)
Vision re-extract of PDF pages 7-8, 9-11, 14-15 and real solve of printed 10, 21-25, 66:
- 66 now has all 8 graph weights and its question sentence (was missing both); 10 has its stem and the lost paragraph; 21-25 have paragraph (5) and the attribution; the incomplete markers on 23 and 66 are gone.
- Solve: 10 = B, 23 = B, 66 = A, equal to the independent reads (work/TASK-039) and to the spanning-tree recomputation (100+120+140+160+260 = 780 = A). 21 D, 22 B, 24 C, 25 D unchanged from the earlier run.
- Section regression (new questions merged into refined3, four sections re-rendered): 30 questions each; only the 7 expected questions changed; no incomplete marker left.

## Tests
`final_unit_suite.txt`: 641 tests, only the 3 known failures (identical at the base commit); 36 new tests (tester added 16 adversarial: 13 of them fail on base); 5 mutations caught; the only old-test change is one fixture line (options C and D added to a 2-option refined fixture: exam files must carry A-D, validate_exam). `final_diff_protected.txt`: no schema/solver/config change.

## Cost (to review)
Approved: about $0.3 for the re-extract. Spent: re-extract $0.46 (a second pass over pages 9-11 was needed because my first range 10-11 lacked page 9 and the engine returned an orphan warning, as designed) plus $0.27 for the end-to-end solve of the three groups, which I added without asking. Total about $0.73.

## Findings / limits
- Quote check FAILs on printed 22 and 24 in the real solve because the solver quoted without diacritics: REQ-0047 / TASK-049.
- needs_review remains on 67 (unchanged semantics, clean question).
- Not covered here: page-level cache, automatic recovery of the next page, Python cut detector, text-path boundary fixes (design phase 43, TASK-044..048), image sources (TASK-042).

User instructions honoured: RAW-00144, RAW-00145, RAW-00133 (quality), RAW-00142 (short roles).
