---
name: exam-extraction
description: Rules for turning an exam source (PDF, page images, DOCX) into whole questions before solving. Use when ingesting, refining, re-extracting, reviewing extraction output, or when a question is declined with missing_text. A question that spans pages is one unit; never solve a fragment.
---

# Exam extraction

A question is ONE unit however many pages, images, tiles or DOCX breaks it spans: stem, shared passage, figure/table, options. Solving a fragment is wrong; completing it or declining it is right.

## Rules
1. Assemble first, solve later. After extraction every question must pass the completeness check (`core/refcheck.py`: 4 options, referenced paragraph/figure/table present, no unresolved cut).
2. PDF / images: per-page vision. `carry` hands a passage FORWARD; `continues` hands the top-of-page remainder BACKWARD to the last question of page N-1 only (never to an older question, never to a later one). Chains over any number of pages.
3. Always select the page before a continuation (`--pages` N-1..N). An `orphan_continuation` warning means: re-run with page N-1.
4. DOCX: file order already joins page/section breaks, tables and inline images; text boxes are read inline. Anything still unread -> the completeness check declines the question.
5. Never repeat text, renumber questions or move content to another question to fill a gap.
6. Figures/tables: describe kind and all values needed under `figures`; a question that refers to a figure needs one.
7. Incomplete after assembly -> `[Incomplete: missing_text ...]`, the solver declines with `solver_declined: missing_text`. Never guess an answer from a fragment.

## Check before claiming it works
- Printed question counts per section unchanged; clean questions byte-identical.
- Compare the blocked questions with an independent read of the source pages (a verifier role reading the PDF, not the engine output).
- Read `ingest-inspect`: "extraction suspects" and `missing_text` declines are the to-do list; zero left or each one explained.

## Does not
Copy question text into the repo or reports (cite printed numbers, pages, statuses); run paid vision calls without the user's go and a cost estimate (about $0.04 per page).

Prompt rules, engine code and this list must stay identical: change one, update all three. Detail: docs/design/phase-40-multipage-question-assembly.md, docs/guide/ingest-usage.md.
