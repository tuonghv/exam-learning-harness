# Report phase 67: answer with a trailing note matches the key (TASK-067; REQ-0075)

Verdict: adopted. The keyed regression set (phase 66) found a false FAIL: key `sqrt(2)`, engine answer `sqrt(2) (xấp xỉ 1.4142)`, scored FAIL in both runs. Cause: `scorer.py:46` — the numeric parser returns nothing for a key starting with `sqrt`, so the comparison fell back to string equality with the note still attached (the computed check and the reviewer had both passed it). Fix: an additive value-part match (`_note_match`): the value must equal the key exactly, any number in the note must agree with the value, the sign (ASCII or U+2212) is compared, and it can only turn a FAIL into a match. `verifier.py` `_TAIL_NOTE` now needs whitespace before the parenthesis, so `sqrt(2)` is no longer mangled.

## Evidence (work/TASK-067/evidence/, not published)
1304 tests, only baseline failures. Free replay of 36 saved items: exactly math/005 FAIL -> PASS (run1 and run2). Adversarial pairs stay FAIL (wrong value with a note, `sqrt(3)` with `(approx 1.4142)`, disagreeing note number, `2` vs `sqrt(2)`, multi-value, sign flip, note-only); mutations killed. Paid re-score (run3, 0.618 USD, 18 items): math/005 FAIL -> PASS as intended; math/gen-102 PASS -> UNCERTAIN is `malformed_output` on both attempts (a model format error, scorer not involved; it passed in run1 and run2), so a single flip needs a repeat before it counts as a regression.

## Limits
Pre-existing and unfixed here: note-less answers are sign-blind (`scorer._strip` drops a leading `-`; `sqrt(2)` matches key `-sqrt(2)`), REQ-0076, next. Low: a note-less `f(2)` can still pick an option letter in `verifier.py:90` (accepted). One malformed-output flake in 18 items shows the noise is not zero.

User instructions honoured: RAW-00188.
