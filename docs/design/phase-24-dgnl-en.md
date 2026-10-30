# Phase 24: DGNL English items with blind double review (REQ-0029)

## Goal
Language items have no code oracle, so key trust comes from two independent blind reviews instead. Same files, benchmark and lessons as phases 22-23.

## Design
- `gen-exams --profile dgnl-en`: subject `english` (dir `english`), header `Exam type: University Entrance (DGNL)`, `Task: Multiple Choice`, `Language: en`.
- Prompt `prompts/dev/genexam_dgnl_en.md`: one 4-option grammar / vocabulary / short-reading item (a 2-4 sentence passage only for reading); reply `{skill, question, passage?, options{A-D}, correct, solution}`. No `check`.
- `check_mc(obj)`: A-D non-empty distinct texts, `correct` in A-D, `solution` non-empty; `final_answer` = letter.
- Blind QA `blind_qa(llm, obj)`: two calls with `blind_prompt` = question (+ passage) + options only, never the key or solution; asks `{"answer": "A-D"}`. Pass only if both letters equal the key; one disagreement or unreadable reply = fail (item to `rejected/` with both letters in `qa-N.txt`).
- Topic list `TOPICS["dgnl-en"]` (tense, conditionals, word choice, collocation, reported speech, passive, short reading detail, reading inference), one per item.
- Input: passage section when present, then question and `A.`-`D.`; key as in phase 23; manifest adds `key_basis: "2 blind reviews"`.
- Engine, solver prompt, scorer unchanged. The solver sees the same text as a blind reviewer, so agreement between solver and key is partly circular: lessons from this profile are weaker evidence than from math; the report says so.

## Tests ($0)
dgnl-en mock writes a pair that passes the format checker; reviewers' prompts contain no key, no solution; one disagreeing reviewer rejects to `rejected/`; duplicate option texts and bad letter rejected; prompt carries the topic.

## Limits
Keys are model opinions confirmed by the same model family; a person must spot-check. Vietnamese-language items are a later round.
