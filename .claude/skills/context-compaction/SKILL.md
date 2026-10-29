---
name: context-compaction
description: When and how to suggest ending a context boundary in this repo - after state is persisted in task.json/phase-log.md/backlog.json and committed to git. Use at the end of a phase transition, after reaching DONE, when the user asks to compact or clear, or when context has grown large between tasks.
---

# Context compaction

State lives in `.claude/state/task.json`, `.claude/state/phase-log.md`,
`.claude/state/backlog.json`, and git commits - never in conversation memory
(CLAUDE.md rule 8). Once a phase's evidence is written to those files and
committed, nothing about it needs to survive in this conversation's context.

`/clear` and `/compact` are user-typed local commands. This agent cannot run
them, cannot toggle auto-compaction, and never claims either happened on its
own.

## Boundary (all must hold)

1. A phase transition just closed: `workflow-check.sh` passed for the new
   state and the transition is committed (`commit` skill).
2. `git status --porcelain -- . ':!manifest.json'` is clean - no uncommitted
   `task.json`, `phase-log.md`, doc, or code changes left over from this
   transition (`manifest.json` is scan progress, rewritten by every scan and
   never part of a workflow commit). The PreCompact hook checks the same scope.
3. `task.json`'s `next` field names a concrete next action (or the task is
   `DONE` and `bash .claude/scripts/backlog.sh next` names the following
   task, if any).
4. `python3 .claude/req/req.py check` shows no `[GAP]` (every RAW triaged),
   and a REQ in progress has `req.py focus --next "<step>"` set. The PreCompact
   hook ignores new RAW files, `INDEX.md` and `STATE.json`; edited REQ/EPIC
   files still count as uncommitted.

## Never let compaction be blocked (RAW-00290..00294, 2026-10-02)

A session once filled its context while the tree held stray untracked files
(`nohup.out`, `tmp_*.sh`). The PreCompact hook then exited 2, which *blocks*
both `/compact` and auto-compact, and every prompt failed with "Prompt is too
long" until the user ran `/clear` and lost the conversation.
- `pre-compact-check.sh` only warns (exit 0, dirty list on stdout). Never
  make a PreCompact hook exit 2 or otherwise block; uncommitted work is
  committed *after* compaction.
- Keep the tree clean as you go: scratch scripts and logs go to
  `$CLAUDE_JOB_DIR/tmp` or `work/<T>/`, never the repo root; run
  `nohup` with an explicit log path outside the repo.
- Keep the main session small: big outputs go to files, reads use
  `limit`, long work goes to roles. On the guard's `orch_big` warning, persist
  state, commit, and suggest `/compact` at once instead of continuing.

Emergency (compaction refused at a full context): `references/emergency-and-archive.md`

Not a boundary: mid-implementation with tests not yet run, a failing check,
or a state change not yet committed. Compacting there loses work-in-progress
context that isn't in a file yet.

## At the boundary

Add one line to the end-of-turn summary:

- A phase closed (or the task reached `DONE`) and nothing else is queued in
  this turn: `Context boundary: state persisted; run /clear.`
- The very next step is the next phase of the same task (e.g. UNIT_TESTED
  right after IMPLEMENTING) and this turn's detail would help it:
  `Context boundary: state persisted; run /compact.`

Boundary not met → no line; finish persisting state first instead of
suggesting compaction.

Keeping the persisted state small (phase-log archive): `references/emergency-and-archive.md`

## After /clear or /compact

The SessionStart hook prints the resume point (`task-state.sh`, backlog,
uncommitted state, gate warnings); act on it per `workflow`'s (`references/resume-and-failure.md`) "Resuming an
in-progress task". After `/compact` (no new session) run
`bash .claude/scripts/task-state.sh` yourself. A second block
(`=== Requirement ledger ===`, from `.claude/req/hook_context.py`) gives the
focus REQ and its next step; with a focus, `req.py gaps` is the only
"what is left" answer — not the compaction summary. Don't ask the user to re-explain what's
already recorded there, and don't re-read files already covered by
`token-efficiency`'s reuse rules.
