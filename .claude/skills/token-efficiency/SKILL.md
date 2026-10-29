---
name: token-efficiency
description: Working-approach rules to save tokens and keep scope minimal - what to read, when to reuse prior results, how verbose to be, and never guessing APIs, flags or versions. Load at the start of any session, or whenever a task feels bigger than it needs to be.
---

# Token efficiency

Priority: user request, existing skill/rules, existing results (`task.json`, `phase-log.md`, `backlog.json`, git log), the minimum files needed, then asking for more scope, then expensive operations (spawning agents, remote calls).

## Scope
- Scope is the repo root. Do not read outside it unless the user names the path in the current request.
- Never read `.env*`, `node_modules/`, or `.git/objects`. Work only on the active task; load only the skill the change touches.

## Read the smallest thing that answers
| You need | Use | Not |
|---|---|---|
| Whether X is there, where, how often | `grep -n X f`, `grep -c`, `grep -rl` (Grep tool: `head_limit`) | `cat` |
| Lines around a match | `grep -n -A3 -B1 X f` | `sed -n 1,200p` |
| A test result | `... 2>&1 \| grep -E "SUMMARY\|FAIL\|ERROR"` | the full log |
| A known part of a file | Read with `offset`/`limit` after a `grep -n` | the whole file |
| Start or end of a file | `head -n N` / `tail -n N`, N small | bare `head`/`tail` |
| A long run kept as evidence | `.claude/scripts/save-evidence.sh <name> -- <cmd>`, then grep the file | printing it |

- Read a file once per session; re-read only if it changed or you will cite it as evidence.
- Before redoing work, check what is recorded (`git log --grep="Task: <id>"`, grep `TASK-NNN` in `phase-log.md`, the `task.json` sub-status). A check already passed and recorded is not re-run "to be sure".
- Count first (`wc -l`, `jq length`), then grep or `jq select` the rows you need; never read a whole report or findings file.
- Never guess API names, CLI flags, versions or config keys: read the code or run `--help`. Confirm runtime behaviour by running it.

## Output and end of turn
- Action, Result, Decision, Next; deltas only. One short line per step while working; a table only when a phase finishes. Comments say why, in few words.
- Paste real command output as evidence; never reconstruct it from memory.
- Batch pending decisions into one numbered list, each marked "pick ONE" or "approve any/all", with a recommended option. Recommend, don't survey.
- End the turn with `Decisions: None` or the numbered list, so the next message is either "keep going" or a specific answer.
