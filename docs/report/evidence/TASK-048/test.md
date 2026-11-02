PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency, crosscheck
## Commands / results
- new suites: `unittest discover -s tests/unit -p 'test_assembly*.py'` -> 21 OK (10 coder + 11 new in tests/unit/test_assembly_qa.py); evidence work/TASK-048/evidence/t48qa-new.txt
- full suite: 1094 run, FAIL 3 + ERROR 1, skipped 35; FAIL/ERROR names identical to the TASK-058 baseline-failures list (lxml docx, check_examples x2, cwd_independence, scripts_exam); evidence work/TASK-048/evidence/t48qa-full.txt
- (the TASK-058 evidence file could not be opened by me: guard B1 binds me to TASK-048; compared against the names in the brief and the earlier read)

## (1) Design test -> test map
| design | test | status |
|---|---|---|
| 1 | test_assembly.AssemblyTest.test_refined_rows | PASS |
| 2 | AssemblyTest.test_uncertain_and_failed | PASS |
| 3 | AssemblyTest.test_failed_iff_marker_in_exam_text | PASS |
| 4 golden | MISSING in coder tests; added test_assembly_qa.Golden.* (git archive 63a5299) | PASS |
| 5 | WriterTest.test_sidecar_written... + SidecarContent.* | PASS |
| 6 | InspectTest.test_table_per_question_and_omitted | PASS |
| 7 | PlanCopyTest (helper, import_dir); PlanWriter.start MISSING; added PlanStart.* | PASS |
| 8 | MISSING; added Prompts.* (dev lines, releases untouched) | PASS |
| 9 | full suite, only known failures | PASS |

## (2) Golden vs 63a5299
- exam-format md examples (all examples/*/input-001.md): doc.json + exam text byte-identical, no sidecar.
- generated 2-page text-path PDF (fitz): doc.json + exam text byte-identical; only new file is e.md.assembly.json.
- `--refined work/dgnl-real/v3/13-22.json` on the dgnl PDF: doc.json + exam text byte-identical; only new file is the sidecar.
- Gap: the real PDFs under examples/dgnl and input/exam/math do not segment on the text path (no_questions) at either commit; covered by the refined run.

## (3) Sidecar content (2-page refined fixture via CLI)
- q1 printed 1, source_pages [1,2], complete/passed; q2 [2] complete/passed; q3 [2] uncertain/failed ["cut_unresolved"]; q4 [2] uncertain/failed (orphan_on_page). Text path: source_pages []. Two runs byte-identical. All PASS.

## (4) G2
- ingest-inspect on real work/dgnl-real/v3/13-22.json (full doc with `refined`): rc 0, `## Assembly` table printed, one row per question (e.g. `| 1 | 49 | 13 | complete | passed | - |`). Closed (code.md said unchecked). Test RealShaped.test_48_g2 (skips if file absent).

## (5) G3
- `declined_missing_text` (metrics.py:144) counts only status_reason containing `missing_text` (gate marker / visual flags: engine.py:182,227,283). A solver decline from the new system.md rule has status_reason plain `solver_declined`; the `missing_text:` text lands in qa_findings (solver.py:176). Counted in `declined`, NOT in `declined_missing_text`. Pinned by test_48_g3. No engine change in scope; see I-G3.

## (6) Plan copy
- PlanWriter.start and import_dir copy `<exam>.assembly.json` to input/assembly.json; absent -> none; symlinked sidecar not followed. PASS.

## (7) Prompts
- Lines present: prompts/dev/system.md, dev/lang/vi/system.md (`missing_text:`), dev/ingest/refine.md rule 12.
- `git diff 63a5299 -- prompts/releases config` empty; no release file holds the new line; default prompt_release stays v1.0.0 so default solves are unchanged.
- Added chars (chars/4): system.md en 184 -> ~46 tokens per solve call; vi 192 -> ~48; refine.md 107 -> ~27 per refine call. Design estimated ~30 (en): real is ~46.

## (8) Mutations (scratch copy /tmp/scratch-kit.tpZJSD, test_assembly*.py)
| mutation | killed by |
|---|---|
| source_pages dropped | 3 tests |
| assembly_status always complete | 3 tests |
| sidecar overwrites exam text path | 3 tests (incl. never_replaces_exam_text) |
| plan copy off | 3 tests (incl. PlanStart.start) |
| plan copy follows symlink (extra) | PlanStart.symlink |
No survivors.

## Defects
- I-G3 (info, metrics.py:144 / solver.py:176): declines from the new `missing_text:` rule are not in `declined_missing_text`, only in `declined`. Decide: leave or follow-up.
- I-T1 (low, tests): design tests 4, 7 (PlanWriter.start) and 8 had no test in test_assembly.py; now covered in test_assembly_qa.py.
- I-C1 (info, cli.py:523): md detection `text != doc["source"].get("text")` is a heuristic; correct for exam-format md (no sidecar) and non-exam md (no questions, no rows).
- I-P1 (info): solve-line cost ~46 tokens (en) vs ~30 in design.
FILES: tests/unit/test_assembly_qa.py (new)
