# Phase 37 - Score the DGNL sample against the official answers (TASK-037)
Task: TASK-037 (REQ-0040) · Status: designed.

## Goal
Measure real end-to-end answer accuracy of the saved DGNL runs (120 questions) with the official answers the user supplied, and re-check the worst questions with the current engine.

## Constraints
The answer list is used for scoring only: it stays untracked in `input/dgnl/`, never reaches a solver input, a prompt, a tracked file or a reply beyond counts and question numbers.

## Generality
The scoring method is exam-neutral (key parsed into {number: letter}; subject offsets stated and verified by option text).

## Plan modes
Analysis task, no pipeline change.

## Design
A read-only inspector scores each saved run per subject (answered, declined, correct, wrong, silent wrong PASS, lost correct) and maps subject files to printed numbers; the worst questions are re-solved with the current engine from the refined window text (Source pages, image scope declined) and the three remaining wrong answers get a root-cause check against the PDF.

## Unit tests
None (no code); counts cross-checked in the report.

## Verification
`work/TASK-037/evidence/dgnl-score.txt` and the re-solve results in `plans/dgnl-retry/` (not tracked).

## Failure modes
Mapping offsets that do not match by text (Math symbols) are stated as lower confidence; a rate-limit message in a saved run is an infrastructure failure, not a wrong answer.

## Decisions
Value answers equal to the keyed option are counted correct after mapping to the letter (strict letter matching is also reported).

## Out of scope
Extraction-only gold (REQ-0078), engine changes (REQ-0079, REQ-0080).
