PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency
# TASK-015 tester (Nemesis)
Added 9 tests to tests/unit/test_ingest_docx.py (13 -> 22; test_ingest_spec.py unchanged, its 10 cases cover the spec list): vertical merge + rows, table-with-image warning, auto-numbered (numPr) list, footer warning, no-warning baseline, no assets dir created without --assets, source file unchanged, CLI `ingest x.docx --exam-out`, CLI bad file exit 2.
Run: `python3 -I -m unittest discover -s tests/unit` -> 356 OK (347 + 9).
Mutations (each restored, cmp-verified): table block skipped -> 3 fail; merged-cell dedupe off -> 2 fail; asset sha wrong -> 1 fail; image bytes truncated -> 1 fail; "image in table" warning removed -> 1 fail.
Probed already covered: non-zip, zip w/o package, zero bytes, blank doc, OLE (encrypted), NFC, header, math, key/parts guard.
## Defects
None found.
