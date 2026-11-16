# Phase 132 – Report names for a non-Latin or missing subject (TASK-132, REQ-0139)

## Finding (TASK-131 D1, confirmed)
`reporter.default_names` (reporter.py:474) slugs the subject with `[a-z0-9]` only; `数学`, an empty subject or `All`
give `''`/`all`, the fallback is `all`, and `report_kinds.name(..., "answer-sheet")` (report_kinds.py:53) raises
`ValueError: kind answer-sheet has scope subject, subject 'all'`: no report is written for such an exam.

## Plan modes
Report naming only (solve report build, report-pack, rebuild-reports via report_build.py:53). Latin subjects keep
their names; no prompt, cache or result change.

## Design
`subject = slug(...)`; when it is `''` or the reserved `all`, use `subject`. One line in default_names.

## Verification ($0)
tests/unit/test_report_subject_slug_132.py (names for `数学`/empty/None/`All`/`---`, Latin unchanged, write_reports
writes md + answer sheet for `数学`); 2/3 fail on old code; `--fast` NEW 0.
