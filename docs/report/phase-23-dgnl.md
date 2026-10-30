# Phase 23 report: DGNL-style generated items, concept round (REQ-0028, TASK-023)

## Result
- 3 four-option DGNL-style items (probability, Vietnamese) generated with the real model, each QA-reviewed by an independent call: 0 QA fails; generation $0.068.
- Unchanged `benchmark` (prompts v1.2.0) on them: 3 pass, 0 fail, 6 calls, $0.114. Lessons: 0. Total about $0.18.
- n=3, one section (math/logic), same model writes and solves: shows the DGNL path works end to end, not that the engine is accurate on DGNL.

## Cross-check yourself
- 101 (key B, 12/37): 12 balls, C(12,3)=220; at least one red: 220−C(7,3)=185; all three colours: 5·4·3=60; 60/185=12/37.
- 102 and 103 (key 3/7 and 3/7): box II then has 7 balls; P(red)=3/8·5/7+5/8·4/7=35/56; P(red moved | red)=15/35=3/7.
- Files: `evals/generated-dgnl/{inputs,keys}/math/`, `manifest.json` (`source: model knowledge, not an official exam`, `reviewed: false`); runs in `work/exam-runs/2026-10-30-dgnl1/`.

## Findings
- 102 and 103 are the same problem (only "trắng"/"xanh" differs): the generator's variety is weak (same as phase 22). Next fix: a topic list per index.
- Items are probability only; real DGNL math covers sequences, percent, logic, data reading. Topic variety is the next improvement, then the language and science sections (one per round).
