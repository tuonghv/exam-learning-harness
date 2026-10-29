PROGRESS: COMPLETE
SKILLS: python

| id | task | topic | edge case | answer | recomputed |
|---|---|---|---|---|---|
| examples/physics 001 | MC | spring period | unit g->kg | B-distractors; A 0,40 s | python3 -I: 2*pi*sqrt(0.2/50)=0.3974 |
| examples/physics 002 | SA | ideal gas isochoric | C->K | 2,67.10^5 Pa | 2e5*400/300=266667 |
| evals 003 | MC | RLC AC | sign of phase | B -0,93 rad | atan((40-80)/30)=-0.9273 |
| evals 004 | SA | interference | cm->m, boundary k=±5 excluded | 9 cực đại | lambda=2 cm, AB/lambda=5, k=-4..4 |
| evals 005 | SA | photoelectric | um->m, eV->J | 1,8.10^-19 J | 6.625e-19-4.8e-19=1.825e-19 |

Checker: `python3 -I scripts/exam.py check-examples` -> no ERROR for physics (first run had 2 final-answer mismatches, fixed). Only NOTE: legacy english.

## Defects
None.
