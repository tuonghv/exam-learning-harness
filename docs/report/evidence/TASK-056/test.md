PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency, crosscheck
## Checks (evidence in work/TASK-056/evidence/)
- recount-oracle: PASS 3 runs x 10 fields = 30 rows, 1 rounding-only diff (English cost_vs_log4dp 0.3417 vs 0.3418: sum of 4dp-rounded log costs vs exact result.json cost 0.341747; not a defect) -> recount.tsv, recount-oracle.txt. Oracle = jq/grep/awk on result.json + run.log (answered/declined/malformed/uncertain/fail/retry_rate/calls/cost/llm_s); Math 29 ans/1 decl, English 30/0, Science 28/2, fail 8, retry 2/3/11, calls 4 each, cost 0.31147/0.341747/0.402896 all match run-stats --json. Entry point is scripts/exam.py (not ./exam.py); history was a scratch file.
- compare-check: PASS compare-check.txt. 12-q keyed dirs (scratch): 3 flips -> regressed 1,2,3 "within noise" exit 0; 1 flip -> noise exit 0; 6 flips -> "signal (regressed)" exit 1; reverse -> fixed 1-6 "signal (improved)" exit 0; differing exam_sha256 -> "ERROR: different exam" exit 2; unknown ref -> exit 2. n and flips always printed.
- mutations (scratch copy /tmp/scratch-kit.F5tUj1): killed: answered denominator (n), key denominator, low_conf denominator, noise rule off, noise threshold 1*sqrt, mock appends history, compare sha check off, exit code 1 off. Survivors: (a) QA label "(proxy)" removed / QA line labelled "key" -> NEW tests added; now killed; (b) noise `F+R>=4` guard -> equivalent mutant (|F-R|>=2sqrt(F+R) already implies F+R>=4 for ints); (c) qa-fills-key mutation is ineffective (qa set after keyed list) -> equivalent. Note: same-size edits hit stale .pyc in scratch; use PYTHONDONTWRITEBYTECODE.
- mock block/report: PASS. Solve stdout prints `metrics:`, `accuracy: none`, `cost:` after the pass= line; report.md has `## Metrics` with the same 3 bullets; no `results/` created without --history; with --history 1 line appended.
- suite-full: 924 tests, failures=3 errors=1 = only known (lxml docx TestRealDocxTextBox, check_examples 12b, cwd_independence, scripts_exam check_examples_ok). suite-full.txt
## Tests added
- tests/unit/test_run_stats.py class ProxyLabelTest (3): qa-only line is exactly `accuracy: qa agree 1/2 (proxy)` and accuracy.key null; key + qa shown apart; QA never yields key accuracy. 14 tests in file pass; bite: killed M2a/M2b on scratch copy (2-3 fail each).
## Defects
none
