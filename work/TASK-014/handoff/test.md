PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency
Edited: tests/unit/test_ingest_inspect.py only (+10 tests, class ExtraUnit: vi/en/no-diacritic headings, first-3-blocks rule, key-to-end, page-spec errors, out-of-range/non-contiguous select, assets/warnings filter, guard + allow flag, report sections, stray threshold, markdown no parts + CLI on file/missing json).
Run: full suite 323 OK (was 313); file 22 tests OK (fitz present).
Mutations (src temporarily edited, restored byte-identical, cmp OK): find_parts never key -> 9 failures; select_pages range check removed -> 4; parse_pages lo/hi check removed -> 3.
## Defects
none
