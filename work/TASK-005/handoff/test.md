PROGRESS: COMPLETE
SKILLS: unit-test, python

# TASK-005 tester handoff (Nemesis)
Files: tools/examples/tests/test_exam_report.py (41 tests), tools/examples/tests/test_md2html.py (16 tests).

## Command and result
`python3 -I -m unittest discover -s tools/examples/tests -v` -> Ran 165 tests, OK (was 108; +57).
No real Chrome/Popen (Popen patched to raise; FakeProc runners; fake PATH). The normal suite leaves no temp profile dirs (asserted in tests).
Note: the drop-cleanup mutation run leaked exam_chrome_* dirs in /tmp (expected from that mutant); I did not delete them (cleanup of /tmp globs was denied by the classifier). Safe to remove by hand.

## Design test -> tests
1 evidence_kind: EvidenceKind (7: computed, key_match, only quote/format/ai_review, none, non-independent computed)
2 build_markdown: Markdown (contents, escaping, pipe/newline, Vietnamese, totals from summary not questions)
3 Literature Open: test_3_* (2)
4 md2html: test_md2html.py (blocks, escaping, javascript:/data: refused, --lang vi, CLI)
5 find_pdf_renderer: Renderer (CHROME_BIN first, name order, None, empty real PATH)
6 no renderer: test_6 (html kept, pdf_status skipped, report.md "PDF skipped")
7 fake pdf ok: test_7 (html removed, argv list, temp profile removed, weasyprint/wkhtmltopdf argv)
8 timeout: test_8 (hang terminated at PDF_RENDER_TIMEOUT=1/2, (False, reason), non-%PDF fail, raising runner, stale pdf)
9 run(): RunIntegration (valid RESULT, evidence_kind on disk, totals = summary, pdf=True w/o renderer)
10 CLI --mock --no-pdf: Cli.test_10

## Mutation table (temp COPY, one change each)
| mutation | result |
|---|---|
| drop html escaping (md2html inline) | FAIL 3 tests (test_4_script_text_is_escaped, test_2_script_never_becomes_live_markup, ...) |
| drop %PDF check | FAIL 2 (test_8_non_pdf_output_is_failure_and_keeps_html, test_2_vietnamese...) |
| recount totals from questions | FAIL 2 (test_2_totals_come_from_summary_not_questions, test_10) |
| drop temp-profile cleanup | FAIL 3 (test_7_chrome_argv_..._temp_profile_removed, ...) |
| drop timeout kill (terminate) | FAIL 2 (test_8_hang_is_terminated..., test_8_md_to_pdf_returns_false...) |
| allow javascript: scheme | FAIL 3 (test_4_javascript_link_refused, ...) |

## Defects
- D1 low: exam_report.py md_to_pdf (~line 195-200): when the renderer writes a non-PDF file, it stays as report.pdf next to report.html (misleading); only info["pdf"] is None. Input: fake runner writing "<html>not a pdf". Suggest os.remove of the bad pdf.
