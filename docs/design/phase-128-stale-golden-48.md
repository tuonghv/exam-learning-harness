# Phase 128 – Stale TASK-048 real-doc golden (TASK-128, REQ-0135)

## Finding
`test_assembly_qa.Golden.test_48_golden_refined_real_doc` (outside `--fast`) compares doc.json and e.md of HEAD with
the code of 63a5299 (before TASK-048) on the DGNL 2026 PDF + work/dgnl-real/v3/13-22.json. Since TASK-114..126 the
native segmentation finds 120 questions (base: 0, segmentation_skipped) and the refined exam text carries source
pages, group figures, continued pages and section labels (58 diff lines, all intended). It failed before TASK-126.

## Plan modes
Test-only change: no src, prompt, config or pipeline behaviour changes; single-source and pipeline plans unaffected.

## Design
Replace the byte equality in that test only with the TASK-048 invariants on HEAD: e.md.assembly.json written, one
row per `## Question` of e.md, every row has source pages, failed rows = `[Incomplete:` markers, statuses in
{passed, failed}, a second run gives identical e.md and sidecar. The synthetic goldens (examples, two-page PDF) keep
their 63a5299 byte comparison (they still pass).

## Verification
Test passes on HEAD; bite: with the sidecar writer stubbed the test fails. `--fast` NEW 0.
