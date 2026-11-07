# Phase 81 report - De-thi-mau-DHQG-HCM-2024 solved with the current engine (REQ-0086)

- Result: 109/120 answered, 11 declined (printed 9, 10, 26, 29, 57, 64, 65, 66, 67, 105 and 28). All answers UNCERTAIN: no answer key exists, nothing is scored.
- Layout: 16 pages, 3 parts. Vietnamese 1-20, English 21-40, Math 41-70, Science 71-120 (the design assumed 4x30).
- Doubt: low 100, medium 11, high 9 (9, 26, 28, 57, 64-67, 105). Reviewer check FAIL on 13: 3, 62, 68, 69, 73, 82, 86, 87, 95, 106, 107, 108, 119.
- Cost: refine 0.67 + solve 1.44 = 2.11 USD (cap 5).
- Prior run (2026-11-05): 15 printed numbers differ, see `plans/dhqg2024-t81/diff-prior.tsv` (untracked); not adjudicated.
- Independent check (verifier + main, from pdf native text): declines 64-67 are wrong, the answers are D, A, D, B; 9 is wrongly declined; 57 and 105 are legitimate; 26 undecided; 62, 68, 69 need the chart image (unverified).
- Defect: refine keeps only a description of the p8 bus-fare table, so the solver lacks the values and declines 64-67. Filed as REQ-0088 (not fixed here, out of scope).
- Open: unit suite has 4 failures that predate this task (examples/dgnl "unknown subject dir", docx text box, cwd test, check_examples); tracked code untouched.
- Outputs (untracked): `plans/dhqg2024-t81/answers.tsv`, `reports/dhqg2024-t81/<Section>/report.{md,pdf}` (learn view, 4 md + 4 pdf).
- Evidence: `work/TASK-081/evidence/crosscheck-counts.txt` (120 = 109 answered + 11 declined).
