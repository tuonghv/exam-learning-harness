# Phase 86 report - every report .md has a .pdf (REQ-0093)

- Result: `config/report_kinds.json` has a top-level `pdf_with_md` flag and lists `pdf` for every kind that has `md` (answer-sheet and score-summary gained pdf). `exam report-pack` renders a pdf beside every md (md_to_pdf, no AI cost), removes a stale pdf when its md is rewritten, and fails clearly before writing anything if no PDF renderer exists (the old "html stands in" path is gone). `tools/check_report_pack.py` reads the flag from the registry (no kind is hard-coded) and fails on an md without a pdf and on a pdf without an md.
- DGNL 2026 pack rebuilt at $0: `reports/dgnl2026/` = 10 md + 10 pdf + INDEX.md + 9 json + 4 log + 2 tsv; checker 62 checks 0 failed; 113 of 120 correct. Legacy report folders are not touched and report-index does not enforce the pair there.
- Tests: `test_report_kinds` 54 (11 new, 9 fail on the previous code); full suite 1701 run, only the 4 known pre-existing failures.
- Open (minor): in the answer-sheet pdf the circled letters are readable but not column-aligned under the numbers (font fallback); the .md version is aligned. Only the DGNL 2026 pack has the pair rule so far; the DHQG 2024 pack is REQ-0094.
- Evidence: `work/TASK-086/evidence/` (untracked).
