# Phase 79: Vietnamese diacritics in solve output (TASK-079; REQ-0087)

Root cause (RAW-00218): `prompts/dev/exam/solve.md` rule 2 says only "Explain in the `Language:` value"; no diacritics rule and no code check, so an English-subject reply came back as ASCII Vietnamese ("Menh de quan he khong xac dinh"). Students cannot read it comfortably (RAW-00219: defect, not style). Intermittent: 4 of 9 earlier English runs were unaccented.

## Plan modes
solve only (prompt + det_checks). Ingest, extraction, single-source and pipeline plans are untouched; with `Language: en` or accented replies the output is unchanged.

## Design
### 79.1 prompt (owner: prompts/dev/exam/solve.md rule 2)
Add: "With `Language: vi`, write `solution`, `explanation`, `checks` and `uncertainty.reason` in normal Vietnamese with full diacritics (UTF-8), never unaccented ASCII. English words and terms stay as they are." Only `dev`; releases are frozen.

### 79.2 code check (owner: src/exam_engine/pipeline/verifier.py `det_checks`)
New `_diacritics(ans, exam)` returning `_chk("diacritics", detail, "pass"|"fail", False)`; appended to every non-declined result (also open tasks). Rule: language(exam) == "vi" and the joined text of solution/explanation/checks has >= 4 words from a small unaccented-Vietnamese stopword set (khong, cua, nen, dung, sai, va, la, duoc, cho, voi, mot, nhung, thi, nay) and 0 Vietnamese-accented letters -> fail; otherwise pass. A fail yields a finding via solve_round, status FAIL, so the existing retry loop re-asks (max_attempts) with the finding as review note.
Reuse: `router.language`, `utils.text.fold`. Helper `has_accents(s)` lives in utils/text.py.

### 79.3 retry text
No change: `retry_prompt` already feeds `findings[].message`; detail reads "explanation is Vietnamese without diacritics; rewrite with full diacritics".

## Backward compatibility
`Language: en` and accented replies: check passes, no new finding. Result schema unchanged (a new check kind only).

## Unit tests (tests/unit/test_vi_diacritics.py, stdlib, $0)
1. unaccented vi reply -> fail check; 2. accented vi -> pass; 3. en language -> pass; 4. English words only in explanation -> pass (below the 4-word threshold); 5. solve_round with a fake runner: first reply unaccented, second accented -> final PASS, attempts == 2; 6. prompt contains the rule.

## Risks
False fail on a short unaccented explanation is avoided by the 4-word threshold; a model that keeps answering unaccented ends FAIL after max_attempts (visible, not silent).

## Out of scope
Re-solving other exams (AC4 re-solve of dhqg2024 English is a paid run, coordinator after VERIFIED).
