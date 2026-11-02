# Report phase 53: senior-solver QA in the review pack (TASK-053; REQ-0056)

Verdict: adopted and in use. `review-pack --qa FILE` fills a `QA:` line per question (QA letter, confidence, reasoning) and a verdict: agrees, differs, flawed (`flawed (engine X vs QA Y)` when they differ), qa-only (engine declined), unresolved, engine-nonletter (the engine returned a value that matches no unique option). INDEX.md gets `qa` and `verdict` columns and per-subject counts. QA lines persist across re-runs and the verdict is recomputed from the current engine answer; the user's marks are kept by printed number. Skill `solve-qa` documents how to run the QA without API cost.

## DGNL sample result (QA = independent in-session reads of the PDF, adjudication overrides; same model family as the engine, so not an official key)
Vietnamese agrees 21, flawed 8 (4, 8, 11, 14, 18, 21, 23, 24), qa-only 1; English agrees 30; Math agrees 29, qa-only 1 (66); Science agrees 23, flawed 3 (112 shown as engine D vs QA A, 114, 120), engine-nonletter 4 (value answers such as `230%` with no unique matching option). 3 of the 7 value answers were matched to an option and agree.

## Evidence (work/TASK-053/evidence)
847 tests, only the 3 known failures (identical at base); 32 review tests OK; independent oracle on the real rebuilt pack 0 mismatches over 120 rows; mutations killed (stale verdict, wipe on re-run, first of two options, 4-cell flawed). Tester defects D1 (QA wiped on re-run), D2 (value answers marked differs), D3 (4-column tables), D4 (stale verdict), D5 (flawed hid engine vs QA) fixed.

## Limits
QA and engine are the same model family; agreement is not accuracy; value answers with no unique option stay `engine-nonletter`; the first QA data comes from reads made before the extraction repairs of printed 10, 21-25, 66 (header says so).

User instructions honoured: RAW-00159, RAW-00161, RAW-00162, RAW-00151, RAW-00163.
