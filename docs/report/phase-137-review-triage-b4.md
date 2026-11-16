# Phase 137 – Code-review triage, batch 4 report (TASK-137, REQ-0144)

**Verdict: done.** All 28 batch-4 findings were checked against HEAD: 26 BUG, 2 IMPROVEMENT, 0 NOT-A-DEFECT.

## Results
- Table, evidence and replacement fixes: `docs/design/phase-137-review-triage-b4.md`.
- Most important: 137-F001 (HIGH) a fraction key `14/3` scores a bare `14` as correct (4 eval keys have this shape);
  137-F008 an ordering key is counted as letter B in run-stats; 136-F001/F002 cost extra paid calls or turn a correct
  adjudicated answer into FAIL; 139-F001 `--out` into a run folder skips the publish guard.
- 20 ids reproduced at $0 (repro A R1-R5, repro B), the rest traced to file:line.
- Six review fixes are not adopted as written (137-F001 decimal acceptance, 137-F009, 136-F005, 138-F001, F005, F006);
  one review case is wrong (137-F001 "`14/5` matches `14/3`" is false).
- Prompt v2 worked: no false positives this batch (batches 1-3: 5 of 80); fix-risk notes caught 2 conflicts
  (137-F009 vs 136-F004).
- Fix tasks queued: TASK-138 (scorer, P1), 139 (engine, P1), 140 (runlayout, P1), 141 (verifier, P2), 142 (pdf OCR,
  P2), 143 (pdf text placement, P2, with a before/after re-ingest of input/). Ledger: 28 open on those, 0 problems.

## Open questions (user)
- Integer key `5` accepts `5.5` and `4.5` (half-unit tolerance, 8 keys): keep or make strict?
- Should a decimal answer (`4.67`) be accepted for a fraction key (`14/3`)?

## Spend
$0. Two designer runs.
