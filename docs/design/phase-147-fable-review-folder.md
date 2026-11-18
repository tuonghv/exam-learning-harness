# Phase 147 – Fable review reports folder + status header + 138-F006 re-check (TASK-147, REQ-0153)

Source: REQ-0153 (RAW-00368, RAW-00369).

## Plan modes
Single-source and pipeline plans: no change except PDF ingest (147.5) keeps stem lines that sit beside a table in
a merged block; pages without such blocks give the same output. No paid run.

## Design
- 147.1 Move the 13 Fable code-review reports (files with `### Fnnn – [SEV]` headings) from `docs/report/` to
  `docs/report/fable-review/<YYYY-MM-DD>-phase<N>-<slug>.md`; date = first commit of the report (RAW-00369).
  `git mv`, so history follows.
- 147.2 Prepend to each a `<!-- fable-status -->` block: `**Status (2026-11-18):**` with the triage/fix TASKs from
  `docs/review/findings.tsv` and what is still open, plus the Action rule (RAW-00368) as in the user's sample.
- 147.3 `tools/review_ledger.py`: scan `docs/report/fable-review/` (id from `phase<N>` or the old `phase-<N>-`),
  keep `docs/report/phase-*` for older layouts; ledger `report` column = new file name.
- 147.4 code-reviewer agent + `docs/prompts/cost-efficient_code_review_instructions.md`: new reports go to
  `docs/report/fable-review/<date>-phase<ID>-<slug>.md`.
- 147.5 Re-check every not-fixed finding. Only 138-F006 (waived): true positive - `pdf._extract` drops a whole
  text block whose centre is inside a table box even when some of its lines lie outside; the waiver reason
  (no line boxes) is wrong, `_line_blocks` already gives them. Fix: for such a block that extends > 2pt beyond
  its table, keep its lines whose own centre is outside every table (merged with `_merge_column`).
  Ledger row -> `fixed TASK-147`. The 5 not-a-defect rows keep their recorded reasons (false positives, skipped).

## Verification
`review_ledger.py`: 108 ids, 0 open, 0 problems; unit test for the F006 case fails on the old code;
`--fast` suite no new failures; real ingest of an input PDF unchanged where no block straddles a table.
