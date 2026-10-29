---
name: req-track
description: Answer "is this requirement done, what is left, what next" from the ledger instead of memory, and move REQ status TODO→DESIGN→IMPLEMENTING→UNIT_TESTED→VERIFIED→DONE with evidence. Use while implementing, testing, verifying, reporting, after compaction, and whenever the user asks for progress.
---

# req-track: stay focused on "is the requirement satisfied?"

Tool: `python3 .claude/req/req.py` (below: `req`).

## The only answer to "am I done?"
```
req gaps            # focus REQ: missing acceptance, open questions, next gate READY/BLOCKED
req gaps REQ-0042
```
Never answer from recollection. If it's not ticked in the REQ file, it's not done.

## Context discipline (200k window, auto-compact)
- WIP limit: one focus REQ (at most 2 active). Finish to UNIT_TESTED before opening another.
- Read with filters, never whole files/ledger: `req show <id> --section Acceptance`, `req list --active`,
  `req list --epic EPIC-003`. Do not open INDEX.md unless the user asks for an overview.
- After every meaningful step (test written, bug fixed, file done): `req focus --next "<next concrete step>"`.
  This line is what you get back after compaction - make it specific ("fix 429 header in ratelimit.go:88", not "continue").
- Tick acceptance items (`- [ ]` → `- [x]`) the moment they are proven, with a one-line note of how.
- Long outputs (test logs, builds): pipe through `tail` / `grep SUMMARY`; paste only the verdict.
- Phase boundary = checkpoint + good time for manual `/compact`.

## Status moves (gated by the tool - don't edit `status:` by hand)

| Move | Requires | Example |
|---|---|---|
| TODO → DESIGN | Requirement filled, no open questions | `req status REQ-12 DESIGN` |
| DESIGN → IMPLEMENTING | Design filled (skill `design`) | `req status REQ-12 IMPLEMENTING` |
| IMPLEMENTING → UNIT_TESTED | ≥1 acceptance item + evidence | `req status REQ-12 UNIT_TESTED --evidence "go test ./ratelimit/... 14 pass"` |
| UNIT_TESTED → VERIFIED | all acceptance ticked + evidence | `req status REQ-12 VERIFIED --evidence "verifier subagent: AC1-3 pass"` |
| VERIFIED → DONE | reported / merged | `req status REQ-12 DONE --evidence "MR !231 merged"` |
| back (regression) | `--reason` | `req status REQ-12 IMPLEMENTING --reason "AC2 fails on prod data"` |
| SUPERSEDED / REJECTED | `--reason` | |

Add `--next "<next step>"` to any move to set the focus and next step in the same call (skipped on
DONE, which clears the focus): `req status REQ-12 UNIT_TESTED --evidence "..." --next "verify on real run"`.

`docs/req/config.json` `checks` run `.claude/req/task_gate.py {id} <STATE>` for IMPLEMENTING,
UNIT_TESTED, VERIFIED and DONE: the move is refused while a linked TASK (task.json/backlog.json)
has not reached that state. So: TASK transition first (skill `workflow`), then the REQ. `--force --reason` exists but is logged as FORCED.

## VERIFIED = the linked TASK's verification
In this repo the independent check is the workflow's VERIFIED phase (skill `verify`, `/verify-phase`
verifier role), recorded on the TASK. Do not run a second verification for the REQ: tick each REQ
acceptance item from that evidence with `req ac REQ-12 AC1,AC3 --evidence "<which verify step>"`
(`all` ticks the rest; unknown ids are refused), then move the REQ. Never tick with sed/hand edits.
An item the TASK evidence does not cover is a real gap: send the TASK back, don't tick it.

## Reporting progress to the user
`req next`, `req list --active`, `req epic list`, `req check`. Summarize in a few lines; don't paste files.
After DONE: `req next` tells you what to pick up (resume active → ready TODO → waiting on user answers).

## Designing one REQ
- The design lives on disk, not in chat: `req focus REQ-x --next "design: <item>"`, `req status REQ-x DESIGN` (refused while open questions remain), then write `docs/design/phase-<N>-<slug>.md` (skill `design`); `## Design` in the REQ holds a 3-line summary and that path. Read only this REQ.
- Too big (more than ~6 acceptance items or several components): keep the first slice, move the rest to new REQs or `- [ ] TBD:` EPIC lines, `req log` the split.
- A gap found while designing becomes an acceptance item or an open question, never chat-only.
