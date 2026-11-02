# Phase 56 - Solve-run metrics, history and compare
# Phase 56 - run metrics (draft for docs/design/phase-56-run-metrics.md)
Task: TASK-056 (REQ-0060, RAW-00170) · Status: draft
## Goal
After every solve run the user sees one metrics block (stdout + report.md), the run is one line in a history file,
and `exam.py run-stats compare A B` / `trend` shows what got better or worse per question, with engine commit,
prompt version, model and config beside it. No paid call anywhere in this feature.
## Constraints
- Pure read of result.json + run.log (+ optional exam file, key, review pack); result.json schema unchanged (v1).
- History holds answer letters of copyrighted exams + local paths -> git-ignored (`results/*` already ignored, .gitignore:1).
- No reply cache for solver/QA (phase-54/55 Constraints), so no cache key is touched.
- Tests and `engine.run` callers (benchmark.run_all) must not write the history: append only in `cli.solve_main`.
## Known incidents
none found for metrics/history.
## Facts from inspection (what exists)
- result.json: `run.{llm,model,max_attempts,timeout_s,max_cost_usd,cost_usd,calls,stopped,prompt{channel,version}}`
  (engine.py:115-119); per q `verification_status, status_reason, evidence_kind, attempts, uncertainty.level,
  qa_findings[{source,code}], score{points,max,basis}, answer` (engine.py:99-106); summary pass/fail/uncertain/unresolved.
- Reasons: `solver_declined[: missing_text (..)]`, `malformed_output` (solver.py:154-156), `reviewer_disagrees`,
  `reviewer_unsure`, `no_review`, `solver_uncertainty_not_low`, `no_independent_check`, `check_failed: <kind>`,
  `not_solved` (decision.py:23-38, engine.py:95). QA codes `review_failed/_malformed/_missing` (verifier.py:227-241),
  key code `differs_from_key` (scorer.py:118).
- run.log: one line per call `call N ok= cls= dur=Xs cost= prompt_bytes= answer_bytes=` (engine.py:45). No tokens anywhere
  (claude.Call has no usage field, claude.py:15).
- Not recorded: git commit, run time stamp, exam hash, wall time, first-attempt answer.
- Group kind (REQ-0058): `parser.groups(exam)` -> kind dependent|passage|independent (parser.py:279-301), needs the exam file.
- QA line: review pack `QA: <L> conf <c> | <verdict>` per printed n; `review.qa_verdict`, `value_letter`, `_parse_qaline`,
  `parse_subject` (review.py:176,169,188,227); printed n = id + offset (offset is a pack flag, not stored).
- Prior art: `benchmark.summarize/regression` (benchmark.py:77-127) = per-subject pass counts + "pass fell" only.
- Real data: work/dgnl-real/{run,run2,run3}-{Math,Science,English,Vietnamese}, run1. run3-Math: 30/30 UNCERTAIN
  `no_independent_check`, 4 calls, $0.31147 = sum of run.log costs. So pass-rate is flat 0 on DGNL: status metrics
  are health only; progress must be read from answer agreement (key or QA line).
## Design
### 56.1 Metric catalogue (owner: new `src/exam_engine/pipeline/metrics.py`, `compute(result, log_lines=None, exam=None, key=None, qa=None)`)
Denominator N = len(questions) unless stated. Kind: A accuracy, P proxy (not accuracy), H health, C cost.
| metric | formula | kind |
|---|---|---|
| answered | answer not None and reason not solver_declined*/malformed_output/not_solved | H |
| declined | status_reason startswith `solver_declined` (sub-count `missing_text`) | H |
| malformed | reason == malformed_output or any qa_findings code in {malformed_output, review_malformed} | H |
| not_solved | reason == not_solved (stop/cap) | H |
| pass / fail / uncertain | verification_status counts (= summary) | H |
| uncertain_by_reason | {status_reason prefix before ':' : n} | H |
| retry_rate | #(attempts > 1) / N | H |
| qa_disagree | #(reason == reviewer_disagrees) / answered | H |
| qa_unavailable | #(qa code in review_failed/missing) | H |
| low_conf | #(uncertainty.level != "low") / answered | H |
| key_correct | with key: #(score.points == score.max > 0) / #keyed; also points / max_points | A |
| qa_agree | with QA line: agrees / (agrees+differs); flawed, qa-only, unresolved, engine-nonletter listed apart | P |
| needs_review | review-pack flag count (refined needs_review) when a pack is given, else null | H |
| calls, cost_usd | result.run | C |
| llm_s, prompt_kb, answer_kb | sum of run.log dur / bytes; tokens = null (Gap G1) | C |
| wall_s | cli monotonic clock around engine.run (new runs only) | C |
| cost_per_answered | cost_usd / answered | C |
Breakdowns: `by_subject` (exam.subject), `by_group_kind` (dependent/passage/independent, only when exam is parsed),
`by_evidence` (code oracle/key match/Claude review only). Not valid accuracy claims: pass rate (PASS needs an independent
check; DGNL is 0 by design), qa_agree (same model family as engine, review.py:27 says so; agreement != correct),
answer change between runs without a reference, low uncertainty.
Output shape: `{"n":30,"counts":{...},"rates":{...},"accuracy":{"key":null|{..},"qa":null|{..}},"cost":{...},
"by_subject":{},"by_group_kind":{},"questions":[{"id","answer","status","reason","attempts","group_kind","key_ok","qa"}]}`.
### 56.2 History line (owner: `metrics.history_line(result, m, meta)`, `metrics.append(path, line)`)
One JSON object per line, `results/run-history.jsonl` (default; `--history FILE` overrides). Fields:
`v:1, run_id (out dir basename + ts), ts (UTC ISO), exam_id (exam path stem), exam_sha256 (of exam text, null if absent),
subject, git {commit, dirty}, prompt {channel, version}, model, llm, config {max_attempts, timeout_s, max_cost_usd, lang},
result_path, metrics (56.1 without by_* when null), source: "solve"|"backfill"`.
git via `git rev-parse HEAD` + `git status --porcelain -- src prompts config` (subprocess, cwd = repo root; null on error).
Append in `cli.solve_main` after engine.run only when `--real` or `--history` given (mock/test runs stay out).
### 56.3 Backfill (owner: `run-stats backfill DIR... [--exam F] [--history F]`)
For each DIR with result.json: compute from result.json + run.log, ts = result.json mtime, git = null, source=backfill;
skip when (result_path, exam_sha256) already in history (idempotent).
### 56.4 CLI `exam.py run-stats` (owner: `cli.run_stats_main`, add to COMMANDS cli.py:20 and table cli.py:924)
- `stats RESULT_DIR [--exam F] [--key F] [--review-pack F --offset K]` -> metrics block (56.5) + `--json`.
- `compare A B` (A/B = run_id from history or a result dir): refuses (exit 2) when exam_sha256 differ; warns when null.
  Prints side by side metrics with delta, then per question: `fixed` / `regressed` (wrong->right / right->wrong vs key,
  else vs QA letter, labelled `vs key` or `vs QA`), `changed` (answer differs, no reference), `status+`/`status-`
  (H only), `unchanged` count. Header lists what changed: commit, prompt version, model, config keys.
- `trend [--exam ID] [--subject S] [--last N]`: one row per run (ts, commit, prompt, model, n, answered, key/qa agreement, cost).
- Noise rule: per compare, F = fixed, R = regressed; signal only when `|F-R| >= 2*sqrt(F+R)` and `F+R >= 4`
  (sign test ~95%), else print `within noise (n=..., flips=...)`. Always print n and flips. Trend marks runs with same
  commit+prompt+model as repeats; their min..max is shown as the noise band.
Exit 0 ok, 1 regression signal, 2 usage/input error.
### 56.5 Metrics block placement (owner: `metrics.block(m)`, `reporter.build_markdown(result, metrics=None)`)
- stdout: 3 lines after the existing summary line (cli.py:113): `metrics: answered a/N declined d malformed m retry r%`,
  `accuracy: key k/K | qa agree x/y (proxy) | none`, `cost: calls c $x llm_s t`.
- report.md: `## Metrics` section after `- Points` (reporter.py:157), same text; engine.run passes metrics computed
  from result + log; `report` command (cli.py:180) reads run.log beside result.json if present.
### 56.6 Tests-first fixtures (owner: `tests/unit/test_metrics.py`, `tests/fixtures/metrics/`)
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| run.log missing | log metrics null | `llm_s -` |
| history line malformed | skip line, count | `WARN: history line N skipped` |
| compare across different exams | exit 2 | `ERROR: different exam (sha ...)` |
| QA pack ids do not map (offset wrong) | qa metrics null, unmatched count | `qa_unmatched N` |
| git unavailable | git null | `commit -` |
## Unit tests (fixtures: 3 hand-written result.json + run.log: mixed statuses, key-scored, stopped)
1. counts/rates equal hand counts per row of 56.1 (declined incl. missing_text, malformed, not_solved, retry).
2. key_correct only over keyed questions; null without key; qa_agree excludes flawed/qa-only/unresolved.
3. by_group_kind from a labelled fixture exam (dependent/passage/independent).
4. history_line has every 56.2 field; append is one line; backfill idempotent (run twice -> one line).
5. compare: fixed/regressed/changed classification vs key and vs QA; different sha -> exit 2.
6. noise rule boundaries: F=3,R=1 noise; F=6,R=0 signal; F=0,R=0 unchanged.
7. block text and report.md `## Metrics` present; mock `solve` without `--history` writes no history (tmp HOME/cwd).
8. legacy result.json (no qa, no pages) computes without error.
## Verification
| Item | command -> expected | tier |
|---|---|---|
| 56.1-56.6 unit | `python3 -I -m unittest discover -s tests/unit` -> OK | free |
| crosscheck | `run-stats stats work/dgnl-real/run3-Math --json` vs grep/awk recount: `"verification_status": "UNCERTAIN"` = 30, `"attempts": 2` count, run.log `cost=` sum = 0.3115, 4 call lines -> all equal (TSV mismatch list empty) | free |
| backfill | `run-stats backfill work/dgnl-real/run*-*/ --history $TMP/h.jsonl` -> 12 lines (+run1), rerun adds 0 | free |
| compare | `run-stats compare work/dgnl-real/run2-English work/dgnl-real/run3-English --history $TMP/h.jsonl` -> per-q list, `within noise` or signal with n | free |
| solve block | mock `solve ... --history $TMP/h.jsonl` -> 3 metric lines, report.md has `## Metrics`, h.jsonl +1 | free |
## Decisions (recommendations; user may override)
- New module `metrics.py` + `run-stats` command, reusing benchmark.basis, review.qa_verdict/value_letter/_parse_qaline,
  parser.groups - rejected: extend review-pack (writes human-marked files, merge logic; metrics would couple to marks)
  and extend benchmark (needs evals keys, runs the engine; its regression() is pass-count only). Benchmark may later call compute().
- JSONL - rejected sqlite: append-only, greppable, diff-able, crosscheck with jq/grep; volume is tens of runs.
- Ignored `results/run-history.jsonl` - rejected committed: answer letters of copyrighted exams + local paths; a
  committed trend summary (no answers) can be added later if the user asks.
- Smallest version first: 56.1 + 56.4 stats/compare on result dirs (no history) is usable alone; 56.2/56.3 next; 56.5 last.
## Out of scope
Token capture (G1), recording first-attempt answers (G2), any paid run, changes to result.json schema.
## Gaps
- G1: no token counts recorded anywhere; proposal (separate item, needs one real envelope check by main): parse `usage`
  from the claude -p JSON envelope in claude.py:114 into run.log `in_tok= out_tok=`. Until then bytes are the proxy.
- G2: "QA-flip" inside a run (answer changed by retry after QA) is not recoverable from result.json (only attempts and
  final answer). Metric offered: retry_rate + qa_disagree. Exact flip needs engine to keep `first_answer` (schema change).
- G3: old runs lack commit/time/exam hash; backfill sets git null, ts = mtime; exam.path in result.json is the relative
  path given at solve time (e3-Math.md), so `--exam` must be passed to get sha/group kind.
- G4: QA agreement for a run other than the one a pack was built from needs `--offset`, which the pack does not store.
- G5: no answer key for DGNL real runs -> only proxy (QA) accuracy is available there; say so in every block.
- Q for user (one-click): history committed or ignored? Recommend ignored (above).
## Defects
- D1 (low) cli.py:679: benchmark summary records prompt as `basename(prompt_root())` while solve records
  `prompts.prompt_info()` {channel, version} (engine.py:119): two formats for the same fact; history must use prompt_info.
- D2 (low) engine.py:115-119: result.json run block has no git commit or timestamp, so a result cannot be tied to the
  engine version that produced it (root cause of G3).

Nova

## Decision (coordinator)
History file is git-ignored (answer letters from copyrighted exams); only code, tests and fixtures are committed.
