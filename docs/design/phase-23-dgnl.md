# Phase 23: DGNL-style generated items (REQ-0028, concept)

## Goal
The generator also writes Vietnamese university competency assessment (DGNL) style items so the learning loop trains on that exam type. Start with math/logic/data analysis; same files, QA and benchmark as phase 22.

## Design
- `gen-exams --profile dgnl` (default `hs` = phase 22). Subject stays `math` (the checker allows only the five subject dirs); the input header says `Exam type: University Entrance (DGNL)`, `Task: Multiple Choice`, `Level: University entrance`.
- Prompt `prompts/dev/genexam_dgnl.md`: one 4-option item, reply `{skill, question, options{A,B,C,D}, correct, solution, check}`; options are numbers or fractions, `check` is the arithmetic of the correct option.
- `check_reply` (dgnl): options A-D present, `correct` in A-D, the four option values differ, `check` equals the correct option value; a wrong key is a bad reply (retry once). `final_answer` = the letter.
- Key file: `Final answer: B`, `Correct answer: B. <text>`, solution, per-option explanation line, grading (as `evals/keys/english/expected-003.md`). Input: question plus `A. ... D.` lines. Leak check and solution QA as before; QA compares the reviewer's letter to the key.
- Manifest: `profile`, `source: model knowledge, not an official exam`, `reviewed: false`. Engine, solver prompt and scorer unchanged.

## Tests ($0)
dgnl mock writes a pair that passes the format checker; a wrong letter, duplicate option values and a missing option are rejected; QA compares letters; hs behaviour unchanged (existing tests).

## Limits
Model knowledge of the format, not official items; the same model writes and solves. Real round needs the user's go.
