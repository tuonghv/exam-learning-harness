PROGRESS: COMPLETE
SKILLS: none

Created under prompts/dev/lang/vi/: system.md, exam/solve.md, verification/verify_answer.md, subjects/{math,physics,english,literature}.md (Vietnamese, same rules/numbering/limits; JSON examples byte-identical to default, verified by diff).

| file | marker : grep -c (all >= 1) |
|---|---|
| system.md | answer_status 1, uncertain 2, unanswerable 1, not_independently_verified 1, uncertainty 1, issues 1, sqrt(3) 1 |
| exam/solve.md | Language: 2, expr 2, checks 2, answer_status 2, schema_version 1, Open 1, c-a-d-b-e 1 |
| verification/verify_answer.md | verdict 3, agree 4, disagree 2, unsure 2, findings 3, reviews 1 |
| subjects/literature.md | Passage 1 |

Note: physics.md keeps `Given:`/`Find:` verbatim (labels the solver writes).

## Defects
none
