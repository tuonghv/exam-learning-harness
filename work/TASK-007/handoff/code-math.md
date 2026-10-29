PROGRESS: COMPLETE
SKILLS: python

| id | task | topic | edge case | answer | recomputed |
|---|---|---|---|---|---|
| ex-001 | MC | log equation | domain restriction / extraneous root x=-2 | A {4} | python log2(4)+log2(2)=3 |
| ex-002 | SA | definite integral | - | (e-1)/2 | midpoint sum 0.85914091 vs formula |
| ev-003 | MC | cubic extremum, parameter | parameter boundary m=3 (double root) | A 8 | python count m in [-5,5], 36-12m>0 -> 8 |
| ev-004 | SA | probability | - | 37/42 | Fractions: 1-10/84 and direct sum |
| ev-005 | SA | complex modulus | - | sqrt(2) | python abs((3-1j)/(1+2j)), back-substitution |

Checker (`python3 -I scripts/exam.py check-examples`): no ERROR for math files; remaining ERRORs are physics pairing only (not my scope).

## Defects
None.
