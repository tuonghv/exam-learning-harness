# Phase 116 – Unaccented `Cau N - M` group sharing report (TASK-116, REQ-0123)

**Verdict: done.** A group intro written without diacritics (`Cau 31 - 35: ...`) now shares its passage with every
question of its range, as `Câu` / `CÂU` already did.

## Premise corrected
TASK-114's report said a `CÂU 31 - 35` passage reached q31 only. That was wrong: sharing (`api._share_context`) uses
`segment.GROUP_ANY` (case-insensitive), so `CÂU` was already shared. Only the unaccented `Cau` was not.

## Results
- `segment.build()` now builds `GROUP_ANY` from the 114.2 intro span (`C[aâ]u`, re.I); GROUP_RE and `_INTRO` unchanged.
- 2 tests (Cau shared: bites on old code; CÂU guard). `--fast` 2050 ran, KNOWN 4, NEW 0.
- Real data ($0, `work/TASK-116/evidence/summary.md`): share and segment oracles old vs new over 4 input PDFs (533 q)
  and 22 examples: 0 changes. No current input uses `Cau N - M`, so this is latent hardening.

## Spend
1 coder run; designer, tester and verifier waived (size-S, one regex) with coordinator-run oracles. No paid run.
