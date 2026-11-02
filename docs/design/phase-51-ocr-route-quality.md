# Phase 51 - OCR route quality

# Phase 51 - OCR route quality (draft for docs/design/phase-51-ocr-route-quality.md)
Task: TASK-051 · REQ-0054 AC1-AC4 · Status: draft · Evidence: work/TASK-051/handoff/diagnosis.md

## Premise (facts at HEAD 1ecb5ee)
- OCR text: pdf.py:337 `get_textpage_ocr` -> `_page_blocks(page, tp)` (:63-78, joins `dict` spans). The bridge drops spaces (glued 16/424 words vs CLI 0-1); `rawdict` char boxes + gap > 0.15 x median char height -> 2 glued (diagnosis :6, :64). One family, 2 pages: threshold not proven.
- Language: `pick_ocr_language` (:49) wants vie+eng; this host has eng only -> one `ocr_language_missing` warning (:332-335), 225/424 words wrong, 0 questions marked.
- Furniture: `_strip_furniture` (:162-190) key = `fold_digits` (:176) keeps spaces -> OCR header "thử- Môn" (p4) vs "thử-Môn" survives (7/8 removed on 4 pages).
- Gate: `refcheck.incomplete_reasons` (refcheck.py:106-131) reads q fields (e.g. `unreadable`) -> `marker` (:145) `[Incomplete: missing_text <r1>, <r2>]` written by api.py:274-275; engine.py:73 declines marked questions; api.py:224 `UNCERTAIN` -> sidecar `assembly_status uncertain`. extract_eval `_judge` (:265-271) calls the same `incomplete_by_question` on file records, so a new q field reaches `reasons` with no eval change.
- Segmented questions carry no line/page index (segment.py:155, :176); `segment_reviewed` (boundary.py:421) already passes `page_of`.
- AI fallback (REQ-0053) runs only when `config["boundary"]` is set (boundary.py:423): default off today; this design adds no AI call.

## Goal
OCR questions reach the solver with words spaced as printed and furniture removed; a question whose OCR text is doubtful carries `[Incomplete: missing_text ocr_doubt <kind>]`, is declined by the engine and listed `uncertain` in the sidecar. Known by: extract-eval on scanned F1 + 2 new families, before/after (51.7).

## Constraints
- Native (text-layer) route byte-identical: every change is gated on `method == "ocr"` except 51.3 (space-free key, a no-op on identical native headers).
- Text is never corrected beyond spacing; the doubt marker never removes text. Python stdlib; tesseract only through PyMuPDF (no new subprocess in the minimum set).
- Doc schema unchanged: new q field `ocr_doubt` (list of str) only when non-empty; `starts` index is internal.
- Cache: boundary AI cache key holds window text (boundary.py:300 `_key(w, sha)`), so respaced lines get new keys; no stale reuse.

## Known incidents
none found (docs/notes/incidents.md not present).

## Plan modes
- Native PDF: unaffected (gate on `method == "ocr"`); 51.3 key change is a no-op there.
- Scanned PDF, vie present: 51.1 + 51.3 + 51.4 apply.
- Scanned PDF, vie absent: 51.5 marks every OCR question; text still produced for review.
- Refined route (`use_refined`, AI refine): not affected; doubt does not propagate (Gap G4).
- `--boundary` AI hints on: unchanged contract, fed the respaced lines.

## Design
### 51.1 Char-box respacing (owner: pdf.py new `_ocr_blocks(page, tp, gap=OCR_GAP)`, used at :339)
- `page.get_text("rawdict", textpage=tp)`; per block/line, chars of all spans in order; emit a bridge space char as one space; insert a space before char c when `c.x0 - prev.x1 > gap * median_h(line)` (median of char bbox heights of that line). NFC, strip; returns the `_page_blocks` shape `[(bbox, text, fonts)]`.
- Fallback per line: no chars, or a char without `bbox` -> that line's span text (today's join). `OCR_GAP = 0.15` constant, set by 51.6.
### 51.2 Question start index (owner: segment.segment, boundary.segment_reviewed)
- New optional `starts=None` list: at the two `qs.append` sites (:155, :176) append `i`. Output dicts unchanged. `segment_reviewed(config, lines, page_of=None, starts=None)` passes it through.
### 51.3 Furniture key tolerant to OCR spacing (owner: pdf.py `_strip_furniture` :176)
- Key = `re.sub(r"\s+", "", fold_digits(ln))` (spaces around "-" and before digits no longer split a key). Page-number rule unchanged.
- Near-miss leak: an edge line (not content, not dropped) with `difflib.SequenceMatcher(None, key, k).ratio() >= 0.8` against a dropped key is kept in the text and returned as a leak index -> signal `furniture` (51.4). Return becomes `(pages, removed, leaks)`; leaks = set of (page, line index).
### 51.4 OCR doubt signals per question (owner: pdf.py new `_ocr_doubt(lines, page_idx, ocr_pages, leaks, lang_ok)` after :414)
- Question k spans flat lines `starts[k]..starts[k+1]-1` (last: to end); its pages = page of each line (from `page_lines` lengths). Only lines on OCR pages count.
- `glued`: a token with >= 2 vowel clusters that each carry a combining mark after NFD, split by a consonant (a Vietnamese syllable has one tone/vowel mark; e.g. "tửtửánh", "sốđơn"). Free, no wordlist.
- `chars`: a token holding a char outside Latin + Vietnamese letters, digits, ASCII punctuation, common math (`+-*/=<>()[]{}^_.,;:%'"`) and `≤≥≠±×÷√π°`; or `_suspect` flags on the page.
- `furniture`: a leak index from 51.3 falls in the question's lines.
- `lang_missing`: from 51.5.
- Set `q["ocr_doubt"] = sorted(kinds)` when any; pop nothing else.
### 51.5 Missing vie data (owner: pdf.py :332-335, refcheck)
- `lang_ok = "vie" in have` (not `len(have) < 2`: vie without eng is fine). When not lang_ok and a page used OCR: every question touching an OCR page gets `lang_missing`; warning `ocr_language_missing` becomes `level="error"` with message "vie.traineddata not found in <dirs>; every OCR question is marked ocr_doubt. Put vie.traineddata in one of: <tessdata_candidates>, or set TESSDATA_PREFIX / config tessdata".
- Needs user: file `vie.traineddata` (tesseract 4/5 LSTM, tessdata or tessdata_fast) placed at `/usr/share/tesseract-ocr/<ver>/tessdata/vie.traineddata` (or any dir via `$TESSDATA_PREFIX`); check with `tesseract --list-langs` (must list `vie`). Not fetched by us.
### 51.6 Gate wiring (owner: refcheck.incomplete_reasons :122, api.UNCERTAIN :224)
- `for k in q.get("ocr_doubt") or (): out.append("ocr_doubt " + k)` -> marker `[Incomplete: missing_text ocr_doubt glued, ocr_doubt lang_missing]`; add `"ocr_doubt"` to `UNCERTAIN`. Engine declines (engine.py:73), sidecar `uncertain`, ingest-inspect shows the reason. No AI fallback (REQ-0053 stays opt-in and boundary-only).
### 51.7 Calibration + measurement (owner: gold_pdf.render, tests; no engine flag)
- gold_pdf.render gains `size=SIZE` keyword + `gold-pdf --size N` (needed for the second family).
- Families (synthetic text only, scanned via `gold-pdf --scan`, 2 pages each): A = F1 DejaVuSans 11 (existing); B = F1 gold, second font (DejaVuSerif or LiberationSerif if present, else DejaVuSans Condensed) at size 9 and 13; C = new synthetic gold dense in short diacritic syllables ("tử", "ở", "đề", "kỳ", "ủy") + digits glued to words ("đề 101").
- Sweep `gap` in {0.10, 0.12, 0.15, 0.18, 0.20, 0.25} on A/B/C with vie+eng: glued and over-split (ocr_words - gold_words > 0) per family. Pick the value with 0 over-split on every family and min glued sum; if no single value has 0 over-split on all, switch to the per-line gap split (largest jump in sorted gaps, space if gap > split and > 0.08 h) and re-measure. Record the table in work/TASK-051/qa/.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| rawdict has no chars/bbox | line falls back to span text | today's text; 51.4 may mark `glued` |
| gap too small (over-split "tr ường") | caught by 51.7 over-split column before merge | eval row content=False |
| vie absent | all OCR questions `ocr_doubt lang_missing`, error warning | 0 OCR questions solved; install note |
| leaked header variant | kept, question marked `ocr_doubt furniture` | marker + sidecar uncertain |
| `glued` false positive (loanword with 2 marks) | question declined | false_alarm rate in 51.7 |
| English exam on eng-only host | marked lang_missing (false alarm) | see Decision D3 |

## Unit tests (tests first, tier 0, skipIf no fitz/tessdata for OCR ones; 2-page slices, one 4-page)
- 51.1 `_ocr_blocks` on a fake rawdict (no OCR): gaps 0.1h/0.3h -> join/space; bridge space kept once; missing bbox -> span text. OCR test on scanned F1 p1-2: glued <= 2 (vie) via the 51.4 glued counter.
- 51.2 `segment(lines, starts=s)` -> s == start line of each question, incl. a hint-started one; output equal to call without `starts`.
- 51.3 4-page slice with headers "thử-Môn" x3 + "thử- Môn" x1 -> removed 8/8; a header garbled beyond 0.8 on p4 -> kept + leak index; a numbered question line at page top never dropped.
- 51.4 tokens: "tửtửánh", "sốđơn" glued; "trường", "Nguyễn", "x2" not; "¢ó" chars; questions on native pages never get `ocr_doubt`.
- 51.5 have=["eng"] (fake candidates dir) -> every OCR question `lang_missing`, error-level warning text names the dirs; have=["vie"] -> none.
- 51.6 `incomplete_reasons({"ocr_doubt": ["glued"]})` -> ["ocr_doubt glued"]; `api.assembly` row uncertain; `engine.incomplete_ids` declines it.

## Verification (tier 0, no paid call; written before implementation)
| Item | command -> expected |
|---|---|
| 51.1 | `exam.py gold-pdf F1 a.pdf --furniture --scan` (2 pages) -> ingest -> extract-eval `--completeness`: content-equal-but-not-exact rows drop from before to <= 2 |
| 51.2 | unit suite PASS (`python3 -I -m unittest discover -s tests/unit`) |
| 51.3 | 4-page scanned F8 slice: `page_furniture_removed` 8 (was 7) |
| 51.4 | families A-C: incomplete_to_solver_content (real errors unmarked) after <= before, false_alarm reported |
| 51.5 | on this host (eng only): every OCR question marked, error warning present; with vie (scratch TESSDATA_PREFIX) none marked lang_missing |
| 51.6 | sidecar rows `uncertain` = marked count; engine dry-run declines them |
| 51.7 | sweep table saved; chosen gap 0 over-split on A, B(9,13), C |
Report: real-error rate (content=False / present) and share reaching the solver unmarked (incomplete_to_solver_content), before/after, per family, with Wilson intervals; n small (~25 q/family): a direction, not a rate.

## Decisions (recommended; main to confirm)
- D1 Respacing: chosen rawdict char gaps (51.1): 0 extra OCR cost, local change. Rejected: tesseract CLI TSV route (0-1 glued, 2 s vs 8 s, gives confidence) because it adds a subprocess path, needs the tesseract binary (the bridge needs only tessdata) and a TSV->block rebuild for ordering/tables; revisit if 51.7 cannot find a stable gap. Rejected psm/dpi/preserve_interword_spaces: no effect (diagnosis :59-61).
- D2 Doubt signal: chosen free text signals (glued, chars, furniture, lang_missing). Per-word confidence deferred: bridge exposes none; CLI TSV conf<70 caught 2 of 9 wrong words with vie (weak), and its strong case (eng only) is already covered by lang_missing. Add later as `ocr_doubt low_conf` (share of words conf < 80 > 5%) only if 51.7 shows real errors unmarked.
- D3 "vie needed": every OCR page needs vie (Vietnamese exam harness; pick_ocr_language already wants it). English-only scans on an eng-only host get false alarms; accepted (decline is safe). Alternative: skip when config `lang == "en"` reaches ingest (not wired today).
- D4 Furniture: space-free key + near-miss marking. Rejected: fuzzy drop (could delete a real stem line).
- D5 AI fallback for OCR spots: none in this phase (default off kept); REQ-0053 hints stay boundary-only.

## Gaps
- G1 Single-column, clean synthetic renders only; skew, JPEG noise, multi-column, rotated pages untested; 144 dpi scan zoom fixed.
- G2 vie measurements used a traineddata outside the repo; this host cannot reproduce vie rows without the user's file (51.5 needs user).
- G3 `chars` set and `glued` rule have no measured false-positive rate yet; 51.7 reports it.
- G4 Refined route (AI refine of OCR pages) does not carry `ocr_doubt`; separate item if wanted.
- G5 Metrics fold diacritics (diagnosis :84): eng-only CER understated; 51.7 must also report un-folded content equality.
- G6 Second font availability under /usr/share/fonts not checked (outside repo); main to `ls /usr/share/fonts/truetype`.

## Defects
- D-1 major, pdf.py:339-341 + :63-78: OCR text joined from `dict` spans; bridge-synthesised spacing glues words (16/424). Evidence diagnosis.md:6,62-64.
- D-2 major, pdf.py:332-335: missing vie only warns (level warning, once); 225/424 words wrong and no question marked. Also condition `len(have) < 2` fires when only eng is missing (harmless) and is the wrong test for vie. Evidence diagnosis.md:7,71.
- D-3 minor, pdf.py:176-177: furniture key keeps spaces, OCR header variant survives (7/8). Evidence diagnosis.md:78-79.
- D-4 major, gate: no OCR-specific reason in refcheck.incomplete_reasons (refcheck.py:106-131): 200/200 TASK-046 OCR questions reached the solver unmarked (REQ-0054).

## Out of scope
Paid/vision runs; skew/multi-column OCR; fetching language data; refined-route doubt; CLI TSV confidence (D2).

Nova

## Decisions (coordinator)
- Per-word confidence through the tesseract CLI TSV (D2) stays deferred; no AI fallback.
- vie.traineddata is a user input (needs user): put it in /usr/share/tesseract-ocr/<ver>/tessdata/ or $TESSDATA_PREFIX; the engine never fetches it. Without it every OCR question gets the hard ocr_doubt marker.
- OCR_GAP stays a named constant calibrated by the 51.7 sweep on at least 2 families before it is fixed.
