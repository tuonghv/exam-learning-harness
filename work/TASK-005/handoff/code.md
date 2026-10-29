PROGRESS: COMPLETE
SKILLS: coding, python

# TASK-005 coder handoff (Titan)
## Files
- tools/examples/md2html.py: trimmed copy (header cites code-security-scanner, RAW-00037); flow/severity row tint removed; pills PASS/FAIL/UNCERTAIN (sev-pass/fail/uncertain); DejaVu/Noto font stacks; convert(md, page_breaks, title, lang) and CLI --lang; escaping and SAFE_SCHEMES unchanged.
- tools/examples/exam_report.py (new): evidence_kind:~28, build_markdown, find_pdf_renderer, md_to_pdf (Popen argv list, temp profile, 1 s stable-size stop, reap, PDF_RENDER_TIMEOUT), write_reports.
- tools/examples/exam_schema.py: optional evidence_kind enum per question (RESULT).
- tools/examples/exam_run.py: imports exam_report; build_result sets evidence_kind; run() calls write_reports(pdf=cfg.get("pdf", False)) after result.json and stores the info dict in the returned result["reports"] (not in result.json); main(): --no-pdf, cfg["pdf"], prints report paths.
## Results
- Unit suite: 108 tests OK.
- exam_run --mock --no-pdf: result.json + report.md written.
- Fake runner: ok -> report.pdf only, html removed; hang (timeout 2 s) -> terminated, html kept, "skipped: ... timed out"; no renderer -> html kept, report.md ends "PDF skipped: ...". Vietnamese and `|` in cells ok.
## Risks
- evidence_kind follows the design literally: any non-computed/key pass (even format) -> "Claude review only".
- Literature detection: answer == "Open" or exam.task == "Literature".
- Real Chrome not run (coordinator smoke). Chrome PDF with --headless=new; no PDF header flag per brief.
- run() result gains a "reports" key in memory only.
## Defects
None.
