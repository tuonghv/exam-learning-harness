# Phase 38: ingest numbering gaps and restarts (TASK-038; REQ-0041)
<!-- Nova (designer) - TASK-038 / REQ-0041 draft for docs/design/phase-38-<slug>.md (suggested slug: ingest-numbering-gaps) -->

# Phase 38 - Ingest keeps questions when numbering has gaps or restarts
Task: TASK-038 · REQ-0041 · tier 0, $0 · Status: draft

## Goal
A PDF/DOCX whose question numbers have gaps (1, 150; a 31..60 page slice) or restart per section
(1..10, 1..10) keeps the questions it found, with their printed `n`, plus a warning naming the missing
numbers / the restarts. Seen as `doc["questions"]` present and a `numbering_gap` / `numbering_restarted` warning.

## Root cause (static reading; main to confirm with the repro rows below)
- `src/exam_engine/ingest/segment.py:32-33`: `ok` is True only if `[q.n] == range(1, N+1)` and every
  question has text. 1,150 -> `[1,150] != [1,2]` -> ok False.
- `adapters/pdf.py:324-329` and `adapters/docx.py:203-208`: `qs` non-empty and not ok -> warning
  `segmentation_skipped`; `pdf.py:345-347` / `docx.py:219-221` store `questions` only `if ok` -> all dropped.
- `parts.py:79-85` (page selection `--pages`) has the same rule, so a 31..60 slice is dropped too.
- `api.py:162` `_from_questions` writes `## Question <n>`; the exam parser needs 1..N
  (`pipeline/parser.py:161-164`), so printed numbers cannot go straight to the exam file.

## Must stay unchanged
- `segment.segment()` signature and its `ok` meaning (strict 1..N + text); test `test_ingest_pdf.py:281-291`
  (`["1. a","3. c"]` -> not ok) keeps passing unchanged.
- Consecutive docs: byte-identical doc.json (no new warning, same order) and exam text; gold e2e
  `test_gold_pdf.py:90-99` unchanged. `no_question_numbering` unchanged. Empty-text question -> `segmentation_skipped` as today.
- Refine (`refine.py:221` by_id originals for validation/similarity) behaves exactly as today for any doc
  that today has no `questions` -> the real DGNL refined path is untouched. Prompt (`build_prompt(n)`) does not
  include originals, so no cache key is affected.
- No schema change (no new question field), no solver change.

## Design
### 38.1 numbering check (owner: `segment.py`, new function)
`numbering(qs) -> {"usable": bool, "runs": [[n,...],...], "missing": [[run_idx, "2-149"],...]}`
- Split runs at each question with `n == 1` that is not the first question.
- usable iff every question has text AND either
  (a) one run, strictly increasing (gaps allowed, may start > 1), or
  (b) several runs, each exactly consecutive 1..k (a clean restart).
- Anything else (backward jump not to 1, duplicate, restart run with a gap) -> not usable.
- `missing` = per run, numbers in 1..max(run) not found, compressed to ranges `"2-149"`, `"1-30"`.
- Pure helper `ranges(nums) -> "1-30, 45"` for the message.
### 38.2 adapters keep usable questions (owner: `pdf.py:324-347`, `docx.py:203-221`)
Branch order: `not qs` -> `no_question_numbering` (unchanged); `ok` -> as today; `numbering(qs).usable`
-> store `questions`+`intro` and append warnings (below); else `segmentation_skipped` (unchanged).
- `numbering_gap` (level warning): `"missing question numbers: 2-149"`; with runs `"section 2: missing 4-5"`.
- `numbering_restarted` (level warning): `"numbering restarts at 1: 2 sections (1-10, 1-10)"`.
- Also on case "not usable" with >1 run: add `numbering_restarted` next to `segmentation_skipped`
  (flagged, never silent). Share one helper (e.g. `segment.numbering_warnings(qs) -> [(code,msg)]`) so both
  adapters and parts.py stay identical; adapters wrap with their `_warn`.
### 38.3 page selection (owner: `parts.py:69-85`)
Same branch as 38.2; add `numbering_gap`, `numbering_restarted` to the stale-code filter at `parts.py:70`.
### 38.4 exam text renumbers 1..N (owner: `api.py:154-167` `_from_questions`)
Write `## Question k` (k = 1..N, position). If any `k != n`: add under `## Instructions` (create it if no
intro) one line, same style as `api.py:139`: `Questions are numbered from 1 here; printed numbers: 1=1, 2=150.`
(for restarts `11=s2.1`). Strict docs: k == n, no line -> output identical.
### 38.5 refine guard (owner: `refine.py:221`)
`by_id` built only if `[q.n] == range(1, N+1)`, else `{}` (today's behaviour for those docs).
### 38.6 inspect de-dup (owner: `inspect.py:38-41`)
Skip its own `numbering_gap` row when `doc["warnings"]` already has `numbering_gap`.
### 38.7 guide line (main): `docs/guide/ingest-usage.md:68-69` mention the two new codes.

## Over-segmentation risk
`_Q` (`segment.py:4`) matches any line starting `N.`/`N)`. Today a stray number (a year `2019.`, a sub-list
`1) 2) 3)` inside a question) makes the whole doc skip - safe. After: (a) stray inside the sequence is a
backward jump -> still skipped; sub-list restart `1..5, 1,2,3, 6..` -> restart run has a gap -> skipped
+ flagged; (b) stray AFTER the last question (`..20, 2019.`) is accepted as Q2019 with
`numbering_gap 21-2018` -> visible, not silent. Accepted residual risk; the warning is the guard.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| gap 1,150 | 2 questions kept, n=1,150 | `numbering_gap: missing 2-149` |
| clean restart | all kept, order kept | `numbering_restarted` |
| restart with gap / backward jump | no questions | `segmentation_skipped` (+`numbering_restarted` if runs) |
| stray trailing number | extra question | `numbering_gap` with a big range |

## Unit tests (tests first; tier 0, `tests/unit/test_ingest_pdf.py` + `test_gold_pdf.py`)
1. `numbering`: [1,150] usable, missing "2-149"; [31..60] usable, "1-30"; [1..10,1..10] usable 2 runs;
   [1..5,1,2,3,6] not usable; [3,2] not usable; [1,1] usable? -> 2 runs of 1..1: usable (clean restart).
   Empty text -> not usable. `ranges([2,3,4,9])=="2-4, 9"`.
2. `segment()` old asserts (`:281-291`) untouched.
3. gold-pdf fixture ids {1,150}: ingest -> `[q.n]==[1,150]`, `numbering_gap` msg contains `2-149`,
   no `segmentation_skipped` (AC1).
4. gold-pdf fixture 1..10,1..10: 20 questions, `numbering_restarted` (AC2); variant 1..5,1..3,6 via a
   tiny hand-made DOCX/PDF -> no questions, `segmentation_skipped`+`numbering_restarted`.
5. `select_pages` on a 20-question doc keeping the 2nd half -> questions 11..20 + `numbering_gap 1-10`.
6. `_from_questions`: [1,150] -> `## Question 1`, `## Question 2` + mapping line; parser validate -> no errors;
   strict 1..20 -> text equals today's (golden string).
7. refine: doc with n [1,150] -> `by_id == {}` path (mock llm, similarity uses page text).
8. Consecutive doc: warnings list equal to before (no new codes).

## Verification (main runs; $0)
| Item | command -> expected |
|---|---|
| repro before fix | gold-pdf on gold ids 1,150 into `work/TASK-038/`, `exam.py ingest X.pdf --out d.json`; `jq '[.warnings[].code], (.questions\|length)'` -> has `segmentation_skipped`, `0`/null |
| 38.1-38.2 AC1 | same after fix -> `.questions\|map(.n)` = `[1,150]`, code `numbering_gap` |
| AC2 | gold 1..10,1..10 -> 20 questions, `numbering_restarted` |
| AC3 | `python3 -I -m unittest discover -s tests/unit` -> OK, no edited old asserts (`git diff tests/` only adds) |
| DGNL counts | before/after `jq '[.refined.questions[].id\|select(test("^[0-9]+$"))\|tonumber]\|unique\|[map(select(.<=30)),map(select(.>30 and .<=60)),map(select(.>60 and .<=90)),map(select(.>90))]\|map(length)' work/dgnl-real/refined3.json` -> same 4 numbers |
| DGNL exam files | re-run step 4 of `docs/guide/dgnl-real-exam.md` per subject with `--refined work/dgnl-real/refined3.json --questions 1-30` ... into `work/TASK-038/` -> `diff` vs `work/dgnl-real/e3-<S>.md` empty (check the meta used there first) |
| DGNL native | re-ingest the DGNL PDF to `work/TASK-038/doc.json`: `jq '[.warnings[].code]\|map(select(test("segm\|numbering")))'` and `.questions\|length`; today `segmentation_skipped` (doc.json:10356). Either still skipped or kept with a gap/restart warning; report which, and the `n` list, as over-segmentation evidence |

## Decisions (coordinator; user delegated)
1. Restart with a gap -> skip + flag (chosen, quality first) - rejected: keep all (sub-lists become questions).
2. Exam text renumbers 1..N with a mapping line (chosen; parser needs 1..N) - rejected: refuse export.
3. No `section` field on questions (AC3 no schema change); restart sections are order + warning only.

## Out of scope
Better question regex / multi-column order; extract-eval with duplicate ids on restart docs
(`extract_eval.py:91` raises, unchanged); refine/vision changes; answer-key detection.

## Defects
- D1 (major) `segment.py:32` + `pdf.py:345` / `docx.py:219` / `parts.py:80`: any non-1..N numbering drops
  every found question (only a generic `segmentation_skipped`). Evidence: REQ-0041, TASK-036 report D2,
  `work/dgnl-real/doc.json:10356` (real exam also skipped).
- D2 (minor) `inspect.py:38-41` already computes a `numbering_gap` row but nothing in ingest emits it; after
  38.2 it would duplicate -> 38.6.

4. Coordinator addition (quality): a question number > 999 never counts as a question number (not usable, skipped + flagged as today), so a stray year such as `2019.` after the last question cannot become Q2019. Test: `..20, 2019.` stays skipped.
5. Repro confirmed before design install (work/TASK-038/evidence/repro_gap.txt): gold-pdf ids 1,150 -> ingest gives 0 questions + `segmentation_skipped`; consecutive control gives 5 questions.
