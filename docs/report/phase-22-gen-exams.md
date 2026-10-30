# Phase 22 report: generated exams, concept round (REQ-0027, TASK-022)

## Result
- Generated 3 Vietnamese math exams (Oxyz distance, two definite integrals) with the real model; cost $0.035. Each key's arithmetic check equals its final answer (enforced in code).
- Ran the unchanged `benchmark` (prompts v1.2.0) on them: 3 pass, 0 fail, 0 uncertain; 8 calls, $0.136. Total about $0.17.
- Lessons: 0. So AC5 (a lesson turned into an engine fix) is NOT met: these items were too easy to expose anything. n=3, one subject, same model writes and solves: this shows the loop works end to end, not that the engine is accurate.

## Cross-check yourself (no trust in the code)
Keys, recomputed by hand:
- 101: d = |2·2 − 2·(−1) + 3 + 5| / √(4+4+1) = 14/3.
- 102: ∫₁³(4x³−6x)dx = [x⁴−3x²] = (81−27) − (1−3) = 56.
- 103: ∫₁³(2x+1/x²)dx = [x²−1/x] = (9−1/3) − (1−1) = 26/3.
Files: `evals/generated/inputs/math/input-10{1,2,3}.md` (the solver saw only these), `evals/generated/keys/math/expected-10{1,2,3}.md`, `evals/generated/manifest.json` (seed, prompt hash, `reviewed: false`).
Run evidence: `work/exam-runs/2026-10-30-gen1/{summary.json,report.md}`; copy in `work/TASK-022/real/`.
Leak check: `grep -il "Final answer" evals/generated/inputs/math/*` must print nothing (it printed nothing).

## Next (gradual)
Round 2 should be harder (multi-step, traps, several topics, one more subject), then lessons will have something to say. Needs your go.
