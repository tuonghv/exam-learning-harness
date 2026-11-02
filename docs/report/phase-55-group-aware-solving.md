# Report phase 55: group-aware solving (TASK-055; REQ-0058)

Verdict: adopted (option A, smallest change, same call count). The engine keeps one whole-file round-1 call and now: shares group context before `--questions` slicing (a slice starting mid-group keeps guide + passage); recognises more group range forms (`từ câu N đến câu M`, `Câu 3, 4`, `Questions 1 and 2`); derives groups and kinds (independent / passage / dependent) with dependency refs (`parser.groups`, `deps`); renders labelled files with the passage once per group, passes sibling answers on retry and QA; declines `missing_text` for a ref to an absent question or a promised but empty passage (not when the stem carries its own text: warn only); warns `group_link_uncertain` instead of guessing a link; records source pages (`Source pages:` -> `pages` in result.json); `--dry-run` prints the same grouped prompt as a real run. Unlabelled/old files keep byte-identical solve, retry and QA prompts.

## Evidence (work/TASK-055/evidence)
890 tests, only the 5 known failures (identical to baseline 083d0e4); golden hashes of parse, solve, retry and QA prompts equal baseline for 25 inputs; e2e mock statuses (q99 declined, empty passage declined, vague ref warns); mutations (no sharing, no sibling answers, decline off, slice order) caught. Defects found by the tester and fixed: D1 dry-run printed the raw file (major), D2 `## Group` header on single questions, D3 false decline when the stem holds the passage (refcheck via patch, TASK-047 owns the file).

## Limits
No paid real run on a DGNL English/VN reading slice. Prompt release not bumped (`prompts/dev/exam/solve.md` has one rule line; config pins v1.0.0). Visuals stay text-only in `solve`; pre-solve figure warning and page-image check for flagged questions are REQ-0059. The dependency-cycle case (design unit 6) has no dedicated test (UNVERIFIED by the verifier). Dependency regexes are Vietnamese/English only; sibling-retry test is thin (one per path).

User instructions honoured: RAW-00167, RAW-00168, RAW-00169.
