# Phase 122 – DGNL 2026 on the text path (TASK-122, REQ-0129)

**Verdict: done.** All three DGNL/DHQG exams now segment to their 120 printed questions on the free text path.

## Results
- **Cover run** a leading run of numbered lines without options (`1. Cấu trúc đề thi`, `2. Chiến lược làm bài thi`),
  shorter than and followed by a run from 1 that has options and sits under a part heading, is intro text.
  An exam that opens with its own headed essay part keeps those questions (guard test).
- **Image-only question** `Câu 4:` with a picture body is kept as `unreadable`; the numbering check tolerates it and
  the exam text marks it `[Incomplete: missing_text unreadable]`, which the engine declines (never solved from nothing).

## Real data ($0, `work/TASK-122/evidence/summary.md`)
DGNL 2026: 122 -> 120 segmented, 0 -> 120 usable questions (no longer `segmentation_skipped`). DGNL 2025, DHQG 2024,
math and examples/: segment and shared contexts identical.

## Across TASK-121 + TASK-122
| Exam | Before | After |
|---|---|---|
| DGNL 2025 | 197 segmented, unusable | 120, usable |
| DHQG 2024 | 141 segmented, unusable | 120, usable |
| DGNL 2026 | 147 segmented, unusable | 120, usable (q4 declined: picture) |

## Tests / spend
8 tests in `tests/unit/test_segment_cover_unreadable.py` (3 bite, 5 guards); `--fast` 2098, NEW 0.
designer + coder runs; tester/verifier waived (coordinator bite + oracles + rendered check). No paid run.
