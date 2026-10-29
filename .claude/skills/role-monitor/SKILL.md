---
name: role-monitor
description: Watch every launched role (designer, coder, tester, verifier) with one standard, cheap watcher, and never miss the coordinator's own follow-ups (commit, next, open items, issues, stuck roles) via the team-status block. Load when you launch a role, a watcher event arrives, or before the next brief.
---
# role-monitor (coordinator only, REQ-0024)

One watcher per launched role, armed right after the `Agent` call, in the same turn. It prints only
the events you act on, so you never poll, sleep or read transcripts.

## Arm

> **Monitor is disabled in this setup (user, RAW-00160).** When the `Monitor` tool is not available, do not arm a
> watcher: rely on the `Agent` completion notification, and on `Expect:` expiry read the handoff's `PROGRESS:` line
> (skill `coordinator` §2 follow-up). `watch-role.sh status TASK-0NN` still works as a one-shot Bash call.

```
Monitor  description: "<role> TASK-0NN <items>"   timeout_ms: min(2 x Expect + 2 min, 30 min)
command: .claude/scripts/watch-role.sh TASK-0NN <role> <Expect minutes from the brief>
```
`Expect` is the brief's `Expect:` value, so the brief and the watcher agree. For a longer Expect,
re-arm once on expiry. Track all role runs of a task with `.claude/scripts/watch-role.sh status TASK-0NN`
(`work/TASK-0NN/roles.log`: start, done, stall, timeout per role); use it instead of memory.

## Events and what to do

| Event | Meaning | Action |
|---|---|---|
| `START` | watcher armed | nothing |
| `PROGRESS <role>: <line 1>` | handoff line 1 changed (`(stale, earlier run)` = left from a previous brief) | nothing, unless it says PARTIAL/BLOCKED |
| `IDLE` | no writes under work/<task> and no tree change for 5 min | wait for STALL unless Expect is long; then the checklist |
| `STALL` | Expect passed without COMPLETE; facts on the line | root-cause checklist below |
| `DONE` | handoff rewritten with `PROGRESS: COMPLETE` | wait for the Agent reply (≤ 8 lines); open the handoff only if a decision needs it |
| `TIMEOUT` | 2 x Expect, still not COMPLETE | checklist; if it is blocked on the brief, stop it and re-brief smaller |

The Agent completion notification is the reply itself; the watcher only covers the time before it.
DONE, STALL and TIMEOUT are followed by the team-status block (indented), below.

## Team-status block: nothing missed (RAW-00116)

`.claude/scripts/team-status.sh [TASK-0NN]` (read-only, $0) prints only lines that need action. Run it
before every brief, after every role reply, and before ending a turn. Clear every line, top-down:

| Line | Do |
|---|---|
| `TASK ... next:` | `next` still true? If not, fix it in the next commit |
| `COMMIT` | role edits waiting: `wip(<area>): TASK-0NN <items>` via commit-check.sh (never piped: `commit-check.sh msg && git commit`); `includes .claude/state` = finish the transition |
| `PATCH pending/conflict` | review, `git apply`, add the name to `work/TASK-0NN/patches/APPLIED`, rerun the checks; conflict = rebase brief to the role |
| `QUESTION` | a role waits on you: answer by SendMessage now (decide, or ask the user with a recommendation) |
| `HANDOFF` | a PARTIAL/IN_PROGRESS with no running role = re-brief the rest |
| `FINDINGS` | new ids since the last look: route them (design fix, backlog, or note in the report) |
| `LEDGER` | triage the RAWs (skill req-intake) before the turn ends |
| `BLOCKED` | attempts ≥ 3: stop retrying, ask the user |
| `BACKLOG` / `ROLES` | context only: what is queued, which role ran last |

## Root-cause checklist (stuck role), cheapest first

1. The STALL line: `no handoff yet` = never started writing (brief too big, or reading too much);
   `IN_PROGRESS` with an old last write = looping or waiting on a refused call.
2. `head -20 work/TASK-0NN/handoff/<file>` and `ls -t work/TASK-0NN/` (patches, evidence): where it is.
3. Guard refusals (a protected path, a denied command): `tail -5 .claude/agent_setup_violations.jsonl`,
   the hook log; each record names the role and task. No refusals but `over_soft` for the role = its
   context is large (`detail` = tokens): it is over-reading or writing one huge file; the record `ts`
   also tells how long since its last tool call. Protected work is yours (skill `coordinator` §2b): do it, or send the patch route.
4. Then one `SendMessage` to the role: what you saw, the one fix or decision, and "save the handoff and
   reply PARTIAL if more than N turns remain". No chatter, no second message before its reply.
5. Two stalls on the same item = the brief is wrong: split it (smaller items, fewer files, lower Turns).

## Token rules

- Never read the agent's output/transcript file; never `sleep` or loop to poll; one watcher per role.
- Read only watcher lines and the ≤ 8-line reply; the handoff only when a decision depends on it.
- Tell the user one line per meaningful event (started, stuck + cause, done), not every PROGRESS line.
- Prefer the block over separate git status / task.json / ledger reads: one call, a few lines.

Sizing lessons (observed): `references/sizing-lessons.md`
