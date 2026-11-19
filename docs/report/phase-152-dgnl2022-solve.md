# Phase 152 – Solve DGNL HCM 2022 sample exam (TASK-152, REQ-0157)

**Verdict: done.** 120 questions extracted and solved with Sonnet 5.5 on dev line `s22` for **$2.33** (approved cap
$4.70, RAW-00390): 119 answered, 1 declined. No key for 2022, so no score.

## Results
- Input `input/dgnl/de-thi-mau-dgnl-hcm-2022.pdf`: 16 pages, text layer; sections from the cover table:
  Vietnamese 1-20, English 21-40, Math/logic/data 41-70, Science (chem, phys, bio, geo, history) 71-120.
- Refine p2-16: 120 questions, 15 calls, $0.65 (dry-run estimate $1.28). `needs_review` 45 and 101 (low similarity
  only): checked against the PDF, the AI reading is correct; the native text layer scrambles the math.
- Solves (line `s22`, image check on doubt): Vietnamese $0.30, English $0.28, Math $0.42, Science $0.68.
- Report pack `reports/dgnl2022/s22/run-20261119-043718/`: answer table (TSV), full and student solution reports
  (md + pdf). Answer table: 120 rows, printed 1-120, doubt low 108 / medium 10 / high 2.
- Declined: printed 57 (logic seating puzzle): the solver finds options B and D both impossible -> no unique answer;
  check the page/key (an extraction miss of one condition is possible).
- Verifier FAIL (answer kept, flagged): 29, 33 (English), 62, 69 (Math). Medium/high doubt: 18, 26, 28, 58, 89,
  95, 107, 108, 119.
- Evidence: `work/TASK-152/evidence/` (cost.tsv, solve.log, summary.txt).

## Score vs key (RAW-00391, 2026-11-19, $0)
- Key `input/dgnl/de-thi-mau-dgnl-hcm-2022.answer.txt` (one line `1.D 2.A ...`, 120 entries) parsed by report-pack.
- **106/120 (88.3%)**: Vietnamese 18/20, English 17/20, Math 28/30, Science 43/50. Independent recount from the
  answer table matches (`work/TASK-152/evidence/score-crosscheck.txt`). Pack `reports/dgnl2022/s22/run-20261119-052314/`.
- Wrong: 14, 18, 21, 22, 33, 49, 57 (declined; key B, the solver judged B impossible -> check the extraction),
  72, 80, 88, 89, 104, 105, 119.
- Doubt signal: of the 12 medium/high-doubt answers 5 are wrong; 9 wrong answers had low doubt. Of the 4 verifier
  FAILs only 33 is wrong (29, 62, 69 are right).

## Defects
- Section headings in the exam files are wrong (Math: "1.2. TIẾNG ANH", Science: "1.2. TIẾNG ANH > PHẦN 3"): the
  ingest carries a stale heading. Solving uses the `Subject:` header (correct), so only a `section_subject_mismatch`
  warning and a misleading context line; worth a fix before a re-run or publish.
- The first solve attempt used `--line main` and was refused (published line, needs `--publish`); no spend.

## Published (RAW-00392, 2026-11-19)
- `config/published_reports.json` gains `dgnl2022` (line `s22`, key + sha256, 4 plan runs, view sheet).
- `rebuild-reports dgnl2022` -> `reports/dgnl2022/main/run-20261119-053005/` (8 files + INDEX), score 106/120;
  `check_report_pack.py ... --expect-correct 106`: 58 checks, 0 failed (`work/TASK-152/evidence/publish-check.txt`).
- Rebuild recipe: `python3 -I scripts/exam.py rebuild-reports dgnl2022` (same as the other exams).

## Spend
$2.33 (approved $4.70).
