### Emergency: compaction refused at a full context (user, RAW-00297)
`!` commands and `/compact` run locally and still work when every prompt fails with
"Prompt is too long". If any hook (an old copy, another repo's) refuses compaction:
```
! git stash push -u -m pre-compact   # tree clean -> a dirty-tree PreCompact check passes; nothing is lost
/compact
! git stash pop                     # restore the uncommitted work
```
Defense in layers: (1) PreCompact hooks never exit 2 (`.claude/tests/req_kit_test.sh` 6.2/6.3);
(2) auto-compact before the limit (`/autocompact`, e.g. 300k) so it runs while there is room;
(3) the guard's `orch_big` warning -> persist, commit, suggest `/compact` now; (4) scratch files
never in the repo root.

## Keep the persisted state small

`phase-log.md` is append-only and grows ~60 lines per task. When the task
reaches DONE and the live log holds more than the last ~3 tasks, move the
older finished tasks' entries (whole `## ... - TASK-NNN - ...` sections,
unedited) to the end of `.claude/state/phase-log-archive.md`, keeping the
header/template block in `phase-log.md`. `workflow-check.sh` reads both
files, so `done` backlog audits still pass. Run it, then commit as bookkeeping
(`chore(state): archive phase log`, no `Task:` trailer). Never archive the
active task's entries.
