# Phase 73 - Score the 2025 DGNL sample (TASK-073)
Task: TASK-073 (REQ-0081) · Status: designed.

## Goal
Score `reports/dgnl2025/answers.tsv` against the official answers the user supplied, report accuracy per subject and per status, and check whether the flagged questions hold the wrong answers.

## Constraints
The answer list stays untracked in `input/dgnl/` (git-ignored), used for scoring only; only counts and question numbers are recorded; the engine is not changed in this task.

## Generality
The scoring method is exam-neutral and the same as phase 37 (printed number = id + subject offset).

## Plan modes
Analysis task, no pipeline change.

## Design
Join the answers table with the key by printed number (offsets 0, 30, 60, 90); group by subject, status, reason, source and uncertainty with Wilson intervals; list the wrong answers with their flags; an inspector finds the root causes in the saved prompts, replies and the PDF.

## Unit tests
None (no code); the key is checked for 120 distinct numbers.

## Verification
`work/TASK-073/evidence/dgnl2025-score.txt`; root causes from the inspector report.

## Failure modes
A key oddity looks like a solver error: such cases are labelled "key oddity" only with an independent recomputation.

## Decisions
Engine fixes derived from the findings go to REQ-0083 (separate task).

## Out of scope
Engine changes.
