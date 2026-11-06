# Phase 80 report - De-thi-minh-hoa-2026-Final solved (REQ-0085)

- Result: 113/120 correct (94.2%) against the answer file. Vietnamese 28/30, English 28/30, Math 28/30, Science 29/30.
- Wrong printed numbers: 21, 24, 37 (declined), 38, 63, 65, 112.
- Calibration: answers with low doubt 102/108 correct; medium 11/14; high 0/1. Medium or high doubt is a useful flag.
- Cost: refine 1.0593 + solve 1.4280 = 2.4873 USD (cap 3).
- Open: refine flagged needs_review on 67 and 89 (both answered correctly); Q37 declined (missing text from refine, check page); solve exit code 1 is the UNCERTAIN status without a key, not an error.
- Evidence: `docs/report/evidence/TASK-080/run-summary.txt`; per-number table `reports/dgnl2026-t80/answers.tsv` (untracked).
