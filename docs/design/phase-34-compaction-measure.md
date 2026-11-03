# Phase 34 - Compaction and hook-bytes measurement (TASK-034)
Task: TASK-034 (REQ-0038) · Status: designed.

## Goal
Show whether the REQ-0006 fixes (capped SessionStart and UserPromptSubmit hook output) reduce compaction and hook bytes in a later long session, using the same breakdown as the baseline table in `docs/req/items/REQ-0006.md` Design.

## Constraints
Read-only on the session transcript; only numbers are recorded, never transcript content; evidence is a short text table.

## Generality
No exam- or subject-specific content; the method applies to any later session transcript.

## Plan modes
Not a pipeline change; no code.

## Design
Count compaction markers (system compact_boundary, isCompactSummary), the size of the transcript, and the hook output bytes per event type (SessionStart startup/compact, UserPromptSubmit, PreToolUse:Bash, skill_listing, Stop) from attachment stdout; compare per event and per MB with the baseline; list preTokens per compaction when recorded.

## Unit tests
None (no code); the table is cross-checked by two counting signals for compactions.

## Verification
`work/TASK-034/evidence/measure.txt` with the table and a verdict (reduced / not reduced per row).

## Failure modes
A transcript with few compactions gives a small sample: the verdict states the sample size; counting methods differing from the baseline: ratios marked approximate.

## Decisions
This session (12.8 MB, one compaction) is the first later transcript; a longer one can repeat the measurement.

## Out of scope
Changing the hooks; new caps.
