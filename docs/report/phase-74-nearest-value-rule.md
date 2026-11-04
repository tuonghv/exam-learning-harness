# Report phase 74: nearest-value rule for approximate questions (TASK-074; REQ-0080)

Verdict: the rule is adopted in the dev channel, but it did not fix the case that motivated it. DGNL 2026 Math 63 stays wrong (0 of 2 re-solves). The cause is not "closest taken as exact" but a reading ambiguity: the question does not say whether deposits are made at the start or at the end of each month. The solver now applies the rule (it computes 19,973,000 for end-of-month deposits and compares the distance to every option) and writes uncertainty MEDIUM naming the other reading, which would lean to the key option. So the ambiguity is visible, not resolved.

## Change
Dev prompts only: rule 6 in `prompts/dev/exam/solve.md` (rule 5 in the Vietnamese file): for approximate or nearest-value wording, compute every plausible reading, choose the option nearest to a computed reading, never discard a computed value only because no option equals it exactly, list readings and distances in `checks`. Release prompts byte-identical on 47 inputs; 1404 tests, only baseline failures.

## Evidence (paid, coordinator, RAW-00186; `work/TASK-074/evidence/paid-nearest-rule.txt`)
Math slice twice, 0.33 USD in total: 63 still C, 65 still A (key oddity), 66 correct. Regression set on the dev channel (0.674 USD): 15 pass, 0 fail, 3 uncertain; one change against the previous dev run (physics/003 FAIL to PASS, the quote-check flake did not recur): no regression.

## Limits / next
One question tested for the target behaviour. Follow-up REQ-0082: when the solver's own uncertainty names an alternative reading that selects a different option, mark the answer needs_review and feed the confidence tier (REQ-0079).

User instructions honoured: RAW-00197.
