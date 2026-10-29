# Ingest usage (PDF, DOCX, Markdown)

Setup and OCR data: see [ingest-setup.md](ingest-setup.md). Ingest is free and local: no Claude call.

## Commands
    python3 -I scripts/exam.py ingest exam.pdf  --out doc.json [--assets DIR] [--ocr auto|off]
    python3 -I scripts/exam.py ingest exam.docx --out doc.json --assets DIR
    python3 -I scripts/exam.py ingest exam.md   --out doc.json
    python3 -I scripts/exam.py ingest exam.pdf --pages 1-4 --exam-out exam.md \
        --meta Subject=S --meta Level=L --meta "Exam type=E" --meta Task=T --meta Mode=M
    python3 -I scripts/exam.py ingest-inspect exam.pdf [--pages 1-4] [--out report.md]
    python3 -I scripts/exam.py ingest --check

- `--out` saves the canonical document (JSON); `--exam-out` writes the exam file for `solve`.
- `--pages SPEC` (`1-4`, `1,3,5-6`) keeps only those pages; DOCX is one logical page.
- `ingest-inspect` prints a read-only report (blocks, warnings, suspicious spots). Read it before
  trusting a document.
- Key guard: a document with an answer guide after the exam (heading "Hướng dẫn giải", "Đáp án",
  "Answer key") gets `parts`; `--exam-out` fails with `answer_key_present` unless you select the
  exam pages with `--pages` or pass `--allow-key-pages`. An unlabelled guide is not detected.
- OCR (PDF only): runs on pages whose native text looks wrong; `--ocr off` disables it.
- Exit 0 = ok; 2 = a structured error `code: message` on stderr. Codes: `unsupported_format`,
  `empty`, `decode`, `corrupt`, `encrypted`, `missing_dependency` (`pip install <pkg>`),
  `missing_asset`, `invalid_pages`, `no_questions`, `missing_header`, `answer_key_present`.
- An exam-format `.md` (header fields plus `## Question N`) goes to `solve` byte for byte.

## DOCX specifics
Body in file order: headings (`Heading N`, `Title`), list styles, paragraphs, one block per table
(merged cells once), inline images saved unchanged as `docx-img-NNN.ext` under `--assets` (without
`--assets` the block has no file and the warning `asset_not_saved`). Text is NFC.

## Image specifics (PNG, JPG, JPEG, WEBP)
`ingest photo.png --assets DIR --out doc.json`: one page, one `image` block, original bytes copied
unchanged to `--assets` (without it the asset path is the source file name). Status `needs_review`,
warning `image_only`: no text is read unless `--ocr on` (adds an `extracted` paragraph after the
image, never replacing it; `ocr_unavailable` if tesseract data is missing). Errors: `corrupt`
(truncated/not an image), `format_mismatch` (extension vs content), `empty`. Over 5 MB a resized
copy (`origin: normalized`, `derived_from`) is added beside the original; without Pillow that is
`missing_dependency`. `--exam-out` of an image-only document fails with `no_text`: the image goes
to the solver as a visual (later REQ-0021).

## Limits and unresolved risks
- Math stays text. PDF: math fonts give `math_possible` plus a page image. DOCX: equation (OMML)
  text is kept as plain text with `math_possible`, not LaTeX; check formulas by eye.
- OCR can garble characters (Vietnamese diacritics, digits, option letters); OCR pages are marked.
- DOCX headers, footers, text boxes, footnotes and images inside tables are not read
  (`unsupported_content`). Auto-numbered lists lose their numbers (Word keeps them outside the text).
- Password-protected or old `.doc` files are refused (`encrypted`); convert to `.docx` first.
- Question segmentation and answer-key detection are heuristics (`Câu N` / `Question N`);
  `no_question_numbering` or `segmentation_skipped` means fix the saved document by hand.
- Multi-column order and table cells in PDFs are best effort (`reading_order_uncertain`).
- Nothing here proves extraction is 100% correct; the warnings are hints, not guarantees.
