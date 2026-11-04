# Phase 72 - Solve the second DGNL sample exam, 2025 (TASK-072)
Task: TASK-072 (REQ-0077) · Status: designed (run plan).

## Goal
Run the current pipeline on `input/dgnl/2-De-minh-hoa-gioi-thieu-2025-final.pdf` without exam-specific code and report coverage, flags and cost; score it when the user supplies the answers.

## Constraints
Outputs only in git-ignored `plans/dgnl2025/` and `reports/dgnl2025/`; stage caps: refine 1.50 USD, solve 0.80 USD per subject; the PDF has no answers inside (inspector); answers must never reach a solver.

## Generality
No new code: layout inspected free (pages 1-5 intro, 6-20 exam, 120 questions, PHẦN headings, shared passages announced by "Dựa vào thông tin dưới đây", English blocks "Questions X-Y"), subjects split by question range.

## Plan modes
Pipeline run; refine with `--all-pages` and windows, then `ingest --refined --questions RANGE` per subject, `solve --pdf --image-scope doubt`.

## Design
72.1 `ingest-refine --pages 6-20 --all-pages --real --cache`; 72.2 four exam files (Vietnamese 1-30, English 31-60, Math 61-90, Science 91-120) with Source pages; 72.3 four solves with the page-image check on doubtful questions; 72.4 answers table `reports/dgnl2025/answers.tsv` for the user's later comparison.

## Unit tests
None (run task).

## Verification
Counts from the refine and solve logs and result.json files; no accuracy claim without answers.

## Failure modes
Cut questions use the window recovery; cap reached stops a stage and says so.

## Decisions
`--image-scope doubt` is used on all subjects to gather the agreement signal (REQ-0079 evidence).

## Out of scope
Scoring (needs the user's answers), engine changes.
