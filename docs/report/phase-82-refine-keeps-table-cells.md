# Phase 82 report - refine keeps data-table cell values (REQ-0088)

- Result: refine prompt rule 5 now transcribes tables cell by cell, and `_native_tables` appends the page's native table text to the matching figure entry (warning `native_table_unplaced` when none matches). General, no exam-specific text.
- Real re-run (De-thi-mau-DHQG-HCM-2024, page 8 and printed 64-67 only): all 4 answered D, A, D, B, matching the independent recompute from the PDF text; before the fix all 4 were declined. Status UNCERTAIN (no key), doubt low.
- Cost: refine 0.0490 + solve 0.0643 = 0.1133 USD (cap 0.3; total with phase 81: about 2.22 of 5 USD).
- Tests: 8 new NativeTable tests (51 in the file), 4 bite when `_native_tables` is a no-op. Full suite 1613 run, only the 4 pre-existing failures (examples/dgnl unknown subject dir, docx text box, cwd, check_examples), also present before this task.
- Open: the full 120-question results of phase 81 still hold the old declined 64-67; `plans/dhqg2024-t82/` holds the corrected four. Printed 9 (declined) and the chart-only 62, 68, 69 are unaffected by this fix. Other pages were not re-refined with the new prompt.
- Evidence: `work/TASK-082/evidence/` (unit-refine, unit-full, rerun-64-67, cost.tsv; untracked).
