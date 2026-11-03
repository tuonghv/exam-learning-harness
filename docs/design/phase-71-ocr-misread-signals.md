# Phase 71 - OCR single-character misread signals (TASK-071)
Task: TASK-071 · REQ-0065 · Status: designed.

# Phase 71 - OCR misread doubt signals (draft for docs/design/phase-71-ocr-misread-signals.md)
Task: TASK-071 · REQ-0065 · Status: draft · Supersedes: phase-51 D2 (per-word confidence deferred)

## Premise (facts at HEAD 52fd01b)
- Doubt kinds today: glued / chars / furniture / lang_missing in `pdf._ocr_doubt` (pdf.py:301-327), called once at pdf.py:593; gate `refcheck.incomplete_reasons` -> `ocr_doubt <k>` (core/refcheck.py:132); `api.UNCERTAIN` holds `ocr_doubt` (api.py:261) -> sidecar `uncertain`, engine declines.
- Residual (report phase-51 :8-14, work/TASK-051/evidence/ocr-before-after.tsv): wrong-and-unmarked A 1/10, B 4/10, C 4/10; false alarms 0/9 (A), 0/4 (B); only 13 correct questions in total. B residue = single-glyph misreads forming valid tokens (synthetic "Số" -> "$6", "hơn" -> "hon", "Giá" -> "Gia").
- Confidence evidence (work/TASK-051/evidence/diagnosis.md:69, CLI TSV psm 6, 200 dpi): vie+eng correct words mean 91.8 (n=415), wrong 86.2 (n=9); wrong <70: 2/9; correct <90: 5/415. eng-only (diacritics lost, like family C): wrong mean 80.4, <80 flags 50/225 wrong vs 6 correct. Page mean is weak (91.8 -> 90.7 with 225 wrong). The PyMuPDF bridge exposes no confidence.
- Cost (diagnosis.md:17-41,61,65): CLI TSV vie+eng 200 dpi ~1.9 s per 2 pages vs bridge ~8 s per 2 pages.
- Option count: `options_incomplete` already fires for 1-3 of A-D (core/refcheck.py:115); option keys from segment.py:275.
- Structure flags: `api._flag` (api.py:110) -> assembly `structure` (api.py:281,293; ctx copies q, api.py:257, so a doc-level `structure` list survives) -> board parse flags (phase 69.3/69.4, cli.py:1409), `WARN: structure:` (cli.py:541). needs_review_why exists only on the refined route (refine.py:49-55).
- Measurement helper: tests/unit/ocr_before_after.py (families from ocr_gap_sweep.FAMILIES :20; `score` :72-97 counts wrong_unmarked / marked_correct).

## Goal
A scanned question whose OCR holds a likely single-glyph misread is marked before the solver: hard `ocr_doubt low_conf|token` (declined, sidecar uncertain) or soft structure flag `option_parity` (solved, board parse-flagged). Known by: offline re-run of families A/B/C (+ clean family D): wrong_unmarked after-71 < after-51 on B and C, false alarms on correct questions = 0.

## Constraints
- Native pages: no TSV run, no new kind; exam text and sidecar byte-identical (every signal gated on OCR lines, as 51.4).
- Text never corrected; signals only add `ocr_doubt` kinds or a `structure` code. Doc schema: no new key, only new values in existing lists.
- Trust boundary: tesseract via `subprocess.run([...], input=png, timeout=..., capture_output=True)`, list argv, no shell, binary from `shutil.which`; the untrusted PDF reaches it only as pixels.
- Cache: no AI prompt or cached body changes (boundary key holds window text, boundary.py:300; refine input unchanged); solver has no reply cache.
- Host-dependent output (binary present or not) must not reach goldens: goldens pin config `ocr_conf: "off"`.

## Generality
Covers every scanned exam kind and language with tesseract data: confidence is the recognizer's own 0-100 per-word score (same scale for any traineddata), token/parity rules use Unicode categories only, no word list; per-language threshold override is data (`config/lang.json` optional key `ocr_low_conf`); default config keeps native inputs byte-identical (golden `test_generality_golden`); one test uses a synthetic non-DGNL English science exam ("H2O", "x2", "$5", 5 options A-E everywhere) -> no flags.

## Known incidents
none (docs/notes/incidents.md not present).

## Plan modes
- Native PDF / Markdown / DOCX: unaffected (no OCR lines).
- Scanned, tesseract binary present (`ocr_conf: "auto"`, default per D5): 71.1-71.4 apply.
- Scanned, binary absent or `ocr_conf: "off"`: 71.1 returns None, info warning once; 71.3 strong shapes and 71.4 still run (free).
- Refined route (`--refined`): not affected (phase-51 G4 stays; D-1).
- `--boundary-ai haiku`: unchanged, same lines.

## Design
### 71.1 Per-word confidence (owner: pdf.py new `_tsv_conf(page, lang, tess_dir, config) -> dict|None`)
- argv `[tesseract, "stdin", "stdout", "-l", lang, "--psm", "3", ("--tessdata-dir", D)?, "tsv"]`; stdin = `page.get_pixmap(dpi=OCR_DPI).tobytes("png")` (same pixels/dpi as the bridge); `TSV_TIMEOUT = 60` s per page.
- Pure `_parse_tsv(text) -> {word: conf}`: rows level 5, conf >= 0, word = NFC, edge punctuation stripped, duplicates keep the min.
- None when `ocr_conf == "off"`, no binary, non-zero exit, timeout or parse error; warning `ocr_conf_unavailable` (level info, once per doc, reason in text). Called only after `method = "ocr"` is set (pdf.py:485); result kept in local `conf_pages = {page_idx: dict}`.
### 71.2 `low_conf` kind (owner: `_ocr_doubt(..., conf=None)`, pdf.py:301; call pdf.py:593)
- A token of an OCR line on page p (same strip/NFC) with `conf[p].get(tok, 100) < floor(lang)` adds `low_conf`. A token the CLI spelled differently has no entry -> no flag.
- `floor(lang)` = `config/lang.json` `ocr_low_conf` for that language if present, else `OCR_LOW_CONF` (named constant from the 71.5 sweep, comment cites the TSV).
### 71.3 `token` kind - glyph plausibility (owner: pdf.py new `_odd_token(tok, conf=None) -> bool`)
- Strong shapes (flag without confidence): a digit between two letters (`h0n`, `c6u`); a `Sc`/`So` symbol directly touching a letter (`$o`, `S$`).
- Weak shapes (flag only when the word's TSV conf < floor + `TOKEN_MARGIN`): `Sc` followed by digits (`$6`), upper-case letter + digits with no other letter (`S6`). No TSV -> weak shapes never flag (protects money `$5` and math `x2`, `H2O`).
### 71.4 `option_parity` structure flag (owner: pdf.py new `_option_parity(qs, ocr_q)`, after `_ocr_doubt` at :593)
- `ocr_q` = indexes of questions with lines on OCR pages (already computed in `_ocr_doubt`; return it). Writes `q["structure"] = [..., "option_parity"]` (same shape as `api._flag`).
- Shape: options' first-char class (letter / digit / symbol); exactly one option differs from >= 3 others -> flag. Count: option count != the mode of OCR questions with options while that mode covers >= 80% of them (a stray `E.` line) -> flag. Soft: solved, assembly `structure`, board parse-flagged, `WARN: structure:` line.
### 71.5 Calibration + measurement (owner: tests/unit/ocr_before_after.py, tier 0, offline)
- Families A/B/C as phase 51 at 30 questions each (`gold_questions` count param) + D = clean DejaVuSans 14 (false-alarm pool). Arms: after-51 (new kinds disabled) vs after-71. New columns `soft_flagged`, `marked_by_kind`.
- Sweep floor in {50,60,70,75,80,85,90} x `TOKEN_MARGIN` in {0,5,10}: per family wrong_unmarked, marked_correct. Pick the largest floor with marked_correct = 0 on A-D (ties -> smaller margin). Save work/TASK-071/qa/conf-sweep.tsv.
- Adoption gate: no floor lowers wrong_unmarked on B or C by >= 1 at 0 false alarms -> `ocr_conf` default "off", recorded; 71.3 strong shapes and 71.4 still ship.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| tesseract binary absent / timeout / bad TSV | 71.1 None, low_conf and weak tokens skipped | info `ocr_conf_unavailable` once |
| CLI and bridge read a word differently | no match -> not flagged | wrong_unmarked in 71.5 |
| low-conf false alarm on a correct word | question declined (safe) | `ocr_doubt low_conf` marker; 71.5 false-alarm column |
| real `$5`, `x2`, `H2O` | weak shape needs low conf; strong shapes exclude them | nothing (non-DGNL test) |
| exam with mixed option counts | mode < 80% -> no count flag | nothing |
| new script's conf scale differs | `ocr_low_conf` per-language override | re-run 71.5 with that traineddata |
| extra OCR time | ~+1 s/page, OCR pages only | slower ingest; `ocr_conf: "off"` |

## Unit tests (tier 0; image test skipIf no fitz or no tesseract binary)
- `_parse_tsv`: fixture TSV string (levels 1-5, conf -1 rows, duplicate word keeps min, punctuation stripped, NFC).
- `_tsv_conf`: patched `shutil.which` -> None returns None + one warning; patched `subprocess.run` raising TimeoutExpired / returncode 1 -> None; `ocr_conf: "off"` -> subprocess mock called 0 times.
- `_ocr_doubt(conf=...)`: synthetic lines + conf map: token below floor -> `low_conf`; same token on a native page -> none; conf=None -> today's kinds only (existing tests unchanged); lang.json override changes the floor.
- `_odd_token`: "h0n", "$o" true; "x2", "H2O", "$5", "2x", "101" false; "$6" true only with conf below floor + margin.
- `_option_parity`: four sentence options, one starting "$6" -> flag; four numeric options -> none; 4-option mode with one 5-option question -> flag; mixed 2/4 options (mode < 80%) -> none; native question -> none.
- non-DGNL synthetic English science exam (5 options everywhere, money, formulas) on OCR pages: no new kind, no flag.
- golden: native PDF + OCR goldens with `ocr_conf: "off"` byte-identical to HEAD.
- image (skipIf): fitz-rendered synthetic page, 6 pt and 10 pt lines -> `_tsv_conf` non-empty, ints 0..100.

## Verification (tier 0, no paid call)
| Item | command -> expected |
|---|---|
| 71.1 | `python3 -I -m unittest tests.unit.test_ocr_conf` -> OK (TSV, fallback, off) |
| 71.2 | `python3 -I tests/unit/ocr_before_after.py work/TASK-071/qa/after.tsv` -> wrong_unmarked after-71 < after-51 on B and C; marked_correct 0 on A-D |
| 71.3 | same TSV: `marked_by_kind` token > 0 on B, 0 on D |
| 71.4 | same TSV: soft_flagged column filled; marked_correct unchanged by it (soft) |
| 71.5 | work/TASK-071/qa/conf-sweep.tsv saved; chosen floor/margin cited in the pdf.py constant comment |
| all | `python3 -I -m unittest discover -s tests/unit` -> failures equal the baseline list |
Report per family with Wilson intervals; n = 30 per family: a direction, not a rate.

## Decisions (recommended; main to confirm)
- D1 Confidence source: tesseract CLI TSV on the bridge's pixels (~+25% OCR time). Rejected: page mean (weak, diagnosis :69); switching OCR text to the CLI (phase-51 D1, ordering rebuild); a second engine (none in stdlib).
- D2 Threshold: sweep-chosen under a 0-false-alarm constraint on A-D, named constant + per-language data override. Rejected: fixed 70/80 from phase-51 D2 (one family, 9 wrong words).
- D3 low_conf/token hard (same gate as phase 51, decline is safe); option_parity soft (evidence is structural, wider false-alarm risk).
- D4 AI fallback: none built, stays off; the marker names the question, operator path = existing `--refined` route or review pack. Paid checks: none.
- D5 `ocr_conf` default "auto" only if the 71.5 adoption gate passes, else "off".
- D-1 (main, pick ONE): (a) defer refined-route surfacing (phase-51 G4) (recommended: the user named unmarked errors on the segmented route); (b) store per-page low tokens and add needs_review_why `ocr_doubt` in refine (refine.py:49-55, new page key).

- D-coordinator-1 (answers D-1) option (a): defer the refined route (phase-51 G4); the user's problem is unmarked errors on the segmented route.
- D-coordinator-2 71.5 is the gate: `low_conf` ships off by default unless the offline sweep lowers unmarked errors on family B or C with 0 false alarms; 71.3 and 71.4 are judged on the same sweep.
## Out of scope
Correcting misreads; skew/multi-column/real scans; family C diacritic loss beyond flagging; fetching tessdata; AI or paid checks; refined route (D-1a).

## Defects
- D-71-1 minor, tests/unit/ocr_before_after.py:63-69: "before" arm patches `_ocr_doubt` to a no-op; for TASK-071 the baseline arm must keep 51 kinds and disable only the new ones, else the delta is not the TASK-071 effect.
- D-71-2 minor, report phase-51 :11: false-alarm pool is 13 correct questions (upper bounds 0.30/0.49); a new hard signal needs the larger pool (71.5 family D) before adoption.

Nova
