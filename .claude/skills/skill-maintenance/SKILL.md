---
name: skill-maintenance
description: How the skill-curator turns role lessons (L: lines in handoffs) into small reviewed patches of skill, agent-body and CLAUDE.md rule lines. Load when curating lessons after VERIFIED, or when a lesson must be placed in an owner file.
---

# Skill maintenance (TASK-074)

Skills: the curator edits `.claude/skills/*` in place under main's task grant (user, RAW-00537); main
reviews the diff and commits. Agent files and CLAUDE.md: patches under `work/<T>/patches/`, main applies. Helper: `.claude/scripts/lessons.py` (collect, similar, patch,
mark-from, scope).

## Steps
1. `lessons.py collect work/<T>` lists new lessons as JSONL and ends with `TOTAL new=N seen=N bad=N`.
   `new=0` -> write `curate.md` with no rows, no patch, reply DONE.
2. Per lesson run `lessons.py similar "<text>"`. Read only the top hits (`Read` with offset/limit
   around `path:line`). A hit with `raw=RAW-xx` is a user rule.
3. Decide one verdict:
   - `merged`: a hit already says it but lacks the new fact. Replace that line (one line out, one line in).
   - `new`: nothing covers it. Add one line in the one owner file (below).
   - `rejected` with reason `no-evidence`: the lesson's `evidence=` is `-` or not an existing repo file.
   - `rejected`: it contradicts a RAW-cited line, repeats a line with no new fact, is a one-off
     (a number or path valid once), or is the wrong layer. Give the reason in the table.
4. Skill target with the grant: Edit the line (same anchor rule). Otherwise build the patch: `lessons.py patch --file F --anchor "<exact line>" (--replace|--after) "<text>"
   --out work/<T>/patches/NN-<slug>.py`. The anchor must occur once; a re-run changes nothing.

## Owner file (one per rule)
| Lesson is about | Owner |
|---|---|
| How to read, scope, report output | `token-efficiency` |
| Bash or Python habits | `bash` / `python` |
| Test writing | `unit-test` |
| Real verification | `verify` |
| Role hand-offs, commits, state | `coordinator` / `workflow` / `commit` |
| A never-break rule | `CLAUDE.md` only if a user RAW states it; else reject |

## Rules
- Edit a skill line only with evidence of a seen failure (refusal, repeat failure, wasted turn): the
  lesson's `evidence=` path must exist. `mark-from` refuses a skill edit without it (rc 2). Put the evidence path in the reason cell.
- Never delete or weaken a line that cites a RAW id or a user date.
- Never edit agent frontmatter (tools, skills, model, maxTurns). Propose it in `curate.md`
  under `PROPOSALS`; main decides. A body edit of an agent file sets `AGENT_FILES_CHANGED: yes`.
- A lesson line is a habit in one sentence, with the task id; it replaces the old "Going faster" append.
- No skill over 80 lines may grow. If the owner is over 80, reject with reason `size` and name TASK-093.
- Keep the line short; no logs, no code blocks, no secrets, no repo source content.
- Touch only paths the allowed set of `lessons.py scope` lists.

## curate.md (work/<T>/handoff/curate.md)
Line 1 `PROGRESS: COMPLETE`, line 2 `SKILLS: skill-maintenance, token-efficiency`, then:

| key | verdict | path[:line] | reason |
|---|---|---|---|

then `AGENT_FILES_CHANGED: yes|no`, the patch list, and `PROPOSALS:` (or `none`).
`path` is the file the line lives in or is added to; for `rejected` it is the closest hit.

## Watch and revert (REQ-0033 AC8, main)
`mark-from` stores each skill edit as a `watch` row (skill, commit, roles, hunk). Row `revert`: `replace` (hunk = old block, 1+ lines), `delete` (pure addition, hunk empty) or `manual` (unpaired; `watch` shows `revert: manual`); `mark-from --base REV` pairs an edit already committed and fills a manual row in place.
At the next task's DONE:
`lessons.py watch` lists them; `process_metrics.py <tasks> --roles r1,r2 --compare base.json` prints
`verdict ok|worse|insufficient` (rc 5 = worse: refusals or PARTIALs up, or turns up over 10%/2).
`ok` -> `lessons.py watch --set KEY kept`; `insufficient` -> `kept-unproven`; `worse` ->
`lessons.py revert KEY` (puts the old block back, sets `reverted`; refuses on `manual`, a block found
0 or 2+ times, a target outside `.claude/skills/<skill>/SKILL.md`, or a row not in `watch`: then edit by hand and `--set KEY reverted`).
In a curate file `path:line` is the line in the file after the edit; a cite outside the hunks still pairs by text overlap and warns.

## After the curator (main)
Check and apply the bundle, then `lessons.py mark-from work/<T>/handoff/curate.md`, then
`lessons.py scope` must exit 0. Edits and the ledger ride the DONE commit. After
`AGENT_FILES_CHANGED: yes` tell the user to restart the session so agent files reload.
