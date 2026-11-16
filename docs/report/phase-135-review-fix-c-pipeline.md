# Phase 135 – Review leftovers fix C: metrics, report_kinds, review pack report (TASK-135, REQ-0142)

**Verdict: done.** Last 7 batch-1 findings; with this task every finding of the 9 Fable review reports has a final
disposition (ledger: 0 open).

## Results
- metrics: a flip judged by QA (not the key) shows `better (proxy)` via a `proxy` flag (109-F003; the review's
  `mixed` basis was not adopted); explain rows without `primary` are skipped (109-F005); backfill skips an
  unreadable result.json and continues (109-F006).
- report_kinds: a null supersede note is empty, not a crash (111-F001); `_has_text` counts a wrapped option A
  correctly (111-F002, INDEX with_text).
- review pack: exam-text lines starting `QA: ` / `Answer changed:` are guarded (111-F008, untrusted text); reserved
  subject names are refused case-insensitively (111-F009).
- 7 tests (all fail on old code); `--fast` KNOWN 4, NEW 0.

## Spend
$0. One coder run.
