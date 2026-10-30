# Phase 26: harder generated items (REQ-0031)

## Goal
15 easy items gave 0 lessons. Harder items should make the engine fail sometimes, which is what produces lessons.

## Design
- `--level harder` (new choice beside easy|hard). `Level:` already reaches the generator; each DGNL prompt (`genexam_dgnl*.md`) gets a Difficulty paragraph defining `harder`: math = 4-6 steps with a trap and no single-formula shortcut; language = near-correct distractors, a rule with an exception, reading that needs inference across sentences; the key must still be defensible by a rule or by the text.
- Key trust unchanged: math keeps the code `check`, language keeps the two blind reviews; a harder item that the reviewers split is rejected (that is also a signal).
- Engine, solver prompts, scorer unchanged. Round writes to `evals/generated-hard/` so the easy sets stay intact.

## Tests ($0)
`--level harder` accepted; the built prompt carries "Level: harder" and the Difficulty text for each DGNL prompt.

## Limits
Harder items raise the share of bad or ambiguous keys; the report separates engine failures from bad keys by hand.
