PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency
Task TASK-056 / REQ-0060, design docs/design/phase-56-run-metrics.md (56.1-56.6). Evidence dir E = docs/report/evidence/TASK-056/.

## Per-AC verdict
- AC1 (metrics + formulas): VERIFIED. Formulas match the design table (design:39-57) in src/exam_engine/pipeline/metrics.py:120-179. Per subject, group kind and evidence slices are at :175-176. Declined/uncertain/malformed/retry counts match an independent jq/awk recount: E/recount-oracle.txt:9-39 (3 DGNL runs, rc 0; E/recount.tsv). The one diff is English cost_vs_log4dp 0.3417 vs 0.3418, a 4-dp rounding artifact; cost_vs_result is exact (:27).
- AC2 (history append + backfill): VERIFIED for the code path. history_line :196-209 carries run id, ts, exam id, sha, git, prompt, model, config, metrics. cli.py:133-134 and :138-150 append. Backfill run on the real run3-Math: added 1, then added 0 skipped 1 (idempotent) (E/run-stats-backfill-stats.txt:9-14). Gap: git is "-" for backfilled lines.
- AC3 (compare + trend): VERIFIED. E/compare-check.txt:
  - 3 flips -> "within noise", exit 0 (:15)
  - 6 flips -> "signal (regressed)", exit 1 (:31)
  - reverse order -> fixed 1-6, "signal (improved)" (:37-39)
  - different exam sha -> exit 2 (:42)
  - unknown ref -> exit 2 (:45)
  - trend output at E/run-stats-backfill-stats.txt:14
- AC4 (metrics block in solve output and report, no paid call): VERIFIED on mock only. block() metrics.py:281-298 and cli.py:128-132 print it. reporter.py:173 adds `## Metrics` to report.md. test.md:7 records the mock-run output. All computation is local, with no LLM call.
- AC5 (tests first on fixtures + independent recount on a real DGNL run): VERIFIED. 14 tests in test_run_stats.py (3 ProxyLabelTest added), bite mutations in test.md:6 (survivors explained: two equivalent mutants, two killed by new tests). Recount on a real run: E/recount-oracle.txt, rc 0.
  - Caveat: the full suite E/suite-final.txt:1-7 shows 924 tests with 3 failures + 1 error. test.md:8 calls them known and unrelated (lxml docx, check_examples 12b, cwd_independence, check_examples_ok).
  - I did not re-run the suite and have no baseline for them. The suite-final header is missing or has a different head (the evidence head 8b5c3e0+dirty is not HEAD). Main should confirm with a baseline run at 7dd9b4e~8 before DONE.

## Specific checks
- Accuracy vs proxy never mixed: VERIFIED. QA agreement is a separate block (`accuracy.qa`, metrics.py:98-117) and is printed as "qa agree n/m (proxy)" (:289). `accuracy.key` is computed only from key or score points (:64-71, :158-166), and QA cannot fill it (qa is set after the keyed list). The mutation tests for this are in test.md:10.
- null not 0: VERIFIED. _rate returns None on a zero denominator (:38-39). Missing run.log gives llm_s/prompt_kb/answer_kb = None (:51-53). tokens, wall_s and needs_review default to None (:151, :169). block() prints "-" (:296-297). Note: tokens are always None, never recorded.
- Noise rule: VERIFIED. metrics.py:307-309 is `not (F+R>=4 and |F-R|>=2*sqrt(F+R))`, which matches the spec. 3 flips is noise, 6 flips is signal (compare-check.txt:15, :31). The F+R>=4 guard is redundant for integers (equivalent mutant, test.md:6).
- Mock runs not appended: VERIFIED. cli.py:133 appends only when `a.real or a.history`. No results/ dir was created without --history (test.md:7).
- History git-ignored: VERIFIED. .gitignore:1 `results/*`; DEFAULT_HISTORY = results/run-history.jsonl (cli.py:24). The path is relative to the cwd, so running from another dir creates results/ there.

## Security pass (src diff)
- No subprocess, eval, exec, shell= or os.system in metrics.py or the new cli code. The only subprocess is the existing reporter.py:139 git call: arg list, no shell, cwd=root.
- result.json, run.log and history are only parsed (json.loads / regex), never executed. The regexes are simple `\b%s=([\d.]+)`, with no ReDoS risk. Malformed history lines are skipped and counted (metrics.py:231-239).
- Paths:
  - --history and backfill DIR go through os.path.join / abspath. append() does makedirs on the history dir.
  - cli.py:970-981 takes a run_id's `result_path` from the history file and reads only `<dir>/result.json`. The history file is a local, trusted-by-operator file. A tampered history could point to any dir containing a result.json; this is read-only and low risk.
  - Backfill dedupes on (abs result.json, exam sha). A history write failure only warns, with no exit code change (cli.py:149-150).
- parser.parse_exam errors in backfill are caught and group kinds dropped (metrics.py:249-252). A broad except, justified in a comment.
- Verdict: no security finding.

## Gaps (honest)
- Tokens are not recorded in result.json, so the tokens field is null (design Gap G1); cost is the only spend measure.
- Backfilled runs have git = null (no commit known); their ts is the result.json mtime, not the run time.
- No paid or real-LLM run was done. The solve metrics block and history append are proven on mock only. The real path (--real appending a line, wall_s) is UNVERIFIED.
- Accuracy appears only when an answer key (--ans-key / score points) is given. Without one the real DGNL runs show "accuracy: none", and QA agreement is only a proxy.
- The recount oracle covers counts, cost and llm_s on 3 runs. It does not cover by_group_kind, by_evidence, qa_disagree, low_conf or the key-accuracy formulas; those are verified by unit tests and fixtures only.
- The suite has 4 failing/erroring tests (see AC5 caveat); baseline not confirmed.
- Minor: classify() metrics.py:325 uses `qa[...]["answer"] in "ABCD"`, so an empty string would also pass; load_qa gives "-" or a letter, so low risk.

## Defects
none (the suite baseline is an open check, not a content defect)
