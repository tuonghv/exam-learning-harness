# Report: TASK-008 English and Literature examples (REQ-0004)

**Verdict: adopted.** English 002-005 (vocabulary, reading, ordering, grammar) and Literature 001-005, few-shot and eval kept apart.

## Verification
- `check-examples` OK (20 pairs): verbatim quotes, key-leak and format checks. Suite 211 OK incl. English oracle tests (ordering permutation, passage facts).
- Verifier re-solved English 002-005 before reading keys: all match. AC1-AC4 pass. Literature rubrics total 10; quotes verbatim.

## Limitations
- Literature has no independent answer proof (rubric only, by design). Minor: "Any other reading is accepted" line absent in literature keys 003-005 (the leak check flags it as a repeated line); english key 003 option A reason could be tighter. Verifier read files by hand, not the evidence files.
- Not yet measured on a real model (REQ-0009, needs user go).

## Next
REQ-0009 real benchmark (dry-run first, cap shown), architecture doc update.
