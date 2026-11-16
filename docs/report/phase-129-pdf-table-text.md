# Phase 129 – PDF free text path keeps table blocks report (TASK-129, REQ-0136)

**Verdict: done.** Found in the approved paid runs of DGNL 2025 Vietnamese (26/30, $0.37) and Science (19/30, $0.46),
default prompts v1.3.0, 0 diacritics fails. Science: 8 declined, 6 of them because table blocks never reached the
free text path (p16 and p18 data tables, the boxed passage of 118-120).

## Results
- `segment.table_lines`: a box (at most one filled cell per row) becomes plain passage lines; a data table becomes
  `| a | b |` rows (never read as a question, option or heading).
- `pdf._text_lines`: tables are placed in (top, left) order after the last block that starts at or above them, so a
  footer listed early or a wide stem line never pulls them; `parts.select_pages` uses the same lines.
- Real inputs: still 120 questions in all 3 PDFs; table text lands in the right groups (2025 q99-102, q109-111,
  q118-120; 2024 q64-67, q91-93; 2026 q100-102, q109-111, q115-117, q65); DGNL 2026 q4 now reads its boxed poem
  (still declined: its options sit in table cells). Cover structure tables go to the intro.
- 6 tests (fail on old code); `--fast` KNOWN 4, NEW 0.

## Open
Science re-run to measure the gain is a paid step (~$0.46). Options inside table cells (DGNL26 q4) still need refine.

## Spend
This task $0; the two approved section runs $0.83.
