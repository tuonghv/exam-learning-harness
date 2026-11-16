# Phase 119 – Fix-I api report (TASK-119, REQ-0126)

**Verdict: done.** Four assembly bugs fixed (117-F008, F004, F005, F007), with rules narrowed after a real-data check.

## Results
- **F008** a refined question cut by a page break keeps both parts: options A-B + C-D, the second part's figures and
  page (`continued_pages`). This also resolved a recorded known miss in the structure gold set (cross_page now found).
- **F004** a group range closes at a numbering restart without a heading, when the range never resumes later.
- **F005** a member whose context mentions other questions (`answers to questions 3, 4`) no longer opens a new range.
- **F007** the `N + offset` note is printed only when every kept id is consecutive; otherwise the explicit mapping.

## Real data ($0) – the design was corrected
The designed rules moved 96 shared contexts on the 3 DGNL/DHQG PDFs (e.g. q47-52 lost the "Questions 46-52" passage).
Cause: segment reads numbered passage lines and year/formula lines (`1`..`6`, `1991`, `2020`) as questions, so real
group lines sit on false carriers and stray low ids sit inside groups. Narrowed rules: F005 ignores a mention only for
a member of the open range; F004 closes only when the range never resumes, and an outside carrier starts at `lo - 1`.
After: 0 changes over 533 real questions (`work/TASK-119/evidence/summary.md`). Three guard tests pin these shapes.

## Tests
10 in `tests/unit/test_api_fix_i_119.py` (5 bite, 5 guards); gold fixture updated (resolved miss + a genuine no-page
cross_page miss). `--fast` 2071 ran, KNOWN 4, NEW 0.

## Defect found (follow-up)
Segment reads passage/year/formula lines as questions; the real first member of a group then gets no passage
(DHQG 106, 109, 112; DGNL 2025 q46) — before and after this task. Next REQ after Fix-J.

## Spend
designer, coder, tester runs; verifier waived (oracle + tester bite). No paid run.
