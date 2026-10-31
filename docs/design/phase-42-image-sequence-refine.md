# Phase 42: picture sources in refine, image sequences and tiles (TASK-042; REQ-0046)
Design source: docs/design/phase-40-multipage-question-assembly.md item 40.3 plus the Coordinator decisions there. Reuse first: the refine loop, the continuation bridge (owner rule, duplicate guard, number guard, orphans) and the completeness gate from TASK-040/041 stay unchanged; only the page source is new.
- `image.ingest_sequence(paths) -> doc`: file k = page k in the given order; per-page name + sha256; source format `image_seq`; blocks per page via the existing `ingest` (OCR, shrink). Tiles of one tall image are an image sequence (tile overlap handled by the duplicate guard).
- `ingest-refine FILE [FILE...]` (cli.refine_main, `_refine_source` :325): accept images, no longer refuse them; render(page n) = bytes of file n shrunk by `_shrink`; a single image keeps working as page 1.
- Orphan warning names the previous FILE (page N-1) to add, same as PDF.
- Backward compatible: single-image ingest output and PDF refine unchanged; old doc.json load.
- Tier 0 tests with mock replies and tiny PNG fixtures: question spanning 2 and 3 images (stem / figure / options), tile overlap duplicate, orphan warning, no continuation unchanged, wrong file order guard (hash changed), one-image legacy.
- Real check (paid, user go and cost estimate first): a few page images only. Not in this task unless the user provides pictures.
- Skill exam-extraction already states the rule for pictures; update only if behaviour differs.
