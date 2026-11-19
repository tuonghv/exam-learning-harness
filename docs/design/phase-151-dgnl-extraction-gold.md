# Phase 151 – DGNL extraction gold, 40 questions (TASK-151, REQ-0078)

Source: REQ-0078 (RAW-00197; RAW-00387 start; RAW-00388 option A, 40 questions).

## Plan modes
Read-only on plans (published solver inputs); no solve, no paid call. Writes only `work/TASK-151/` and, after the
user's corrections, `evals/extract/gold/dgnl-real-001.json`.

## Design
- 151.1 `tools/extract_gold_draft.py` (stdlib + optional PyMuPDF for page images):
  - Source: `config/published_reports.json` plan runs; each `input/exam.md` parsed with `pipeline.parser.parse_exam`
    (stem `text`, `options`, `pages`), printed numbers from `input/assembly.json`; PDF = the key path with `.pdf`.
  - Sample: questions with a stem and >= 2 options; stratified evenly over the 3 exams (14/13/13), seeded
    (`--seed 151`), sorted by exam and printed number. Shared passages and figures are out of scope (stated).
  - Ids: `<yy><printed:03d>` (e.g. 26061) so one file holds all exams; extra keys `exam`, `subject`, `printed`.
  - Writes `extracted.json` (what the solver saw) and `gold-draft.json` (same text, `checked: false`) in
    extract-eval's question format (`text`, `formula: ""`, `options`, `figures: []`, `pages`).
  - `review.html`: per question the PDF page image(s) (JPEG, deduplicated) beside editable stem and options, a
    "checked against the page" box, edits kept in localStorage (try/catch), "Download gold JSON" builds the
    corrected gold (`checked` per question). Rule on the sheet: fix content (digits, words, diacritics, signs,
    missing/extra text, option letters), keep the plain-text math notation used by the extraction.
- 151.2 User corrects in the browser and saves the JSON; coordinator stores it as
  `evals/extract/gold/dgnl-real-001.json` (refuses if any question is unchecked).
- 151.3 Score: `exam.py extract-eval evals/extract/gold/dgnl-real-001.json work/TASK-151/extracted.json --out
  work/TASK-151/eval` -> exact-match per field, n=40, Wilson 95%; report states the limits.

## Verification
Unit tests on a synthetic exam.md/assembly/config (sampling, ids, formats, refusal of unchecked gold); real run on
the published inputs builds 40 questions + review sheet; extract-eval on the corrected gold.
