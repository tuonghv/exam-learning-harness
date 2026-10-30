# Phase 26 report: harder generated items (REQ-0031, TASK-026)

## Result
- `gen-exams --level harder` (prompt-only; keys still code-checked for math, two blind reviews for language). 9 real items, 3 per section (DGNL math, English, Vietnamese), in `evals/generated-hard/`: 0 rejected; generation $0.19.
- Unchanged `benchmark` (prompts v1.2.0): math 3/3, English 3/3, Vietnamese 3/3 pass; 19 calls, $0.31. Lessons: 0. Round cost about $0.50. Suite 506 OK.
- n=9. Harder in the prompt did not make the engine fail. Same model writes, reviews and solves, so a pass is partly circular and says little about accuracy.

## Cross-check yourself
- math 101 (B, 21/5): rates 1/6, 1/4, -1/12; first 2 h give 1/6; three taps 1/3 per h reach 1/2 after 1 h; then 5/12 per h for 1/2 takes 6/5 h; total 2+1+6/5=21/5. Sound.
- math 102 (B, 12960): 5!·C(6,3)·3!=14400; An first: 4!·C(5,3)·3!=1440; difference 12960. Sound.
- math 103 (B, 6): integers x=2,5,6,7,8,9 (x>=9/5 and x^2-7x+10>=0); x=3,4 fail the domain. Sound; this is a real domain trap.
- english 101 (A), 102 (B), 103 (B): grammar rule and passage support are stated in each key; 102 and 103 share the library theme (low variety). 103 B ("longer than expected") is an inference, mildly arguable.
- vietnamese 101 (B, nhân hóa + ẩn dụ in a folk line), 102 (C, cây bẹo), 103 (A, mạng as a possible cause): each follows its passage or rule. 101 is arguable (B names two devices).
- Files: `evals/generated-hard/{inputs,keys}/{math,english,vietnamese}/`; runs `work/exam-runs/2026-10-30-hard-{math,english,vietnamese}/`.

## Findings
- The solver is not stretched by multi-step DGNL items of this size: 3-step traps (domain, gap method, work-rate) all pass. To get lessons, difficulty must rise beyond what the generating model can verify: that needs gold exams from people (REQ-0025) or another model as solver or reviewer, not a harder prompt.
- Language topics in a round can repeat a theme (library); a per-item theme list would fix it (small).
