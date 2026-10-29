# Workflow — requirement ledger and status hygiene

Part of skill workflow; core rules in ../SKILL.md.

## Requirement ledger (req-kit, `docs/req/`)

The ledger records WHAT the user asked for (RAW prompts → REQ/EPIC); this workflow
(TASK in `.claude/state`) owns HOW it is built and all the evidence. One direction only:
- a user need gets a REQ (skill `req-intake`); the TASK that implements it is created with
  `backlog.sh` as usual (`requirement` = the REQ's Requirement line + `REQ-00NN`), then
  `req.py task REQ-00NN TASK-0NN`;
- REQ status follows its TASK, never runs ahead: after a TASK transition, move the linked REQ
  in the same turn (`req.py status REQ-00NN <STATE> --evidence "TASK-0NN <STATE>, <commit/test>" --next "<step>"`).
  `docs/req/config.json` checks run `.claude/req/task_gate.py`, which refuses the move while
  a linked TASK is behind. Tick REQ acceptance items from the TASK's verification evidence
  (`req.py ac REQ-00NN AC1,AC2 --evidence "..."`); no second verification;
- stage the changed `docs/req/items|epics|raw` files in the same transition commit.
A `/next` or "continue" style prompt is not a requirement: `req.py raw ignore <RAW> --reason ...`.

## Status hygiene across sessions and roles

Many sessions and roles share one `task.json`. If status is not kept truthful,
a later session cannot tell where work really stands and silently redoes or
skips a phase. So, every time you touch the task:

- **Stamp it:** `updated_at` = now in ISO8601 UTC
  (`date -u +%Y-%m-%dT%H:%M:%SZ`); `updated_by` = your role/session. This is how
  the next session sees *when* and *by whom* status last moved, and whether the
  task is stale.
- **Keep `state` and the sub-statuses in agreement.** Do not mark a later phase
  done while an earlier one is still pending, and advance `state` when you finish
  a phase — don't leave `state` lagging behind the evidence. The check fails on a
  broken trail (a later phase passed while an earlier is not) and on `state`
  falling two+ phases behind recorded evidence; it warns at one phase of lag (the
  normal "just finished / awaiting go-ahead" boundary).
- **Always set `next`** to the concrete next action, so any session/role can pick
  up without guessing.
- **The phase log is shared memory.** Append one entry per transition; the check
  requires a `## <STATE> - <task_id> - <ts>` entry for every phase from DESIGN up to the current
  state, so the audit trail has no holes.

## "Is anything not done yet?"

`bash .claude/scripts/status.sh` — one command, answers this directly: lists
any backlog items not `done`, plus the active task's state and per-phase
status. Exits 0 when nothing is pending, 1 otherwise. Use this instead of
hand-reading `backlog.json`/`task.json` whenever asked for an overall status
or "what's left" — it's the deterministic check for that question, same as
`workflow-check.sh` is for state consistency.
