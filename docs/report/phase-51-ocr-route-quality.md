# Report phase 51: OCR route quality (TASK-051; REQ-0054)

Verdict: partly achieved; adopted, with the residual errors tracked in REQ-0065. Four things changed on the OCR route (tesseract via PyMuPDF): (1) word spacing is rebuilt from character boxes (`OCR_GAP = 0.15 x median char height`, chosen by a sweep on 3 synthetic families; the diagnosis found tesseract itself is fine and the PyMuPDF bridge glues words); (2) the page-furniture filter (repeated headers, footers, page numbers) matches with a space-free, case-folded key and marks near-miss header leaks; (3) an `ocr_doubt` reason (glued / chars / furniture / lang_missing) produces `[Incomplete: missing_text ocr_doubt ...]`, an `uncertain` assembly status and an engine decline; (4) when the needed language (vie) is missing, every OCR question is marked doubtful and the `ocr_language_missing` warning is an error with an install note (the user installed `vie.traineddata` in /usr/share/tesseract-ocr/4.00/tessdata/). Native-text PDFs and non-OCR exams are unchanged.

## Measured (synthetic scanned families, vie+eng, 10 questions each, one column; docs/report/evidence/TASK-051/ocr-before-after.tsv)
| Family | Wrong questions before -> after | Wrong and unmarked (reach the solver) | Glued tokens |
|---|---|---|---|
| A | 10/10 -> 1/10 | 1/10 | 50 -> 0 |
| B | 10/10 -> 6/10 | 4/10 | 50 -> 3 |
| C (Caladea, diacritics) | 10/10 -> 10/10 | 4/10 | 173 -> 170 |
False alarms (correct questions marked doubtful): 0/9 (A), 0/4 (B), Wilson intervals wide (n tiny). Tester recount equals the coder's numbers except family C glued 171/168 vs 173/170 (alignment method).

## Not achieved / limits
- OCR text is still not safe to trust unreviewed: 4 of 10 wrong family B questions reach the solver unmarked (single-character misreads that look like valid words, e.g. "Số" -> "$6"); a follow-up with a per-word-confidence signal is REQ-0065. Family C stays fully wrong because tesseract drops diacritics there.
- Synthetic, single-column pages only (no skew, multi-column, real exam scans); the per-word confidence (tesseract CLI TSV) and any AI fallback are deferred and the AI fallback stays off.
- Full suite takes about 5 minutes (OCR tests). Two goldens compare OCR-sourced docs whitespace-insensitively (intended spacing change). No purely native PDF is tracked, so native byte-identity rests on the markdown set plus native pages of two PDFs. The 51.2 hint-started test is missing. Low security note: unbounded difflib input at pdf.py:249.
- The verifier had no shell and judged from code and saved evidence; refine.md/prompt edits are not part of this task.

## Evidence (docs/report/evidence/TASK-051/)
ocr-gap-sweep.tsv, ocr-before-after.tsv, qa-recount.tsv, qa-recount-mismatch.tsv, suite-final.txt and head-failures.txt vs baseline-failures.txt (same known failures as baseline 083d0e4), diagnosis.md, test.md, verify.md.

User instructions honoured: RAW-00146 (completeness guide), RAW-00152 (small slices, no paid call), RAW-00181 (vie installed).
Evidence files for crosscheck: docs/report/evidence/TASK-051/ocr-before-after.tsv, docs/report/evidence/TASK-051/verify.md (index: docs/report/INDEX.md).
