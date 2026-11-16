# Phase 134 – Review leftovers fix B: refine hardening report (TASK-134, REQ-0141)

**Verdict: done.** 5 batch-1 findings (all IMPROVEMENT; reached only by prompt-violating replies, window fallbacks
or non-contiguous `--pages`).

## Results
- A multi-line continuation that starts with a question number is caught as an orphan (108-F003).
- Continuation options with new letters are merged into the owner, not replacing it (108-F006).
- A carried passage survives a reply without `continues` (108-F007) and is not used up by a skipped heading-only
  entry (108-F008).
- The window path checks gaps only over the pending question's pages (108-F009): no false `gap` with `--pages 1,3-4`.
- 8 tests (6 fail on old code, 2 guards); existing refine tests/goldens unchanged; `--fast` KNOWN 4, NEW 0.
  No prompt or cache-key change. A replay of cached real replies was not run (a cache miss would be a paid call).

## Spend
$0. One coder run.
