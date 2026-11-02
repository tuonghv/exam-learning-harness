PROGRESS: AC1 diagnosed (measurement only); AC2 behaviour measured; AC3 signals measured; no repo edits, no paid call
SKILLS: inspector, token-efficiency, crosscheck

# TASK-051 / REQ-0054 AC1-AC3 diagnosis (OCR space loss)

ANSWER: spaces are lost in the PyMuPDF OCR bridge (`get_textpage_ocr`, src/exam_engine/ingest/adapters/pdf.py:337), not in tesseract itself. Same image, vie+eng: tesseract CLI gives 0-1 glued tokens; the bridge gives 16-17 at 150/200/300 dpi. dpi, psm and `preserve_interword_spaces` change nothing about glue. Cheap fix: rebuild text from the char boxes of `get_text("rawdict", textpage=tp)`, inserting a space when the gap to the previous char exceeds 0.15 x median char height: glued 16 -> 2, CER 0.0287 -> 0.0194, no extra OCR cost (measured, 2 pages, 424 gold words).
Second finding: this host has eng + osd only (`tesseract --list-langs`). `pick_ocr_language` (pdf.py:49) then returns `eng` and the engine warns `ocr_language_missing`; Vietnamese diacritics are lost (CER 0.040 eng vs 0.019 vie+eng; 225 of 424 words wrong with eng only).

## Method
- Fixture: `gold_pdf.render(<TASK-046 F1 gold>, furniture=True)` (synthetic Vietnamese text), pages 1-2, PNG at 150/200/300 dpi; oracle = the render's own text layer (424 words). Scan PDF for the production route = `gold_pdf.scan_pdf` (zoom 2 = 144 dpi image). NFD-folded (no diacritics) compare, whitespace-normalised.
- glued = OCR token not in the gold word set but equal to the concatenation of 2-4 consecutive gold words. cer = Levenshtein/len(gold). cer_nospace ignores spaces. sec = both pages.
- vie is not installed under /usr/share: used a scratchpad tessdata dir with a symlink to a vie.traineddata found at /data/process-resume/data (outside the repo, read-only). See Gaps.
- Raw tables and scripts (scratchpad): res_cli.tsv, res_prod.tsv, exp.py, glue.py, conf.py, furn.py.

## Table (TSV; cli_tsv psm 3/6 at 150/200/300, makebox rows, production rows; psm 4 and 11 equal psm 3 within 0.001 CER)
```
name	dpi	psm	pres	lang	glued	gold_words	ocr_words	cer	cer_nospace	mean_conf	sec
cli_tsv	150	3	0	eng	0	424	422	0.0416	0.0482	86.8	1.17
cli_tsv	150	3	0	vie	1	424	423	0.0167	0.0168	92.0	1.61
cli_tsv	150	3	0	vie+eng	1	424	423	0.0167	0.0168	92.0	1.73
cli_tsv	150	3	1	vie+eng	1	424	423	0.0167	0.0168	92.0	1.74
cli_tsv	150	6	0	eng	0	424	424	0.0405	0.0468	86.2	1.10
cli_tsv	150	6	0	vie	1	424	423	0.0167	0.0168	92.0	1.48
cli_tsv	150	6	0	vie+eng	1	424	423	0.0167	0.0168	92.0	1.76
cli_tsv	150	6	1	vie+eng	1	424	423	0.0167	0.0168	92.0	1.75
cli_tsv	200	3	0	eng	0	424	424	0.0378	0.0434	84.9	1.47
cli_tsv	200	3	0	vie	1	424	423	0.0167	0.0168	91.8	1.93
cli_tsv	200	3	0	vie+eng	0	424	424	0.0184	0.0182	91.7	2.11
cli_tsv	200	3	1	vie+eng	0	424	424	0.0184	0.0182	91.7	2.14
cli_tsv	200	6	0	eng	0	424	422	0.0400	0.0462	85.2	1.29
cli_tsv	200	6	0	vie	1	424	423	0.0167	0.0168	91.8	1.75
cli_tsv	200	6	0	vie+eng	0	424	424	0.0184	0.0182	91.7	1.93
cli_tsv	200	6	1	vie+eng	0	424	424	0.0184	0.0182	91.7	1.92
cli_tsv	300	3	0	eng	0	424	424	0.0345	0.0392	85.6	1.91
cli_tsv	300	3	0	vie	0	424	424	0.0173	0.0168	91.8	2.41
cli_tsv	300	3	0	vie+eng	0	424	424	0.0189	0.0189	91.8	2.66
cli_tsv	300	3	1	vie+eng	0	424	424	0.0189	0.0189	91.8	2.67
cli_tsv	300	6	0	eng	0	424	424	0.0335	0.0378	85.7	1.63
cli_tsv	300	6	0	vie	0	424	424	0.0173	0.0168	91.8	2.14
cli_tsv	300	6	0	vie+eng	0	424	424	0.0189	0.0189	91.8	2.42
cli_tsv	300	6	1	vie+eng	0	424	424	0.0189	0.0189	91.8	2.43
cli_makebox_gap0.25	200	3	-	vie+eng	0	424	534	0.0778	0.0182	-1.0	1.99
cli_makebox_gap0.35	200	3	-	vie+eng	0	424	424	0.0184	0.0182	-1.0	1.99
cli_makebox_gap0.25	200	6	-	vie+eng	0	424	534	0.0778	0.0182	-1.0	1.90
cli_makebox_gap0.35	200	6	-	vie+eng	0	424	424	0.0184	0.0182	-1.0	1.90
cli_makebox_gap0.25	300	3	-	vie+eng	2	424	436	0.0296	0.0189	-1.0	2.64
cli_makebox_gap0.35	300	3	-	vie+eng	2	424	420	0.0211	0.0189	-1.0	2.65
cli_makebox_gap0.25	300	6	-	vie+eng	2	424	436	0.0296	0.0189	-1.0	2.39
cli_makebox_gap0.35	300	6	-	vie+eng	2	424	420	0.0211	0.0189	-1.0	2.39
pymupdf_prod	150	auto	-	eng	0	424	422	0.0395	0.0441	-1.0	2.81
pymupdf_prod	200	auto	-	eng	0	424	420	0.0400	0.0448	-1.0	3.03
pymupdf_prod	300	auto	-	eng	0	424	424	0.0362	0.0412	-1.0	3.30
pymupdf_prod	150	auto	-	vie+eng	17	424	404	0.0271	0.0168	-1.0	7.63
pymupdf_prod	200	auto	-	vie+eng	16	424	403	0.0287	0.0168	-1.0	8.16
pymupdf_prod	300	auto	-	vie+eng	16	424	405	0.0293	0.0190	-1.0	8.93
```

## Findings AC1
- preserve_interword_spaces 0 vs 1: identical output in every row (single-column text).
- psm 3/4/6/11: CER within 0.001-0.002; psm 6 not better; psm 11 same as 3. Multi-column pages not tested.
- dpi: CER (vie+eng, CLI) 0.0167 @150, 0.0184 @200, 0.0189 @300; time 1.7/2.0/2.7 s per 2 pages. eng-only improves with dpi (0.042 -> 0.034). No dpi fixes the bridge glue (16-17 at all). Source scan is 144 dpi, so 300 is upscaling.
- Glue sits on short diacritic words: "tử tử ánh" -> "tửtửánh", "thế tụ kỳ" -> "thếtụkỳ(b2.1)", "số đơn" -> "sốđơn", header "Đềthi thử-Môn". The same strings exist in the TASK-046 F1 OCR output (gen/F1.ocr.json). Cause is the bridge's word/space synthesis: CLI TSV on the same pixels yields separate words.
- Bridge `get_text("words")` and `"text"` are equally glued (16); reassembly must use `rawdict` char boxes.
- CLI makebox reassembly: gap 0.25 x height over-splits (534 words vs 424) at 200 dpi; 0.35 is clean at 200 (0 glued, CER 0.0184) but 2 glued at 150/300. Bridge char boxes with gap 0.15 x median char height: 2 glued, 420 words. Threshold is unstable: tune on a second family before coding.
- Best cheap setting: keep the bridge, lang vie+eng, dpi 200 (as now), replace the text join by rawdict char-gap spacing (0.15). Alternative: tesseract CLI `--psm 3 -l vie+eng` with TSV words: 2 s vs 8 s per 2 pages, 0-1 glued, but adds a subprocess path.
- Runtime: bridge vie+eng 8.2 s/2 pages @200 vs eng 3.0 s.

## AC3 signals (what predicts doubtful text)
- Word confidence (CLI TSV, psm 6, 200 dpi): vie+eng correct words mean 91.8 (n=415), wrong words mean 86.2 (n=9); wrong with conf<70: 2 of 9; correct with conf<90: 5 of 415. eng-only (diacritics lost): wrong mean 80.4 (n=225); conf<80 flags 50 of 225, correct with conf<80: 6. Page mean falls only 91.8 -> 90.7 though 225 words are wrong, so the page mean is weak; share of words below 80 is better. The bridge exposes no confidence: a per-word signal needs the CLI TSV.
- Glue heuristic: bridge glue 16 vs 2 after rawdict gap. Free signal: tokens that split in the rawdict join but not in the plain text join. No wordlist in the repo (not checked).
- Language-data signal: `ocr_language_missing` (pdf.py:333) already exists and is the strongest: with eng only, 53% of words are wrong and nothing marks the questions.
- Character-error signal: not quantified.
- `_suspect` (pdf.py:143) flags only replacement/control chars, missing text, no letters: it flagged nothing on these pages.

## AC2 page furniture on OCR lines
- Fixture page lines (furniture=True): header "Đề thi thử - Môn Toán - Mã đề 101" first line, "Trang N" last line, each page.
- OCR header variants: "Đềthi thử-Môn Toán - Mã đề101" (p1, p2), "Đềthi thử- Môn Toán - Mã đề101" (p4). Footer "Trang 1".."Trang 4" read exactly.
- `_strip_furniture` (pdf.py:162) on the OCR lines: 2 pages -> removed 2 (page numbers only; header repeats need >= 3 pages, FURNITURE_PAGES); 4 pages -> removed 7 of 8: 4 page numbers + 3 headers; the page 4 header survives because OCR spacing differs ("thử- Môn" vs "thử-Môn") so the digit-folded key does not match. eng-only run: same 7/8 (header read "Dé thi thir-Mén Todn - Ma dé 101", varies by page).
- Behaviour: the filter works on OCR lines, but exact keys are fragile to OCR noise; a key with spaces removed would match page 4. A leaked-header test needs >= 3 pages. The call at pdf.py:408 does run on OCR pages.

## Gaps
- vie.traineddata is not in the host tessdata dirs; I used a copy outside the repo (/data/process-resume/data, symlink in scratchpad). The engine on this host runs eng only: a finding in itself.
- One family (F1), 2 pages, clean synthetic single-column render, 144 dpi scan: a diagnosis, not a rate. Skew, JPEG noise, multi-column not tested; glue 16 vs 2 is small-n.
- Metrics use diacritic-folded text, so accent loss is not counted as an error; eng-only CER is understated.
- Confidence only via CLI TSV; no false-positive rate of any glue heuristic on glue-free text.
- Not tested: Haiku fallback (REQ-0053), extract-eval share reaching the solver (AC4).
