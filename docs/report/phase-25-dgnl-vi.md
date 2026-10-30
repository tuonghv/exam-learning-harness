# Phase 25 report: DGNL Vietnamese-language items, concept round (REQ-0030, TASK-025)

## Result
- New subject `vietnamese` in `config/subjects.json` (`prompt: null`, so no frozen release prompt changed) and profile `gen-exams --profile dgnl-vi`; keys use the same two blind reviews as `dgnl-en`.
- 4 real items (rhetoric in a poem line, two readings, spelling/word use): 0 rejected by the blind review; generation $0.079.
- Unchanged `benchmark` (prompts v1.2.0): 4 pass, 0 fail, 9 calls, $0.157. Lessons: 0. Round cost about $0.24. Suite 504 OK.
- n=4, one section. Generator, reviewers and solver are the same model, so a pass is partly circular. Keys are `reviewed: false` opinions.

## Cross-check yourself
- 101 (A, ẩn dụ): the line is from Nguyen Khoa Diem's "Khúc hát ru những em bé lớn trên lưng mẹ"; "mặt trời của mẹ" = the child, a metaphor. Sound.
- 102 (C, reading): the passage says the potter walks around the clay set on the ground and shapes by hand, no wheel. Sound.
- 103 (C, inference): fewer customers than before while the owner keeps the shop going; B (closed for good) and A (neglect) are not supported. Sound.
- 104 (C, spelling/word use): the correct spelling is "sơ suất", so A's "sơ xuất" is wrong; D's "chao dồi" should be "trau dồi"; B has "xuất sắc hoàn thành" (should be "hoàn thành xuất sắc"). C is the only clean one, but B's fault is stylistic, so the item is somewhat arguable.
- Files: `evals/generated-dgnl/{inputs,keys}/vietnamese/`, `manifest.json`; run in `work/exam-runs/2026-10-30-vi1/`.

## Findings
- No engine defect found; 15 generated items in total across math, DGNL math, English and Vietnamese, 0 failures after the earlier scorer fix. The items are too easy to produce lessons.
- Next useful step is harder items (ambiguity, multi-step reading) or a person reviewing keys; science sections are not generated.
