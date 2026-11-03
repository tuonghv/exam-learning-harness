# Report phase 68: scorer keeps the sign (TASK-068; REQ-0076)

Verdict: adopted, preventive. The scorer's `_strip` dropped a leading minus, so a note-less answer `-sqrt(2)` matched the key `sqrt(2)` and `sqrt(2)` matched `-sqrt(2)` (found by the TASK-067 tester; a false-pass class). `scorer.match` now compares the sign first (ASCII minus or U+2212; a `- ` bullet is still a bullet) using the phase-67 helpers; numeric keys keep their sign too (`3` no longer matches `-3`). The fix is in `match`, not `_strip`; option letters, order answers, true/false, open rubric and the phase-67 note path are unchanged.

## Evidence (work/TASK-068/evidence/, not published)
1321 tests, failures only the 4 known baseline names. Independent replay of 323 saved answer/key pairs (regression-set runs, DGNL, trial): 0 verdict flips, so no saved score was inflated by the sign blindness; run-stats and score outputs byte-identical; 9 new tests fail on the old scorer; 5 of 6 mutations killed (the survivor, the redundant U+2212 fallback in `_neg`, is equivalent).

## Behaviour change to note
`x = -3` vs `-3` and `−x` vs `-x` now match (both correct, did not before).

## Limits
The replay covers saved pairs only. Design waiver: the designer role was waived (small change); the design is `docs/design/phase-68-scorer-sign.md`.

User instructions honoured: RAW-00188.
