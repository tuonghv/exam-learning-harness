# Report phase 33: one-line UserPromptSubmit hook output (TASK-033; REQ-0006)

Verdict: adopted. `.claude/req/hook_capture.py` now prints one line per prompt (saved-RAW notice joined with the ledger brief by ` | `); same information, same substrings, no settings or wiring change. REQ-0006 AC4 and AC5 are met; AC6 moved to REQ-0038.

## Evidence (work/TASK-033/evidence/)
- `req_kit_test.txt`: pass=41 fail=0 (new section 9: captured prompt prints exactly one line and keeps the notice + brief; bare slash command prints at most one line). Mutation: the old hook fails 9.1 and 9.3 (39/2), observed by the coordinator.
- `hook_lines_old.txt` 2 lines vs `hook_lines_new.txt` 1 line on a bare slash prompt. PreToolUse output was already 0 B (inspector measurement 2026-10-31); SessionStart output 1.4 KB, under its 2 KB cap.
- AC5: the `autoCompactWindow` override is gone from both settings files (grep empty; user RAW-00012).

## Decision to review (coordinator, autonomy rule)
REQ-0006 AC6 (post-fix compaction count over a comparable session) cannot be proven now: the data does not exist until a later session has run. Ticking it would be false, so it was split into REQ-0038 / TASK-034 (queued) and REQ-0006's AC6 line was marked moved. This changes an acceptance item without the user; revert by restoring the checkbox if undesired.

## Limitations / process notes
- The hook change landed in the "pick TASK-033" commit (a staging slip); history is unchanged, evidence is the test files at HEAD.
- Tests created real RAW-00139..00141 in the ledger (all IGNORED, coordinator hook tests); the tests in req_kit_test.sh use a temp ledger.
- Verifier role was waived (guarded path, small change); verification is coordinator-recomputed counts plus a mutation run.

User instructions honoured: RAW-00128, RAW-00129, RAW-00138.
