# Phase 24 report: DGNL English items, concept round (REQ-0029, TASK-024)

## Result
- 4 four-option English items (phrasal verb, reported speech, relative clause, reading) generated with the real model under `--profile dgnl-en`; each key had two blind reviews that both chose the key letter: 0 rejected; generation $0.058.
- Unchanged `benchmark` (prompts v1.2.0): 4 pass, 0 fail, 8 calls, $0.105. Lessons: 0. Round cost about $0.16.
- n=4, one section. The generator, the blind reviewers and the solver are the same model, so agreement with the key is partly circular. Keys are `reviewed: false` opinions until a person checks them.

## Cross-check yourself
- 101 (A, put off): "postpone until data is available" = put off; put out/up/down do not fit.
- 102 (A): backshift won't -> wouldn't, tomorrow -> the following day.
- 103 (C, "which was opened"): DOUBTFUL. "which was being renovated last spring" (A) may also be accepted; the key is only safe if you read "opened" as the point. Treat as a weak item.
- 104 (B, reading): the passage states the access/safety reason; check it against the passage in `evals/generated-dgnl/inputs/english/input-104.md`.
- Files: `evals/generated-dgnl/{inputs,keys}/english/`, `manifest.json` (`key_basis`, `reviewed: false`); run in `work/exam-runs/2026-10-30-en1/`.

## Findings
- The blind double review cannot catch an ambiguous item (103) when both reviewers pick the intended letter; only a person or a different model can.
- No engine defect found; the engine is not yet challenged by these items. Harder or ambiguous items, Vietnamese-language items and science are the next rounds (REQ-0029 AC4), each needing the user's go and cap.
