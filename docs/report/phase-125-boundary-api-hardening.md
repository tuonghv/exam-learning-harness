# Phase 125 – P3-c boundary + api hardening report (TASK-125, REQ-0132)

**Verdict: done.** Last hardening group: 118-F002/F003/F004/F006/F008, 114-F005, 117-F006.

## Results
- Boundary AI replies that omit a requested line or repeat a `window_id` are invalid (not cached); a corrupt or old
  partial cache entry is a miss (re-asked once), never a TypeError/ValueError.
- Dry-run estimate counts each window once across `--pages` passes; trace rows carry the `call` index and the
  per-call cost (docs/guide/ingest-usage.md updated).
- Under a mislabelled boundary hint, a passage line stays in the next question's context, not option D.
- A refined slice is gated by the whole document's verification data, even when its own questions carry none.
- 7 tests (all fail on old code); `--fast` 2118, NEW 0. Real inputs: segment + shared contexts unchanged; dry-run
  boundary estimate unchanged.

## Spend
1 coder run; designer/tester/verifier waived (rows pre-designed; coordinator bite + oracles). No paid run.
