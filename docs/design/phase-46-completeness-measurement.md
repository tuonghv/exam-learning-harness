# Phase 46: measurement of the guide's metrics (TASK-046; REQ-0050)
Source: docs/design/phase-43-question-completeness-gate.md section 3. Text from it:

## 3. Measurement plan (owner: gold_pdf.render, extract_eval.evaluate) - tier 0 except V
- gold_pdf: `--layout split` lets a block cross the page at a line (today moves it whole, gold_pdf.py:79-84); gold records gain optional `pages: [p..]`. Fixture families (synthetic text only, never real exam text): F1 single page; F2 stem over 2 pages; F3 options on the next page; F4 passage over 3 pages + group of 3; F5 table/figure stand-in on next page; F6 4+ questions per page; F7 formula cut at the break; F8 header/footer/page number on every page.
- Scanned: render each page to PNG (fitz) -> image-only PDF -> ingest OCR (skipIf no tesseract); vision path: oracle mock replies generated from gold per page (tests bridge/recovery, not vision accuracy).
- extract_eval new rates (Wilson each): boundary = gold ids matched 1:1 with exact text start/end; cross_page = exact over gold with len(pages)>1; missing_detection = wrong extracted questions with reasons/total wrong; false_merge = extracted text holding another gold question's opening; incomplete_to_solver = wrong and unmarked (must be 0 on fixtures; any >0 = FAIL).
- Expected on fixtures (tier 0): F1-F8 x 25 questions = 200; boundary 200/200, cross_page = all split ones, false_merge 0, incomplete_to_solver 0.
- Honesty: 0 errors in n proves >= 99.9% at 95% only for n ~ 3000 (zero_error_n, extract_eval.py:34); report k/n with Wilson, never "99.9%". V (paid): vision on scanned gold, ~3000 q ~ 400 pages x $0.04 ~ $16, user go only.

## Plan modes
Tier 0, $0: synthetic text only, no network, no model call (the scanned/vision variant uses oracle MOCK replies generated from gold, testing the bridge and recovery, not vision accuracy). Existing gold-pdf output and extract-eval results for current fixtures must stay byte-identical (the layout `split` is opt-in; new metrics are additions).

## Tests-first list (tier 0)
1. gold_pdf `--layout split`: a block may cross the page at a line; default layout unchanged (byte-identical PDF text layer on the existing fixtures).
2. gold records carry optional `pages: [p..]` computed by the renderer; extract-eval loads files without it unchanged.
3. fixture families F1-F8 generated from synthetic text, 25 questions each (single page; stem over 2 pages; options on the next page; passage over 3 pages; table/figure on the next page; several questions per page; scanned variant = page image + OCR (skipIf no tesseract) or mock vision replies; formula split across pages).
4. extract-eval new rates as k/n with Wilson: boundary (gold ids matched 1:1 with exact text start and end), cross_page (exact over gold with len(pages)>1), missing_detection (wrong extracted questions that carry a reason / all wrong), false_merge (extracted text holding another gold question's opening), incomplete_to_solver (extracted questions with a reason that would still reach the solver; must be 0 on the fixtures).
5. expected counts on the fixtures computed independently by the tester (not from the code under test); a corrupted extraction lowers the right rate (metric bites).
6. the report states the zero-error n for 99.9% (computed) and that nothing is claimed; Wilson intervals shown.
7. old extract-eval output byte-identical for the existing perfect/corrupted fixtures.
## Verification
Tier 0: unit suite; generate F1-F8, run the whole chain ingest (text route and refine with mock replies) -> extract-eval, save the table of rates with intervals; independent oracle by the tester. Honesty: with about 200 questions a result of 0 errors proves no more than about 98.5% at 95%; say so. Paid scanned run (about 3000 questions about $16) is out of scope and needs the user's go.
## Risks / out of scope
Synthetic gold is easier than real exams (optimistic upper bound); real pages are REQ-0040.
