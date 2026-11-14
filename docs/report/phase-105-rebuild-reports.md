# Phase 105 report: one command rebuilds every published report

Task: TASK-105 · REQ-0111 (RAW-00323, RAW-00325) · design `docs/design/phase-105-rebuild-reports.md`

- Action: tracked recipe `config/published_reports.json` (per exam: source line, plan runs, key path + sha256,
  overlays with reason, view, pdf; seeded by `--write-recipe` from the main manifests) and
  `exam rebuild-reports [EXAM...] [--dry-run]`: every check (plan run, overlay, key sha256, pdf renderer, path under
  --root) runs before any delete, then main + source-line packs are rebuilt by the existing report-pack/publish.
  Guide: report-kinds.md "How to rebuild reports" (5 lines), toolkit-reference line.
- Result: real rebuild of all 3 exams at $0, rc 0; 25/25 md/tsv report files byte-identical to the previous runs
  (run id normalized; INDEX.md differs only in the engine commit line); scores 113/120, 113/120, 105/119;
  checker 0 failed x3. Verifier finding F1 (recipe path could leave --root) fixed with 2 tests. Fast suite KNOWN 4 NEW 0.
- Decision: reports are rebuilt from the recipe, never migrated or hand-made; a missing input stops before deleting.
  Next: TASK-106 (`exam backup` of the untracked plans/ and input/ that the rebuild depends on).

## Defects
- input/dgnl/De-thi-mau-DHQG-HCM-2024.answer.txt: `Câu 65. I` (unchanged; reported as KEYISSUE).

Evidence: `docs/report/evidence/TASK-105/verify.md`
