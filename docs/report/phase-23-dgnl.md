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

## Round 2: topic variety (user go, RAW-00095)
- Generator now gives each item a different topic (`genexam.TOPICS`, seed-dependent start, no repeat in a round; tests added, suite 496 OK).
- 4 items, 4 topics: arithmetic/geometric progression (104), compound interest with a withdrawal (105), conditional probability (106), counting with constraints (107). QA fails 0; generation $0.097. Benchmark: 4 pass, 0 fail, 12 calls, $0.214. Lessons: 0. Round cost about $0.31.
- Cross-check by hand: 104 d²+7d−44=0, d=4 or −11, products 231 or −504, max 231 (C); 105 100·1.08−20=88, 88·1.08=95.04 (A); 106 (0.5·0.6)/(0.5·0.6+0.5·0.4)=3/5 (B); 107 brute force over all 120 orders gives 16 (B).
- Duplicate problem fixed. Still n=7 DGNL math items in total, 0 engine defects found in them; the language and science sections are not generated yet (no code oracle for their keys, so they need a different QA design).
