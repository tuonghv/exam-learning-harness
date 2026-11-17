# Phase 145 – Re-solve DGNL 2026 (TASK-145, REQ-0091)

Source: REQ-0091, paid run approved by the user (RAW-00361, 2026-11-17).

## Plan modes
Paid solve (claude-p) of the 4 refined DGNL 2026 subject files `work/dgnl2026f/e-{Vietnamese,English,Math,Science}.md`
(sha256 equal to the published line-f inputs). New dev line `r4`; published `main` untouched. No refine re-run
(the TASK-143 table fix needs a paid re-refine).

## Design
- 145.1 Already-solved summary first (run-list): line f, sonnet, 113/120, $1.37.
- 145.2 `exam solve <file> --exam-id dgnl2026 --line r4 --real --yes --model claude-sonnet-5-5 --max-cost-usd 0.8`
  per subject (cap $3.20 total, ~$1.5 expected), solve cache on; current code (batch-4 fixes).
- 145.3 `report-pack` of the 4 r4 plan runs with `--key input/dgnl/De-thi-minh-hoa-2026-Final.answer.txt` into
  `reports/dgnl2026/r4/run-r4pack`; compare with the published score-vs-key per question.
- 145.4 Cache proof: one subject re-run on line `r4cache` must make 0 calls.

## Verification
Real run: costs, score, per-question diff vs main, report file count (`work/TASK-145/evidence/summary.md`).
