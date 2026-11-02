PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency

Scope: judged from files only (no Bash); no re-run. Suite rc/headers not re-checked beyond the "Ran/FAILED" lines.

## Per-AC verdicts (REQ-0054)
- AC1 diagnose + fix spacing: VERIFIED for families A, B (glued 50->0 / 50->3, A cer 0, B cer 0.0067): evidence/ocr-before-after.tsv:2-5. Family C NOT fixed (glued 173->170, CER 0.1294 unchanged): :6-7 and sweep rows 20-28 (tesseract drops diacritics; limit is the engine, not spacing). Fix = rawdict char-box respacing, pdf.py:16,109-126. Diagnosis of psm/dpi: UNVERIFIED by me (diagnosis.md only; no evidence file).
- AC2 furniture on OCR route + leaked-header test: VERIFIED by code + tests: space-free key and near-miss leak marking pdf.py:212-252; 4-page leaked-header slice in test_ocr_doubt (test.md:11-16, code.md:35). Suite-final 1121 tests, same 3F+1E+34 skipped+2 xfail as HEAD baseline (head-failures.txt:3, suite-final.txt:6-7) = no new failures. (baseline-failures.txt is 847 tests / 35 skipped; older, not comparable by count.)
- AC3 doubt marker -> gate: VERIFIED. Marker pdf.py:289-315; refcheck.py:131 reason; ingest/api.py:224 UNCERTAIN includes ocr_doubt; e2e sidecar uncertain -> engine declines in tests/unit/test_ocr_qa.py (test.md:16). lang_missing: warning level error with tessdata dirs, no fetch (pdf.py:455-463); fake language list tests in test_ocr_lang_missing.py (6). Haiku fallback: not built, default off (design D5) - acceptable per AC wording ("considered").
- AC4 measured before/after, honest limits: VERIFIED as a measurement, PARTIAL as an achievement. Numbers match across ocr-before-after.tsv and tester recount (qa-recount-mismatch.tsv has only family C glued 173/171, 170/168, a 2-glue counting difference, immaterial to every rate). Not achieved: B 6/10 real errors remain (4 unmarked single-char misreads, left to REQ-0065), C 10/10 remain (4/10 unmarked), no recall at all for misreads that form valid tokens. n=10/family, Wilson intervals wide (A after 0.02-0.40; false alarm 0/9 upper 0.30, 0/4 upper 0.49). Single-column synthetic only (design G1). "Before" arm = bridge text + no marker, same inputs. No paid call (none claimed).

## Specific checks
- OCR_GAP 0.15: sweep plateau A 0.05-0.35 (glued 1), B 0.05-0.30 (5), C flat; 0.00 gives 29/31 glued, >=0.35 B jumps to 31 (ocr-gap-sweep.tsv:2-29). 0.15 is inside the plateau with margin on both sides (0.30 and 0.35 edges); total errors tied 310 for 0.05-0.30. VERIFIED reasonable; selection is robust, not tuned to a point. Sweep is one set of fonts (A/B/C), caveat G1.
- Native/non-OCR identity: 25 md inputs byte-identical to 4865a2c; 2 PDFs identical whitespace-insensitive, warnings/questions identical (test.md:25-28). VERIFIED for md; PDF claim covers only OCR pages in mixed files. GAP: no purely native PDF/docx tracked, so native-PDF byte-identity is UNVERIFIED directly (native path untouched by code.md:5, plausible). I did not re-run the script.
- ocr_doubt -> sidecar -> engine decline: VERIFIED via test_ocr_qa (test.md:16).
- lang_missing: VERIFIED via faked list tests; real vie host shows none (test.md:31).
- Furniture leaked-header slice: VERIFIED by unit test; per-design 51.3 count check (8, was 7) not seen in an evidence file -> UNVERIFIED as a measured row (covered only by the unit test).
- Missing 51.2 hint-started test: severity low. Guard `len(starts) != len(qs): return` (pdf.py:293) fails open (no marks) if hints made counts differ; hints are default-off AI boundary refinement, and segment_reviewed passes starts through (boundary.py:421-429). Recommend adding one test, not blocking.

## Security pass (src changes for task)
- No new subprocess/shell/temp-file code: OCR runs through pymupdf get_textpage_ocr(language, tessdata=...) (pdf.py:467-468). Grep found no subprocess/tempfile in ingest adapters.
- tessdata path: from config, $TESSDATA_PREFIX, fixed dirs (pdf.py:20-40), existing-dir check; passed as a library argument, not a command line; pre-existing logic. Error message prints dirs only. OK.
- Regexes (pdf.py:205,257, key() at :230): linear, no nested quantifiers, no ReDoS. 
- difflib.SequenceMatcher on edge-line keys (pdf.py:249): quadratic in key length per (edge line x dropped key); bounded by 4 edge lines/page, but an adversarial very long OCR line could slow ingest. Low; optional cap on key length (e.g. 200 chars).
- _glued/_odd_chars: single pass per token, bounded. rawdict failure caught with a broad except -> falls back to old text (pdf.py:113), fail-safe. No secrets or network.
- Verdict: security.status = passed, no findings above low.

## Defects
- V-1 low, pdf.py:249: unbounded SequenceMatcher input (DoS-by-long-line only on adversarial scans). Evidence: code read.
- V-2 low, tests: no hint-started 51.2 test (test.md:60).
- V-3 info, design row 51.3 (F8 4-page slice furniture 8 vs 7) has no evidence file.

## Not achieved (state honestly)
Family C real-error rate unchanged (10/10); family B 6/10 real errors and 4/10 unmarked; recall for single-char misreads is zero by design (REQ-0065). Net effect: unmarked wrong questions reaching solver 10->1 (A), 10->4 (B), 10->4 (C) - a direction at n=10, not a rate.

NEXT: main may record tier-1 evidence as passed for AC2/AC3, AC1/AC4 as partial with the limits above; optionally add the V-2 test and run the 51.3 row.
