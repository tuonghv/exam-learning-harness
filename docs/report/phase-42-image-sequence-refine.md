# Report phase 42: picture sources in refine, image sequences and tiles (TASK-042; REQ-0046)

Verdict: adopted at tier 0. `ingest-refine FILE [FILE...]` now accepts page images: one image = one page in the given order (a tall image cut into tiles is a sequence), and a question spanning images is assembled whole by the same continuation bridge and completeness gate as PDF (REQ-0043); an incomplete one is declined with `missing_text`. The skill `exam-extraction` already states the rule for pictures.

## What changed
`image.ingest_sequence` and source format `image_seq` (per-file name and sha256); `_refine_source` checks every file's hash in order (a changed or reordered file is refused with a clear error); the refine loop and bridge are reused unchanged; single-image ingest and PDF refine are unchanged. Before this, image exams could not be re-extracted at all.

## Evidence (work/TASK-042/evidence)
`final_unit_suite.txt` 660 tests, only the 3 known failures, identical at base (641); `final_image_tests.txt` 19 tests OK; `compat-single-image-*.txt` and the PDF refine output identical to base; `scenarios.txt` 24 CLI scenarios on real tiny PNG/JPEG/WEBP sets with mock replies (spans over 2 and 3 images, overlapping tiles, orphan, wrong order, changed file, mixed formats, duplicate path, zero files, 200 files, odd paths) without crash or silent loss; 0 old assertion lines removed; no schema/solver/config change; four mutations caught (the tester added the owner-rule bypass test because only the TASK-040 tests caught it). Tester defect D1 (empty file hint on a first-file orphan) fixed by the coordinator with a test.

## Limits
No real picture was run: that needs pictures from the user and a go with a cost estimate (REQ-0046 AC4 moved to REQ-0040 AC3). Tiles with overlap rely on the duplicate guard measured only with synthetic overlaps. OCR for scanned pictures follows the existing image adapter.

User instructions honoured: RAW-00145, RAW-00133 (quality), RAW-00142 (short roles).
