# Phase 137 – Code review batch 4: scorer.py and verifier.py

Scope: `src/exam_engine/pipeline/scorer.py` (235 lines) and `src/exam_engine/pipeline/verifier.py` (330 lines), all functions. Risk 4 (scores and decisions) first. Excluded: every row of `docs/review/findings.tsv` (no earlier row touches these two files).

## Findings

### F001 – [HIGH] Fraction keys are compared by numerator only

- File: src/exam_engine/pipeline/scorer.py
- Lines: 49-51, 106-111
- Type: BUG
- Trigger: normal input
- Reached via: `exam.py score` -> score_main() -> score_file() -> match(); solve with a key -> apply_key() -> score() -> match()
- Issue: `_numparse` reads `14/3` as number 14 with unit `/3`; `_unit_ok` accepts any unit when the other side is bare.
- Case: key `14/3` (evals/generated/keys/math/expected-101.md): answer `14` or `14/5` -> correct; answer `4.67` -> wrong.
- Fix: `_numparse` returns None when the remainder starts with `/` plus a digit; `match()` then compares `_exact_value()` of both sides (decimal answer: within half its last digit) before the string compare.
- Fix risk: tests/unit/test_scorer_sign.py:36-37 must stay False (signs differ, so they do).
- Test: `match("14", "14/3")` must be False; `match("4.67", "14/3")` must be True.

### F002 – [MEDIUM] A second value after the leading number is accepted as a unit

- File: src/exam_engine/pipeline/scorer.py
- Lines: 50, 114-117
- Type: BUG
- Trigger: off-prompt LLM reply
- Reached via: apply_key() -> score() -> match(); score_file() -> match()
- Issue: the answer's whole tail is its "unit" and a bare key unit accepts any tail, so a hedged answer matches when its first number is the key.
- Case: key `8`, answer `8 hoặc 9` or `8; 9` -> correct (tests/unit/test_benchmark_fixes.py:19 only covers the form that does not start with the number).
- Fix: at line 50 return False when `re.search(r"(?<![\w^])\d", unit_a)` holds and the same search on `unit_k` does not.
- Fix risk: none found; `62 host`, `1.8e-19 J`, `m/s2`, `m^2` have no standalone digit; `(...)` remarks are removed at line 104.
- Test: `match("8 hoặc 9", "8")` must be False.

### F003 – [MEDIUM] Thousands-grouped numbers are read as decimals

- File: src/exam_engine/pipeline/scorer.py
- Lines: 99, 106-111
- Type: BUG
- Trigger: normal input
- Reached via: apply_key() -> score() -> match() -> _numparse()
- Issue: `_NUMX` takes only the first separator group, so `19.975.000` becomes 19.975 with unit `.000`.
- Case: key `19.975.000 đồng`: answer `19975000` -> wrong; answer `19.975` -> correct.
- Fix: in `_numparse`, before line 106, when `t` starts with `-?\d{1,3}` followed by two or more `.\d{3}` groups (or two or more `,\d{3}` groups) not followed by a digit, delete those separators.
- Fix risk: none; `3,46`, `1.000` (one group) and `1,8.10^-19` do not match the rule.
- Test: `match("19975000", "19.975.000 đồng")` must be True.

### F004 – [MEDIUM] Trailing "= value" misses a U+2212 minus

- File: src/exam_engine/pipeline/scorer.py
- Lines: 44-47
- Type: BUG
- Trigger: normal input
- Reached via: apply_key() -> score() -> match()
- Issue: `_numparse` maps U+2212 to `-`, but the tail search at line 46 runs on the raw answer and only accepts ASCII `-`.
- Case: key `-3`, answer `x = −3` (U+2212) -> wrong; the ASCII form `x = -3` is correct (tests/unit/test_scorer_sign.py:38).
- Fix: line 46: search in `a.replace("−", "-")`.
- Fix risk: none.
- Test: `match("x = −3", "-3")` must be True.

### F005 – [MEDIUM] Computed check compares the first number of a labelled answer

- File: src/exam_engine/pipeline/verifier.py
- Lines: 123-130, 147-152
- Type: BUG
- Trigger: normal input
- Reached via: solver/engine -> det_checks() -> _computed()
- Issue: `_EXACT` is anchored at the start, so a leading label gives an empty match; `_computed` then falls back to the first number in the answer.
- Case: expr `1/2`, answer `x = 1/2` -> compares 0.5 with 1 -> independent `fail` -> status FAIL, paid retry. Same for `v2 = 10` (reads 2).
- Fix: in `_answer_value` (line 116) and before `_answer_number` (line 147) drop a leading `^[^=]*[^\W\d][^=]*=\s*` label (text with a letter before the first `=`).
- Fix risk: none; tests/unit/test_benchmark_fixes.py answers carry no `=`.
- Test: `_computed({"expr": "1/2", "answer": "x = 1/2"})["result"]` must be `pass`.

### F006 – [MEDIUM] A root sign without parentheses fails the computed check

- File: src/exam_engine/pipeline/verifier.py
- Lines: 116, 123-130
- Type: BUG
- Trigger: normal input
- Reached via: det_checks() -> _computed() -> _answer_value()
- Issue: `√` is replaced by `sqrt` with no parentheses (`√3/2` -> `sqrt3/2`); `_EXACT` needs `sqrt(`, so the value is not read and the first number is compared.
- Case: expr `sqrt(3)/2`, answer `√3/2` -> compares 0.866 with 3 -> `fail` -> FAIL.
- Fix: line 116: first replace `√\s*(\d+(?:[.,]\d+)?)` by `sqrt(\1)`, then the plain `√` replace. Same replace in scorer.py line 60 (`_exact_value`).
- Fix risk: none; `sqrt(2)` text is untouched.
- Test: `_computed({"expr": "sqrt(3)/2", "answer": "√3/2"})["result"]` must be `pass`.

### F007 – [MEDIUM] Ordering format check knows only letters a-e

- File: src/exam_engine/pipeline/verifier.py
- Lines: 32-33, 70, 77-79
- Type: BUG
- Trigger: normal input
- Reached via: det_checks() -> _format()
- Issue: `_letters` collects only `[a-e]`, but the ordering check requires the answer's letters to equal that list.
- Case: Sentence Ordering question with six sentences `a.`-`f.`, answer `b-d-a-f-e-c` -> want is a-e -> format `fail` -> status FAIL, QA skipped.
- Fix: for line 70/77 build `want` with a separate regex using `[a-z]`; leave `_letters` (a-e) as is.
- Fix risk: `_part_format` (lines 50, 53) keeps `_letters`, so the tf4/number shapes do not change.
- Test: `_format` for that question and answer must return `pass`.

### F008 – [MEDIUM] key_letters turns an ordering key into a letter

- File: src/exam_engine/pipeline/scorer.py
- Lines: 232-234
- Type: BUG
- Trigger: normal input
- Reached via: run-stats with an answer key -> cli._rs_compute() -> key_letters() -> metrics._key_ok()
- Issue: `\b` also matches before `-`, so a non-letter key starting with a-d is not left out as the docstring says.
- Case: key `b-d-a-e-c` (evals/keys/english/expected-004.md) -> `B`; the saved answer `b-d-a-e-c` != `B` -> counted as keyed and wrong.
- Fix: line 232: replace `\b` by `(?![\w-])`.
- Fix risk: none; `B`, `B. 2`, `B)` still give `B`.
- Test: a key file with `Final answer: b-d-a-e-c` must give `key_letters() is None`.

### F009 – [MEDIUM] An "Open" answer to a keyed question is left unscored

- File: src/exam_engine/pipeline/scorer.py
- Lines: 158-166
- Type: BUG
- Trigger: off-prompt LLM reply
- Reached via: engine solve with a key -> apply_key()
- Issue: `not is_open(a)` excludes the answer from the 0-point branch even when the key is a real value; line 163 then sets points None.
- Case: key `B`, answer `Open` -> score None, left out of the accuracy denominator; a declined answer gets 0/1.
- Fix: line 158: use `(a is None or declined(a) or is_open(a))` and drop `and not is_open(a)`.
- Fix risk: subjects with `score_basis` none never reach apply_key (engine.py:505-506); an essay key whose final is prose instead of `Open (rubric)` would now score 0.
- Test: recs with answer `Open`, key `B` -> `score["points"] == 0`.

### F010 – [LOW] score_file counts a key question without a final answer as wrong

- File: src/exam_engine/pipeline/scorer.py
- Lines: 124, 131-136
- Type: HARDENING
- Trigger: malformed file
- Reached via: `exam.py score` -> score_main() -> score_file()
- Issue: `q["final"] or ""` is matched as an empty key; the key is parsed without `legacy=True`, unlike apply_key (line 154), where `score()` reports `no key`.
- Case: key question with only `Correct answer: B`: answer `B` -> `wrong`, and TOTAL counts it.
- Fix: in the loop, when `q["final"] is None` append `(q["id"], "manual")` and continue (score_main leaves `manual` out of TOTAL).
- Fix risk: none; keys with a `Final answer:` line are unchanged.

## Summary

- Total findings: 10 (CRITICAL 0, HIGH 1, MEDIUM 8, LOW 1; BUG 9, HARDENING 1)
- Cap hit: yes
- Not reviewed: both files were read in full; candidates left unreported and not fully proven: `match()` half-unit tolerance on integer keys (key `5` accepts `5.5` and `4.5`); score_main counts an unanswered open item in TOTAL but not an answered one (lines 131-132, 221-223); `qa_round` keeps the first of two conflicting reviews for one id (verifier.py 311-313); `_quotes` passes a quote that is only an option label (`"B. "` -> empty `bare`, verifier.py 217-218); `qa_prompt` copies instructions/passage text into the prompt unfenced (risk 1, verifier.py 279-291).
