---
name: role-monitor
description: Watch every launched role (designer, coder, tester, verifier) with one standard, cheap watcher, and never miss the coordinator's own follow-ups (commit, next, open items, issues, stuck roles) via the team-status block. Load when you launch a role, a watcher event arrives, or before the next brief.
---
# role-monitor (coordinator only)

One watcher per launched role, armed right after the `Agent` call, in the same turn. It prints only the
events you act on, so you never poll, sleep or read transcripts.

## Arm

`Monitor` is disabled in this setup. Rely on the `Agent` completion notification; on `Expect:` expiry read the
handoff's `PROGRESS:` line. `.claude/scripts/watch-role.sh status TASK-0NN` still works as a one-shot Bash
call (`work/TASK-0NN/roles.log`: start, done, stall, timeout per role); use it instead of memory.
Where Monitor is available: `command: .claude/scripts/watch-role.sh TASK-0NN <role> <Expect minutes>`,
`timeout_ms` = min(2 x Expect + 2 min, 30 min); re-arm once on expiry.

## Events and what to do

| Event | Meaning | Action |
|---|---|---|
| `START` | watcher armed | nothing |
| `PROGRESS <role>: <line 1>` | handoff line 1 changed (`(stale, earlier run)` = from a previous brief) | nothing, unless PARTIAL/BLOCKED |
| `IDLE` | no writes under work/<task> and no tree change for 5 min | wait for STALL unless Expect is long; then the checklist |
| `STALL` | Expect passed without COMPLETE | root-cause checklist |
| `DONE` | handoff has `PROGRESS: COMPLETE` | wait for the Agent reply (≤ 8 lines); open the handoff only if a decision needs it |
| `TIMEOUT` | 2 x Expect, still not COMPLETE | checklist; if blocked on the brief, stop it and re-brief smaller |

DONE, STALL and TIMEOUT are followed by the team-status block.

## Team-status block: nothing missed

`.claude/scripts/team-status.sh [TASK-0NN]` (read-only, $0) prints only lines that need action. Run it before
every brief, after every role reply, and before ending a turn. Clear every line, top-down:

| Line | Do |
|---|---|
| `TASK ... next:` | `next` still true? If not, fix it in the next commit |
| `COMMIT` | role edits waiting: `wip(<area>): TASK-0NN <items>` via commit-check.sh (never piped); `includes .claude/state` = finish the transition |
| `PATCH pending/conflict` | review, apply, add the name to `work/TASK-0NN/patches/APPLIED`, rerun the checks; conflict = rebase brief to the role |
| `QUESTION` | a role waits on you: answer by SendMessage now (decide, or ask the user with a recommendation) |
| `HANDOFF` | a PARTIAL/IN_PROGRESS with no running role = re-brief the rest |
| `FINDINGS` | new ids since the last look: route them (design fix, backlog, or note in the report) |
| `LEDGER` | triage the RAWs (skill req-intake) before the turn ends |
| `BLOCKED` | attempts ≥ 3: stop retrying, ask the user |
| `BACKLOG` / `ROLES` | context only |

## Root-cause checklist (stuck role), cheapest first

1. The STALL line: `no handoff yet` = never started writing (brief too big, or reading too much);
   `IN_PROGRESS` with an old last write = looping or waiting on a refused call.
2. `head -20 work/TASK-0NN/handoff/<file>` and `ls -t work/TASK-0NN/`: where it is.
3. Guard refusals: `tail -5 .claude/agent_setup_violations.jsonl`, the hook log; each record names role and
   task. No refusals but `over_soft` = its context is large (over-reading or one huge file). Protected work
   is yours (skill `coordinator`): do it, or send the patch route.
4. One `SendMessage` to the role: what you saw, the one fix or decision, and "save the handoff and reply
   PARTIAL if more than N turns remain". No second message before its reply.
5. Two stalls on the same item = the brief is wrong: split it (≤ 3 design items, fewer files, lower Turns;
   a new test suite gets its own brief).

## Token rules

- Never read the agent's transcript file; never sleep or loop to poll; one watcher per role.
- Read only watcher lines and the ≤ 8-line reply; the handoff only when a decision depends on it.
- Tell the user one line per meaningful event (started, stuck + cause, done).
- Prefer the block over separate git status / task.json / ledger reads.
