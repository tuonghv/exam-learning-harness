# Phase 60 - Quality solve path (TASK-060)
Task: TASK-060 (REQ-0066, RAW-00183/184) · Status: designed
## Premise (facts at HEAD 16b883e)
- Cause table (work/TASK-060/handoff/failures.md, 42 non-pass rows; no proven wrong answers; DGNL has no key):
  qa_false_alarm 23, other 6, cut_question 5, parse_ocr 3, missing_visual 3, solver_reasoning 2.
- qa_false_alarm splits into 4 mechanisms (from result.json `status_reason`):
  F1 `check_failed: format` 7 (sci 97-107): MC with numeric options; solver replied the option value (e.g. "230%", or
  value + "(rounded ...)") instead of the letter; `verifier._format` needs `^[A-D]$` (verifier.py:58-60). Deterministic.
  F2 `check_failed: quote` 3 (vi 20, t040 q2/q4): diacritic-insensitive + elided quote route already landed (phase 49,
  verifier.py:148-168); these runs predate it. Only a free re-check is needed.
  F3 `solver_uncertainty_not_low` / `reviewer_unsure` / doubt 9 (vi 9,11,27,28; en 37,56,59; t040 q10; trial 17):
  decision.py:33-36; same-family QA cannot clear them; needs a second read from another input channel.
  F4 refine `needs_review` 4 (6, 67, 89, 67-window): refine.py:503 sets one bool (unreadable | sim<min | gap), no reason.
- Phase 59 image check exists (engine.py:120-212): trigger = `visual_flags` only; `skip` (marker/cut declines) excluded
  (engine.py:126, phase-59 G4). apply_image (engine.py:145) already reconciles text vs image (same / differ / image-only).
- Solve path has no reply cache (grep: only refine ReplyCache, key = model+prompt+image sha, refine.py:273) -> prompt
  changes here cannot reuse stale answers. FLAGGED_RULES live in code (cross.py:25), not in prompt version (59 G3).
- Cost basis (measured): text solve ~0.31 USD / 30-q subject (run3-Math, 4 calls) -> ~1.25 / 120-q DGNL exam;
  image call 0.03 + 0.035*pages (59 header); single page 0.04-0.08, window 0.07-0.11.
## Goal
Fewer false non-passes and fewer blocked questions per exam, visible in `run-stats` (phase 56) per cause:
`uncertain_by_reason["check_failed"]` drops by F1+F2 on saved runs at 0 USD; cut/visual declines get an image answer;
doubt ids carry a second-read verdict. No answer may change silently (every change leaves a finding).
## Options compared (cost per DGNL exam ~120 q / 4 subject files; trial 22 q = 1 file)
| Opt | What | Extra cost / exam | Expected gain (rows of 42) | Risk | Proving measurement |
|---|---|---|---|---|---|
| A | Deterministic QA fixes: value->letter map (F1), re-check quotes (F2), needs_review reason codes (F4) | 0 | F1 7 + F2 3 cleared; F4 4 made measurable (not cleared) | mapping picks wrong option when two options share a number (guard: unique match) | `run-stats recheck` on run3-Science + run-21-25: `check_failed` 7->0, 2->0; `answer_mapped` 7 |
| B | Image check also for cut/declined ids (59 trigger + `skip` + solver_declined) | +1 image call per subject with targets, <=4 pages: 0.10-0.17; ~0.2-0.45 / DGNL | cut 5, missing_visual 3 -> answered from page (trial 10/18 already proven in t059) | wrong page / key-page leak (guard exists: answer_key_page); image answer stays UNCERTAIN no_review | `image_answered` up, `declined` down; trial key: points of 10/18 |
| C | Second read for doubt ids via the same image call (other channel than parsed text) + optional adjudication for differs | shares B's call if pages fit cap; else +0.10-0.17 / subject (~0.4-0.7 / DGNL); adjudication +0.04-0.08 per differ | F3 9 get `image_agrees` (proxy, not PASS); solver_reasoning 2 surfaced as `image_differs` | same model family -> correlated agreement; page cap drops ids | new `image_agrees` / `image_differs` counts; on trial key: agree rows key-correct |
| D | Per-question parse verification vs page image (all pages) | 0.04-0.08 x ~25-30 pages = 1.0-2.4 | parse_ocr 3; could clear F4 4 | highest cost; vision also drops diacritics; duplicates refine | diff parsed vs image text per q; famB/famC synthetic recall |
| E | Flawed-source flag (other 6) | 0 (prompt field) | 6 labelled, not solved | prompt version change | `flawed` count in metrics |
Recommendation: A -> B -> C (one shared image call) -> measure -> D only for OCR-route pages after REQ-0065. E out of scope.
## Plan modes
Single-source and pipeline plans: unchanged by default (`--image-scope flagged`); the slow path is opt-in per run. 60.1-60.3 and 60.7 change text-route checks and metrics only; old inputs keep byte-identical prompts. Cross-solve unaffected.

## Design
### 60.1 Option value -> letter (owner: new pure `verifier.option_for_value(answer, options) -> letter|None`)
- Strip a trailing `(...)` note and trailing `.`; take the first number (`_answer_number`); a candidate option has exactly
  one number; match when numbers equal (`,`/`.` folded, `%` and unit text ignored). Exactly one match -> letter, else None.
- Called in `solver.solve_round` (solver.py:172, before det_checks) and `engine.apply_image` (engine.py:166) only when
  `q["options"]` and the answer is not `^[A-D]$`: set `a["answer"]=letter`, finding
  `deterministic/answer_mapped: "<orig[:40]>" -> <L>`. None -> unchanged (format still fails, detail
  `single letter A-D (value not among options)`).
### 60.2 Saved-run recheck (owner: `cli._rs_recheck`, new sub `recheck` in run-stats choices cli.py:1300)
- `run-stats recheck RESULT_DIR --exam F [--json]`: for each saved question with `check_failed:*`, apply 60.1 then
  `verifier.det_checks` on the saved answer; prints TSV `id old_reason new_code_result mapped` + counts
  `cleared N still_failed M`. Read-only (writes nothing); no LLM.
### 60.3 needs_review reason (owner: refine.py:503 and :551, :359, :370)
- Add `needs_review_why: [unreadable|similarity|gap|orphan_page|joined_page]` beside the bool (optional field, schema
  optional). metrics.compute: `needs_review_by_why` when given. Thresholds unchanged (no ground truth yet).
### 60.4 Image scope: cut/declined (owner: `engine.image_targets`, engine.py:120; `image_check` :186)
- New arg `scope` (cfg `image_scope`, CLI `--image-scope flagged|declined|doubt`, default `flagged` = today).
- `declined`: candidates = flagged ∪ skip ∪ {ids whose final reason starts `solver_declined`}; skip ids no longer
  excluded (59 G4). Same page/key/cap rules; order: skip ids first (blocking), then declined, then flagged.
- apply_image row "declined/open + image answered" (engine.py:164) also covers skip ids; their reason
  `solver_declined: missing_text` is replaced only by an image answer. FLAGGED_RULES gains one line: "a question may
  continue on the next attached page".
### 60.5 Image scope: doubt (owner: same + `apply_image`)
- `doubt` = `declined` ∪ {answered ids with reason in solver_uncertainty_not_low, reviewer_unsure, reviewer_disagrees,
  no_review}; lowest priority under the page cap. One call total (union of pages, `--max-image-pages`, default 4).
- apply_image same-answer row: add finding `image/image_agrees` (status unchanged; agreement is a proxy, not PASS).
  Differ row unchanged (`needs_review: text/image differ`).
### 60.6 Adjudication (stage 2, optional, owner: new `cross.adjudicate_prompt(exam, items)`; flag `--adjudicate`)
- Only for `image_differs` ids: one text call with question text, both answers + both explanations, asks for one
  answer + why. Result: finding `adjudicated: <L>`; answer = adjudicated; status stays UNCERTAIN `needs_review: adjudicated`.
  `call_cap` +1 only with the flag. Build only if 60.5 paid run shows >= 1 differ.
### 60.7 Metrics (owner: metrics.compute :120, block :286; add rows, rename none)
- counts: `answer_mapped`, `image_agrees`, `image_differs` (exists in 59.5 wording), `image_scope`, `needs_review_by_why`.
  None when absent, so old results and backfill are unchanged.
## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| two options hold the answer's number | no mapping | format fail, `value not among options` |
| answer number in no option | no mapping | same, QA sees value answer |
| page cap reached | lowest-priority ids skipped | finding `image_skipped: page_cap` |
| cut question's continuation page not in `q.pages` | model declines per rules | reason `... image: <why>` |
| key page in union | id skipped | `image_skipped: answer_key_page` |
| image answer differs | text kept, UNCERTAIN | `needs_review: text/image differ` |
| recheck exam ids do not match result | rows skipped | `unmatched N` |
## Unit tests (tier 0, mock LLM, synthetic text only)
1. option_for_value: "230%" vs options "230%." -> C; value + "(rounded ...)" -> letter; "12,7" vs "12.7%/yr" -> letter;
   two options with same number -> None; option "2 and 3" never matched; letter answer untouched.
2. solve_round: mapped answer -> format pass, finding `answer_mapped`; key scoring sees the letter.
3. recheck: fixture result with 2 `check_failed: format` + 1 `check_failed: quote` (folded) -> cleared 3; no file written.
4. needs_review_why: similarity-only and gap-only fixtures give the right code; bool unchanged.
5. image_targets scope: flagged = 59 golden (unchanged); declined includes skip ids; doubt adds uncertain ids last; cap.
6. apply_image: skip id + image answer -> source image, reason no longer missing_text; same answer -> `image_agrees`.
7. metrics: new counts None on a pre-60 result; set on a 60 fixture; block line shows them.
8. no `--image-scope` / no `--pdf`: prompts and result.json byte-equal to pre-change run (golden).
## Verification
| Item | command -> expected | tier |
|---|---|---|
| 60.1-60.7 | `python3 -I -m unittest discover -s tests/unit` -> OK | 0 |
| 60.1+60.2 F1 | `scripts/exam.py run-stats recheck work/dgnl-real/run3-Science --exam work/dgnl-real/e3-Science.md` -> cleared 7 (97-107), mapped 7 | 0 |
| 60.2 F2 | same on work/TASK-040/real/run-21-25 and run3-Vietnamese -> quote rows cleared 3 | 0 |
| 60.3 | mock ingest-refine fixture -> needs_review_why present; run-stats shows by_why | 0 |
| 60.4/60.5 dry | `solve <slice> --pdf <doc.json> --image-scope doubt --dry-run` -> image prompt lists skip ids first, est. cost | 0 |
### Paid items (user go each; caps are hard `--max-cost-usd`)
- P1 (60.4): DGNL-vi slice with 10, 23, 24, 25 + DGNL-math 66, `--image-scope declined` -> >= 3 of 5 answered from image;
  cap 0.60 USD. Trial slice Q10/Q18 key-correct regression, cap 0.30.
- P2 (60.5): DGNL-vi 9, 11, 27, 28 + DGNL-en 37, 56, 59, `--image-scope doubt` -> each id has image_agrees or image_differs;
  cap 0.80. Trial full exam with key `--image-scope doubt` -> no key-correct answer regresses, cap 0.50.
- P3 (60.6, only if P2 has a differ): `--adjudicate` on those ids, cap 0.30. Total cap 2.50 USD.
## Decisions (coordinator, confirmed)
1. Order A -> B -> C -> measure -> D. A is free and removes ~10/23 false alarms; B targets every blocking defect; C reuses
   B's single call. Rejected: D first (1.0-2.4 USD/exam for 3 rows); text re-solve for C (same input, same model,
   correlated; the image is a different channel and also catches parse errors).
2. Second read never makes PASS (PASS needs an independent check; same family, phase 56). It is a labelled proxy.
3. Code mapping (60.1) over a prompt change "answer the letter": free, no prompt-version bump, works on saved runs.
4. Defaults unchanged (`--image-scope flagged`); slow path is opt-in per run so cost is the user's choice.
5. D deferred to OCR-route pages with per-word doubt (REQ-0065); E (flawed flag) out of scope here.
6. (coordinator, RAW-00186) Paid checks P1-P3 are run by the coordinator one at a time inside their own caps (P1 0.60+0.30, P2 0.80+0.50, P3 0.30); the user is told afterwards, not asked, unless a cap must rise.
7. Order of work: 60.1-60.3 and 60.7 first (free, proven on saved runs), then 60.4-60.5, 60.6 only if P2 shows a differ.
## Out of scope
D (full parse verification), E (flawed-source flag), threshold tuning for needs_review, new models.
## Defects
- D1 (major, verifier.py:58-60 + solver.py:172): MC answer given as the option value fails format -> 7 correct-looking
  sci answers UNCERTAIN `check_failed: format` (run3-Science result.json:336,391,451,546,601...).
- D2 (major, engine.py:126 + :287): marker/cut-declined ids never reach the image check (59 G4) -> cut questions stay
  declined even with `--pdf`.
- D3 (minor, refine.py:503): needs_review has no reason code; 4 of 6 DGNL flags were false (needs_review_vs_extraction.txt:12)
  and cannot be told apart.
- D4 (minor, review.py:169-173): `value_letter` needs exact text equality; misses value + trailing note answers.
