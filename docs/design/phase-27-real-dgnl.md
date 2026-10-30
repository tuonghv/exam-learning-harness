# Phase 27: the real ĐGNL ĐHQG-HCM 2026 sample exam (REQ-0032)

## Goal
First real exam: `examples/dgnl/De-thi-minh-hoa-2026-Final.pdf` (22 pages, 120 questions: language 60, math 30, science 30; no answer key; third-party copyright, kept untracked).

## Design
- Ingest is free: `ingest` / `ingest-inspect` show what the extractor keeps. Native text loses math symbols and tables, and finds 0 segmented questions, so the plain `--exam-out` path is not usable for math.
- Small slice first: math pages (11-14) through the existing `ingest-refine --real` (vision transcription, `--max-cost-usd`), then the refined questions of a small slice (10 math questions, 61-70) become one exam-format file in `work/dgnl-real/` (header `Subject: Math`, `Exam type: University Entrance (DGNL)`, `Task: Multiple Choice`), solved by the unchanged `solve --real`.
- No key exists: confidence comes from (a) the engine's own checks, (b) my hand computation for each question, (c) agreement between the solve and a second `solve` run where cheap. The report says so, and gives no accuracy figure.
- Copyright: the PDF, its text and the exam file stay untracked; commits carry only code, state, design/report text with question numbers and answers, not the question texts.

## Limits
n=10, math only. Diagram questions (graphs, network figures) depend on vision transcription and may be flagged `needs_review`.
