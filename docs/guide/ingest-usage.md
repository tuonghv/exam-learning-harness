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
  On a refined document (`ingest-refine` output) it adds `## Extraction suspects`: per part, the
  printed numbers whose text looks incomplete, with reasons `referenced_part_missing paragraph (N)` /
  `figure/table` (the text names a paragraph or figure/table it does not contain), `low_similarity`,
  `joined_page`, `needs_review`. Heuristic (misses are possible); `solve` marks a declined question
  of this kind `solver_declined: missing_text (...)` in `status_reason`.
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

## Optional AI refine (REQ-0021)
    python3 -I scripts/exam.py ingest-refine exam.pdf --pages 1-4 --dry-run
    python3 -I scripts/exam.py ingest-refine exam.pdf --pages 1-4 --mock replies.json --out refined.json
    python3 -I scripts/exam.py ingest-refine exam.pdf --pages 1-4 --real --max-cost-usd 1.00 --out refined.json

- Off by default; exactly one of `--dry-run`, `--mock FILE`, `--real` is required (never defaults to
  real). `--real` costs money: run it only after the user's go. Dry run prints the page list, the
  call cap (pages x 2), the cost cap and the exact prompt, and makes no call.
- Only selected pages that are flagged (`missing_text`, `bad_encoding`, `no_question_numbering`,
  `math_possible`, or OCR status) are sent, one call per page, one retry on an invalid reply.
  A `.json` document needs its source PDF next to it for `--real`.
- Pages inside a detected answer-key part are refused (`answer_key_present`, exit 3) unless
  `--allow-key-pages`.
- The reply is checked (schema, consecutive ids, options A-D, no `answer`/`solution` field) and
  stored as `refined` with `origin: "ai"`, a difflib `similarity` and `needs_review`; source blocks
  are never changed and `to_exam_text` ignores `refined`. Similarity is a hint, not an accuracy claim.
- A question cut over pages: the reply's top-level `continues` (text, options, figures, passage) and per-question `cut`
  are merged into the last question of the previous page only; an unmergeable one is listed in `refined.orphans` with
  warning `orphan_continuation` (add the page before it to `--pages`). Exam text then marks questions that are not whole
  with `[Incomplete: missing_text ...]`; the engine declines them (`solver_declined: missing_text (...)`).
- Exit 0 ok; 1 some question needs review; 2 usage/input; 3 blocked or call/reply error
  (`stream_format`, `call_failed`, `invalid_reply`, `cost_cap`, `answer_key_present`).

## Limits and unresolved risks
- Math stays text. PDF: math fonts give `math_possible` plus a page image. DOCX: equation (OMML)
  text is kept as plain text with `math_possible`, not LaTeX; check formulas by eye.
- OCR can garble characters (Vietnamese diacritics, digits, option letters); OCR pages are marked.
- DOCX text boxes are read inline at their anchor (info `text_box_inlined`). Headers, footers, footnotes and images
  inside tables are not read (`unsupported_content`). Auto-numbered lists lose their numbers (Word keeps them outside the text).
- Password-protected or old `.doc` files are refused (`encrypted`); convert to `.docx` first.
- Question segmentation and answer-key detection are heuristics (`Câu N` / `Question N`);
  `no_question_numbering` or `segmentation_skipped` means fix the saved document by hand.
  Numbering with gaps (a page slice, `1, 150`) or clean restarts at 1 keeps the questions and adds
  `numbering_gap` (missing numbers) / `numbering_restarted`; exam text renumbers 1..N with a mapping line.
  A restart that also has a gap, a backward jump or a number above 999 stays skipped (flagged).
- Multi-column order and table cells in PDFs are best effort (`reading_order_uncertain`).
- Nothing here proves extraction is 100% correct; the warnings are hints, not guarantees.

## Cross-solve (REQ-0023): second opinion at answer level

```
python3 -I scripts/exam.py cross-solve EXAM.md --pdf FILE.pdf --pages 1-4 --dry-run          # $0: prompts, call bound
python3 -I scripts/exam.py cross-solve EXAM.md --pdf FILE.pdf --pages 1-4 --real --max-cost-usd 1.00 --out DIR
```
Route A solves the exam text, route B the page images; per question `agree` or `needs_review` (`differ`, `missing_*`, `declined_*`, `count_mismatch`). Outputs `cross.json`, `review.md`, `cross.trace.json` (raw replies). Exit 0 all agree, 1 review needed, 2 usage, 3 call/cost/key-page stop. At most 4 calls (about $0.35 for 22 questions). Never defaults to real; answer-guide pages are refused. Agreement is evidence, not proof (one exam, n=22, same model).

Real multi-subject exam PDF (ĐGNL): see `dgnl-real-exam.md`.

## PDF extraction benchmark (REQ-0039, tier 0, $0)
Renders the synthetic gold to a PDF, ingests it on the text route and scores the result:
```
python3 -I scripts/exam.py gold-pdf evals/extract/gold/synthetic-001.json work/x/text.pdf [--variant text|formula-image] [--font TTF]
python3 -I scripts/exam.py ingest work/x/text.pdf --ocr off --assets work/x/a --out work/x/text.doc.json
python3 -I scripts/exam.py extract-eval evals/extract/gold/synthetic-001.json work/x/text.doc.json --out work/x/eval
```
Measures: text and option fidelity of the text-layer route on clean, single-column, generator-made PDFs with an
embedded Unicode font (an optimistic upper bound). The `formula-image` variant rasterises the formula line, so
text/options 20/20 show fidelity alone. Does not measure: scanned or photographed pages, OCR, two-column or grid
tables, real exams. This is not real-exam accuracy. The text route never fills formula or figures, so overall is 8/20 (40%) by construction; 99.999% is not claimed (n=20).
