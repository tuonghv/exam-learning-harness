# Phase 75 - Discriminating confidence (draft for docs/design/phase-75-discriminating-confidence.md)
Task: TASK-075 · REQ-0079 · Status: draft
Note: the guard refused work/TASK-075/handoff/design.md (role bound to TASK-074); main to copy this file there.

## Premise (facts read)
- PASS needs reviewer agree + uncertainty low + an `independent` pass check (core/decision.py:31-39). Independent checks:
  only `computed` with a numeric answer (verifier.py:133-154) and `key_match`. `quote`, `format`, `ai_review` are
  `independent: False` (verifier.py:187-194, :275-277). On MCQ the answer is a letter, so `computed` gives
  "arithmetic only: answer has no number", result unknown (verifier.py:147-149) although the solver sent `expr`
  (run3-Math result.json:139-144). So every keyless MCQ that clears review ends at `no_independent_check`.
- `retry_ids` skips `no_independent_check` (engine.py:67-70); `unresolved` is false for it (engine.py:284).
- Image agree is recorded as finding `image_agrees` only; the status stays as it was (engine.py:177-180). `image_differs` sets
  UNCERTAIN `needs_review` (:181-186).
- run3 (work/dgnl-real/run3-*/result.json, grep counts, tester to recount): 116 answered, 111 correct.
  Uncertainty medium on about 13 answered (V 7, S 3, E 3, M 0), 1 of them wrong (V24). Low + agree on about 103, 3-4 wrong
  (E38, M63, M65; S112 is a rate-limit error, see D2). M63 (id 3): attempts 2, reviewer agree with a caveat finding.
  M65 (id 5): attempts 1, quote pass, no finding. No image check in run3.
- Base precision on answered 111/116 = 0.957, Wilson 95% [0.903, 0.981] (metrics.wilson, metrics.py:221).
- Cost basis: text solve 0.31 USD per 30-question subject, about 1.25 USD per 120 questions (phase-60 Premise, run3-Math);
  the brief's figure is 0.015-0.03 USD per question (1.8-3.6 per exam). A call costs 0.04-0.08. The solve path has no
  reply cache (phase-60 Premise), so a new prompt body cannot reuse old replies.

## Goal
Each answered question gets a `confidence` tier, `likely_ok` | `likely_wrong` | `unknown` (`verified` when PASS). The tier
comes from measurable channels that agree or differ. PASS, FAIL, UNCERTAIN, exit codes and `unresolved` stay as they are.
Done when `run-stats` on a keyed run shows, per tier, correct/wrong counts with Wilson intervals, and likely_wrong holds a
clearly higher wrong share than the base rate (see Verification).

## Constraints
- PASS bar unchanged: the tier is a separate field and never feeds `decide()`. `verification_status` bytes are unchanged.
- Default off: there is no `confidence` key in cfg and no `--second-sample` flag, so result.json, prompts and calls stay
  byte-identical (same pattern as cli.py:101-104).
- Do not touch prompts/dev/exam/solve.md or lang/vi/exam/solve.md (TASK-074). The second sample reuses
  `solver.base_prompt` read-only.
- Trust boundary: the key never enters the second-sample prompt. `fewshot` is not used there (it reads key_path,
  solver.py:28).

## Generality
Covers every MCQ exam kind with lettered options (any language or subject). Tiers use letter keys from `q["options"]`,
never a literal. Open tasks and numeric answers are untouched. One test uses a synthetic non-DGNL English 4-option exam.
The golden test covers the default config.

## Known incidents
none found (no incident row for status/confidence).

## Options compared (120-question keyless MCQ exam)
| Opt | What | Extra cost / exam | Expected separation on run3 | Main risk |
|---|---|---|---|---|
| A | Second independent sample: re-solve the target ids with permuted option order and other question order. Agree gives likely_ok, differ gives likely_wrong | +1 solve on ~110 ids: 1.2-3.6 USD (x2 solve) | Catches unstable answers (position bias, coin flips). Systematic misreads repeat (M63 interpretation, M65 key oddity), so expect 1-3 of 5 wrong flagged. Unmeasured, paid | Same model gives correlated errors. Reply parse failures |
| B | Existing signals as features: uncertainty level, reviewer verdict and finding count, image agree/differ, attempts, malformed first round | 0 | Weak: medium group wrong rate 1/13 = 8% vs low group about 3-4%; only E reviewer-unsure flags anything; run3 has 0 image rows | Over-flagging medium (12/13 right) |
| C | Reviewer with a different prompt (blind, does not see the answer) or another model | Blind: 0.8-3.6 USD (needs reasoning output). Other model: price unknown; Haiku excluded (user rule: simple jobs only) | Like A, less correlated if another model; a new prompt to maintain and version | Prompt drift; second prompt family |
| D | Option-distance check: eval `expr`, find the nearest numeric option, mismatch with the chosen letter | 0 | Arithmetic slips only. On M63 and M65 the expr agrees with the wrong letter, so it must never vote "ok" | Thousands-separator parse ("19.975.000"), unit or scale mismatch |
Recommendation: B+D as negative-only signals (0 USD) plus A as the only positive channel (opt-in, capped). C is deferred:
it becomes A with `second_model` set, if A shows correlated agreement.

## Plan modes
- Single-source run: as specified. Pipeline plans and cross-solve: not affected (flags not forwarded; default off).
- `--dry-run` (cli.py:141): prints the second-sample prompt only when the flag is set.
- run-stats on old results: tier block absent (no `confidence` field), output unchanged.

## Design
### 75.1 Option-distance check (owner: new `verifier.option_distance(q, ans) -> check|None`)
- Applies when the answer is one key of `q["options"]`, `expr` evaluates (`safe_eval`), and every option holds exactly one
  number (existing `_NUM`, as in option_for_value :103-106). It reuses `_answer_value` for fractions and sqrt.
- Returns `{"kind":"option_distance","detail":"expr=v nearest=X chosen=Y","result":"pass"|"unknown","independent":False}`.
  It is never "fail", so decide() and the status cannot change. A mismatch adds finding `("deterministic","option_mismatch",detail)`.
- Mismatch only when nearest != chosen and the nearest is unique (2nd-nearest distance >= 2x) and 0.5 <= v/opt <= 2 (scale
  guard). Otherwise unknown.
### 75.2 Second sample (owner: new `engine.second_sample(exam, recs, rn, ids)`, `solver.permuted(exam, ids) -> (exam2, back)`)
- Targets: answered, not open, not declined, status UNCERTAIN, reason `no_independent_check` or in `DOUBT_REASONS`
  (engine.py:120), ascending. It runs after image_check (engine.py:350), inside the same try, so a Stop keeps the first answers.
- `permuted`: per id, rotate the option texts by `1 + id % (k-1)` (k = option count >= 2; the correct position always
  moves). Skip the rotation when any option text names another letter (`\b<key>\b` for keys of that question). The shifts
  are deterministic, so there is no seed, and `back` maps a new letter to the original.
- Prompt: `base_prompt + Language + exam_context + render_questions(exam2, ids)`, plus one line "Solve independently". No
  review notes, no fewshot, no first answers. Tag `second`. One call per subject; reuse `solve_round`'s parse (`sch.SOLVE_OUT`)
  into a temp dict, never into `recs[i]["ans"]`.
- Per id: `rec["second"] = back[answer]`. Finding `("second","second_agrees"|"second_differs"|"second_missing", "...")`.
  A call or parse failure gives finding `second_failed` on all ids, and the tier stays as computed without A.
- Cap: honours `max_cost_usd` via Runner (no new budget logic). Flag `--second-sample` (cli, cfg only if set).
### 75.3 Tier (owner: new pure `decision.confidence(rec) -> str|None`, called in build_result)
- None: declined, open, or no answer. `verified`: status PASS.
- `likely_wrong` if any of: status FAIL; review verdict disagree/unsure; finding code in {second_differs, image_differs,
  adjudicated, option_mismatch}; uncertainty level high.
- `likely_ok` if reason == `no_independent_check` (reviewer agree, low uncertainty, no fail) and a positive channel exists:
  `second_agrees` or `image_agrees`. `option_distance` pass is never positive (it is the solver's own expr).
- else `unknown` (for example medium uncertainty alone).
- result.json question gains `"confidence"` (and `"second_answer"` when set) only when cfg `confidence` is true.
  Schema: add both optional properties at schemas/result.schema.json (question object, additionalProperties false, ~:123/:326).
  `summary` gains `confidence: {tier: n}` only then.
- Flag: `--confidence` turns on 75.1 and 75.3 (0 USD). `--second-sample` implies `--confidence`.
### 75.4 Measurement (owner: `metrics._quality` metrics.py:246, `metrics.block` :475)
- When the key is present and any q has `confidence`, add `by_confidence: {tier: {n, correct, wrong, precision,
  precision_ci (wilson)}}`, `wrong_in_likely_ok` (silent wrong), and `wrong_recall` = wrong in likely_wrong / wrong answered (with CI).
- block line: `confidence: likely_ok 95/97 [0.93,0.99] | unknown .. | likely_wrong 3/9 wrong`.

## Unit tests (tier 0, mock LLM)
- option_distance: nearest unique and equal gives pass; mismatch gives unknown + option_mismatch finding; scale mismatch
  (v/opt 1e6) gives unknown; two options share a number gives unknown; letter answer without expr gives None; status unchanged.
- permuted: the rotation moves every answer position; `back` inverts it; an option text with a letter reference is not
  rotated; k=2 works.
- second_sample: agree, differ and missing findings; failed call keeps recs; prompt has no key text and no first answer;
  targets exclude PASS, FAIL and declined.
- confidence: a table test over each rule; option_distance pass alone never gives likely_ok; PASS gives verified.
- Golden: default cfg run on an existing fixture is byte-identical (result.json and prompts); synthetic English 4-option exam
  with `--second-sample` gives the expected tiers.
- metrics: by_confidence counts and Wilson on a hand-made keyed result; old result means no key added.

## Verification
| Item | Command -> expected | Tier |
|---|---|---|
| 75.1-75.3 | `python3 -I -m unittest discover -s tests/unit` -> new tests pass, only baseline failures | 0 |
| 75.3 default | golden test -> byte-identical | 0 |
| 75.2 P1 | coordinator: run3 subjects Math + Vietnamese (3 of 5 wrong) with `--second-sample --max-cost-usd 3` each (cap 6 USD), keyed by input/dgnl -> by_confidence printed | paid |
| 75.4 P2 | if P1 flags >= 1 wrong: English + Science, cap 6 USD -> 120-question table with Wilson | paid |
| 75.4 P3 | DGNL 2025 after REQ-0081 key -> same table, pooled n about 230 | paid |
Adoption rule (pre-registered): wrong share in likely_wrong >= 3x the base wrong rate AND wrong_in_likely_ok <= the base
wrong rate in likely_ok. Sample size: at an observed 0.99 the Wilson lower bound clears 0.957 only at n >= 200 in likely_ok
(99/100 gives lo 0.946, 198/200 gives lo 0.964), so about 2 exams. Recall of wrong answers needs >= 20 wrong (CI about ±0.2),
which is 4-5 exams at a 4-5% error rate. One 120-question run is report-only, not proof.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| second call fails or is malformed | first answers kept, finding second_failed | tier from B/D only, `second_failed` count |
| budget hit mid second sample | Stop as usual; tiers on the done ids | run.stopped, partial tiers |
| permute breaks a letter-referencing option | rotation skipped for that id | finding detail "not permuted" |
| correlated agreement (same model) | wrong answer lands in likely_ok | wrong_in_likely_ok in run-stats (measured) |
| expr scale or thousands parse | result unknown, no finding | none |

## Decisions (for the user; recommended first)
1. Pick ONE: (a) the tier is a separate field and PASS is unchanged (rec; AC2 "PASS precision" is reported as likely_ok
   precision); (b) count second_agrees as an independent check, so it can reach PASS. That lowers the bar.
2. Pick ONE: second-sample scope (a) no_independent_check + doubt ids (rec); (b) all answered.
3. Pick ONE: second sample model (a) same model (rec, measure correlation first); (b) another model via `second_model` (option C).
4. Approve: paid P1 cap 6 USD, P2 cap 6 USD.

- D-coordinator-1 Decisions 1-3 taken: a separate `confidence` tier beside the verification status (PASS bar unchanged); the second sample runs on no_independent_check and doubt ids; same model (no new model).
- D-coordinator-2 Decision 4 (paid P1/P2 with caps of 6 USD each) is the user's: registered as a question on the task; free slice 75.1, 75.3, 75.4 first.
- D-coordinator-3 Defects D1 (stray AC1 line in REQ-0079) and D2 (dgnl-score counts the Science 112 rate-limit error as a wrong answer) are fixed in this task.
## Out of scope
REQ-0080 (nearest-option prompt rule, TASK-074 prompts); the user key check of M65; the 2025 key (REQ-0081).

## Defects
- D1 low, docs/req/items/REQ-0079.md:26: stray empty `- [ ] AC1:` line duplicates AC1.
- D2 medium, work/TASK-037/evidence/dgnl-score.txt:4,23-24 vs :34: Science 112 is counted as answered wrong (30 answered,
  0 declined) while its reason is solver_declined and the saved text is a rate-limit error. The real baseline is about 4
  answered-wrong + 1 infrastructure miss, so the denominators in 75.4 must use metrics._outcome, not this table.
- D3 info, verifier.py:147-149: on MCQ the solver's `expr` is never used (always unknown); 75.1 closes it negatively only.
- D4 guard: designer is bound to TASK-074, so writing work/TASK-075/ was refused (B1). Rebind the role, or main copies this file.

Nova
