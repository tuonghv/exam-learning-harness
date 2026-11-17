# Phase 144 – Scorer: strict half-unit tolerance, no decimal for fraction keys (TASK-144, REQ-0151)

Source: user decision RAW-00360 on the TASK-137 policy questions (D1 strict, no decimals).

## Plan modes
Numeric scoring of every keyed run (`scorer.match`, `_note_match`). No solve, prompt or cache change.

## Design
- 144.1 D1: the numeric tolerance becomes exclusive at the half unit of the key's last digit: scorer.py ~57
  `abs(diff) < 0.5 * 10 ** (-d) * 10 ** ke - eps` and ~103 `abs(v - x) < 0.5 * 10 ** (-d) - eps`, with a tiny
  eps (1e-12 scaled) so float noise on the exact half does not pass. Rounding still counts (`5.49` for `5`,
  `3.457` for `3.46`); `5.5`, `4.5` for `5` and `3.465` for `3.46` are wrong.
- 144.2 No decimal for a fraction key: already the behaviour since TASK-138 (exact fraction compare); add a test
  that pins it (`4.67` vs `14/3` wrong, `28/6` correct).

## Verification ($0)
`tests/unit/test_scorer_strict_144.py` (D1 tests fail on old code; the fraction test pins current behaviour);
`test_scorer_sign.py`, `test_scorer_fixes_138.py`, `test_benchmark_fixes.py` green; `--fast` NEW 0; re-score of
the stored keyed answers (`work/rescore/`) old vs new, flips listed.
