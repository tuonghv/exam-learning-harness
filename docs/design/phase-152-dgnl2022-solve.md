# Phase 152 – Solve DGNL HCM 2022 sample exam (TASK-152, REQ-0157)

Source: REQ-0157 (RAW-00389 solve; RAW-00390 approved: sonnet, cap $4.70). No key for 2022: answers, no score.

## Plan modes
Run only (no code/prompt change); recipe `docs/guide/dgnl-real-exam.md`. Outputs in git-ignored `plans/dgnl2022/`
and `reports/dgnl2022/`; published config untouched.

## Design
P=`input/dgnl/de-thi-mau-dgnl-hcm-2022.pdf` (16 pages, text layer, 120 questions; page 1 = cover/structure).
- 152.1 Free: ingest found Câu 1-120; sections from the cover table: Vietnamese 1-20, English 21-40, Math (math,
  logic, data) 41-70, Science (chemistry, physics, biology, geography, history) 71-120.
- 152.2 Refine pages 2-16, `--all-pages --real --model claude-sonnet-5-5 --max-cost-usd 1.50` (dry run: <= 32
  calls, est $1.28), cache `plans/dgnl2022/cache-refine`; `ingest-inspect` for suspects; incomplete questions
  stay declined, never guessed.
- 152.3 Exam files `ingest P --refined ... --questions <range> --meta ...` per section; check counts 20/20/30/50.
- 152.4 `solve e-<S>.md --exam-id dgnl2022 --line main --real --yes --model claude-sonnet-5-5 --no-pdf`, caps
  Vietnamese 0.60, English 0.50, Math 0.80, Science 1.30 (solve total 3.20; with refine <= 4.70).
- 152.5 `report-pack` of the 4 plan runs (`--exam dgnl2022`), answers by printed number; running cost in
  `work/TASK-152/evidence/cost.tsv`; stop before any step that would pass $4.70.

## Verification
Real run: 120 answered or declined with reason, costs <= $4.70, report pack INDEX.
