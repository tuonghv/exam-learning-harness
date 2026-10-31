# Report phase 38: ingest numbering gaps and restarts (TASK-038; REQ-0041)

Verdict: adopted. Ingest no longer drops every question when numbering is not exactly 1..N. Gaps (ids 1 and 150) keep the questions with their printed numbers and a `numbering_gap` warning; a clean restart (1..10, 1..10) is kept with `numbering_restarted`; a restart that also has a gap (a numbered sub-list) is still skipped but flagged. Question numbers above 999 never count (a stray year cannot become a question). The exam text is renumbered 1..N with a line mapping each to its printed number.

## Evidence (work/TASK-038/evidence/)
- Defect reproduced before the change: `repro_gap.txt` (ids 1,150 -> 0 questions, `segmentation_skipped`); after: 2 questions with `numbering_gap`, consecutive control unchanged (5).
- `final_unit_suite.txt` 571 tests vs `final_base_unit_suite.txt` 553 at the design commit: the same 3 pre-existing failures; `final_numbering_tests.txt` 18 new tests OK; `final_old_assertions_removed.txt` 0 old test lines removed; `final_diff_protected.txt` no schema/pipeline/prompt/config change.
- Tester Nemesis: ingest diff base vs HEAD on every fixture (`t38_base_vs_head.txt`): differences only on formerly skipped docs; strict-numbering docs and the real DGNL `e3-*.md` byte-identical, refined3 counts 30 each; refine-guard deviation judged safe (gap doc [1,150] keeps both ids); 3 mutations caught (no >999 cap, restart-with-gap usable, gap warning dropped).
- Verifier `work/TASK-038/handoff/verify.md`: AC1-AC3 verified.

## Decision to review
Refine guard (design 38.5) was weakened by the coder: originals are dropped only when a printed number repeats, because the strict guard broke an old test whose fixture has a single question numbered 2. Tester built a gap case through refine with a mock model: no collision or loss.

## Limitations
- Residual risk: a stray number from 1 to 999 after the last question is kept as a question, visible through `numbering_gap`.
- The real DGNL native document stays skipped (7 runs, max number 5000) and now carries an extra `numbering_restarted` warning (additive).
- Documents with restarting numbers produce duplicate ids in `extract-eval` (rc 2) and refine output; out of scope.
- Cosmetic: run-span text now shows runs as printed (fixed after the tester's D1).

User instructions honoured: RAW-00128, RAW-00133 (quality), RAW-00142 (short roles).
