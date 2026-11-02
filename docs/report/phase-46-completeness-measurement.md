# Report phase 46: measurement of the guide's metrics (TASK-046; REQ-0050)

Verdict: adopted. The engine now measures the completeness guide's metrics on synthetic fixtures that force questions across page breaks, with Wilson intervals; nothing is claimed.

## What was built
`gold-pdf --layout split` (a question may cross a page at a line; default layout unchanged) with per-question pages; generator for families F1-F8 (25 synthetic questions each: single page, stem over 2 pages, options on the next page, passage over 3 pages, table/figure on the next page, several per page, scanned, formula split); additive `extract-eval` rates: boundary, cross_page, missing_detection, false_merge, incomplete_to_solver (strict and content-equal), content_errors, missing_to_solver, false_alarm. Old outputs byte-identical (24 runs).

## Results (n = 200 per route, work/TASK-046/evidence/rates_table.txt)
- Text layer and vision (oracle mock replies, tests the bridge not vision accuracy): boundary 200/200 (Wilson 98.1%-100%), cross-page 46/46, false merge 0/200, incomplete-to-solver 0/200, missing 0/200. Finding: false alarm 8/200 (all in F5, table/figure on the next page).
- Scanned PDF via tesseract OCR: strict exact 168/200 differ, 162 of them only by lost spaces, real content errors 6/200 (character errors in F8 and a leaked page header), 6 reach the solver unmarked, missing 0/200. Opened as REQ-0054 / TASK-051 (OCR quality: spaces, furniture, doubt marker).
- 99.9% is not claimed: it needs about 2,995 error-free questions at 95%; with 200, a perfect result only bounds the rate at about 98.1%.

## Evidence
`final_unit_suite.txt` 815 tests, only the 3 known failures (identical at base); new tests fail on base; independent whitespace-stripped fitz oracle 0 mismatches on text, vision and OCR; each corruption (drop, merge, truncate, swap) moves only its own rate; 4 mutations killed; 0 old assertions removed; no schema, solver or ingest change. Tester defects D2-D4 fixed (false claim about missing language data corrected; content-equal companion rates; missing_to_solver); D1 became REQ-0054.

## Limits
Synthetic gold is an optimistic upper bound (real exams: REQ-0040); the vision rows replay replies built from gold; F5 false alarm is not yet fixed (candidate for TASK-047/048).

User instructions honoured: RAW-00146, RAW-00133, RAW-00142, RAW-00151, RAW-00152.
