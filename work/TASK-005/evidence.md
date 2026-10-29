# TASK-005 evidence (coordinator, real runs, $0, no `claude` call)
Commit 211ac3b. Output dirs are under the session scratchpad (`ev/a`, `ev/b`, `ev/c`).

## E1 unit suite
`python3 -I -m unittest discover -s tools/examples/tests` -> Ran 165, OK. Tester mutations 6/6 killed (escaping, %PDF check, recount, profile cleanup, timeout kill, javascript: scheme). D1 (rejected non-PDF kept as report.pdf) fixed in exam_report.py, asserted in test.

## E2 mock end to end (AC1, AC2)
`python3 -I tools/examples/exam_run.py examples/english/input-001.md --mock tools/examples/tests/fixtures/mock_english_001.json --key examples/english/expected-001.md --out ev/a`
-> `pass=1 fail=0 uncertain=0 unresolved=0 calls=2`; files: result.json, report.md, report.pdf, run.log. result.json validated by `run()` against RESULT before writing.

## E3 no renderer (AC3)
`env -i PATH=/nonexistent python3 -I exam_run.py ... --out ev/b` -> report.md + report.html kept, no pdf; stdout and report.md both say
`PDF skipped: no PDF renderer found (Chrome, weasyprint, wkhtmltopdf); HTML kept`.

## E4 real Chrome, Vietnamese + injected markup (AC3)
`write_reports(result with "Nghiệm x = 1/3. Điều kiện xác định: x ≠ 0. <script>alert(1)</script>", ev/c, pdf=True)`
-> pdf_status `ok: PDF written with chrome`, html removed; file starts `%PDF-`; `pdfinfo`: 1 page, A4;
`pdftotext` returns the exact line with diacritics and the `<script>` as visible text (not executed);
`pdffonts`: DejaVuSans and DejaVuSans-Bold embedded.

## E5 leftovers
No chrome process left (only an unrelated bash). 10 `/tmp/exam_chrome_*` dirs remain from the tester's drop-cleanup mutation run (expected from that mutant); the normal suite leaves none (asserted by a test).

## E6 verifier defects D1/D2 (markdown injection, fake pill)
Fixed in exam_report.py `_one_line` (zero-width space before a leading marker, inside `**`); regression test added (166 tests OK); real Chrome render of an explanation "```python / x **PASS**" keeps Explanation, Solution, Uncertainty sections (pdftotext). Raw files: work/TASK-005/evidence/{suite,pdf-vi,no-renderer}.txt.
