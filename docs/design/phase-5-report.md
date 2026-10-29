# Phase 5: report stage (TASK-005, REQ-0011)

Builds on `docs/design/phase-2-exam-pipeline.md` (REPORT stage) and `phase-4-engine-core.md` (result.json).
User change RAW-00037: the PDF follows `code-security-scanner` (read-only reference, script copied here) instead of a
hand-written PDF writer.

## Reuse (cite path:line; the scanner repo is never modified)
| Need | Scanner | Here |
|---|---|---|
| Markdown -> print HTML | `code-security-scanner/md2html.py:1-416` (stdlib; `html.escape`; `safe_href` allows http/https/mailto only; no script) | copied to `tools/examples/md2html.py` with a header naming the source; flow diagrams and severity pills removed, verdict pills PASS/FAIL/UNCERTAIN added, `lang` and a Vietnamese-capable font stack (`DejaVu Sans`, `Noto Sans`, system sans) |
| renderer lookup | `report_common.sh:719-735` `find_pdf_renderer` (Chrome, else weasyprint, else wkhtmltopdf) | rewritten in Python: `exam_report.find_pdf_renderer(env)`; `google-chrome`, `chromium`, then `weasyprint`, `wkhtmltopdf` on PATH, `CHROME_BIN` override |
| HTML -> PDF | `report_common.sh:743-790` `md_to_pdf` (Chrome `--headless=new --print-to-pdf`, wait until the file stops growing, kill; temp profile) | rewritten in Python: `subprocess.Popen` with an argv list, no shell, temp profile dir, `PDF_RENDER_TIMEOUT` (default 120 s), always cleaned up |
| no renderer | keeps the .html, prints a note, never fatal | same: HTML kept, `report.md` carries a line `PDF skipped: <reason>`, exit code unchanged |

## Modules
- `exam_report.py`: `evidence_kind(question) -> "code oracle"|"key match"|"Claude review only"|"none"` (from `checks`: independent pass `computed` -> code oracle; `key_match` -> key match; any other pass -> Claude review only), `build_markdown(result) -> str` (title, run line, totals from `summary`, one section per question: answer, verdict, reason, evidence kind, score, checks table, QA findings, explanation, solution, uncertainty; Literature shows the quotes and "needs a human rubric"), `write_reports(result, out_dir, pdf=True) -> dict(md, html, pdf, pdf_status)`.
- `md2html.py`: the copy above.
- `exam_run.py`: after `result.json`, call `write_reports` (CLI flag `--no-pdf`; `run()` only writes `report.md`, the PDF only when `cfg["pdf"]` is true, so every existing test stays offline); print the written paths.
- `exam_schema.py`: optional `evidence_kind` per question (string enum); `build_result` sets it in code.

## Rules
- All text from the model is data: markdown goes through `md2html` (escaped); the report never executes it. File names are fixed (`report.md`, `report.html`, `report.pdf`).
- Chrome runs `--headless=new --disable-gpu --no-first-run --no-pdf-header-footer --disable-extensions --disable-background-networking --disable-sync` with a temp `--user-data-dir`; the argv is a list; the Popen is always reaped; a hang is killed at the timeout.
- Tests never need a browser: the renderer is injectable (`find_renderer`, `runner`) and a fake PATH proves the no-renderer branch; one optional real smoke test is skipped when no Chrome exists.
- `$0`: rendering is local; no model call.

## Tests (mock only; one real local render by the coordinator)
1 `evidence_kind` for each case; 2 `build_markdown` contains answer, verdict, evidence kind, checks, totals equal to `summary`, and escapes `<script>`; 3 Literature item shows "Open" and UNCERTAIN; 4 `md2html` tables/lists/code/escaping/link scheme (`javascript:` refused); 5 `find_pdf_renderer` order and none; 6 no renderer -> HTML kept, `pdf_status` says skipped, `report.md` flags it; 7 fake renderer writes a pdf -> `pdf_status` ok and html removed; 8 renderer timeout -> killed, skipped flag; 9 `run()` writes `report.md` and still a valid `result.json`; 10 `exam_run --mock --no-pdf` end to end.

## Verification (coordinator, real, $0)
`exam_run.py ... --mock ... --out DIR` then the real Chrome render of a result containing Vietnamese text; check `%PDF`, page count, and `pdftotext` (if present) or Chrome's text dump shows the diacritics; screenshot is not needed.

## Open questions
None.
