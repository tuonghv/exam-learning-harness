PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency

## Run
- `python3 -I -m unittest discover -s tests/unit`: 387 tests OK (was 375; +12). test_ingest_image.py: 31 OK.
## Added (tests/unit/test_ingest_image.py only)
- TestHeaderParse: WEBP VP8/VP8L/VP8X (hand-built, no PIL), truncated WEBP/JPEG/PNG, JPEG baseline + progressive (SOF2), webp wrong extension.
- TestFiveMB: default 5MB constants, exactly 5MB not resized, 5MB+1 shrinks and keeps original, over limit without PIL -> missing_dependency.
- TestClaudeImages: no key text in argv/stdin, multiple images one JSON line in order, 5MB boundary to claude accepted.
## Mutations (src restored, git diff src empty)
- WEBP magic broken: FAIL (1 failure, 2 errors). VP8L branch broken: FAIL (1). 
- MAX_IMAGE_BYTES 5MB->6MB: FAIL (3). `>` -> `>=` limit: FAIL (1).
## Gaps
- OCR only via mocks; real PIL resize covered once (noise PNG). Stream-json with real CLI unverified (paid run).
## Defects
None.
