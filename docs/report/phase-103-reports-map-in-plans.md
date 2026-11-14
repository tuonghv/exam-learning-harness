# Phase 103 report: reports/ holds only reports; clean rebuild

Task: TASK-103 · REQ-0110 (RAW-00320..322) · design `docs/design/phase-103-reports-map-in-plans.md`

- Action: plans-migrate's reports map moved under plans/ (code); then, on the user's call, old reports were not
  migrated at all: reports/ and every report-run record were deleted (backup in the session scratchpad) and the three
  main reports rebuilt at $0 from the stored plan runs (report-pack / publish, no model call).
- Result: dgnl2025 113/120, dgnl2026 113/120, dhqg2024 105/119 in reports/<exam>/main; reports/ holds only
  md/pdf/tsv + INDEX.md. Checker 0 failed for dgnl2025/dgnl2026; dhqg2024 2 checks differ only because the key file
  gives printed 65 = "I" (excluded by the engine).
- Decision: reports are derived data: rebuild, never migrate (user). Next: retire the report-migration code
  (report-manifests-migrate, reports side of plans-migrate); fix the dhqg2024 key for question 65.

## Defects
- input/dgnl/De-thi-mau-DHQG-HCM-2024.answer.txt: `Câu 65. I` is not a valid answer letter.

Evidence: `docs/report/evidence/TASK-103/verify.md`
