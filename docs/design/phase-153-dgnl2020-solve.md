# Phase 153 – Solve DGNL HCM 2020 sample exam (TASK-153, REQ-0158)

Source: REQ-0158 (RAW-00394 solve; RAW-00395 approved: sonnet, cap $4.40). No key for 2020: answers, no score.

## Plan modes
Run only (no code/prompt change); same recipe as TASK-152 (`docs/guide/dgnl-real-exam.md`). Outputs in git-ignored
`plans/dgnl2020/` and `reports/dgnl2020/`; published config untouched. Dev line `s20` (`main` is a published line).

## Design
P=`input/dgnl/De-thi-mau-DHQG-TPHCM-2020.pdf` (14 pages, text layer, 120 questions; page 1 = cover + Câu 1-).
- 153.1 Free: ingest found 120 questions; sections from the cover table: Vietnamese 1-20, English 21-40, Math (math,
  logic, data) 41-70, Science (chemistry, physics, biology, geography, history) 71-120.
- 153.2 Refine pages 1-14, `--all-pages --real --model claude-sonnet-5-5 --max-cost-usd 1.40` (dry run: 14 page
  calls), cache `plans/dgnl2020/cache-refine`; suspects checked against the PDF; incomplete questions stay declined.
- 153.3 Exam files `ingest P --refined ... --questions <range> --meta ...` per section; check counts 20/20/30/50.
- 153.4 `solve <S>.md --exam-id dgnl2020 --line s20 --real --yes --model claude-sonnet-5-5 --pdf P --image-scope doubt`,
  caps Vietnamese 0.60, English 0.50, Math 0.80, Science 1.10 (solve 3.00; with refine <= 4.40).
- 153.5 `report-pack` of the 4 runs (`--exam dgnl2020`), answers by printed number; running cost in
  `work/TASK-153/evidence/cost.tsv`; stop before any step that would pass $4.40.

## Verification
Real run: 120 answered or declined with reason, costs <= $4.40, report pack INDEX.
