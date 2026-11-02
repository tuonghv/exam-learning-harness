PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency, crosscheck

## Verdict: PASS (no production defect). 1 test-side gap added, 2 minor notes.

## (1) Design tests -> passing test
| Design | Test | Res |
|---|---|---|
| 51.1 fake rawdict gaps/bridge/missing bbox | test_ocr_respace.TestOcrBlocks (4) | PASS |
| 51.1 OCR family glued | TestOcrFamilies.test_glued_tokens_per_page (limit <=6/2 pages, design said <=2: loosened, B real glued 3/10q) , respacing_beats_bridge | PASS |
| 51.2 starts + output equal | test_ocr_doubt.TestSegmentStarts | PASS; hint-started question NOT covered (gap) |
| 51.3 8/8 removed, leak kept+index, numbered line kept | TestFurnitureKey (4) | PASS |
| 51.4 tokens, chars, native untouched | TestTokens, TestOcrDoubt (3) | PASS |
| 51.5 have=eng / vie | test_ocr_lang_missing (5) | PASS |
| 51.6 reason/marker/UNCERTAIN | TestGate (2) | PASS |
| 51.6 sidecar uncertain + engine.incomplete_ids declines (was only UNCERTAIN-membership) | NEW tests/unit/test_ocr_qa.py (2 e2e) | PASS |
Evidence: ocr tests 27+3 pass (~84 s).

## (2) Independent recount (own script, own render+scoring; `scratchpad/recount.py`)
- Evidence: work/TASK-051/evidence/qa-recount.tsv, mismatch TSV qa-recount-mismatch.tsv.
- real_error, wrong_unmarked, false_alarm and Wilson intervals: all 18 cells identical to ocr-before-after.tsv (A 10/10->1/10, B 10/10->6/10 | 4/10, C 10/10->10/10 | 4/10; false alarm A 0/9, B 0/4).
- Only mismatch: glued family C 173->171 (before), 170->168 (after): my alignment differs by 2; A/B glued equal (50/0, 50/3). Immaterial.
- Wilson formula recomputed independently: matches.

## (3) Golden vs 4865a2c (git archive, own script)
- 25 markdown inputs: byte-identical ingest output.
- 2 PDFs (examples/dgnl/De-thi-minh-hoa-2026-Final.pdf, input/exam/math/math_12_graduation_2026_001.pdf): both contain OCR pages (warnings missing_text; method reports "pdf"). Whitespace-sensitive hash differs (inserted spaces only); whitespace-insensitive whole-document compare (ignoring `chars`) IDENTICAL for both; warnings, questions identical.
- GAP: no purely native-text PDF or docx is tracked in the repo, so "native byte-identical" is only covered by native pages inside those two files (unchanged by page-level diff) and by the md set.

## (4) ocr_doubt
- Marker/sidecar/engine: verified e2e (test_ocr_qa). Real vie host: no lang_missing, no ocr_language_missing warning; markers real: B glued 2, C glued 6.
- False alarm on correct questions: A 0/9 (upper 0.30), B 0/4 (upper 0.49); n tiny, a direction only.
- Honest: Family B 4 unmarked errors reach the solver. Diffs: B1 "ơ"->"o", B7 "á"->"a" (dropped diacritic, valid word), B4 "6"->"ó" (digit read as letter), B5 "6"->"ó" x2 plus "Số"->"$6" (3 edits, not single-char). A9 also "ơ"->"o" (the 1 unmarked in A). Not 4 strictly single-char: 3 + 1 multi.
- Cheap extra signals (not implemented): (a) option-parity: in a question whose sibling options all contain a digit, an option with none (B4/B5 pattern; also "$" inside a letter token flags B5) - free, token-level; (b) tesseract word confidence (image_to_data conf < ~60) per question is the only thing that sees dropped diacritics (B1/B7/A9); costs a second tesseract call or TSV output, unmeasured. Diacritic drops forming valid words ("hon") are otherwise undetectable without a wordlist.

## (5) 51.5
- Fake [eng]: run completes, every OCR question lang_missing, warning level error with vie.traineddata / TESSDATA_PREFIX / install note; [vie] and [vie,eng]: no lang_missing (tests + real host).

## (6) Furniture
- TestFurnitureKey: 4-page slice with 4 spacing/case variants removes 8/8, no leak; garbled p4 header kept + leak (3,0) -> marked; far-garbled not leaked; numbered top line kept. PASS.

## (7) Mutations (scratch copy /tmp/scratch-kit.r7R0tg; ocr suites)
| Mutation | Killed by |
|---|---|
| OCR_GAP 0.40 | test_glued_tokens_per_page (+ NEW test_51_1_ocr_gap_pinned) |
| furniture key keeps spaces | test_spacing_and_case_variants_removed |
| refcheck ocr_doubt line deleted | 4 failures (incl. test_ocr_qa e2e) |
| lang_missing kind removed | 4 (test_lang_missing, test_vie_absent..., 2 test_ocr_qa) |
All 4 killed. Note gap-0.40 original kill relies on real OCR (skipped without tesseract+vie); the new pin test is host-independent.

## (8) Full suite (evidence work/TASK-051/evidence/task051-full-suite.txt)
- 1118 run, failures=3, errors=1, skipped=34, expected=2. FAIL/ERROR names equal baseline-failures.txt (check_examples x2, cwd_independence, docx textbox error, examples/dgnl pairing). No new failures. (Run started before test_ocr_qa.py existed; that file separately 3/3 OK.)

## Files
- tests/unit/test_ocr_qa.py (new, 3 tests)

## Defects
- none in production code.
- N1 (low) test: 51.1 OCR glued limit loosened from design's <=2 to <=6 per 2 pages (test_ocr_respace.py:71).
- N2 (low) test gap: 51.2 hint-started question start index untested.
