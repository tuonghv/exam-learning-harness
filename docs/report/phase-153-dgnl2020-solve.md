# Phase 153 – Solve DGNL HCM 2020 sample exam (TASK-153, REQ-0158)

**Verdict: done.** 120 questions extracted and solved with Sonnet 5.5 on dev line `s20` for **$2.64** (approved cap
$4.40, RAW-00395): 115 answered, 5 declined (all question defects, checked by hand). No key for 2020, so no score.

## Results
- Input `input/dgnl/De-thi-mau-DHQG-TPHCM-2020.pdf`: 14 pages, text layer, Câu 1 starts on page 1; sections from the
  cover table: Vietnamese 1-20, English 21-40, Math/logic/data 41-70, Science (chem, phys, bio, geo, history) 71-120.
- Refine p1-14: 120 questions, 14 calls, $0.72. `needs_review` 45, 48 (math scrambled in the native text; AI reading
  correct, hand-solved: both A) and 92 (text exact; the passage cites a "dãy điện hóa đã cho ở trên" that the PDF never
  prints).
- Solves (line `s20`, image check on doubt): Vietnamese $0.39, English $0.22, Math $0.53, Science $0.80.
- Report pack `reports/dgnl2020/s20/run-20261121-103828/`: answer table (TSV), full and student solution reports
  (md + pdf). 120 rows, printed 1-120, doubt low 102 / medium 16 / high 2.
- Verifier FAIL (answer kept, flagged): 19 (Vietnamese), 75, 105 (Science). Medium/high doubt: 6, 11, 13, 15, 55, 81,
  83, 85, 86, 93, 95, 102, 117, 118, 119, 120.
- Evidence: `work/TASK-153/evidence/` (cost.tsv, solve.log, summary.txt).

## Declined (5, Math; extraction compared with the PDF, all exact)
- 50: 3a+4b+5c = 3·(A) − (B) = 3·68 − 74 = 130.000đ, not among 118/100/122/132.
- 57: options A (M,N,Q,R,P) and B (N,M,Q,P,R) both meet every condition (enumerated).
- 60: with a boy 4th (4 orders), A and C are always true, B and D only sometimes false: no option is false in every case.
- 63: the "% of quota" base is not defined; no reading of the passage gives one of the options.
- 66: chart 2014 values 566 vs 579 (series sums match the passage totals 2,629 / 3,079): ≈2.2%, no option; D 14.3% is 2015.

## Defects
- Section headings in the Math and Science exam files still carry the stale "1.2. TIẾNG ANH" (same as TASK-152):
  `section_subject_mismatch` warning only, solving uses `Subject:`.
- `tools/run_tests.py --fast` shows NEW 1: `test_rebuild_reports.T1Recipe.test_105_1_tracked_recipe_schema` expects 3
  exams in `config/published_reports.json`; the dgnl2022 publish (3267a14, RAW-00392) made it 4. This was already broken
  before this task (a run with no tracked change), and the UNIT_TESTED entry copied the old "NEW 0". The test needs to
  follow the config.

## Spend
$2.64 (approved $4.40).
