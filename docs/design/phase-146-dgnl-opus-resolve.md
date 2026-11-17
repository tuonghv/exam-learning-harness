# Phase 146 – Re-solve DGNL 2024/2025/2026 with Opus 5.5 (TASK-146, REQ-0152)

Source: REQ-0152; paid run approved by the user (RAW-00365, cap $18).

## Plan modes
Paid solve (claude-p) with `--model claude-opus-5-5` of exactly the inputs of the published plan runs
(`config/published_reports.json`): each run's `input/exam.md` (sha256 = plan.json `exam.sha256`), copied to
`work/TASK-146/in/<exam>/<subject>.md` so run ids keep the subject suffix. New dev line `o55`; published `main`
untouched. No code change, no refine re-run.

## Design
- 146.1 Inputs: 13 plan runs (dhqg2024 4 + t82 overlay slice 64-67, dgnl2025 4, dgnl2026 4); sha check before solving.
- 146.2 Same flags as each published run (from its config.json): `--pdf <image_pdf>`, `--image-scope`,
  `--max-image-pages` when set; `--max-cost-usd 1.50` per subject (overlay slice 0.40); `--real --yes`.
  Runner `work/TASK-146/run.sh` (3 exams in parallel, subjects in sequence), log `evidence/solve.log`.
- 146.3 `report-pack` per exam on line o55 with the same key (and for dhqg2024 the same overlay of printed
  64-67 from the o55 slice run), `--no-pdf`.
- 146.4 Per-question diff vs the published main score-vs-key: fixed / lost / net, plus cost; summary in
  `work/TASK-146/evidence/summary.md`.

## Verification
Real run: total cost <= $18, scores vs key, per-question diff; published main run ids unchanged.
