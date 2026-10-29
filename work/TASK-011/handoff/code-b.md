PROGRESS: COMPLETE
SKILLS: python

| id | skill | answer |
|---|---|---|
| ex-001 | binary->decimal MC | C (90) |
| ex-002 | boolean MC | C (a=1,b=1,c=0) |
| ev-003 | loop trace MC | B (12) |
| ev-004 | SQL COUNT with NULL, short | 3 |
| ev-005 | /26 host count, short | 62 (expr 2**(32-26)-2) |

Files: examples/informatics/{input,expected}-001..002.md; evals/inputs/informatics/input-003..005.md; evals/keys/informatics/expected-003..005.md. All use `Subject: Tin hoc`.

## Recompute (python3 -I, sqlite3)
int('1011010',2)=90; reversed 45; shifted-left 180. Truth table F=(a or b) and not(a and c): true only for (0,1,0),(0,1,1),(1,0,0),(1,1,0). Loop (s=0,i=1; while i<10: s+=i; i+=3) -> s=12, i=10 (with i<=10 would be 22). sqlite: count(*) where diem<5 = 3; diem>=5 = 2; count(distinct diem)=4; count(diem)=5; count(*)=7. 2**(32-26)-2 = 62; 2**6 = 64; /27 -> 30.

## Defects
- none. check_examples.py: "OK: 25 pairs" (did not reject the subject; may not scan informatics until coder A's router change, unverified).
