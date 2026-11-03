# Phase 64 - Evaluation statistics robustness (TASK-064)
Task: TASK-064 · REQ-0071 (RAW-00189) · Status: draft
## Goal
Engine scores that a 2-question exam, a refusal pattern or an exploratory slice cannot distort; seen when the 5
validation scenarios below give the hand-computed numbers in `run-stats board/compare` (AC1-AC3).
## Constraints
- Reuse metrics.compute/classify/pair/verdict and scorer.apply_key; no new module, no new input file, stdlib only.
- `stats` output and metrics.json byte-identical for result.json files without key scores (56 goldens); new fields only in
  `quality` (board-only, 63.1 pattern). No LLM prompt/cache body changes, so no cache-key impact.
- TASK-063 (in progress) owns quality/kind/pair/board_delta/pool/verdict/board/regset; 64 extends them, does not redo them.
## Generality
All exam kinds; rules are on engine reason codes and counts, no subject/language literal; one test uses a synthetic non-DGNL kind.
## Known incidents
none
## Plan modes
mock/real solve: only 64.1 changes result.json (score of non-answered keyed items); all else is read-side (run-stats).

## Current design (review section 1)
- Per question: `_answered` (metrics.py:29-31) = answer set, not `solver_declined*`, not `malformed_output|not_solved`.
  `_key_ok` (64-71): given key -> answer==key (declined = False); else from `score` (points==max).
- Per run: counts (143-153), key block correct/keyed (177-185), 63.1 `quality` precision = correct/(answered keyed) (211-226).
- Engine level: `trend` lists runs, repeats = same (commit, prompt, model) (cli.py:1310-1341); `compare` paired flips +
  `noise()` (cli.py:1277-1303); 63 `board` pools flips per kind (metrics.py:472-492), `_side` aggregates (500-524).
- Benchmark: per-subject pass/fail sums, `regression()` = any pass drop (benchmark.py:77-92,124-127).
- Data: plans/run-history.jsonl 3 lines, all n=4, source=solve, exam_id `exam`/`slice-pages`; lines 2-3 same sha b8b2..,
  same commit 4d613c2, model sonnet (a repeat). evals: 5 subjects x 3 inputs, 1 `## Question` each (keyed n=3 per subject).
  work/dgnl-real run2/run3: 30 q each, declined run2 Vi 10, Sci 9, En 1; run3 Vi 3, Sci 2, Math 1, En 0; no key.

## Gaps (review section 2; ids = Defects)
G1 (D1) refusal rewarded: scorer.apply_key gives declined/no-answer `points None` (scorer.py:108-110) -> `_key_ok` None ->
  not keyed. 30q, 20 answered (16 right), 10 declined: scorer path key 16/20 = 80%; `--key` path 16/30 = 53% for the same run.
  Engine B answering all 30 (20 right) shows 67% < A's 80% though it solved 4 more. Board/regset use the scorer path (cli.py:1362).
G2 (D2) 63's D5 fix needs key_ok on both sides (metrics.py:416): under G1 declined->answered-wrong is never `wrong_new`,
  declined->right never `fixed` in board.
G3 (D3) per-exam averaging: `_side` agree_rate = mean of exam rates (metrics.py:514-515). 2q exam 0/2 + 100q 90/100 -> 45%;
  pooled 90/102 = 88%. Precision and counts are already pooled (509-510).
G4 (D4) `noise()` (386-388) is a normal approximation called "~95%": it calls 4-0, 5-0, 7-1, 9-2, 11-3, 12-4 a signal while
  the exact two-sided sign test p = .125, .0625, .070, .065, .057, .077.
G5 (D5) no "insufficient": F+R<4 prints `same (within noise ...)` (492) / `within noise` (cli.py:1301), and with no key/QA
  compare still says `within noise` (run2->run3 Vi coverage 20->27, flips 0) - nothing was measured.
G6 (D9) no official/exploratory split: board pools all sources unless `--source` (cli.py:1384); trend has no filter (1318).
G7 (D10) baseline = previous line of the sha, any version (metrics.py:459): history lines 2-3 are a same-version repeat paired
  as a regression check.
G8 (D7) counts are not a partition: `malformed` also counts answered q with `review_malformed` (146-147); no
  answered-wrong / unanswered / invalid split.
G9 (D8) benchmark.regression: 1 pass drop on 3 one-question items = regression; budget-skipped item looks like a drop.
G10 small official set: regset ~22+6 keyed q; minimum decisive change = 6 one-way flips (~21% of the set).

## Recommended design (review section 3) and Design items
Primary engine metric = attempt-adjusted score `correct / keyed` pooled by question over a kind, Wilson 95% interval;
coverage and precision shown beside it; version comparison = exact sign test on paired flips (same questions, so a paired
test, not a CI overlap); fewer flips than can ever reach p<=.05 -> `insufficient`. Official = `source=regset` only.
### 64.1 Non-answered keyed items score 0 (owner: scorer.apply_key, scorer.py:103-110)
Declined/no answer with a key final that is not `open (rubric)`: `score={"points":0,"max":1,"basis":"official_key",
"detail":"not_answered"}`; status/reason/findings unchanged (no FAIL). Open tasks and no-key items keep points None.
### 64.2 Outcome partition + score (owner: metrics._quality, quality block only)
`outcomes={correct, wrong, unkeyed_answered, declined, unanswered (not_solved or answer None), invalid (reason
malformed_output)}`, disjoint, sum = n. `score = correct/keyed`, `score_ci=[lo,hi]` Wilson z=1.96 (new `wilson(k, n)`),
`coverage = answered/n`. Precision kept, labelled "of answered".
### 64.3 Pooled kind aggregate (owner: metrics._side)
agree_rate = sum agrees / sum(agrees+differs); score/score_ci from summed correct/keyed; outcomes summed.
### 64.4 Exact sign test (owner: metrics.noise)
`noise(f, r)` = two-sided binomial p > 0.05 (math.comb); new `decisive(f, r)` = f+r >= 6 (smallest n where p<=.05 is possible:
6-0 p=.031; 5-0 p=.0625). Same callers; docstring fixed.
### 64.5 insufficient / unmeasured verdicts (owner: metrics.verdict, cli._rs_compare)
verdict: basis None -> `unmeasured`; both (F,R) and (wrong_gone,wrong_new) not decisive -> `insufficient (flips k<6)`;
else 63 table. compare: basis None -> `unmeasured (no key, no QA)`; not decisive -> `insufficient`; exit codes unchanged.
### 64.6 Tier split (owner: cli._rs_board, cli._rs_trend)
tier = `official` if source==regset else `exploratory`; board groups by (tier, kind), header gains `tier T`, tiers never pooled;
trend gains `--source` (same choices as board).
### 64.7 Version-aware baseline (owner: metrics.pair, metrics.version_key)
`version_key(line)` = (git.commit, prompt json, model) moved from cli._rs_group (cli.py:1310, which then calls it).
Default baseline = latest earlier line of the sha with another version key; none -> previous line, block label `repeat`.

## Implementation plan (review section 4, priority order)
1. 64.1+64.2 (G1,G2,G8; refusal reward is the biggest bias) 2. 64.4+64.5 (G4,G5) 3. 64.3 (G3) 4. 64.6 (G6) 5. 64.7 (G7).
Tests first in tests/unit/test_eval_stats.py; after TASK-063 lands (same functions).

## Unit tests / Validation plan (review section 5; numbers by hand)
1. 30q 20 answered (16 right, 4 wrong) 10 declined: outcomes 16/4/0/10/0/0; score 16/30=.533, CI [.361,.698]; coverage .667;
   precision .80; scorer-path key block keyed=30 (was 20).
2. 2q 1 right 1 declined: score .50 CI [.095,.905]; A->B 1 fixed 0 regressed -> `insufficient (flips 1<6)`.
3. 100q 70 right, 12 wrong, 10 declined, 5 not_solved, 3 malformed: partition sums 100; score .70 CI [.604,.781];
   precision 70/82=.854; coverage .82; an answered q with review_malformed counts once (correct or wrong), not invalid.
4. unusual exam, own kind, 5q 1 right 4 declined (missing_text): score .20 CI [.036,.624], kind separate. If pooled with
   tests 1-3 (2+30+100 q): pooled 87/132=.659 -> 88/137=.642; per-exam mean .578 -> .483 (shows why pooling).
   QA pooling: exam 0/2 + exam 90/100 -> agree .882 (not .45).
5. version A vs B, 100q: F9 R5 -> p=.42 `same (within noise)`; F12 R2 -> p=.013 `better`; F4 R0 -> `insufficient`
   (was signal); 7-1/9-2/11-3/12-4 noise; 6-0, 8-1, 10-2 signal; 56/63 boundaries (3-1 noise, 6-0 signal) hold.
6. tiers: regset + solve line same kind -> two blocks; trend `--source regset` hides solve lines.
7. baseline: lines A(v1), B(v2), C(v2) same sha -> current C, baseline A; only C(v2),D(v2) -> label `repeat`.
8. golden: stats/metrics.json for tests/fixtures/metrics unchanged except key-scored fixtures with declined q (list them).
9. generality: synthetic non-DGNL kind with letters beyond D; grep test no subject literal.
## Verification
| Item | command -> expected | tier |
|---|---|---|
| 64.1-64.7 | `python3 -I -m unittest discover -s tests/unit` -> OK | free |
| 64.5 real | `run-stats compare work/dgnl-real/run2-Vietnamese work/dgnl-real/run3-Vietnamese` -> `unmeasured (no key, no QA)` | free |
| 64.6/64.7 real | `run-stats board --history plans/run-history.jsonl --json` -> tier exploratory, lines 2-3 `repeat` | free |
| 64.1 mock | `benchmark --set evals/regset.json --mock F --out $TMP/b --history $TMP/h.jsonl`; declined item score 0/1 | free |
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| old result.json (pre-64.1) vs new | mixed keyed denominators | rescore with `run-stats ... --key` |
| keyed=0 | score/CI None | `score -` |
| only same-version lines | baseline previous | `repeat` label |
## Decisions
- Pooled-by-question + Wilson - rejected: per-exam mean (2q weighs as 100q), weighted/Bayesian models (no demonstrated need;
  Wilson is exact-enough at small n and 3 lines of math).
- Refusal = not correct in the primary score - rejected: excluding declines (G1), penalising wrong < 0 (no exam rule to justify).
- Thresholds derived, not chosen: p<=.05 (convention already in 56/63 "~95%"), 6 flips = its smallest reachable n; no
  min-n for levels: the CI width shows it.
- Official = existing `source=regset` - rejected: new history field/tag file (no new input).
- Scorer-side 64.1 - rejected: metrics-side guess (cannot tell open task from declined without the key).
- D-coordinator-1 (RAW-00189) Order: TASK-063 first (its coder already received D2 and D6); TASK-064 implements 64.1-64.7 after it, tests first, golden-compatible: existing outputs stay byte-identical and new fields are additive.
- D-coordinator-2 64.1 changes how a keyed refusal is scored (counts as not correct): the headline becomes attempt-adjusted; the old figure stays printed as `answered-only` so history stays comparable.
- D-coordinator-3 Thresholds (e.g. 6 flips for insufficient) are kept only if the design's rationale (exact sign test p-values) holds; no other new constants.
## Out of scope
Difficulty segmentation (no field); growing the regset (data decision for main, G10); benchmark.regression rewrite (G9:
recommend board verdict on regset instead); another team's work.
## Final recommendation (review section 6)
Keep the architecture; fix the scorer denominator, pool by question, use the exact paired test with an `insufficient`
floor, and separate official/exploratory and repeat runs. Seven small edits in 3 files remove every distortion shown above.

## Defects
- D1 high src/exam_engine/pipeline/scorer.py:108-110 + metrics.py:68-71: declined unkeyed -> refusal raises key rate (G1).
- D2 high src/exam_engine/pipeline/metrics.py:416: 63 D5 fix inert on the scorer path (TASK-063 AC2; tell the coder).
- D3 medium metrics.py:514-515 per-exam mean agree_rate.
- D4 medium metrics.py:386-388 noise anti-conservative at small n (exact p list in G4).
- D5 medium metrics.py:492, cli.py:1300-1302: "within noise" when unmeasured/insufficient.
- D6 medium cli.py:1398,1414: one review pack applied to every exam in board, ids collide across exams (TASK-063).
- D7 low metrics.py:146-147 malformed overlaps answered.
- D8 low benchmark.py:124-127 regression on any pass drop, skipped item counts as drop.
- D9 low cli.py:1318 trend has no source filter; history lines 2-3 exploratory slices look official.
- D10 low metrics.py:459 baseline ignores version; repeat paired as regression check.
Nova (designer)
