# Report phase 52: human review path (TASK-052; REQ-0055)

Verdict: adopted and in first use by the user. `exam.py review-pack` writes `review/<exam-id>/INDEX.md` plus one file per subject (one section per question: extracted stem and options, engine answer, short solution, flags, a `QA:` slot, and `Your review: extraction [ ] ok [ ] defect | solution (optional) ... | note`); `exam.py review-apply` reads the marks and reports extraction ok/defect and optional solution agreement with Wilson 95%, defects by printed number with notes, and `improvements.md`. `review/` is user-visible and gitignored (exam copyright).

## Scope decisions by the user
RAW-00156/00157: per exam and subject, few files, outside work/. RAW-00159: the human reviews EXTRACTION; answer correctness is the senior-solver QA's job (REQ-0056 / TASK-053). RAW-00158: stop re-running loops and ask the human (skill `review-loop`).

## Quality evidence (work/TASK-052/evidence)
829 tests, only the 3 known failures (identical at base); 14 review tests fail on base; independent oracle on 120 real questions of the 4 DGNL packs 0 mismatches; round trip with the new grammar (CRLF, two boxes, deleted lines, edited headings, `|` and unicode in notes) parses or lands in `unparsed`, never guessed; marks are merged by printed number and a changed answer is flagged; 6 mutations killed; 0 old assertions removed; no schema/solver/prompt change.

## Defects found and fixed
Stale first pack (built from an earlier run: declines and needs_review flags did not show) rebuilt from the final runs, with a header note for printed 10, 21-25, 66 whose extraction was repaired after that run; `kind: a|b` and an edited section heading were silently mis-parsed; a changed answer kept an old mark without a flag. Low, open: improvements.md carries printed numbers and kinds while the notes appear in the `review-apply` output; the header note repeats in all four subject files.

## First user review (RAW-00160)
Printed 31-32 are separate questions with options A-D and the group instruction present; the section heading repeated in each stem is noise: REQ-0057 / TASK-054.

User instructions honoured: RAW-00156, RAW-00157, RAW-00158, RAW-00159, RAW-00160, RAW-00151.
