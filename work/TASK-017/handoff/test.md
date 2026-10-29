PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency
Edited: tests/unit/test_ingest_refine.py (+13 tests: TestRenderPage x5 with a synthetic FakeFitz since pymupdf is not installed, TestPromptFile, TestEdges x6).
Cmd: python3 -I -m unittest discover -s tests/unit -> 423 tests OK; suite file 36 tests OK.
Mutations (src restored, cmp identical): MAX_ATTEMPTS=1 -> 2 fail+2 err; drop similarity flag -> 3 fail; drop size cap in render_page -> 1 err. All bite.
Covered: modes gate, exit 0/1/2/3, key guard, call count, retry, forbidden fields, ids, option count, threshold, source hash, dry-run, render_page, real unreachable (run_claude_images patched), prompt has no answers.
## Defects
None found.
