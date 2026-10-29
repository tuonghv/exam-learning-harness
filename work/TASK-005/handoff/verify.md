PROGRESS: COMPLETE
SKILLS: verify, python

# Verify TASK-005 / REQ-0011 (Argus)
Method: code reading plus work/TASK-005/evidence.md E1-E5 (a prose file with no `# cmd/# rc` headers, so E1-E5 are the coordinator's stated results, not saved raw output). I did not rerun anything.

## Per-AC verdict
- AC1 (result.json schema, per-question answer/uncertainty/verdict/evidence kind/score): VERIFIED.
  - exam_run.py:290 sets `evidence_kind` from `exam_report.evidence_kind`.
  - exam_run.py:351-354 validates `result` against `sch.RESULT` before writing; exam_schema.py:134 holds the enum.
  - Tests: test_exam_report.py:449 (bad enum rejected), :422 and :464 (end to end). E2 states the mock run validated.
- AC2 (md lists each question with answer, explanation, checks, verdict; totals by code): VERIFIED.
  - exam_report.py:60-63 takes totals from `result["summary"]`; exam_run.py:310-314 computes them by code.
  - exam_report.py:65-103 renders per question: answer, verdict, reason, evidence, score, checks table, explanation.
  - Test :217 checks totals come from summary, not from the questions.
- AC3 (PDF via md2html + find_pdf_renderer, Chrome first, `%PDF`, diacritics, no-renderer flag): VERIFIED on the code path and on E3/E4.
  - exam_report.py:107-121: CHROME_BIN first, then the chrome names, then weasyprint and wkhtmltopdf.
  - exam_report.py:124-131 does the `%PDF` byte check.
  - exam_report.py:191-192 and :250-254 give the no-renderer behaviour: html kept, report.md says "PDF skipped".
  - E3 and E4 (real Chrome, pdftotext shows diacritics, fonts embedded) rest on the coordinator's prose.
  - I could not inspect the saved output files. Please confirm `ev/c/report.pdf` and the E3 report.md exist (UNVERIFIED as raw files).
- AC4 (mocked-result tests for JSON, md and PDF, $0): VERIFIED. test_exam_report.py has 40+ tests, including fake renderer/runner tests at :307-:394 and the end-to-end tests :422-:464. Evidence E1: 165 tests OK.

## Checks requested
- Totals from `result['summary']`: VERIFIED (exam_report.py:52,60-63).
- evidence_kind honest: VERIFIED. exam_report.py:24-31 gives "code oracle" only for a passed `computed` check with `independent` true. quote, format and ai_review passes fall to "Claude review only". Tests :132 and :144 cover this. Caveat: it reads passed checks only, so a PASS-check question whose verdict is FAIL or UNCERTAIN still shows its evidence (low, informational).
- Escaping in md and html: VERIFIED for HTML.
  - md2html.py:117 runs `html.escape` before the other rules; code spans are escaped at :141.
  - `_one_line` and `_cell` (exam_report.py:34-40) escape pipes and newlines.
  - Tests :165 and :186 cover this. Markdown structure is not escaped; see D1.
- javascript: links refused: VERIFIED (md2html.py:92-99 strips control characters and whitelists http, https, mailto; test :179). Entity tricks stay inert because `&` is escaped first.
- PDF failure never aborts the run: VERIFIED. exam_report.py:223 catches everything in `md_to_pdf`; a bad PDF is removed (:218) and a timeout reaps the process (:213, :226). Tests :337-:394. One gap: `write_reports` writes report.md outside any try (:240); this is an OSError on a disk problem that would already break result.json, so it is acceptable.
- Temp profile cleanup: VERIFIED (finally with rmtree, exam_report.py:228-229; test :317). The 10 leftover dirs in E5 come from the tester's mutation run.
- md2html.py trimmed copy: VERIFIED. Docstring at :5-6 only mentions its origin. SEV_CLASS is only PASS/FAIL/UNCERTAIN (:79). No scan-specific code remains in the grep hits.
- No key text beyond `result`: VERIFIED. exam_run.py:272 uses the fixed detail "matches the key"; exam_checks.py:226 uses "matches key" or "differs_from_key". No key answer string reaches report files.

## Defects
- D1 (low-medium, markdown structure injection): exam_report.py:96 (explanation), :99 (solution steps), :70 (answer) put model text at the start of a line. `_one_line` removes newlines but not leading markers. A model explanation that starts with "```" opens a fence in md2html.py:175-186 that swallows the rest of the report. A leading "# " creates a fake heading and "- " a list. Not XSS (output is still html-escaped), but a model can break the layout and fake a "Question N" section. Fix: prefix or escape leading `#`, `>`, `-`, `` ` ``, `|`, digit+`.` (for example render the explanation as a blockquote or a code span) and add a test with an explanation of "```".
- D2 (low, verdict spoofing): md2html.py:136-138 turns any `<strong>PASS</strong>` into a coloured pill. Model text `**PASS**` (exam_report.py:96, :72 reason) renders as a verdict pill. Cosmetic; same fix as D1 (escape `*` in model text).
- D3 (info, evidence format): evidence.md has no `# cmd:/# head:/# rc:` header files in work/TASK-005/evidence/. Ask main to save E2-E4 via save-evidence.sh before the VERIFIED transition.

## NEXT
Fix D1 and D2 (small), or record them as accepted risks. Then save raw evidence for E2-E4.
