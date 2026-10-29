PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency
# TASK-015 verify (Argus)
Evidence: work/TASK-015/evidence/unit.txt (rc 0, 356 tests OK, head 629204b+dirty). Static/Tier 0-1; no real run needed (no network, no claude).

## Verdicts
- AC1 VERIFIED (by tests): headings/paragraph/list valid + sha (test_ingest_docx.py:70-88), table one block merged once (:90-100), image bytes unchanged (:102), questions -> exam text (:246-251), CLI ingest docx --exam-out (:215-230). No single test has all four elements in one file, but each is covered and the combined path is the same code. Minor.
- AC2 VERIFIED: test_ingest_spec.py has the ten cases: 1 digital :29, 2 scanned :35 (skipUnless eng), 3 Vietnamese :41 (skipUnless fonts), 4 math :46, 5 table/diagram :54, 6 multi-column :71, 7 DOCX :83, 8 Markdown :104, 9 invalid :111, 10 backward compat :122 (byte for byte, run_claude mocked to fail, --dry-run). Skips carry a reason. Suite shows no failures.
- AC3 VERIFIED: docs/guide/ingest-usage.md:5-12 (PDF/DOCX/MD commands), :27-30 DOCX specifics, :32-42 limits and unresolved risks.
- AC3b VERIFIED: ingest-setup.md:6 pip packages, :8-11 why -I needs user-site loader, :13-24 tesseract, vie.traineddata, TESSDATA_PREFIX, :26-30 self-check `ingest --check`; implemented at src/exam_engine/cli.py:191-207, tested at tests/unit/test_ingest_pdf.py:296.
- AC4 out of scope (report later).

## Other checks
- Original DOCX not modified: adapter opens "rb" only (docx.py:113); test_source_file_unchanged_by_ingest (test_ingest_docx.py:207-213). VERIFIED.
- No network/Claude: docx.py imports only hashlib/io/os/re/unicodedata/zipfile + ingest modules (docx.py:7-15); spec test 10 mocks run_claude to raise. VERIFIED.
- No eval keys: grep of docx.py for answer-key/expected terms found none. Leakage in test fixtures not grepped (synthetic strings only seen). VERIFIED for adapter.
- Writes only image files under --assets (docx.py:166-167); no dir created without --assets (test :200-205).

## Defects
None blocking.
- D1 (low, doc/test): no single test ingests one DOCX containing heading+paragraph+table+image together and converts to exam (AC1 is covered piecewise). Optional.
- D2 (low): ingest-setup.md:3 says "PDF (and later DOCX/image)" and still reads as if DOCX is future; update wording.
