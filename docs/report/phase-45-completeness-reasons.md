# Report phase 45: completeness reasons (TASK-045; REQ-0049)

Verdict: adopted. `core/refcheck.incomplete_reasons` now also flags a truncated formula (`formula_unbalanced`: brackets `( [ {` counted together, odd `$`; half-open intervals stay balanced; line-start enumerators like `a)` ignored), a `trailing_operator`, a `merge_suspect` (a foreign question number inside the stem, or two A-D option runs) and a part the vision reply marked unreadable (stored as an optional field by refine). The first three are scoped to page-end, cut or continued questions so a mid-page stem with an unbalanced bracket is not flagged. A same-id rejoined question keeps its `continued_pages` and the last part's `cut`, so a resolved split question is no longer declined as `cut_unresolved`.

## Quality evidence (work/TASK-045/evidence)
`final_unit_suite.txt` 727 tests, only the 3 known failures (identical at base); `final_reasons_tests.txt` 22 tests OK (11 of the first 20 fail on the base code, proving they bite); tester oracle 500/500 (`final2_oracle.txt`); render of all 24 refined files (real and synthetic) byte-identical to base apart from the already-known printed 23 and 66 (`final2_render_head.txt`); 4 mutations killed (`final2_mutations.txt`); 0 old assertions removed; no schema, solver, prompt or config change.

## A real defect found by real data
The tester's regression found a false decline on an older real refined file (work/TASK-017): a page-end question with four line-start list enumerators (`a)`, `b)`, ...) was flagged `formula_unbalanced` though it balanced without them. Fixed (enumerators ignored in the bracket count, other brackets still counted) with tests. Synthetic tests alone would not have found it.

## Limits
Heuristics: a stem with intentionally unbalanced brackets at a page end can still be flagged (measured: 0 on the real DGNL data); `merge_suspect` does not understand a numbered sub-list inside a stem; id normalisation relies on `refine.norm_id` (checked directly for '7', '7 ', 7, ' 7.').

User instructions honoured: RAW-00146, RAW-00133 (quality), RAW-00142 (short roles).
