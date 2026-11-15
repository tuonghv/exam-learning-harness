PROGRESS: COMPLETE
SKILLS: design, token-efficiency, review-loop
# Phase 110 - review pack fixes (draft for docs/design/phase-110-<slug>.md; slug proposal `review-pack-marks-safe`)
Task: TASK-110 · REQ-0117 · Status: draft

## Premise
- Source: triage `docs/design/phase-107-review-triage.md` rows 111-F004..F007; traces `work/TASK-107/handoff/design-pipeline.md:25-28`.
  Review report `docs/report/phase-111-review-report-kinds.md` is advisory (RAW-00330); each claim re-checked against `src/exam_engine/pipeline/review.py` (R:).
- Shared root of F004/F006/F007: `parse_subject` (R:233-259) gives a section whose heading fails HEAD_RE (R:25) either
  `n=None` (LOOSE_RE R:26 fails, e.g. `## Question 5`) or `answer="-"` (`bad=True`, number kept). Callers trust `n`/`answer`
  anyway: `pack` drops n None and duplicate n (R:323), `apply` formats `%d` of None (R:459), `pack` compares the
  placeholder `-` (R:359). Fix = callers treat "no trusted identity / no trusted answer" explicitly; parse_subject's row
  shape is kept (callers: pack, write_index R:396, apply R:445). Three call sites -> three items, one per REQ AC.
- Real pack `review/dgnl-2026-sample/{Science,Math,English,Vietnamese}.md`: 120 `## ` headings, all 120 match HEAD_RE
  exactly (grep counts equal), so `bad=False`, no n None; every fix below is gated on `bad`/`n None`/duplicate/`.old.md`
  -> these files parse, index and apply byte-identically (checked by 110.5).
- No cache involved (review pack is post-solve file I/O); no new inputs, flags or config.

## Plan modes
- single-source solve plan: not affected (review.py not on the solve path).
- pipeline solve plan: not affected; only `exam.py review-pack` / `review-apply` output changes, and only for the fixed cases.

## Generality
All exam kinds; no exam-, subject- or language-specific literal. Tests use the synthetic `X1` exam of `tests/unit/test_review.py`.

## Known incidents
none

## Design
### 110.1 Re-pack never drops marks of unnumbered or duplicate sections (F004, AC1) (owner: `pack`, R:319-345)
- After R:322 compute `orphans`: marked rows (`_is_marked`) with `n is None`, or whose `n` occurs on more than one row
  of `rows`. Labels: `"?"` for n None, `str(n)` for a duplicate (sorted, unique).
- R:339 condition becomes `if lost or orphans:`; same branch (write `<subject>.new.md`, keep the old file, `old = {}`).
- Message: `why = []`; lost -> `"Q%s not in the new pack" % ",".join(...)` (today's text); orphans ->
  `"Q%s unnumbered or duplicate heading" % ",".join(labels)`; msg = `"kept your marks in %s.md (%s); wrote %s instead" %
  (subject, "; ".join(why), path)`. Pure-lost message stays byte-identical (test R test_review.py:143-144).
- Unmarked n None / duplicate sections keep today's behaviour (merge; e.g. test_d4 `## my own section`).
- Risk: a user who duplicated a heading on purpose now gets `.new.md` until the heading is fixed (safe direction, message says why).

### 110.2 review-apply does not raise on a section without a number (F006, AC2) (owner: `apply`, R:453-459)
- `lab = "?" if r["n"] is None else r["n"]`; R:453 `tag = "%s Q%s" % (sub, lab)`; R:459 `dl.append("Q%s%s" % (lab, ...))`.
- Nothing else: R:454-455 already reports the section in `secbad` -> `unparsed section (unnumbered ...)` line and
  `- unparsed section:` in improvements.md (= "reported as unmatched"). Counts e/s unchanged (the tick is still counted).
- Output change only for n None rows: tag `S QNone` -> `S Q?` (was garbage, fixed case).

### 110.3 Edited heading with the same answer gives no "Answer changed" (F007, AC3) (owner: `parse_subject` R:243, `pack` R:356-361)
- parse_subject: when `not m and lm`, recover the answer from the edited heading with
  `ANS_LOOSE_RE = re.compile(r"\banswer\s+(\S)(?:\s|$)")` (module constant next to LOOSE_RE); set `answer` only if found.
  `bad` stays True (INDEX `heading_edited`, apply `heading edited` unchanged).
- pack: `known = not o["bad"] or o["answer"] != "-"`. Replace R:357-361 by:
  `if o["changed"] and (not known or o["answer"] == h["answer"])`: keep `o["changed"]`;
  `elif known and o["answer"] != h["answer"]`: new line + `changed += 1`. So an unrecoverable answer never yields a change line.
- Rows with HEAD_RE match (`bad=False`): identical to today.
- Risk: INDEX/apply rows of edited headings now show the recovered answer instead of `-` (fixed case only).

### 110.4 Backup files are not subjects (F005, AC4) (owner: `_subject_files`, R:301-303)
- Skip names ending `.new.md` or `.old.md` (`f.endswith((".new.md", ".old.md"))`); these are the only two backups pack writes (R:331, R:340).
- Used by write_index (R:394) and apply (R:442): both stop listing `S.old`.
- Risk: a subject literally named `X.old`/`X.new` is hidden; already true for `.new` today. Reserved names = 111-F009, out of scope.

### 110.5 Real pack unchanged (AC5) - verification only, no code
Old (HEAD) vs new review.py on a scratch copy of `review/dgnl-2026-sample/`: parse_subject rows, write_index INDEX.md,
apply (lines, summary) and improvements.md are byte-identical.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| Marked section heading loses its number | `.new.md` written, old file kept | message `Q? unnumbered or duplicate heading` |
| Two headings share a number, one marked | same | `Q12 unnumbered or duplicate heading` |
| `[x] defect` under unnumbered heading | apply completes | `S Q?` in defects + `unparsed section` line |
| Edited heading, answer token deleted | no change line, old `Answer changed` kept if any | INDEX `heading_edited` |

## Unit tests (tests/unit/test_review.py; helpers pack/fill/tick/q/read/run_cli)
- PackTests.test_110_1_unnumbered_marked_kept: pack A [q1,q2]; fill Q2 `tick("ok")`; rewrite `## Q2  p.-...` heading to
  `## Question 2`; re-pack -> msg has `A.new.md` and `Q? unnumbered or duplicate heading`; A.md still has the mark.
- PackTests.test_110_1_duplicate_marked_kept: fill Q2 `tick("defect")`; rename heading Q1 -> Q2 (two Q2); re-pack ->
  `.new.md`, msg `Q2 unnumbered or duplicate heading`, both sections still in A.md.
- PackTests.test_110_1_unmarked_unnumbered_merges: append `## my own section` (no review line); re-pack -> `merged 1`, no `.new.md`.
- ApplyTests.test_110_2_defect_in_unnumbered_section: pack A [q1]; heading -> `## Question 1`; review `tick("defect", note="x")`;
  `review.apply("X1", out)` returns; lines contain `extraction defects: Q? (x)` and `unparsed section`; improvements.md has
  `A Q?` and `- unparsed section: A`. (= repro design-pipeline.md:27)
- PackTests.test_110_3_edited_heading_same_answer: pack A [q(1,"A")]; fill `tick("ok")`; heading -> `## Q1 p.- PASS answer A conf low`
  (single spaces); re-pack same result -> no `Answer changed` in A.md, msg lacks `marked answers changed`, `merged 1`.
- PackTests.test_110_3_edited_heading_real_change: same, re-pack with q(1,"C") -> `Answer changed: was A now C`, count 1.
- PackTests.test_110_3_edited_heading_no_answer_token: heading -> `## Q1 edited` -> no change line, count 0.
- Unit: `parse_subject("## Q5 p.1 PASS answer A conf high\n")[0]` -> n 5, bad True, answer `A` (repro.py:20 now answer A).
- ApplyTests.test_110_4_old_backup_not_subject: write `X1/A.md` and `X1/A.old.md`; `_subject_files` == [`A.md`];
  apply summary keys == {`A`}; INDEX.md has no `A.old`.
- Existing test_d4 / test_d6 / test_c_qa_line_and_old_format / lost test (test_review.py:136-147) pass unchanged.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 110.1-110.4 | `python3 -I tools/run_tests.py --affected` then `--fast` -> NEW 0, new tests pass | $0 |
| repro | `python3 -I work/TASK-107/repro.py` -> rows 111-F004/F007 no longer BUG (F004 repro asserts parse n None: still None by design; judge by test_110_1) | $0 |
| 110.5 | main: `git show HEAD:src/exam_engine/pipeline/review.py > <scratch>/old_review.py`; copy `review/dgnl-2026-sample` to two scratch dirs; run write_index + apply + parse_subject per file with old and new module; `diff -r` the dirs and compare returned (lines, summary) -> identical | $0 |

## Decisions
- 110.3 recover the answer from the edited heading (chosen) vs review's "skip compare when bad" (rejected: hides a real
  answer change on one re-pack, after which the heading is regenerated and the flag is gone).
- 110.1 route orphans to the existing `.new.md` branch (chosen) vs merging by position (rejected: guesses identity).
- 110.2 format fix only (chosen) vs `continue` for n None (rejected: drops the tick from counts; more output change).
- Items split per AC although F004/F006/F007 share one root: the fixes live in three call sites with separate behaviours.

## Out of scope
111-F001/F002/F003/F008/F009 (IMPROVEMENT/cosmetic), LOOSE_RE widening (`## Question 5` stays unnumbered; flagged, not guessed).

## Defects
- 110-D1 (low) work/TASK-107/repro.py:19 asserts the F004 bug as `n == [None]`, which stays true after the fix (n None is
  correct parsing); the regression is the re-pack outcome (test_110_1), not the parse.
