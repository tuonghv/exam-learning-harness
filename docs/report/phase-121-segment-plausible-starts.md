# Phase 121 – Segment rejects implausible question starts (TASK-121, REQ-0128)

**Verdict: done.** The free text path now reads the DGNL 2025 and DHQG 2024 exams as their 120 printed questions.

## Problem
Segment took numbered reading-passage paragraphs (`1 The world of rap...`), years (`1991`, `2020`) and formula lines
(`0`, `5000`) as question starts: 197 / 141 / 147 "questions" on the three 120-question DGNL/DHQG exams. The PDFs were
then marked `segmentation_skipped` (text path unusable) and the real first question of a group lost its passage.

## Fix
A start whose number breaks the running sequence while the expected next number still comes later is text, not a
question (`_implausible`, lookahead over precomputed candidates). A real restart at 1 whose own run reaches the
previous number is kept. Numbering checks (`numbering`, usable/skipped) are unchanged.

## Real data ($0, `work/TASK-121/evidence/summary.md`)
| Exam | Segmented before -> after | Usable by the text path |
|---|---|---|
| DGNL 2025 | 197 -> 120 | no -> yes (120 questions) |
| DHQG 2024 | 141 -> 120 | no -> yes (120 questions) |
| DGNL 2026 | 147 -> 122 | no -> no (2 cover lines `1.`/`2.`: residual) |
| math graduation | 48 -> 46 | no (key pages; refused anyway) |
24 real first members of a group now carry their passage/data (e.g. DHQG q106/q109/q112, DGNL25 q46/q70/q85).
examples/: unchanged. Nothing lost.

## Tests
8 in `tests/unit/test_segment_plausible.py`; test_numbering_gaps restart case repointed to a true restart-with-gap and
the old `[1..5,1,2,3,6]` shape pinned as numbered text. `--fast` 2090 ran, NEW 0.

## Residuals (follow-up)
DGNL26 cover-page numbered lines keep it `segmentation_skipped`; mid-line group intros are handled by this fix in the
inputs seen. The refined (paid) path is unchanged and still chosen explicitly.

## Spend
designer + coder runs; tester/verifier waived (coordinator bite + two oracles). No paid run.
