---
name: task-priority
description: Order and batch work when many user requests arrive while the team is busy. Use after intake of 2+ new requests, after the user approves a batch ("approve all", "just do"), when the backlog grows during an active task, or when a reply would carry more than ~3 open items. Produces one ordered plan and a short reply instead of a long one.
---

# task-priority: summarise, order, batch (user RAW-00426, 2026-10-07)

Why: the user sends several requests while roles are still working. Without an order the team
builds in arrival order, scripts and reports change several times, and replies get overloaded.
This skill runs after `req-intake` (requests are already REQs) and before `workflow` picks a task.
It never designs or implements, and never moves a state.

## 1. When to run
- 2+ new REQs since the last ordering, or the user approves a batch.
- A new request touches files or outputs that a queued or active task also touches.
- The reply you are about to write lists more than ~3 open items or questions.

## 2. Collect (cheap, from the ledger, not memory)
```
python3 .claude/req/req.py list --status TODO      # open requirements
.claude/scripts/backlog.sh list                     # queued tasks
bash .claude/scripts/task-state.sh                  # the active task
```
For each open REQ/task note one line: goal, outputs it changes (schema, script, report file),
depends on, cost ($0 / paid), who must act (team / user).

## 3. Order (rules, applied in this order)
1. **The active task finishes first** unless the user says it is superseded. New work queues behind it.
2. **User-blocking first:** anything waiting on a user decision or command goes to the user now,
   batched in one message (step 5); the team keeps building other items meanwhile.
3. **Foundations before consumers:** config/input -> data format/schema -> views/reports -> extras.
   A report never ships before the record it reads is final.
4. **Same output, one task:** REQs that change the same schema, script or report go into ONE task
   with ONE design (items N.1..N.k in dependency order), so each file changes once (RAW-00425).
5. **Fixes before features** when a fix changes numbers a feature would show.
6. **$0 before paid;** a paid/scan step waits for the user's explicit go, never blocks $0 work.
7. **Then priority** (`high` > `normal` > `low`), then age (older first).
8. Things the user said to skip or hold stay out (record the reason in the REQ, never delete).

## 4. Record (persist state, not memory)
- Backlog: one item per task, `title` lists its items in build order, `requirement` lists the REQs.
- Ledger: `req.py task REQ-x TASK-y` for each REQ; the EPIC gets a `Build order (...)` line.
- Commit the backlog + ledger change (`chore(backlog): ...`).

## 5. Reply (keep it short)
- Max ~10 lines: the order as a numbered list (one line each, why in a few words), what runs now,
  what waits.
- Questions: all in ONE block, each with the recommended answer first and a one-line why
  (req-intake rule). If the user delegated ("just do", "your recommendation"), decide with the
  recommended answer, record it, and only report it.
- Never re-list work already reported; point to the EPIC/backlog id instead.
- Last line: `Wait for <what>` or `Your turn: <decision>`.

## 6. Run independent work in parallel (user RAW-00427: "speed up with subagent if it is independent")
Default to parallel, not serial. Before starting the next step, list the open steps and launch every
one that is independent at once, each to its role in the background:
- independent = no shared output file, no order dependency, not the same scarce resource
  (one `run_all.sh` at a time, one `scan_batch.sh`, one real-plan writer).
- Typical parallel sets: tester QA of task N || designer draft of task N+1 || inspector fact checks
  for N+1 || main's $0 real check on a scratch copy. Coder items of one design run in parallel only
  when they own different files (design's owner column).
- Never parallel: two writers of one file, two test suites, anything paid, state moves (main only).
While the active task's role works, a free role may draft the next task's design or run read-only
checks on a scratch copy, never files the active task is changing (coordinator §3).

## Example (EPIC-004, 2026-10-07)
Six REQs on ext reports arrived during TASK-083. Ordered into one TASK-085 behind it:
85.1 language->scanners config -> 85.2 unified record (schema) -> 85.3 BASE view -> 85.4 in-scope
report -> 85.5 two report times -> 85.6 snippet script. One design; Nova drafted it while Nemesis
ran TASK-083 tests.
