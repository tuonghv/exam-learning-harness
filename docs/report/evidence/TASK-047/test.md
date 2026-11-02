PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency, crosscheck (mutation scratch copy)

## Commands / evidence
- full suite: work/TASK-047/evidence/t47-suite2.txt -> Ran 1072, failures=3 errors=1 skipped=35 xfail=2; FAIL/ERROR names identical to work/TASK-058/evidence/baseline-failures.txt (lxml docx, check_examples x2 incl dgnl pairing, cwd_independence, scripts_exam). t47-suite.txt = before my tests (1062).
- new tests (mine): tests/unit/test_refine_window.py class TestQaGaps (9 tests), tests/unit/test_window_golden.py (1 test, ~35 s).

## 1. Design unit tests -> test (all pass; none unmapped)
1 test1_stem_split | 2 test2_options_on_next_page | 3 test3_figure_on_next_page | 4 test4_three_pages_then_bridge | 5 test5_no_cut_unchanged | 6 test6_failed_window_falls_back_to_bridge | 7 test7_duplicate_guard | 8 test8_missing_open_id_falls_back | 9 test9_scanned | 10 TestDetector (test_s1.., test_s2_s3_prose, test_s4_image, test_complete_boundary_and_s2_alone; "never removes a page" not asserted explicitly, see gaps) | 11 test11_cache, test11_template_change_misses, test11_mock_never_reads_disk | 12 test12_trace_rows | 13 test13_* (6) | 14 test14_old_refined_unchanged | 15 test15_cost_cap_before_window (+ test_cost_cap_before_fallback_call)

## 2. Cost cap (D2)
- cap check is in refine.ask, before every call (pages, windows, fallbacks, backward re-run).
- added: test_cap_hit_mid_backward_recovery, test_cap_checked_before_every_call_in_run, test_cap_equal_to_spend_stops. Recovery caps: test13_run_cap_four, test_chain_cap_two_extra_pages, test_chain_cap_alone_with_wider_window, test_backward_run_cap.

## 3. Bounded recovery
- test_cut_cycle_terminates (every page and window cut): calls <= 8+14, window len <= WINDOW_MAX. test13_owner_has_options_not_recovered passes.

## 4. Golden vs 2cc9808 (git archive src/config/schemas/prompts)
- test_window_golden: `ingest` of examples/dgnl PDF and input/exam/math PDF: identical except added info warnings `page_cut_suspect` (DGNL: 6+ boundaries, e.g. 2|3 S2+S3). Not byte-identical for DGNL: the detector fires there, so the "no cut" premise does not hold for that file (see D1). Files with no detected cut are asserted byte-identical.

## 5. Cache/trace
- key = model + prompt sha + png shas (refine._ask). Tests: second run 0 calls, template change miss, other model miss, corrupt cache file = miss, trace rows page/pages/png_sha256/cached (hit rows too).

## 6. Oracle
- test_completeness_measure_pdf.test_window_oracle_whole_questions_no_orphans passes (25 q, 0 orphans, cross_page = gold); fails (failures=1) with cut-test always false and with window disabled.

## 7. Mutations (scratch /tmp/scratch-kit.4vxqoa, test_refine_window.py)
cut test false: FAIL (1F+5E) | window disabled: FAIL (6F+16E) | cap only per page: FAIL (2) | key w/o prompt: FAIL (1) | key w/o model: FAIL (1) | recovery cap off: FAIL (1) | RUN_EXTRA off: FAIL (1) | WINDOW_MAX off: FAIL (2) | corrupt hit not miss: FAIL (30E) | cap `>` instead of `>=`: survived -> added test, now FAIL | CHAIN_EXTRA off: survived (equivalent while WINDOW_MAX=3) -> added test with WINDOW_MAX=6, now FAIL | backward cap off: survived -> added test, now FAIL | backward kind filter removed: survives, equivalent (owner_has_options owner is always inside `pages`, filtered anyway).

## 8. EST_CALL_USD = 0.08
- work/dgnl-real/v3/*.trace.json (2 files): 18 calls, total 0.650, mean 0.036, max single-page 0.045. Only single-page calls exist: no measured window cost.
- 0.08 = 2.2x mean, 1.8x max single page: safe for single pages and a 2-image window; a 3-image window is likely ~0.08-0.11 (unmeasured), so 0.08 is an estimate, not a bound. Dry-run line is advisory, hard cap is --max-cost-usd. Recommend keep 0.08 and measure on the real slice.

## Defects
- D1 (low) src/exam_engine/ingest/adapters/pdf.py `_cut_boundaries`: `ingest` output of the existing DGNL PDF gains 6+ info `page_cut_suspect` warnings vs 2cc9808 (diff 66 lines, warnings only). Brief expected byte-identical with no cut; accepted per design if detector hits are intentional. Golden test asserts "only these warnings".
## Gaps
- design test 10 "never removes a page" has no explicit assertion; real PDF/real call path untested (mock only); EST for windows unmeasured.
FILES: tests/unit/test_refine_window.py, tests/unit/test_window_golden.py (new)
