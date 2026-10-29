# Workflow: tasks

- `task.json` holds the active task, `backlog.json` queued work. Move work with `.claude/scripts/backlog.sh`
  (`list` / `next` / `pick <id>` / `complete <id>`), never by hand-editing `task_id`. Honour every
  `User notes` line `task-state.sh` prints; add new ones with `backlog.sh note`.
- Plan checklist: a design doc may hold a `| # | Item | Task / doc | Done |` table. `.claude/scripts/checklist.sh`
  lists open rows; tick `[x]` in the commit that finishes a row. DONE fails while the task owns an open row.
- Active tasks live in `.claude/state/task.<TASK>.json` (`task.json` is a view). Every commit names one task
  (`Task: TASK-N`). `tasks.sh status` shows the resume view, `tasks.sh show T` the detail;
  `tasks.sh hold T --reason R --next N` / `resume T` park and restart one.
- An older queued task must not undo a newer feature (the newer requirement wins); the design states `## Newer features kept`.
