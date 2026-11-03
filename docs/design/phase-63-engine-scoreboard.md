# Phase 63 - Engine scoreboard (TASK-063)
Task: TASK-063 · REQ-0069 (RAW-00188) · Status: designed · Extends: phase-56-run-metrics.md 56.1/56.4 (no rewrite)

## Goal
`exam.py run-stats board` shows, per exam kind, coverage next to quality and cost, with delta vs baseline/previous and a
verdict `better | same | regression | unmeasured`; a change that raises coverage while quality falls is flagged.
Known when: synthetic-run tests pass and a free board over existing history + work/dgnl-real prints `quality unmeasured` for DGNL.

## Constraints
- No AI call in board; reads history lines + the result.json each line points to (history keeps no per-question rows, metrics.py:219).
- Keys: board never reads a key file; key quality comes from `score{points,max}` that the scorer wrote into result.json
  (`_key_ok` fallback, metrics.py:68-71). Keys reach only the scorer (benchmark path, REQ-0009, test_benchmark.py:56).
- History stays git-ignored (`plans/run-history.jsonl`, phase-56 decision); new fields additive, `v` stays 1; old lines read.
- Noise rule unchanged: `metrics.noise(f, r)` (metrics.py:342), applied to flip counts only, never to rates.
- No cached query body changes (solve has no reply cache; only ingest uses replycache).

## Generality
Covers every exam kind; kind = `exam.subject/exam.language/exam.level` from result.json (engine.py:292-294), all data;
no subject, language, letter or DGNL literal in new code; regression set is a data file. Default: existing `stats/compare/trend`
output byte-identical (golden test on tests/fixtures/metrics). One test uses a synthetic non-DGNL keyed exam (fr/chemistry-like kind).

## Known incidents
none matching (phase-60 report: "only keyed exam scored 4/4 and 22/22; DGNL has no key").

## Plan modes
board: read-only, free. regset scoring (63.5): mock = free plumbing only; real = paid, main runs with user go. solve/ingest/refine/cross-solve unchanged.

## Design
### 63.1 Quality fields per run (owner: `metrics.compute` adds `quality` block; existing keys untouched)
`quality = {"basis": "key"|"qa"|None, "correct", "keyed", "precision" (correct/answered keyed), "wrong_answered",
"silent_wrong" (answered, key wrong, not flagged), "flagged", "false_alarm" (flagged and key-correct / flagged),
"proxy": {qa agree_rate, proxy_false_alarm (flagged and QA agrees / flagged), needs_review_by_why, image_agrees, image_differs}}`.
`flagged` = reason prefix in `FLAG_REASONS = (reviewer_disagrees, check_failed, needs_review)` or code `image_differs`
(engine codes, not exam data). Basis None -> all key fields None and `"unmeasured": true`. Added only when computed by board
(new kwarg `quality=True`) so stats/metrics.json stay byte-identical.

### 63.2 Exam kind + pairing (owner: `metrics.kind(result)`, `metrics.pair(lines, baseline=None)`)
- `kind(result) -> "subject/language/level"` (`-` for a missing field). History line gains `kind` (history_line, metrics.py:222).
- Pairing key = `exam_sha256` (not exam_id: D3). Current = latest line per sha; baseline = `--baseline RUN_ID|DIR` (same sha)
  else the previous line of that sha. No baseline -> row `baseline: none`, verdict `-`. sha null -> row skipped, counted `no_sha N`.

### 63.3 Per-pair delta (owner: `metrics.board_delta(ma, mb)`; reuses `classify`, metrics.py:347)
Per question A->B: `fixed/regressed` (classify, vs key else vs QA), `cov_up` (not answered -> answered), `cov_down`,
`wrong_new` (B answered-wrong, A not), `wrong_gone`. With no key and no QA: only cov_up/cov_down.
Delta row: coverage a/N -> b/N, precision, key correct, false_alarm, silent_wrong, cost_usd, calls, cost_per_answered (B-A).

### 63.4 Verdict and coverage-up/quality-down flag (owner: `metrics.verdict(d)`)
Kind level pools pair counts (sum F,R,wrong_new,wrong_gone,cov_up,cov_down over exams of the kind), then:
| condition (signal = `not noise(x, y)`) | verdict |
|---|---|
| basis None | `unmeasured` (coverage delta shown, text `quality unmeasured (no key, no QA)`) |
| signal(F,R) with R>F, or signal(wrong_gone,wrong_new) with wrong_new>wrong_gone | `regression` |
| signal(F,R) with F>R and no regression | `better` (basis qa -> `better (proxy)`) |
| else | `same (within noise n=.. flips=..)` |
Flag `COVERAGE_UP_QUALITY_DOWN` when cov_up>cov_down and verdict regression; `watch: coverage up, quality down within noise`
when cov_up>cov_down and (R>F or wrong_new>wrong_gone) but no signal. Coverage alone never yields `better`.

### 63.5 CLI `run-stats board` (owner: `cli._rs_board`, choice added at cli.py:1358)
`board [--history F] [--baseline REF] [--kind K] [--source solve|backfill|regset] [--json]`.
One block per kind: header `kind <k>  basis key|qa(proxy)|none  exams E  runs R`, then lines `coverage`, `quality`
(or `quality unmeasured`), `false_alarm/silent_wrong` (key) or `proxy: qa agree x% false_alarm~ y% review_why .. image a/d`,
`cost $a -> $b (per answered ..)`, `verdict <v> [FLAG]`. Exit 0; 1 when any kind is `regression`; 2 input error.
Result file missing for a line -> `result missing: <run_id>` and that pair is skipped.

### 63.6 Keyed regression set (owner: `benchmark_main --set FILE --history F`, cli.py:839; data `evals/regset.json`, git-ignored)
- Set file: `{"v":1,"items":[{"id","input","key","key_basis":"official"|"generated: code check"|"generated: 2 blind reviews"}]}`.
  Proposed: trial exam (22 q, official key; path from main, Q1) + 2 items each from existing generated sets
  (`evals/generated` hs math, `evals/generated-dgnl` dgnl-en english, dgnl-vi vietnamese) = 3+ kinds, 2 languages; fixed, never re-generated.
- `--set` replaces `discover()` with the listed pairs; each item appends one history line `source=regset`, `set_id`, `key_basis`,
  git, prompt_info (fixes D4). Key passed only as `cfg["key"]` to engine.run (existing path, benchmark.py:63).
- Cost: mock $0 (proves plumbing, not quality); real calls <= items x `engine.call_cap(cfg)`, estimate ~$0.30 trial + ~$0.05/generated
  item ≈ $0.60, cap `--budget-usd 1.00`. Run after each engine change on prompts/src (main, user go). First real run twice at
  one commit -> noise band in trend.
- Board labels generated-key kinds `key (generated)`; generated keys are model-made, so a kind only with them never claims "official".

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| no key, no QA | verdict unmeasured | `quality unmeasured (no key, no QA)` |
| no baseline for sha | no verdict | `baseline: none` |
| result.json moved/deleted | pair skipped | `result missing: <run_id>` |
| baseline is another exam | exit 2 | `ERROR: different exam (sha ..)` |
| exam_sha256 null (old backfill) | skipped | `no_sha N` |
| regset item key missing | item skipped | benchmark `skipped=N`, exit 3 |
| budget spent mid-set | later items not run, no history line | `skipped` list |

## Unit tests (tests/unit/test_run_board.py, synthetic result.json in tmp + history lines)
1. coverage-up/quality-down: A 20/30 answered 18 correct, B 30/30 20 correct (wrong 2->10) -> `regression` + `COVERAGE_UP_QUALITY_DOWN`, exit 1.
2. better: F=6,R=0 -> `better`; F=3,R=1 -> `same (within noise)`; boundaries reuse noise().
3. no key, no QA, coverage 25->30 -> `unmeasured`, never `better`; with QA ref -> `better (proxy)`.
4. false_alarm/silent_wrong/precision equal hand counts on a mixed fixture.
5. pooling: two exams of one kind each within noise, pooled signal -> regression.
6. pairing by sha, not exam_id (two lines exam_id "exam", different sha -> two pairs); `--baseline` other sha -> exit 2.
7. Generality: non-DGNL kind (fr/chemistry fixture, letters beyond D) grouped by its own kind label; grep test: no subject/lang literal in board code.
8. golden: stats/compare/trend output and metrics.json for tests/fixtures/metrics unchanged.
9. benchmark `--set` mock: history +1 line per item with source=regset, key_basis; mock prompt capture has no key text.
10. result missing / null sha rows reported, exit 0.

## Verification (free first)
| Item | command -> expected | tier |
|---|---|---|
| 63.1-63.6 unit | `python3 -I -m unittest discover -s tests/unit` -> OK (baseline failures only) | free |
| 63.5 real data | `run-stats backfill work/dgnl-real/run2-* work/dgnl-real/run3-* --exam <same exam per subject> --history $TMP/h.jsonl` then `run-stats board --history $TMP/h.jsonl` -> DGNL kinds `quality unmeasured`, coverage delta shown, exit 0 | free |
| 63.4 crosscheck | jq/grep recount of answered and wrong flips on the same two result.json vs board --json -> equal | free |
| 63.6 mock | `benchmark --set evals/regset.json --mock F --out $TMP/b --history $TMP/h.jsonl` -> +items lines, board prints keyed kinds | free |
| 63.6 real | same with `--real --budget-usd 1.00` (main, user go) -> cost <= 1.00, board shows key basis per kind | paid ~$0.60 |

## Decisions (recommendations)
- Extend metrics/run-stats + benchmark `--set` - rejected: new scoreboard module (duplicates compute/classify); rerun engine inside board (AI call, violates AC1).
- Quality-down = flips of wrong answers (sign test), not rate delta - rate delta has no noise rule and hides small n.
- Kind from result.exam metadata - rejected: new config key (nothing to select; kinds already data).
- Generated keys count as key with label - rejected: proxy (they are checked by code or 2 blind reviews, stronger than QA).

- D-coordinator-1 (answers Q1, RAW-00186 autonomy): the keyed regression set is the already committed benchmark data: `evals/inputs` + `evals/keys` (math, english, literature, physics, informatics) and `evals/generated*` (inputs/keys/manifest); the trial exam (22 q) is added from the local answer-guide pages when present (key stays local, scoring only, never in tracked inputs). `evals/regset.json` lists ids and is git-ignored; no new key file is created.
- D-coordinator-2 Defects D1-D5 are fixed inside TASK-063; D5 (classify counts a declined question later answered wrong as unchanged, metrics.py:358-371) is required for AC2.
- D-coordinator-3 Paid scoring runs for the set (about 0.60 USD, cap 1.00) are decided by the coordinator inside the cap after the free slice is verified.
## Out of scope
New metrics capture in engine (tokens G1, first_answer G2); generating new exams; committed trend summary; another team's work.

## Gaps / questions
- Q1 (main): path of the keyed trial exam + key (not found in tracked files; phase-60 report cites 22/22). Recommend main supplies it in regset.json.
- G1: backfilled DGNL lines need `--exam` for a sha, else they are skipped (`no_sha`).

## Defects
- D1 (low) src/exam_engine/pipeline/metrics.py:360 `qa[..]["answer"] in "ABCD"`: substring test ("" or "AB" pass) and option-letter literal (Generality). Fix: single label in the question's options.
- D2 (low) src/exam_engine/cli.py:1232 `^[A-D]$` option-letter literal in recheck (exam kinds with E+ options).
- D3 (low) src/exam_engine/cli.py:283 exam_id = stem of the exam path; plan runs give `exam` for every exam (plans/run-history.jsonl lines 1-3), so `trend --exam-id` cannot separate exams.
- D4 (low) src/exam_engine/cli.py:905-916 benchmark writes no history line and records prompt as basename (phase-56 D1 still open at :913): keyed runs never reach trend.
- D5 (medium) src/exam_engine/pipeline/metrics.py:358-371 classify: declined -> answered-wrong is key_ok False both sides, counted `unchanged`: the exact coverage-up/quality-down case is invisible to compare today (63.3 wrong_new fixes it in board).

Nova
