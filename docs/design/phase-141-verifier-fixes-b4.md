# Phase 141 – Verifier fixes from review batch 4 (TASK-141, REQ-0148)

Source: triage `docs/design/phase-137-review-triage-b4.md`, rows in `work/TASK-137/handoff/design-a.md`, repro R2.

## Plan modes
Deterministic checks of every solve (`det_checks`: computed, format, quote). A false `fail` costs a paid retry, so
these fixes reduce paid calls; no prompt or cache-key change.

## Design
- 141.1 137-F005: at the top of `_computed`, strip one leading label `^[^=]*[^\W\d][^=]*=\s*` (text with a letter
  before the first `=`) from the answer before both value readers: `x = 1/2` -> `1/2`, `v2 = 10` -> `10`.
- 141.2 137-F006: replace `√\s*(\d+(?:[.,]\d+)?)` with `sqrt(\1)` before the plain `√` replace in verifier.py
  (~116) and scorer.py `_exact_value` (~60); also `(\d)\s*sqrt` -> `\1*sqrt` so `2√3` evaluates.
- 141.3 137-F007: the ordering format check collects option letters with its own `[a-z]` regex (verifier.py ~70/77);
  `_letters` (a-e) stays for `_part_format`.
- 141.4 D4: `_quotes` skips the bare-text match when `bare.strip()` is empty (a quote that is only an option label).

## Verification ($0)
`tests/unit/test_verifier_fixes_141.py`, one test per id failing on old code (R2 -> ['pass','pass','pass','pass'],
6-letter ordering format pass, `2√3` computed pass, label-only quote not passed); existing verifier/scorer tests
green; `--fast` NEW 0; 3 ledger rows fixed (D4 has no ledger row).
