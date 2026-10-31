# Report phase 36: gold to PDF extraction benchmark, tier 0 (TASK-036; REQ-0039)

Verdict: adopted as a PDF-level measuring step, not as the engine's real extraction accuracy. `python3 -I scripts/exam.py gold-pdf GOLD OUT.pdf [--variant text|formula-image]` renders the 20 synthetic gold questions to a PDF with a text layer (fitz + DejaVu, Vietnamese diacritics intact), the real ingest text route reads it, and `extract-eval` scores the result.

## Numbers (recomputed independently; oracle output saved as evidence)
- Text variant: overall 8/20 = 40.0% (Wilson 21.9%-61.3%), text 10/20, options 20/20.
- Formula-image variant: text 20/20, options 20/20, overall 8/20.
- Why 8/20: the text route never fills formula or figure fields, so 12 questions fail by construction; in the text variant the formula line is also read into the question text (text 10/20). These numbers show a limit of the route, not extraction quality on text.
- They are an optimistic upper bound (clean single-column generator PDFs), explicitly NOT real-exam accuracy (stated in docs/guide/ingest-usage.md). Real numbers need REQ-0040 (the user's labelled pages).

## Quality checks
Tester Nemesis regenerated the PDFs, checked the text layer with fitz (ids once, NFC diacritics, formula as image only), looked at a rendered page, ran edge cases (1 question, 120-char option -> clear error exit 2, id > 99, unwritable path), and three mutations (drop a question, NFD text, scoring bypass). It found a weak test (NFD renderer passed because the test normalised to NFC): fixed with a raw NFC assertion, mutation now fails (D1). Designer's hand count equals the real run exactly, and the coordinator additionally saved the tester's oracle output as headered evidence (`oracle_text.txt`, `oracle_formula-image.txt`) after the verifier could not confirm it.

## Evidence (work/TASK-036/evidence/)
`final_unit_suite.txt` (553 tests, only the 3 known pre-existing failures), `final_gold_pdf_tests.txt` (7/7, none skipped), `final_diff_protected.txt` (no ingest, solver, schema, engine, prompts, config change), `oracle_*.txt`, `cli_*.txt`, tester `t36-*.txt`, verifier `work/TASK-036/handoff/verify.md` (AC1, AC2 PASS).

## Findings and follow-ups
- D2: non-consecutive ids (1 then 150) make ingest emit `segmentation_skipped` and no questions; this also hits real exams. New REQ-0041 / TASK-038 (queued).
- D3 cosmetic: formula-image raster smaller and indented.

User instructions honoured: RAW-00128, RAW-00133 (quality), RAW-00141.
