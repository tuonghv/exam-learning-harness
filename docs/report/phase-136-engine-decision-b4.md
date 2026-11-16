# Phase 136 – engine.py and core/decision.py (batch 4)

Scope: src/exam_engine/engine.py (all functions), src/exam_engine/core/decision.py (all functions)

## Findings

### F001 – [MEDIUM] Failed retry round re-reviews unchanged answers

- File: src/exam_engine/engine.py
- Lines: 490-492
- Type: BUG
- Trigger: off-prompt LLM reply
- Reached via: `exam-engine solve` -> run() -> solver.solve_round() / verifier.qa_round()
- Issue: qa_round runs for all retry ids even when the retry solve call failed or was malformed and left every answer unchanged.
- Case: round 1 answer B, reviewer disagrees (FAIL); retry reply malformed -> second paid QA call on B, duplicate `ai_review` check, an `agree` flips it to PASS.
- Fix: before solve_round keep `prev = {i: recs[i]["ans"] for i in ids}`; pass qa_round only ids where `recs[i]["ans"] is not prev[i]`.
- Fix risk: mock fixtures that queue a QA reply after a failed retry reply consume one reply less.

### F002 – [MEDIUM] Adjudicated answer keeps review and checks of the replaced answer

- File: src/exam_engine/engine.py
- Lines: 272-277
- Type: BUG
- Trigger: normal input
- Reached via: `exam-engine solve --pdf --adjudicate` -> image_check() -> adjudicate() -> scorer.apply_key()
- Issue: `r["ans"] = g` leaves `review`, `code_checks`, `checks` of the old text answer (apply_image resets them at 230-232).
- Case: text B reviewed `disagree`, image C, adjudicated C, key C -> apply_key calls decide_rec -> FAIL `reviewer_disagrees` for the correct answer.
- Fix: when `not keep_fail`, set `r["review"] = None`, `r["code_checks"] = verifier.det_checks(q, g, exam)`, `r["checks"] = list(r["code_checks"])` before setting status.
- Fix risk: tests asserting old checks after adjudication; a key match then gives `no_review` instead of PASS/FAIL.

### F003 – [MEDIUM] Image and adjudicated answers skip the option value-to-letter mapping

- File: src/exam_engine/engine.py
- Lines: 213-214, 230-231
- Type: BUG
- Trigger: off-prompt LLM reply
- Reached via: `exam-engine solve --pdf` -> image_check() -> apply_image()
- Issue: solver.solve_round maps an option value to its letter (60.1); apply_image compares and stores the raw image answer.
- Case: text answer B (option B = 12), image answer "12" -> `image_differs`, PASS becomes UNCERTAIN (plus an adjudication call); a declined text gets FAIL `check_failed: format`.
- Fix: in apply_image, when `qs[i]` has options and `g["answer"]` is not `^[A-D]$`, replace it with `verifier.option_for_value(g["answer"], qs[i]["options"])` when that is not None; same for `g` in adjudicate line 266.
- Fix risk: none.

### F004 – [MEDIUM] A real answer "open" is treated as the open-task sentinel

- File: src/exam_engine/core/decision.py
- Lines: 18-19, 26-28
- Type: BUG
- Trigger: normal input
- Reached via: `exam-engine solve` -> run() -> decide_rec() / retry_ids() / scorer.apply_key()
- Issue: is_open matches any answer whose norm is "open", for every task type.
- Case: gap-fill "Keep the door ____", solver answers "open", key "open" -> UNCERTAIN `open_task_no_rubric`, no retry, score `points: None` (question not counted).
- Fix: in scorer.apply_key line 163 skip the comparison for `is_open(a)` only when the key final is None or "Open (rubric)"; otherwise call score().
- Fix risk: an essay answered "Open" against a non-rubric key now scores 0 `differs_from_key`; tests on "no key comparison" may need that case.

### F005 – [LOW] Image miss overwrites the incomplete-marker reason

- File: src/exam_engine/engine.py
- Lines: 246-248
- Type: BUG
- Trigger: normal input
- Reached via: `exam-engine solve --pdf --image-scope declined` -> image_check() -> apply_image()
- Issue: for a marker-skipped question the reason set at run() line 480 is rebuilt from `flags` only.
- Case: reason `solver_declined: missing_text (options cut)`, image reply omits the id -> `solver_declined: missing_text (image: not in reply)`; the marker reason is lost from result.json.
- Fix: when `r["reason"]` starts with `solver_declined: missing_text (` and ends with `)`, insert `; image: <why>` before the closing `)` instead of rebuilding.
- Fix risk: tests asserting the exact rebuilt reason string for skipped ids.

## Summary

- Total findings: 5 (CRITICAL 0, HIGH 0, MEDIUM 4, LOW 1; BUG 5, HARDENING 0)
- Cap hit: no
- Not reviewed: none
