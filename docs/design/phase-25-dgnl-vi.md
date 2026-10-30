# Phase 25: DGNL Vietnamese-language items (REQ-0030)

## Goal
The third DGNL section (tieng Viet: usage, word choice, short reading) as generated items, same loop as phases 22-24.

## Design
- Subject: the checker only knows subjects from `config/subjects.json`, and `literature` forces an open rubric. Add subject `vietnamese` there (aliases `vietnamese`, `tiếng việt`; Closed, `official_key`, `language: vi`, `prompt: null`). `prompt: null` means no subject addendum, so no frozen release prompt changes. Add it to `examples/FORMAT.md` line 14.
- `gen-exams --profile dgnl-vi`: subject/dir `vietnamese`, header `Subject: Vietnamese`, `Exam type: University Entrance (DGNL)`, `Task: Multiple Choice`, `Language: vi`, instructions in Vietnamese.
- Prompt `prompts/dev/genexam_dgnl_vi.md`: one 4-option item (spelling/word choice, sentence structure, meaning of idiom or word, short reading), same JSON as dgnl-en; `TOPICS["dgnl-vi"]`.
- Key trust: `blind_qa` (two blind reviews), shared with dgnl-en through a `BLIND` profile tuple; `check_mc` reused.
- Engine, solver prompts, scorer unchanged.

## Tests ($0)
vi mock pair passes `check-examples`; subject must match profile; one disagreeing reviewer rejects; topic in prompt.

## Limits
Same circularity as dgnl-en; Vietnamese usage keys are the most opinion-prone, so the report lists every item for a person to check.
