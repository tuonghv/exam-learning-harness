# Phase 49: quote check tolerant of missing diacritics (TASK-049; REQ-0047)
Defect: `verifier._quotes` (src/exam_engine/pipeline/verifier.py:128-136) compares the solver's evidence quote with the passage/question/options by whitespace-folded exact match only; a correct quote that lost Vietnamese diacritics fails (`check_failed: quote`), seen on printed 22 and 24 of the real DGNL re-solve (work/TASK-040/evidence/real_solve_21-25.txt).
Design (smallest, reuse `utils.text.fold`: NFD, diacritics removed, đ->d, casefold, single-spaced):
- Keep the exact match first (unchanged result, unchanged detail text for exact quotes).
- If it fails, accept when `fold(quote)` (also with the leading option label stripped as today) is a substring of `fold(hay)`; the check detail says `verbatim (diacritics-insensitive)`. Still `pass` and still marks `independent=True` as today (the quote is evidence from the source, not a second opinion).
- Fabricated quote, quote from another question, empty or `null` quote: still fail. A quote shorter than 4 folded characters is not accepted by the folded route (avoids trivial matches like "mat").
- Backward compatible: results for exact-matching quotes are byte-identical; result schema unchanged.
Tests (tier 0, synthetic Vietnamese placeholder text, never real exam text): exact quote pass unchanged; diacritic-less quote of a passage pass with the new detail; fabricated quote fail; quote of another question's text fail; case and whitespace variants; 3-character quote via the folded route fail; empty/null as today.
Real regression (no paid call): re-evaluate work/TASK-040/real/run-21-25/result.json answers' evidence with the new check (read-only copy): printed 22 and 24 no longer FAIL for the quote; nothing else changes (print printed numbers and statuses only).
Risks: folding can accept a quote that differs by diacritics only (a different word); stated limit, the answer correctness is not judged by this check. Out of scope: solver prompt (asking for diacritics), other checks.

## Plan modes
Single-source solve and the pipeline use the same `det_checks`; the change affects every plan that verifies quotes (Vietnamese/English closed subjects), with no change to plans without quote evidence. Mock runs and real runs behave the same.
