# Phase 70 - Route-B structure and generic dev prompts (TASK-070)
Task: TASK-070 (REQ-0070) · Status: designed. Slice B of `docs/design/phase-62-exam-kind-generality.md` (62.7, 62.8); groundwork `work/REQ-0070/handoff/prep.md` (inspector).

## Goal
The cross-solve route-B image prompt and the dev solve/verify prompts no longer fix one exam kind ("Part I 1-12, Part II 1-4", "Vietnamese Grade 12 ... Mathematics, Physics, English, Literature"); structure comes from the route-A headings and subject, level and language come from the exam header.

## Constraints
Dev channel prompts only (`prompts/dev`); `prompts/releases/` is frozen. Old inputs: the route-A and solve prompts change only in the named sentences. Stdlib only. No test pins the IMAGE_RULES or system.md wording today (prep.md), so new tests pin the new behaviour.

## Generality
No exam-specific literal in code or prompt wording; the part structure is derived from headings found in the text (`ingest/segment.py` heading helpers), with a generic fallback "Printed numbering may restart per part or section."

## Plan modes
Cross-solve route B (cross.py), dev prompts for solve/verify. Release channel and `solve` prompt assembly code unchanged.

## Design
- 70.1 (= 62.7) `cross.structure_hint(text)` builds the part/number span hint from route-A headings; `IMAGE_RULES` takes `%s` for it and the sentence "Answer every question, Part II and III included." becomes "Answer every question in every part."; `route_b_prompt(exam, text=None)` callers at cli.py (dry-run) and cross.py pass the text they hold. Trial exam: the hint must list the same spans as the old literal (checked against the input headings).
- 70.2 (= 62.8) generic wording in `prompts/dev/system.md:1-2`, `lang/vi/system.md:1-2`, `verification/verify_answer.md:1-2`, `exam/solve.md:11` and `lang/vi/exam/solve.md:11` (open task = essay/rubric, not "Literature"). `genexam_qa.md` (per profile, pinned by test_generality_golden) and `ingest/refine.md` (no matching wording) stay.

## Unit tests
Synthetic exams: headings `SECTION 1/2`, `PART I/II/III`, no heading (fallback), non-Vietnamese header; the trial exam hint equals the old literal spans; dev prompts contain no fixed subject list; golden: other prompt bytes unchanged.

## Verification
Free: unit suite; `cross-solve --dry-run` before/after diff (only the IMAGE_RULES delta); dev prompt diff = exactly the changed sentences. Paid (coordinator, cap 0.60 USD): one `cross-solve --real` on the trial exam against the key (pass = no new disagreement with the last run) and one dev solve check on the keyed regression set (cap 0.60; verdicts equal to run 3 apart from the known malformed flake).

## Failure modes
No heading found: generic fallback, never a guessed structure; unreadable text: route B prompt without the hint; header lacks subject: generic line.

## Decisions
Dev channel only, so no release bump; wording is generic and shorter, which also lowers tokens.

## Out of scope
Release prompt rewrite; per-subject prompt files.
