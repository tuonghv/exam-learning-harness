PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency

# Verify TASK-016 (REQ-0019) - Argus (verifier)

Evidence: work/TASK-016/evidence/unit.txt (rc 0 in header line 7; "Ran 387 tests ... OK" lines 19-21). Static + unit evidence only (Tier 0/1); no real call made (correct for AC6).

## Verdicts
- AC1 VERIFIED. image.py:138-169 reads bytes, sha256 (159), asset {path,mime,sha256,page,origin} (168), dims from header (155-158), format from magic (30-38). Original: only opened "rb" (142); copy via _store (131-135) writes `raw`; resize writes a separate a2 file (176). Tests: TestFormats test_png / test_jpeg_jpg_webp (test_ingest_image.py:94-103).
- AC2 VERIFIED. IngestError codes: empty (147), corrupt for not-image/truncated/unreadable (151,157), format_mismatch (153), unsupported ext falls to mismatch/corrupt. Image always becomes block b1 (181). Tests TestErrors 143-165, TestHeaderParse 228-257. Missing-asset: only the "missing_dependency" resize case is covered (185-192); no separate missing-asset-file test seen (minor, see D2).
- AC3 UNVERIFIED for real stream-json behaviour (limit: needs paid run); mock part VERIFIED. claude.py:53-73 builds base64 image blocks + text on one stdin JSON line, validates type/size/non-empty before any call (60-65), no paths sent; _run (76-79) keeps `--tools ""`, `--strict-mcp-config`, cwd passthrough, shell=False (82). Tests 307-364 show image block, argv, cwd, no key text (344-351), no call on invalid input (335-342). Flag issue: run_claude_images appends only `--input-format stream-json` and keeps `--output-format json` (claude.py:77,73). `claude --help` says stream-json input may require `--output-format stream-json` (and `--verbose`); the code neither handles nor flags this, and the result parser (90-104) expects a single JSON envelope, which stream-json output would not give. See D1. "Unsupported path is reported, not skipped": invalid image returns Call(ok=False, cls other) (61-70) - VERIFIED.
- AC4 VERIFIED (resize needs Pillow, lazy). image.py:160-180: > limit (default 5 MB, line 17) adds derived a2 (origin normalized, derived_from a1) plus warning image_resized (179); <= limit untouched. Without PIL: missing_dependency (171). Tests TestOversize 167-195, TestFiveMB 259-288 (exactly-limit not resized, 266). Real PIL resize quality is only as good as the unit test; no split into pieces (resize only), acceptable per design Q2.
- AC5 VERIFIED. image.py:183-190: ocr default "off"; on adds b2 paragraph origin extracted after b1; failure gives ocr_unavailable warning, image block kept. Tests 108-126. Real tesseract not run here (UNVERIFIED on a real install; tests use fakes).
- AC6 VERIFIED. Synthetic images in tests, no real call; 387 tests OK (unit.txt:19-21). claude is invoked only through the injected Rec runner (test:290-305).

## Defects
- D1 (medium, AC3): claude.py:73/77 passes `--input-format stream-json` with `--output-format json`. The CLI may require stream-json output (and `--verbose`) for stream-json input. Neither handled nor documented in docs/guide/ingest-usage.md or the design (no stream-json mention found there). Needs a paid/real smoke run (with the user's go) or a documented limit; if output must be stream-json, the parser at claude.py:90-104 must read the final `result` event.
- D2 (low): run_claude_images has no caller in src/ (grep: only its definition, claude.py:53). The requirement says "the solve step SHALL pass the image to claude -p"; the solver wiring is not done, only the adapter function. Confirm that is out of TASK-016 scope or record a follow-up.
- D3 (low): no unit test for the "missing asset" case named in AC2 (only missing PIL dependency).
