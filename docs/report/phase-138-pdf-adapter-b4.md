# Phase 138 – PDF adapter review (batch 4)

Scope: `src/exam_engine/ingest/adapters/pdf.py` (744 lines, whole file). Callees read only to prove findings:
`segment.table_lines`, `segment._OPT`, `segment._INTRO`, `cli.py` ingest handler (1068-1127).
Entry point for every finding: CLI ingest (`cli.py:1093`) -> `api.ingest_document` -> `pdf.ingest` -> `_extract`.
`docs/review/findings.tsv` has no earlier row for this file.

## Findings

### F001 – [MEDIUM] Table text is attached to the wrong column's question on two-column pages

- File: src/exam_engine/ingest/adapters/pdf.py
- Lines: 233-234
- Type: BUG
- Trigger: normal input
- Reached via: `_extract` -> `_text_lines` (line 685)
- Issue: `above[-1]` is the last block in sequence order, not the nearest block above. On two-column pages `seq` is left column then right column.
- Case: left-column table at y=300, right-column blocks at y=100 and y=290 -> table lines land after the right block, inside another question.
- Fix: add `mid=None`; when given, keep only `above` blocks on the table's side of `mid`; pick the greatest `pb[1]` (ties: highest index). Line 685 passes `pw / 2.0 if two_col else None`.
- Fix risk: `test_pdf_table_text_129.py` Placement tests call without `mid`; greatest-top with highest-index tie keeps both.

### F002 – [MEDIUM] Table cells with a line break or a `|` are re-split into wrong rows and columns

- File: src/exam_engine/ingest/adapters/pdf.py
- Lines: 234, 639
- Type: BUG
- Trigger: normal input
- Reached via: `_extract` -> `_text_lines` -> `segment.table_lines`
- Issue: rows are joined with ` | ` and `\n`, then split again on the same characters.
- Case: row `["Đắk\nNông", "1,064"]` -> `| Đắk |` and `| Nông | 1,064 |`. Boxed passage `Cho |x - 1| < 3` -> `| Cho | x - 1 | < 3 |`.
- Fix: in `_text_lines`, when the item extras hold `rows`, build lines from them: all rows <= 1 non-empty cell -> that cell's `split("\n")`; else one `| a | b |` line per row with `\n` in cells replaced by a space.
- Fix risk: items without `rows` (unit tests) keep `segment.table_lines(text)`. Paths that re-segment saved block text (`test_pages_resegment_keeps_tables`) still re-split; check them.

### F003 – [MEDIUM] A page of short questions with options in a row is read as two columns

- File: src/exam_engine/ingest/adapters/pdf.py
- Lines: 177-180, 193-196
- Type: BUG
- Trigger: normal input
- Reached via: `_extract` -> `_order_page` -> `_order` (line retry)
- Issue: any page whose lines all sit left or right of the middle counts as two-column.
- Case: stems shorter than half the width, options `A. 1  B. 2  C. 3  D. 4` on one baseline, no centred line -> all `C.`/`D.` lines move after the last question; earlier questions keep only A and B.
- Fix: in `_order`, return `(blocks, False)` when every `right` item's first text line matches `segment._OPT`.
- Fix risk: a true two-column page whose right column holds only option-start blocks stays in native order (as before the line retry existed). No test calls `_order` directly.

### F004 – [MEDIUM] Group lead lines are removed as repeated page headers

- File: src/exam_engine/ingest/adapters/pdf.py
- Lines: 252-253, 256, 267
- Type: BUG
- Trigger: normal input
- Reached via: `_extract` -> `_strip_furniture` (line 694)
- Issue: `key()` folds digits and `content()` protects only question and option lines.
- Case: 6-page exam; on 3 pages one of the first two lines is `Dựa vào thông tin dưới đây để trả lời các câu từ N đến M` -> same key, count >= 3, all three lead lines dropped; the groups lose their range.
- Fix: `content(ln)` also returns True when `segment._INTRO.match(ln)` or `segment._READ.match(ln)`.
- Fix risk: none; header/footer fixtures in `test_text_boundaries*.py` and `test_ocr_doubt.py` do not match those patterns.

### F005 – [MEDIUM] On an OCR page the table area keeps the bad native text and drops the OCR text

- File: src/exam_engine/ingest/adapters/pdf.py
- Lines: 576, 623-624, 638-639
- Type: BUG
- Trigger: normal input
- Reached via: `_extract` page loop, OCR branch
- Issue: `tables` come from the native text layer before OCR; OCR blocks inside a table box are filtered out.
- Case: page flagged `bad_encoding` with a ruled table -> OCR text is chosen for paragraphs, but the table lines are the garbled native cells and the readable OCR text of that area is discarded.
- Fix: when `method` becomes `"ocr"`, build `ocr_blocks` without the `tbbox` filter and set `tables = []` and `tbbox = []`.
- Fix risk: drawing clusters inside the former table box become crops (line 655), bounded by `MAX_CROPS`.

### F006 – [MEDIUM] A text block that only partly covers a table is dropped whole

- File: src/exam_engine/ingest/adapters/pdf.py
- Lines: 165-167, 582
- Type: BUG
- Trigger: normal input
- Reached via: `_extract` page loop
- Issue: a block is removed when its centre is inside a table box, even if some of its lines are outside the box.
- Case: block (50,100,500,200) holding a stem line plus the first cells; table box (50,120,500,200) -> centre y=150 is inside, the stem line at y=100-120 is in no paragraph and no table row.
- Fix: for a block whose centre is inside a table but whose bbox exceeds it by more than 2pt, keep its lines whose own centre is outside every table (same test on line bboxes).
- Fix risk: none; fully contained blocks behave as today.

### F007 – [MEDIUM] Garbled native text is kept when clean OCR text is not longer

- File: src/exam_engine/ingest/adapters/pdf.py
- Lines: 626
- Type: BUG
- Trigger: normal input
- Reached via: `_extract` page loop, OCR branch
- Issue: OCR is accepted only when `len(ocr_text) > len(native_text)`; for a `bad_encoding` page length says nothing about quality.
- Case: broken font map, 3000 native chars of garbage, OCR gives 2800 readable chars -> the garbage becomes the question text.
- Fix: accept OCR when `len(ocr_text.strip()) >= MIN_CHARS and (len(ocr_text) > len(native_text) or (flags != ["missing_text"] and not _suspect(ocr_text)))`.
- Fix risk: `missing_text` pages unchanged. Any test that mocks OCR on a `bad_encoding` page and expects native text must change.

### F008 – [MEDIUM] `ocr_doubt` "chars" is driven by the native text flags, not by the OCR text

- File: src/exam_engine/ingest/adapters/pdf.py
- Lines: 601-603, 629, 734-735
- Type: BUG
- Trigger: normal input
- Reached via: `_extract` -> `_ocr_doubt` (`suspect_pages`)
- Issue: `sus` looks for a `bad_encoding` warning, which is written only for native text; a suspect OCR text adds no warning.
- Case: native text is digits only (`no_letters`), OCR is clean -> every question of the page gets `ocr_doubt: ["chars"]` and counts as uncertain. A scan whose OCR text is suspect is never in `sus`.
- Fix: collect `pno` in a set when OCR is chosen and `_suspect(ocr_text)` is non-empty; pass that set as `sus`.
- Fix risk: none; `_ocr_doubt` signature unchanged.

### F009 – [LOW] Page-cut detector treats suspect OCR pages as native text

- File: src/exam_engine/ingest/adapters/pdf.py
- Lines: 479-480
- Type: BUG
- Trigger: normal input
- Reached via: `_extract` -> `_cut_boundaries` (line 699)
- Issue: `ok()` tests `status != "ocr"`, but an OCR page whose text is suspect has status `needs_review` and method `ocr`.
- Case: two scanned pages with suspect OCR text -> `page_cut_suspect` is raised from OCR lines, against the docstring ("both pages need native text").
- Fix: `ok()` also requires `p.get("method", "native") != "ocr"`.
- Fix risk: `test_refine_window.py` page dicts have no `method`; the default keeps them.

### F010 – [LOW] A page that fails to load or render ends ingest with a traceback

- File: src/exam_engine/ingest/adapters/pdf.py
- Lines: 544-545, 571, 582, 668
- Type: HARDENING
- Trigger: malformed file
- Reached via: `pdf.ingest` -> `_extract`; `cli.py:1123-1126` catches only IngestError, OSError, ValueError
- Issue: `pdf[pno]`, `_page_blocks` and `_save_crop` are not guarded; PyMuPDF raises its own error types.
- Case: PDF that opens but has one broken page object -> uncaught error, no `ERROR: ingest` line, crops of earlier pages stay in the asset dir.
- Fix: in `ingest`, around `_extract`: `except IngestError: raise`, then `except Exception as exc: raise IngestError("corrupt", "cannot read PDF %s: %s" % (os.path.basename(path), exc))`.
- Fix risk: a programming error in `_extract` is then reported as `corrupt`; the message keeps the exception text.

## Summary

- Total findings: 10 (CRITICAL 0, HIGH 0, MEDIUM 8, LOW 2; BUG 9, HARDENING 1)
- Cap hit: yes
- Not reviewed: two candidates left out by the cap, not fully proven: (1) lines 640 and 673 place table and image
  blocks by top edge only, so on two-column pages the block order in `pages[].blocks` can put them in the other
  column (same cause as F001, affects `_image_before_question`); (2) line 267 drops a repeated edge line of any
  key length (`LEAK_MIN_KEY` is applied only to leaks at 263), so short digit-folded lines such as bare numeric
  answer lines at page edges can be removed. Not provable from code alone: reading order of two-column scanned
  pages (OCR blocks are not passed through `_order_page`). Read without a finding: tessdata lookup,
  `_ocr_line_text`, `_parse_tsv`, `_tsv_conf`, `_odd_token`, `_option_parity`, asset paths.
