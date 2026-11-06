# Phase 80 - Solve De-thi-minh-hoa-2026-Final end to end (REQ-0085)

Run task, no code change. Follow `docs/guide/dgnl-real-exam.md`: free ingest, refine in 3 page batches, merge (exact
duplicate ids 17-25 dropped), 4 section files, one paid solve per section (cap 0.48 USD each), score by printed number
against the answer file. Cap 3 USD total. Outputs in git-ignored `plans/dgnl2026-t80/`, `reports/dgnl2026-t80/`.
Reuse: existing engine only. Risk: refine needs_review on Q67 and Q89 (recorded as doubt).

## Plan modes
No impact on single-source or pipeline plans: engine and prompts unchanged, only runs.
