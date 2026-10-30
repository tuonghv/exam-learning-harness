---
name: switch-account
description: Save and restore working context around a Claude account switch (quota or user change). Use when the user says they will switch Claude account, or at the start of a session that resumes after a switch.
---

# Switch account

State lives in files, never in conversation memory (CLAUDE.md rule 8). A switch is safe when the files hold everything.

## Before the switch (coordinator, no new subagents)
1. Let running roles finish or stop; read their handoff. Start no new role.
2. Commit every change; `git status --short` must be empty; `.claude/scripts/workflow-check.sh` PASS.
3. Write the resume plan into the active task: `.claude/scripts/tasks.sh checkpoint <TASK> --next "RESUME: <numbered steps with commands, specs and handoff paths>"`; commit it.
4. Park open decisions as `- [ ] Qn` in the REQ, with a recommended answer; open items go in `req.py focus --next`.
5. Tell the user: "ready to switch", then the TASK, the next step and anything only they can decide.

## After the switch (first turn of the new account)
1. `python3 .claude/req/req.py gaps` and `.claude/scripts/task-state.sh`, `status.sh`: they replace memory.
2. Read the active task's `next` and its `work/<TASK>/handoff/*.md` `PROGRESS:` lines; do not re-derive finished work.
3. Check `git log --oneline -8` and `git status --short`; a dirty tree means an interrupted step: finish or restore it first.
4. Subagents of the old account are gone: re-brief roles from the handoff paths (skill `coordinator`).
5. Continue with `advance.sh` for the next transition (skill `advance`); do not ask the user "shall I continue".

## Does not
Store secrets or tokens, copy conversation text into files, or change settings, hooks or permissions.
