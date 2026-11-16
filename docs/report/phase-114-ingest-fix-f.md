# Phase 114 – Fix-F ingest report (TASK-114, REQ-0121)

**Verdict: done.** Four triaged ingest bugs fixed (114-F001, F002, F010, F004); verifier PASS on AC1-AC5.

## Results
- **F001** a question with no parsed options no longer swallows the next `PHẦN ...` heading or `Questions N-M:` intro;
  it becomes the next question's context. End-of-input crash path removed.
- **F002** `CÂU 31 - 35: ...` / `Cau 31 - 35` is a group intro, not question 31 (scoped `(?i:)` in `_INTRO`; GROUP_RE unchanged).
- **F010** a window result merges with the passage carried from a question-less page (`_dedupe`), no overwrite.
- **F004** a failed backward re-run (call_failed / invalid_reply / cost_cap) keeps the finished first pass with a
  `recover_failed` warning; calls/cost report the whole run.
- Tests: 14 in `tests/unit/test_ingest_fix_f.py` (10 bite on old src, 4+1 guards); 2 existing tests updated that pinned
  the old behaviour (golden `_INTRO` pattern; cost_cap mid-backward). `--fast` 2036 ran, KNOWN 4, NEW 0.

## Real data ($0, `work/TASK-114/evidence/oracle-summary.md`)
- 22 `examples/` files: 0 changes. 4 input PDFs, 533 questions: same count, numbering and options.
- 17 questions changed, all F001: 9 stems lost a trailing heading/intro, each equal to the context the next question
  gained (0 mismatches). So F001 was live on DGNL 2025/2026, DHQG 2024 and the math graduation exam.
- Refine replay from the page cache is not possible: the page prompt changed since the cached runs (all misses, 0 paid
  calls). F004/F010 rest on unit tests.

## Spend
designer, coder, tester, verifier runs; no paid exam run.

## Defects / follow-ups
- F002 follow-up: `api.py` GROUP_RE stays case-sensitive, so a `CÂU 31 - 35` passage reaches q31 only, not q32-35.
- Residual risk: an option-less stem whose wrapped line starts `Phần N` would move out; none seen in real data.

## Next
TASK-115 Fix-G cli (113-F001, F003, F005, F002).
