# Phase 36: gold to PDF extraction benchmark (TASK-036; REQ-0039)
# Phase 36 - PDF-level extraction benchmark (draft for docs/design/phase-36-<slug>.md; slug suggestion `gold-pdf-extraction-benchmark`)
Task: TASK-036 · REQ-0039 AC1-AC2 (tier 0, $0) · Status: draft (Nova, designer)
## Goal
The synthetic gold (`evals/extract/gold/synthetic-001.json`, 20 q) is rendered to a real PDF with a text layer,
ingested by the real PDF adapter (text route, OCR off), and the resulting `doc.json` is scored by `extract-eval`
(accuracy + Wilson 95%). Evidence: report files under `work/TASK-036/ev/` with the numbers of §Verification.
## Constraints
- Python stdlib + already-required PyMuPDF (`fitz`, loaded via `ingest.optional.load`, same lib the adapter reads).
  No new dependency, no network. Font: DejaVuSans TTF (already used by tests, test_ingest_pdf.py:24).
- Gold stays outside `evals/inputs|keys|examples`; generated PDFs go to `work/` only (git-ignored).
- Text route unchanged: no edit to `ingest/adapters/pdf.py`, `segment.py`, `extract_eval.py`.
## Known incidents
none (phase-35 Risks noted AC1 "from synthetic PDFs" was deferred to this task).
## Premise / reuse (facts)
- `pdf.ingest` -> `doc["questions"] = segment.segment(all_lines)` (pdf.py:324-346): `{n, text, options:[{key,text}]}`,
  lines of a question joined by " " (segment.py:28-31); `_Q` = `Câu N.` (segment.py:4), `_OPT` = `A.`-`D.` (:5).
  Text is NFC (pdf.py:57). Text route never emits `latex`, `figures` or `verification`.
- `extract_eval.load_questions` accepts a canonical doc directly (`n` -> `norm_id`, list options -> dict, missing
  formula -> "", missing figures -> [], missing status -> "unverified") (extract_eval.py:51-81). So **no converter
  is needed**: `ingest --out doc.json` feeds `extract-eval` as is. `canon` = NFC + whitespace collapse, so gold
  `\n` in table text equals the " " join of segment.
- Existing CLI: `ingest FILE --ocr off --assets DIR --out DOC.json` (cli.py:225-287), `extract-eval GOLD EXTRACTED
  --out DIR` (cli.py:723-743). PDF writing pattern: `fitz.open(); new_page(); insert_text(..., fontname="dj",
  fontfile=TTF)` (test_ingest_pdf.py:57-67).
- Gold facts: formula in 10 q (1-8,15,20); figures in 4 q (6->p1, 12->p2, 13->p3, 15->p4); tables as markdown text in
  q10, q11; open q 18-20; Vietnamese in 1-7,11,12,15,19.
## Design
### 36.1 renderer `render(gold_path, out_pdf, variant="text", font=None) -> {"pages": int, "placed": {id: page}}`
Owner: new `src/exam_engine/pipeline/gold_pdf.py`. Reads gold via `extract_eval.load_questions` (reuses its
FORBIDDEN/dup checks). A4, margin 50, fontsize 11, leading 14, one `insert_text` per line (no auto-wrap).
Per question (ascending id): line `Câu <id>. <text line 1>`, remaining `text.split("\n")` lines, then the formula
(36.3), then `"<K>. <option>"` per key A-D, then figure (36.2), then one blank leading.
Pagination: a question block starts a new page when it does not fit, or when `figures[0] > current page`
(move it to its gold page). `ValueError` when a figure question would land after its gold page, a line is wider than
the text width (`fitz.get_text_length`), or the font file is missing. Font default: first of
`glob("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")`.
### 36.2 figure stand-in
For each `figures` page: a vector triangle + bounding rect, 80x60 pt, below the options (`page.draw_polyline`,
`draw_rect`); size >= 30x30 so the adapter's `cluster_drawings` crops it (pdf.py:283-286). No text inside.
### 36.3 variants (`--variant text|formula-image`)
- `text` (default, AC1/AC2): formula written as its own text line, literal LaTeX source (the gold string).
- `formula-image` (the one cheap harder variant): formula line rasterised (temp `fitz` page with the same
  insert_text -> `get_pixmap(dpi=150)` -> `page.insert_image(rect, pixmap=...)`): visible to a future vision
  refine, no text layer. Isolates pure text/option fidelity from formula placement.
Not added (follow-up only): two-column layout, grid tables (`find_tables` moves them out of question text).
### 36.4 CLI `gold-pdf GOLD OUT.pdf [--variant V] [--font TTF]` (cli.py `COMMANDS` :20-22, `table` :749-756)
`gold_pdf_main(argv)` in the style of `extract_eval_main`; prints `wrote OUT.pdf pages=N`; exit 0; usage /
ValueError / IngestError (fitz missing) / OSError -> `ERROR: gold-pdf: <msg>`, exit 2. The end-to-end run is the
three existing commands chained (no `extract-bench` wrapper: smallest, each step inspectable).
### 36.5 end-to-end step (documented in docs/guide/ingest-usage.md, one short section, coder may add)
`gold-pdf` -> `ingest --ocr off --assets work/.../assets --out doc.json` -> `extract-eval gold doc.json --out DIR`.
`--ocr off` makes the result independent of installed tesseract data.
### 36.6 what this measures (goes verbatim-ish into the report)
Text-layer extraction of clean, single-column, generator-made PDFs with an embedded Unicode font: an optimistic
upper bound for born-digital exams, not scanned/photographed pages. Headline = text route as shipped: it never fills
formula or figures, so formula/figure-bearing questions are wrong by construction (capability gap, filled only by
paid refine). The `formula-image` run shows text+options fidelity alone. 99.999% stays NOT claimed (n=20).
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| fitz not installed | IngestError -> exit 2 | `ERROR: gold-pdf: ... pymupdf` |
| no DejaVu / bad `--font` | ValueError -> exit 2 | `ERROR: gold-pdf: font ...` |
| figure q cannot reach gold page / line too wide | ValueError -> exit 2 | message names question id |
| segmentation off (numbering broken) | ingest warns `segmentation_skipped`, no questions | extract-eval all missing, 0/20 |
| diacritics lost (font w/o ToUnicode) | text mismatch | text rate < 20/20, ids in "Wrong questions" |
## Unit tests (tests first: tests/unit/test_gold_pdf.py; skipIf no fitz / no DejaVu, like test_ingest_pdf.py:43,88)
1. render text: page_count 4; `placed` == {6:1,12:2,13:3,15:4} for figure q; `get_drawings()` non-empty on p1-p4.
2. diacritics: fitz page text (NFC) contains "Tính giá trị của biểu thức dưới đây.", "Sĩ số", "Bằng nhau",
   "Hãy nêu ý nghĩa của định luật bảo toàn năng lượng." exactly.
3. e2e text: ingest(ocr off, tmp assets) -> q n == 1..20, no `segmentation_skipped`; evaluate -> exact k:
   overall 8/20, text 10/20, options 20/20, formula 10/20 (applicable 0/10), figures 16/20 (applicable 0/4),
   missing [] extra [], verified precision n/a, needs_review 0/20.
4. e2e formula-image: text 20/20, options 20/20, overall 8/20, formula applicable 0/10; no gold formula string
   in page text; `get_image_info()` non-empty on p1.
5. bite: render a temp gold copy with q9 text "Mercury"->"Mars" in text and q17 option A changed; score vs the
   original gold -> overall 6/20 and those ids in wrong list (the pipeline really reads the PDF).
6. errors: figure page 1 on a q that cannot fit page 1 -> ValueError naming it; overlong line -> ValueError;
   missing font -> ValueError.
7. CLI: `main(["gold-pdf", gold, out])` exit 0 + file exists; `--variant bad` -> 2; missing gold -> 2 + `ERROR: gold-pdf:`.
Anti-trivial: 3-5 assert exact k from the PDF round trip, never from the gold object.
## Verification (tier 0, $0; tester recomputes numbers independently, e.g. jq over doc.json vs gold)
| Item | command -> expected |
|---|---|
| unit | `python3 -I -m unittest discover -s tests/unit` -> all pass, test_gold_pdf not skipped (`fitz`, DejaVu present: `python3 -I scripts/exam.py ingest --check`) |
| 36.1 AC1 | `python3 -I scripts/exam.py gold-pdf evals/extract/gold/synthetic-001.json work/TASK-036/ev/text.pdf` -> exit 0, `pages=4` |
| 36.5 AC2 | `ingest work/TASK-036/ev/text.pdf --ocr off --assets work/TASK-036/ev/a1 --out work/TASK-036/ev/text.doc.json` then `extract-eval <gold> work/TASK-036/ev/text.doc.json --out work/TASK-036/ev/text` -> overall 8/20 = 40% (Wilson ~21.88-61.34%), text 10/20 (29.93-70.07%), options 20/20 (83.89-100%), formula applicable 0/10 (0-27.75%), figures applicable 0/4 (0-48.99%), "NOT claimed", "299572" |
| 36.3 | same chain with `--variant formula-image` -> text 20/20, options 20/20, overall 8/20 |
| 36.4 error | `gold-pdf <gold> /nonexistent-dir/x.pdf` -> exit 2, `ERROR: gold-pdf:` |
| leak | `python3 -I scripts/exam.py check-examples` -> unchanged PASS; `git status` shows no PDF outside work/ |
Interval values are my hand computation (4 dp, rounded); report_lines format decides digits.
## Decisions (proposed)
- Score the raw ingest doc - rejected a `$..$`->formula bridge - a bridge would score our own markup, not ingest.
- Reuse fitz (adapter's lib) - rejected stdlib PDF writer - Type-0/ToUnicode font embedding for Vietnamese in a
  hand-written PDF is a new fragile component; fitz already embeds DejaVu correctly in tests.
- Three chained existing commands - rejected one `extract-bench` subcommand - smaller; can wrap later.
- One harder variant = formula-image (cheap, same lib); two-column/grid tables deferred.
## Risks
- Segment split errors: a formula/option/table line starting with `N.`/`N)` or `A.`-`D.` would be misread; gold
  lines checked by hand: none do (tables start `|`, formulas `\`, `(`, `-`, digits without `.`/`)`).
- MuPDF block grouping/order: single column, x0=50 for all lines -> `_order` two-column never triggers.
- NFC/NFD: gold is loaded and compared via NFC canon; adapter outputs NFC; test 2 asserts exact NFC strings.
- Fonts: DejaVu missing on another host -> tests skip (visible in unittest output); verification requires not-skipped.
- formula-image: >6 images on a page -> `crops_capped` warning only (no effect on questions).
- Headline 40% may read as "ingest is bad": report must state 36.6 (gap = formula/figures by construction).
## Out of scope
Real/scanned/photographed PDFs and user-labelled pages (REQ-0040), OCR route, paid vision refine, attaching
figures/latex to text-route questions (ingest feature change), REQ-0024 gating, two-column/grid-table variants.
## Defects
None found. Observation (not a defect): text route has no formula/figure fields, so its PDF-level accuracy is
capped at 8/20 on this gold whatever the text fidelity; worth a backlog note if the user wants a free formula path.


## Coordinator note
fitz is installed in the user site and `python3 -I` ignores user site; the ingest adapter adds it deliberately (see `exam.py ingest --check`, "user site"). Reuse that mechanism (how pdf.py / test_ingest_pdf.py import fitz), never `pip install`. Expected scores are the designer's hand count and must be recomputed independently by the tester.
