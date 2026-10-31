# Solving a real ĐGNL exam PDF (multi-subject)

Learned on the ĐHQG-HCM 2026 sample (22 PDF pages, 120 questions, no key). Run from the repo root; the PDF,
`doc.json`, `refined*.json`, exam files and runs stay untracked (copyright). Never commit question text.

## Shape of the exam
Printed page = PDF page - 3. 1-30 Vietnamese (reading, shared passages), 31-60 English (cloze, error, passage),
61-90 math, 91-120 science (logic/data with charts, physics, chemistry, biology, social). Groups are announced
in text ("Questions 46-52", "câu từ 103 đến 105"). The answer key is not in the PDF: confidence comes from
agreement and hand checks, status stays `uncertain`.

## Steps
1. `python3 -I scripts/exam.py ingest EXAM.pdf --out work/x/doc.json` (free). Native text is NOT enough: math
   symbols and tables are lost, 0 questions segment, columns mix options.
2. `ingest-refine EXAM.pdf --pages A-B --all-pages --real --max-cost-usd 1 --out work/x/parts/A-B.json`.
   `--all-pages` is needed (math pages are not flagged). Run in batches of 4-8 pages: a failed call loses the whole
   batch's output, and the 5-hour usage limit can hit mid-run. About $0.04/page, whole exam about $0.8.
   Re-run a page range alone when a reply is invalid.
3. Merge the batches' `refined.questions` into one `doc["refined"]` (keep page order; no dedupe: a question cut by
   a page break appears twice and is joined later).
4. One exam file per section, renumbered from 1 (the engine needs 1..N):
   `ingest EXAM.pdf --refined merged.json --questions 61-90 --meta Subject=Math --meta Level="Grade 12"
   --meta "Exam type=University Entrance (DGNL)" --meta "Task=Multiple Choice" --meta Mode=Solve --meta Language=vi
   --exam-out e-Math.md`. Subjects: Vietnamese, English, Math, Science (config `science`, `vietnamese` have no
   subject prompt).
5. `solve e-Math.md --real --max-cost-usd 1.5 --no-pdf --out run-Math` (about $0.3-0.45 per section).
6. Report answers by printed exam number (section index + offset), page, status and doubt; no question text.

## What made it fail first, and the fixes (REQ-0033)
- Shared passage kept only in the first question: later questions got "missing text", 18 declined, 21 quote-check
  fails. Fix: `context` per question plus `_share_context` repeats the passage for every question of its group.
- Passage on the previous page than its questions: the vision call sees one page. Fix: refine prompt `carry`
  field handed to the next page's first question.
- Question cut by a page break (stem on one page, options on the next): joined in `_from_refined`.
- Question over N pages (phase 40): the reply field `continues` (text, options, figures, passage) holds what is printed above
  the first number of page N+1; `refine._attach` merges it into the last question of page N-1 only, chains over pages,
  drops overlap and refuses a number-led or wrong-owner continuation (`orphans`, warning `orphan_continuation`: re-run with
  page N-1). Always select the page before a continuation in `--pages`.
- Completeness at render time (`refcheck.incomplete_reasons`: `options_incomplete`, `cut_unresolved`, `referenced_part_missing`,
  `orphan_on_page`): the exam text gets `[Incomplete: missing_text ...]` and the engine records `solver_declined: missing_text (...)`
  without sending the question to the solver.
- Figures/tables: written as `[Figure/table: ...]` text from the refine reply. A question needing pixels that
  the reply cannot describe is still guessed from the description: re-check those by hand (e.g. cable diagram).
- Numeric science answers come back as the value ("230%") not the letter: format check fails although the value
  equals exactly one option. Map the value to its option letter when reporting; engine unchanged (open item).

## Checking without a key
Math: recompute by hand. The 10-question slice and the vision-extracted run agree 10/10 (61-71 except 66).
Language/science: accept only `solver_uncertainty` low plus agreement; list the rest as unresolved, never guess.
