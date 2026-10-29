PROGRESS: COMPLETE
SKILLS: python

| id | skill | answer |
|---|---|---|
| few-shot 002 | vocabulary collocation (take measures) | A |
| eval 003 | reading detail (sleep study) | B |
| eval 004 | sentence ordering (Linh teacher) | b-d-a-e-c |
| eval 005 | grammar, Hardly...when (trap: than) | A |

Checker: `python3 -I scripts/exam.py check-examples` -> OK: 15 pairs (6 few-shot, 9 eval); only NOTE legacy allowance for expected-001.
001 files untouched. Orderings and answers checked twice by reasoning.

## Defects
- D1 low: examples/english/*-001.md contain leftover scan text (not edited, per brief).
