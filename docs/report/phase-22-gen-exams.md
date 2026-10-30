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

## Round 2 (hard level, solution QA; user go, RAW-00091)
- Generated 4+2 hard math exams (3 attempts incl. fixes), kept 5 (104-108), cost $0.20; the independent solution QA (AC6) ran on each.
- QA bug found by the run, not by tests: 5 exams were rejected although the reviewer said "ok", because my answer compare could not read plain integers ("7") or labelled answers ("x = 3"). Fixed in `genexam.value`, tests added; the rejected exams were regenerated. Real wrong solutions found by QA: 0 (n=5).
- Benchmark of 104-108 ($0.24): 4 pass, 1 fail. The fail (106) is an ENGINE lesson: the solver's answer "x = 8 là nghiệm duy nhất; tổng các nghiệm = 8" was right (key 8; recomputed: x²−4x−32=0, x=8 or −4, domain x>5) but the scorer could not read a number from a sentence. Fix: `scorer.match` reads a trailing "= value". Rerun of 106 ($0.06): PASS. Before/after: 4/5 -> 5/5 (the rerun is one item, one sample).
- Generator weakness found: 105, 107, 108 are near-identical (log₃(x+2)+log₃(x−4)=3); the seed does not give variety. Not fixed yet; next change is to give the generator a topic list per index.
- Lesson classifier labelled 106 "variance"; it was a scorer defect. The classifier is a rough rule; a human reclassifies.
- Cross-check: keys 104: x²−4x−12=9 → x=7 (x=−3 invalid), P=9/11; 105/108: x²−2x−8=27 → x=7, T=15; 106 above; 107 sum of roots 7 (only x=7 valid). Run evidence: `work/exam-runs/2026-10-30-gen2/`, `2026-10-30-gen2-fix/`.
- Total real spend this REQ: about $0.49 (rounds 1+2 about $0.66).
