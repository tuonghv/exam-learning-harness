# Phase 74 - Nearest-value rule for approximate questions (TASK-074)
Task: TASK-074 (REQ-0080) · Status: designed.

## Goal
When a question asks for an approximate or nearest value (Vietnamese "gần nhất" / "xấp xỉ", English "closest", "approximately", "nearest"), the solver computes the plausible readings (for example deposits at the start or at the end of a period) and chooses the option nearest to the computed value; a non-exact match never rejects a reading. Seen when: DGNL 2026 Math 63, where the solver computed 19.855 million, discarded it because no option matched exactly and answered with another reading (19.975 million) that equals an option.

## Constraints
Dev channel prompt only (`prompts/dev/exam/solve.md`, `prompts/dev/lang/vi/exam/solve.md`); the release channel stays frozen; one added rule, no subject or exam literal; all other prompt bytes unchanged (golden); no schema change.

## Generality
The rule is about approximate wording and ambiguous readings of any quantitative question; the trigger words are listed in both languages, not by subject.

## Plan modes
`solve` dev channel only (cross-solve route A uses the same solve prompt: unchanged apart from the rule).

## Design
- 74.1 Rule 6 in `exam/solve.md` and `lang/vi/exam/solve.md`: "If the question asks for an approximate or nearest value, compute every plausible reading of the wording (for example start or end of a period, inclusive or exclusive), then choose the option whose value is nearest to a computed reading; never discard a computed value only because no option equals it exactly; list the readings and their distances in `checks`."
- 74.2 Unit tests: the rule appears in both dev prompt files and in the assembled dev prompt; absent from the release prompt; all other prompt bytes unchanged for examples/ and evals/ inputs.
- 74.3 Real check (coordinator, caps): re-solve DGNL 2026 Math 63 with the dev channel, then the 18-item regression set once (cap 0.80 USD) on the dev channel: verdicts equal to the last dev run apart from known flakes.

## Unit tests
As 74.2.

## Verification
Free: unit suite and prompt diff. Paid: Math 63 re-solve (about 0.1 USD) and one regression-set dev run (about 0.7 USD).

## Failure modes
A rule that makes the solver always pick the nearest option for exact-value questions: the rule applies only to approximate wording; checked on the regression set (exact-value items must not change).

## Decisions
Prompt rule over code: the failure is a reasoning step ("closest" treated as "exact").

## Out of scope
A code-level post-check of the chosen option's distance (can follow if the prompt rule is not enough).
