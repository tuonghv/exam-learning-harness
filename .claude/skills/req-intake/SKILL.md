---
name: req-intake
description: Turn user input into tracked requirements. Use when the hook reports untriaged RAW prompts, when the user states a new need or changes an old one, or when a request is too big to design in one go.
---

# req-intake: capture → normalize → decompose (do NOT design here)

Tool: `python3 .claude/req/req.py` (below: `req`). Intake must stay cheap: a big request is
split into small REQs now and designed later, one at a time. Never start designing during intake.

## 1. Triage every NEW RAW (Stop hook blocks until done)

Background-task notifications (`<task-notification>`, `[SYSTEM NOTIFICATION`) are not captured; a
RAW is always the user's own words.

```
req raw list --new
req raw show RAW-00031
```
For each RAW decide ONE of:

| RAW contains | Action |
|---|---|
| New need, small (≈ one feature, ≤ ~5 acceptance items) | `req search <keywords>` → `req new --title "..." --from RAW-00031 [--epic EPIC-003] --area <area>` |
| New need, big / vague / many parts | `req epic new --title "..." --from RAW-00031`, then decompose (step 3) |
| Adds to / changes an existing REQ | `req raw link RAW-00031 --to REQ-0042` then update that REQ (step 4) |
| Answer to an open question | `req raw link ... --to REQ-x`, tick the question: `- [x] Q1: ... -> answer (date)` |
| Only a question, chatter, "continue", instruction for the current step | `req raw ignore RAW-00031 --reason "question"` |

Always `req search` before `new` - duplicates are the main way 1000-item ledgers rot.
One RAW may map to several items: `--to REQ-0042,REQ-0051`.

**Note it in the task (user, RAW-00478, REQ-0059):** every RAW that steers a task (requirement,
instruction, decision, even one ignored as "instruction") is also noted in the task it applies to, in the
same turn: `task.json` `.user_notes` for the active task, the backlog item's `.user_notes` for a queued
one: `.claude/scripts/backlog.sh note <TASK-NNN|active> RAW-x "<one line>"` (no secrets/URLs; ALREADY
on a repeat), committed with the triage. A RAW that steers no task is ignored with a reason containing
`not task-related`; workflow-check warns on a RAW triaged since the pick that no task notes.

## 2. Normalize (the user's wording may be unclear, mixed language, no diacritics)

Edit the new REQ file. `## Original` is the verbatim quote - never edit it. Fill:
- `## Requirement`: one clear statement, English, EARS style
  (`WHEN <trigger>, the <system> SHALL <response>` / `IF <condition>, THEN ...`).
- `## Acceptance`: `- [ ] AC1: ...` each objectively checkable (input → expected output / measurable).
- `## Open questions`: anything you had to guess → `- [ ] Q1: ...`. Do not silently assume.
  A REQ with open questions cannot enter DESIGN - this is intended.

Then ask the user ALL open questions of this intake in ONE message, numbered with REQ ids.
Each question carries **your recommended answer and a one-line why** (user, 2026-09-27: "should
give recommended decision base you know which one is better"): weigh it against the standing rules
(findings never edited, trust model, nothing lost, cost) and the latest run's evidence. Never ask a
bare question or hand over a menu. On "accept all", record each answer in the REQ as
`- [x] Qn: ... -> <answer> (user, <date>)`, re-align the Acceptance to it, and continue.

## 3. Decompose an EPIC (rolling wave)

In the EPIC `## Decomposition`:
- Parts that are clear enough → create REQs now (`req new ... --epic EPIC-003`), status TODO.
- Parts still vague → one line each: `- [ ] TBD: <coarse description>`.
  TBD lines are reported by `req check`/hooks until converted, so nothing is forgotten
  even if you design only the first REQ now.
- Aim for REQs that can go TODO→UNIT_TESTED within a fraction of one context window.

## 4. Change to an existing REQ

- Status TODO/DESIGN: edit Requirement/Acceptance, then `req log REQ-x "scope changed per RAW-..."`.
- Status IMPLEMENTING or later: don't rewrite history. Either add acceptance items and
  `req status REQ-x DESIGN --reason "scope change RAW-..."`, or create a new REQ
  with `--supersedes REQ-x` (old one becomes SUPERSEDED).

## 5. Finish

`req check` must show no `[GAP]`. Do not print the ledger into chat; one line per item created/linked is enough.
