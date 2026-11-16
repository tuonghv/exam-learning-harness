# Phase 126 – Free text path fixes from the DGNL English solve (TASK-126, REQ-0133)

Source: the approved paid solve (RAW-00344) of DGNL 2025 English from the free text path: 24/25 correct, but the file
first failed to parse and one group instruction was split. Designer waived: two one-line causes traced by the coordinator.

## Plan modes
Free text path only (`ingest --exam-out` without `--refined`): `api._from_questions` and `segment.split_guide`
(also used by `question_lines` on the refined path, so 126.2 applies there too). No prompt, cache key or solver change.

## Design
- 126.1 `api._from_questions`: when the header `Task` is Multiple Choice (same casefold test as parser.py:228) and a
  question has no options, add the reason `options_missing` to its incomplete reasons. The marker line makes the parser
  accept the question (parser.py:233) and the engine declines it as `missing_text` instead of the whole file being
  refused. Seen on DGNL 2025 q36-40 (error-finding items: the underlined A-D marks are lost in native text).
  Non-MC tasks keep 0-option questions unmarked.
- 126.2 `segment.split_guide`: the guide line extends over following lines while it does not end with sentence
  punctuation (`.`, `:`, `?`, `!`, `)`) and the next line starts with a lower-case letter (a wrapped sentence).
  `Questions 36-40: ... blacken your` + `choice on your answer sheet.` -> one guide, empty passage. A guide that ends
  with `.`/`:` keeps the next line as passage.
- 126.3 docs/guide/dgnl-real-exam.md: a "Free text path" section: when it works (text sections; math needs refine),
  slicing a section from the full exam file (no `--questions` without `--refined`; sections share pages), pinned
  `--model claude-sonnet-5-5` for `solve --real`, error-finding items declined, measured result 24/25 for $0.25.

## Verification ($0)
tests/unit/test_text_path_126.py (fails on HEAD for 126.1/126.2); `--fast` NEW 0; exam text of the 4 input PDFs
(full free path) HEAD vs new: only `options_missing` marker lines and joined guide lines differ.

## Out of scope
Recovering underlined options (needs refine/vision); the diacritics check on the English run was correct (the solver
wrote unaccented Vietnamese and its retry failed) – a solver-prompt matter, not changed here.
