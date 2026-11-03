# Phase 67 - Answer with a trailing note matches the key (TASK-067)
Task: TASK-067 · REQ-0075 · Status: designed.

# Phase 67 - answer note keeps the key match (draft for docs/design/phase-67-<slug>.md)
Task: TASK-067 (REQ-0075). Suggested slug: `answer-note-key-match`.

## Root cause (evidence)
- Saved run1/run2 math/005 result.json:30 answer = exact form + trailing parenthetical approx note; key = same exact form.
- Not the verifier: `computed` check passed (verifier.py:142 `_answer_value` already strips a trailing note, line 116); `format` pass; reviewer `agree` (result.json:42-60, 64-69).
- Failing layer = SCORE: `scorer.match` (src/exam_engine/pipeline/scorer.py:24-46) via `score` :96 -> `apply_key` :122-124 sets FAIL/differs_from_key.
  - :32 letter path no; :36 order path no; :38 `_numparse(key)` = None (key starts with `sqrt`, `_NUMX` :50 needs a leading digit), so the numeric path (:42-45), which does drop `(...)` notes (:55), is skipped.
  - :46 falls through to raw `norm(answer) == norm(key)`; the note is still in `na` -> False.
- Solver output form is fine: requested form first, note after. No prompt change needed.

## Goal
A short answer whose value part equals the key, followed by one trailing parenthetical note consistent with that value, scores `matches key`; math/005 PASS in both replays.

## Constraints
- Purely additive in `match`: only a case that returned False can become True; every old True/None/False elsewhere byte-identical (old results re-scored give identical output except the fixed rows).
- Never turn a wrong value into a pass: value part must equal the key string after `norm`; a note holding a number must agree with the value part; a note with 2+ numbers blocks the pass.
- Key is never stripped (keys may legitimately end with `(...)`, e.g. `Open (rubric)` handled at :29).
- Trust boundary unchanged: scorer stays the only key reader; no key text in findings.

## Generality
Covers every keyed non-letter, non-ordering, non-numeric short answer (exact forms: roots, fractions with symbols, expressions, words) in any subject/language; no subject, exam or language literal; no config. Golden: existing `test_score_eval.test_13_match` unchanged. Synthetic non-DGNL test with a made-up key.

## Known incidents
Phase 60.1 (`option_for_value`, notes ignored on MC). Same class.

## Plan modes
- solve/benchmark/regset: score via `apply_key` -> fixed. - eval `score` CLI (`score_file` :87): same `match` -> fixed. - verifier, reviewer, prompts, cache: not affected (scorer is deterministic, no reply cache key involved).

## Design
### 67.1 Trailing-note fallback in key match (owner: scorer.match, scorer.py:46)
- Replace the final `return na == nk` with `return na == nk or _note_match(a, k)`.
- New `_note_match(answer, key) -> bool` in scorer.py:
  1. `m = _NOTE.match(answer)` with `_NOTE = re.compile(r"^(.*\S)\s+\(([^()]*)\)\s*\.?\s*$", re.S)` (whitespace before `(` required, so `sqrt(2)` itself is never split; one note only, no nesting).
  2. No match -> False. `value, note = m.group(1), m.group(2)`.
  3. `norm(value) != norm(key)` -> False (value part must equal key exactly; multi-number / wrong value never pass).
  4. `nums = _NOTE_NUM.findall(note)` (`-?\d+(?:[.,]\d+)?`, after `−` -> `-`). `len(nums) == 0` -> True. `len(nums) > 1` -> False.
  5. One number: `v = _exact_value(value)`; None -> False; else True iff `abs(v - x) <= 0.5 * 10**-d + 1e-12` (x, d = note number and its decimals; same rounding rule as :45).
- New `_exact_value(s) -> float|None`: replace `√`->`sqrt`, `^`->`**`, `,`->`.`, then `core.safe_eval.safe_eval`; `ValueError` -> None. Import `from exam_engine.core.safe_eval import safe_eval` (core, no pipeline cycle).
- Do NOT reuse verifier `_TAIL_NOTE` (verifier.py:90): its `\s*` strips `(2)` off `sqrt(2)` (see Defects).

### 67.2 Replay of saved replies (owner: test only, no code)
- Free proof that both saved paid answers now match, through `apply_key` on records built from the saved result.json answer strings (test fixture with a synthetic key file holding the same exact form; no exam text).

## Unit tests (tests/unit/test_score_eval.py, new test_67_*)
- t1 exact form + word note with one consistent approx (both note wordings, any language) -> True.
- t2 note number inconsistent with value (e.g. value sqrt(3), note 1.4142) -> False.
- t3 note with two numbers (hedge `(or 2, 3)`) -> False.
- t4 value part differs from key, note correct for the answer -> False.
- t5 note without number -> True; no space before `(` (`sqrt(2)` vs key `sqrt(2)` already equal; `x(2)` vs key `x`) -> False.
- t6 key itself ends with a note, answer identical -> True (old path); answer without the key's note -> False (key never stripped).
- t7 regression: all test_13 asserts unchanged; numeric key with note (`2.5 (approx) m/s^2`) result unchanged vs pre-change (call old expectation).
- t8 synthetic non-DGNL exam: `apply_key` on a record with answer `sqrt(3)/2 (≈ 0.866)` and a temp key `sqrt(3)/2` -> score points 1, `key_match` check added, status not FAIL.
- t9 unparseable value with numeric note (`abc (1.5)` vs key `abc`) -> False (conservative).
- Run: `python3 -I -m unittest discover -s tests/unit` -> all OK.

## Verification
| Item | Command -> expected | Tier |
|---|---|---|
| 67.1 | `python3 -I -m unittest tests.unit.test_score_eval` -> OK incl. test_67_* | free |
| 67.1 | full suite `python3 -I -m unittest discover -s tests/unit` -> OK, no changed old asserts | free |
| 67.2 | replay: feed run1 + run2 math/005 saved answers to `scorer.match` against the 005 key (main runs, prints only True/False) -> True, True; other regset rows' scores unchanged (re-score saved answers before/after, diff = only math/005) | free |
| 67.2 | paid: `exam.py benchmark --set evals/regset.json --real` (main, cap USD 0.60) -> math/005 PASS, no other row regresses vs run1/run2 | paid |

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| Note number contradicts value | no pass, FAIL differs_from_key (as today) | same as before |
| Hedge with 2+ numbers in note | no pass | FAIL |
| safe_eval rejects value form | no pass if note has a number | FAIL (as today) |
| Note not trailing / nested parens | regex no match -> old result | FAIL (as today) |

## Decisions
- Fix in scorer fallback only - rejected: solver prompt "requested form first, notes after" (output already in that form; run used release prompts so dev change would not affect regset), stripping the key, numeric equivalence of a bare decimal answer vs exact key (exam asked the exact form; widens pass surface).
- Note number checked against value (0.5 ulp of note decimals) - rejected: ignore note content (lets `(or 2)` hedges pass).

- D-coordinator-1 Low defect D1 (verifier.py:90 `_TAIL_NOTE` would strip the `(2)` in `sqrt(2)`) is fixed in the same task with a test: the note must be separated by whitespace and not be an argument list.
- D-coordinator-2 Paid check: re-score the regression set once (cap 0.60 USD) by the coordinator; expected change: math/005 FAIL -> PASS, nothing else.
## Out of scope
- Value equivalence between different exact forms (`√2` vs `sqrt(2)`, `2/sqrt(2)`); MC `option_for_value`; prompts.

## Defects
- D1 low, src/exam_engine/pipeline/verifier.py:90 `_TAIL_NOTE` uses `\s*\(` so it also strips a final `(arg)` of a function form (`sqrt(2)` -> `sqrt`); harmless in `option_for_value` today (result None either way) but unsafe to reuse. Not fixed here.
- D2 info, regset math/005 run1/run2: correct answer scored FAIL by scorer.py:46 (root cause above).

Nova
