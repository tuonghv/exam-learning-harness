PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency
## Per-AC verdict (REQ-0052; design phase-48; tier 0, no paid run)
- AC1 VERIFIED: api.assembly src/exam_engine/ingest/api.py:227-253 (keys id, printed, source_pages, assembly_status, validation_status, reasons); sidecar cli.py:523-527 (`<exam-out>.assembly.json`, schema assembly/1, new file only, written after exam text :521); inspect table inspect.py:139-150; plan copy planrun.py:97,236-240,288. Tests test_assembly.py + test_assembly_qa.py (21 OK, evidence t48qa-new.txt); sidecar content/determinism/golden vs 63a5299 (exam text + doc.json byte-identical, only sidecar new) in handoff/test.md items 2,3,6 (tester-run, not re-run by me: no Bash).
- AC2 VERIFIED (dev channel): refine.md:15 rule 12; dev system.md:9; dev lang/vi/system.md:9 (`missing_text:`). Releases/config untouched per test.md item 7 (`git diff 63a5299 -- prompts/releases config` empty). Prompt channel tests in suite-final.txt: no new failures.
- AC3 VERIFIED: no schema/result.json change in diff scope (src list: api, cli, inspect, planrun); exam-format md writes no sidecar (cli.py:523-524); goldens identical (test.md item 2).
- AC4 VERIFIED: suite-final.txt `Ran 1094`, failures=3 errors=1 skipped=35 = the same 4 names as baseline-failures.txt and head-failures.txt (lxml docx, check_examples x2, cwd_independence/scripts_exam); no expectation edits outside new tests. Mutation run 5/5 killed (test.md item 8).
## Specific checks
- Sidecar new file only, exam text unchanged: VERIFIED (cli.py:521-527; golden test.md:22-24).
- Deterministic: VERIFIED (two runs byte-identical, test.md:28; no timestamps in the row/wrapper code).
- Text-path source_pages []: VERIFIED in code (api.py:242) and design docs (design Decisions); documented.
- Inspect Assembly table and plan copy (symlink not followed, planrun.py:239 `_plain_file`): VERIFIED.
- Prompt lines dev only, releases untouched: VERIFIED (test.md:41; default prompt_release stays v1.0.0, so default solves unchanged).
- Solve line cost: ~46 tokens en / ~48 vi (chars/4, test.md:42); design said ~30, REQ AC2 said ~25. UNDER-ESTIMATED, not a failure; update report numbers.
- Refine cache voided after refine.md edit: documented (code.md:11, design Decisions); the cache key includes the prompt hash (refine.py:277 per design). UNVERIFIED by run (no refine run); state it in the report.
- G3 accepted limit: VERIFIED by test.md:34 (metrics.py:144 counts only status_reason containing missing_text; solver declines with the new rule land in `declined`, not `declined_missing_text`; pinned by test_48_g3). Not read by me in metrics.py.
- G2 closed: ingest-inspect on real work/dgnl-real/v3/13-22.json rc 0 with table (test.md:31).
## Security pass (git diff 63a5299..HEAD -- src prompts, by reading the touched code)
- Sidecar path: `args.exam_out + ".assembly.json"` (cli.py:526) is the same user-supplied trust level as exam_out itself; no new path input; OSError -> exit 2 via the existing handler (:531). Writes follow a pre-existing symlink at that path, same as the exam-out write; low, accepted.
- Content leak: row fields are ids, printed numbers, ints and `reasons` from refcheck (fixed tokens plus a printed id/page, e.g. `referenced_part_missing X`, `orphan_on_page N`); no question or option text copied. `exam` = basename only (no absolute path).
- Plan copy: lexists + plain-file check refuses symlinks; copies a file already next to the exam; no traversal.
- Prompt lines: static text in dev prompts; no interpolation of exam content; no new injection surface. Refine rule 12 only restricts transcription.
## Open
- UNVERIFIED: re-run of the golden/mutation checks by me (no Bash; relying on tester evidence t48qa-*.txt and test.md). Suite files record head `62e281f+dirty`; re-run suite on committed HEAD before VERIFIED if main wants a clean head.
- t48qa-full.txt has unclosed-file ResourceWarnings from test_assembly_qa.py:188,190,200 (noise, not failures).
## Defects
- D1 (low, tests/unit/test_assembly_qa.py:188-200): files opened without close (ResourceWarning spam, ~40 lines in the suite log). Fix with `with open`.
- D2 (info): solve-line cost ~46 tokens vs 25-30 in REQ AC2/design; align the wording in report.
- I-G3 (info, accepted): see above; follow-up only if the user wants it counted.
