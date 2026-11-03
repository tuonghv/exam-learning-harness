# Phase 68 - Scorer keeps the sign (TASK-068)
Task: TASK-068 (REQ-0076) · Status: designed. Builds on phase 67 (`_neg`, `_SIGN`, `_note_match`).

## Goal
`scorer.match` must not treat an answer that differs from the key only by a leading minus (ASCII `-` or U+2212) as a match. Seen when: key `sqrt(2)` vs answer `-sqrt(2)` is False (today True) and the reverse is False; `- sqrt(2)` (a bullet with a space) is still a bullet, not a sign.

## Constraints
`_strip` (scorer.py:21) removes `^\s*[-*]\s*` — a leading bullet or sign. Only the sign case changes; option letters, order answers, true/false, fractions and the phase-67 note path keep their results. Additive for matches that were already False. Stdlib only.

## Generality
No subject or exam literal; the rule is about signed values in any subject.

## Plan modes
Scorer only (benchmark, solve --key, run-stats). Solve prompts unchanged.

## Design
- 68.1 In `match`, before comparing the stripped values, compute `_neg(answer)` and `_neg(key)` (phase 67 helpers, which already treat `- ` with a space as a bullet and U+2212 as a sign); if they differ, return False for non-open keys. Equal signs: compare stripped values as today.
- 68.2 Free replay: re-score every saved result under plans/ and work/ (regset run1-run3, dgnl-real, trial) with old and new scorer; list every verdict flip (expected: none; any flip is a real false pass found).

## Unit tests
`-x` vs key `x`, `x` vs key `-x`, `−x` (U+2212), `- x` bullet vs key `x` (match), `-3` vs `-3` (match), `-3` vs `3`, `-1/2` vs `1/2`, key with minus and answer without, option letters/true-false unchanged, phase-67 note cases unchanged.

## Verification
Free: unit suite, golden outputs byte-identical elsewhere, replay of saved results. No paid run.

## Failure modes
A dash that is not a sign (list bullet `- `) must keep matching; an answer starting with an en/em dash is not a sign (stay as today).

## Decisions
Fix in `match`, not in `_strip` (other callers of `_strip` unchanged).

## Out of scope
Fractions/units normalisation; changes to the verifier or reviewer.
