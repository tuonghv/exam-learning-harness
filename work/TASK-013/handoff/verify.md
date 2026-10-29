PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency
Verifier: Argus. Method: code reading + saved evidence (suite rc=0, 301 tests, 1 skipped; integration rc=0; ingest-check rc=0; vn-pdf-ingest rc=0). Evidence head is fb97b77+dirty (pre-commit), not 304c4ec.

## AC verdicts
- AC1 digital VN PDF -> native_text, diacritics, pages, bboxes: VERIFIED (synthetic only). pdf.py:61-76 (NFC, bbox), :317 page n/size, :338-344 status; test_ingest_pdf.py:89 (diacritics), evidence/vn-pdf-ingest.txt:20-29. No real exam PDF tried (Q3 open).
- AC2 OCR only on flagged pages; native not replaced automatically; missing tesseract/vie -> warning: VERIFIED for logic, vie OCR UNVERIFIED. OCR gated by `if flags` pdf.py:242-264; good pages untouched (test :228); missing data -> ocr_unavailable + needs_review, no raise (pdf.py:246-247, test :237); vie missing -> ocr_language_missing (pdf.py:249-252). vie OCR test skipped (ingest-check.txt:14 shows eng only); test :234 only checks language pick.
- AC3 conservative order, table data, crop asset with bbox: VERIFIED (synthetic). pdf.py:115-138, tables :213-216/:268-271, assets with page+bbox :301-302, MAX_CROPS :287-289, DPI cap :158; tests :96,:107,:128,:146. Heuristic, no accuracy claim.
- AC4 encrypted/corrupt/empty structured errors: VERIFIED. pdf.py:174-177, :191-194, :322-323; tests :171,:178,:186.
- AC5 original never modified; no accuracy claim: VERIFIED. File opened "rb", parsed from stream (pdf.py:172-180), never written; test_digital_pdf_valid_and_hash checks sha before/after (test :77,:82). Docs make no accuracy claim.

## Checklist items
- Loader: optional.py:25-27 appends only the existing user site to END of sys.path, never cwd; test :261 asserts sys.path[-1]. VERIFIED.
- Statuses: pdf.py:330-338 (needs_review dominates; mixed = some ocr + some non-ocr).
- Asset paths relative, fixed names p{n}_v{i}.png: pdf.py:155-166,:290. VERIFIED.
- Segmenter keeps all text, skips unless consecutive from 1 and non-empty (segment.py:14-33; pdf.py:327-329; test :288). VERIFIED.
- to_exam_text no_questions: api.py:76-81; test :313. VERIFIED.
- Guide ingest-setup.md matches code. Tests bite (mutations in code.md); only conditional skips (vie data, fonts, eng data).

## Defects
- No major defects.
- D1 minor: pdf.py:259-261 on a flagged page OCR text replaces all native text of that page (even if mostly good, e.g. >1% bad chars); native not kept in the JSON. Consider a warning like native_replaced.
- D2 minor: Vietnamese OCR (vie) unverified; install tesseract-ocr-vie and run one scanned VN page.
- D3 minor: no real PDF fidelity check (REQ Q3); evidence is synthetic.
- D4 minor: segment.py:29,31 joins wrapped lines with one space; options limited to A-D (segment.py:5). Characters unchanged.
- D5 minor: no dedicated test for `mixed` status (source-unchanged IS tested, test :82).
- D6 minor: evidence head is fb97b77+dirty; re-save suite evidence at final head before VERIFIED.
