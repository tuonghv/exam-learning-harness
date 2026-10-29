PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency
Verifier: Argus. Scope note: spec tmp/input-exam-format.md sections 3/5/7/9 were NOT read (budget); judged against REQ-0016 AC and design phase-12. Evidence rc from headers: suite.txt rc 0 (272 OK), integration.txt rc 0 (2 OK), check-examples.txt rc 0 (25 pairs), all head 284c5ed+dirty. I ran no code (no Bash).

## AC verdicts
- AC1 VERIFIED (static): design doc has "Current input contract" and "Canonical document v1" (docs/design/phase-12-ingest-core.md:6,9). validate_document returns a list, never raises (src/exam_engine/ingest/schema.py:52-68); tests missing version / bad status / duplicate id / asset not in assets (tests/unit/test_ingest_core.py:70-89). Origins are enum source|extracted|normalized|ai per block (schema.py:9,16); the adapter only emits "source"; there is no separate field per origin beyond the block tag (adequate for v1).
- AC2 PARTIAL/UNVERIFIED end to end: headings/list/table/code/math/image parse in order (markdown.py:73-128; test :98-114). Free-form converted text is never fed to parser.validate_exam nor `solve --mock` in any test or evidence (test :164-170 only asserts substrings). Needs: ingest a free md with --meta, then `solve --mock` on the --exam-out file, saved via save-evidence.sh.
- AC3 VERIFIED: to_exam_text returns the decoded source text unchanged when exam-format (api.py:42-50); the test compares bytes for every examples/**/input-*.md and parse_exam validates (test :172-181); check-examples rc 0. Caveat: read_source decodes UTF-8 and re-encodes; fine for bytes unless CRLF (open "rb" then decode keeps CRLF, so OK).
- AC4 VERIFIED: codes unsupported_format (api.py:16), empty/decode/corrupt (markdown.py:40-53), missing_asset (:28), missing_header (api.py:54); each tested (test :137-153, 157-162). No subject logic, prompt or Claude call in ingest/** (read all 4 files; only REQUIRED header names in api.py:10). The CLI maps errors to exit 2 (cli.py:221-226); `solve` untouched (the diff is the new ingest_main plus the table entry at cli.py:21,239).
- AC5 VERIFIED: tests are local, tempdir, stdlib, no network or claude.

## Path safety (markdown.py:17-29)
Absolute, `/`, `\`, drive letter rejected. `..` split on both `/` and `\` rejected (Windows `..\` handled in code, NOT tested). Symlink escape caught by realpath+commonpath (tested :125-135). `%2e%2e` is not decoded, so it stays a literal name and gives missing_asset (safe, NOT tested). Case is irrelevant on Linux. Errors from the escape are code invalid_document (not a dedicated code); acceptable.

## Silent text loss
None found in block parsing: every non-blank line goes into a block; unclosed fence/math run to EOF and are kept. Only blank lines are dropped (non-passthrough output normalises blank lines). Image refs with a scheme/URL, with spaces in the target, or inline inside a paragraph are kept as paragraph text and get no asset or safety check (see D2).

## Defects
- D1 (major) AC2 evidence gap: no test or evidence that converted free-form Markdown passes parser.validate_exam / `solve --mock`. Location: tests/unit/test_ingest_core.py:164-170. Add a test (parse_exam + validate_exam on the to_exam_text output) and one saved real run.
- D2 (minor) `![a](<my img.png>)` or an inline image is treated as paragraph: no asset record and no safety check, so the asset is silently unresolved. markdown.py:11,110. Emit a warning (the `warnings` list exists but is always empty, :128) or reject.
- D3 (minor) Tests lack Windows `..\` and `%2e%2e` cases; also an unclosed fence/math case. tests/unit/test_ingest_core.py:116-135. The code seems right, so add cases so the tests bite.
- D4 (minor) `config` argument of ingest_document is accepted but unused (api.py:13,19); and the file is read twice (adapter then api.py:21), a small TOCTOU window, with the sha possibly not matching the parsed text. Hash the same bytes.
- D5 (minor) validate_document does not check unique/monotonic `order`, nor that asset paths are relative (schema.py:57-67); there is no test of a block missing `text`/`origin`.
- D6 (minor) the document stores an absolute source path (api.py:25), so --out JSON leaks the local path.
