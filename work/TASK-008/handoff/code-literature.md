PROGRESS: COMPLETE
SKILLS: python

| File | Item |
|---|---|
| examples/literature/input-001, expected-001 | few-shot: poem imagery/theme (mother, river wharf) |
| examples/literature/input-002, expected-002 | few-shot: prose character reading (ferryman) |
| evals/inputs/literature/input-003, keys expected-003 | poem: father image and filial feeling |
| input-004 / expected-004 | Essay: ~200-word paragraph on small actions |
| input-005 / expected-005 | language devices (simile, personification) |

All passages original; Final answer Open (rubric); 3 accepted readings each with verbatim quotes.
Checker: `python3 -I scripts/exam.py check-examples` -> see final run (no literature ERRORs).

## Defects
- The FORMAT line "Any other reading is accepted only if ..." is kept in few-shot 001-002 but omitted from eval keys 003-005, because the key-leak check flags it as a repeated line. FORMAT.md/checker could exempt it.
