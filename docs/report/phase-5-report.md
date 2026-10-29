# Report: TASK-005 report stage (REQ-0011)

**Verdict: adopted.** `exam_run.py` now writes `report.md` always and a PDF when a renderer exists. No real `claude` call was made.

## Task and requirement
REQ-0011: validated `result.json` with evidence kind, a Markdown report, and a readable PDF. Per RAW-00037 the PDF path is copied from `code-security-scanner` (`md2html.py`, renderer chain) and rewritten in Python.

## Implementation (commits)
- `e56cd05`: `md2html.py` (copied, trimmed to 300 lines), `exam_report.py` (`evidence_kind`, `build_markdown`, `find_pdf_renderer`, `md_to_pdf`, `write_reports`), `evidence_kind` in `exam_schema.py`, hook and `--no-pdf` in `exam_run.py`.
- `211ac3b`: 57 tests; an invalid PDF is deleted instead of staying as `report.pdf`.
- `c574021`: model text can no longer open a code fence, fake a heading or a verdict pill (zero-width space); evidence files.

## Decisions that matter
- Renderer order: `CHROME_BIN`, `google-chrome` and relatives, weasyprint, wkhtmltopdf; none found gives "PDF skipped", HTML kept.
- `evidence_kind` is `code_oracle` only with an independent passing check; `key_match`; otherwise `claude_review_only`.
- Report totals come from `result['summary']`, never recounted.
- A PDF failure never fails the run; the headless Chrome profile is a temp dir that is removed.

## Tests and verification
- 166 unit tests OK (108 + 58), fakes only; 6/6 mutations killed.
- Real runs at $0 (`work/TASK-005/evidence.md`): mock end to end gives result.json + report.md + report.pdf; empty PATH keeps HTML and says "PDF skipped"; real Chrome renders Vietnamese to a one-page A4 PDF with diacritics and embedded DejaVu fonts, `<script>` shown as text.
- Verifier: AC1-AC4 pass; D1 and D2 fixed, D3 (raw evidence files) done.

## Limitations
- Chrome's PDF is only as good as the installed fonts; the tests prove structure, not typography.
- Math in the PDF is plain text (no LaTeX rendering).
- 10 `/tmp/exam_chrome_*` folders remain from the tester's mutation run; remove by hand.

## Next
REQ-0012 restructure (TASK-006), then REQ-0003/0004 examples and REQ-0009 real benchmark (user's go).
