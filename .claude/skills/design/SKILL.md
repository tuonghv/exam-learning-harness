---
name: design
description: Design non-trivial changes before implementation, with emphasis on reuse, simplicity, interfaces and testability. Owns the phase design doc path convention (docs/design/phase-<N>-<slug>.md) and its section structure.
---

# Design

Before coding:
1. Understand requirements and acceptance criteria.
2. Inspect existing implementation and similar functionality (`ls docs/design`, `git log --oneline -- docs/design`, `grep -n '^#'` the docs the change touches, then read only those sections).
3. Identify reusable modules, helpers and interfaces.
4. Define the smallest design that satisfies the requirement.
5. Identify affected components, compatibility risks and failure modes.
6. Define unit and real verification strategy.

Reuse order: existing component, extend, extract reusable component, create new.
Avoid speculative abstractions and unnecessary dependencies. Scope is this repo only: never design for, or depend on, work by another team; drop it under `Out of scope` in one line.
For every non-trivial change answer: what can this break, how will we detect it, and what is the smallest version the user would accept.

## Path convention - one task, one phase, one path
| Artifact | Path |
|---|---|
| Design | `docs/design/phase-<N>-<slug>.md` |
| Design split by component (past ~300 lines) | `docs/design/phase-<N>-<slug>-<component>.md` |
| Report (at DONE) | `docs/report/phase-<N>-<slug>.md` (same basename as the design) |

- `<N>` = the number in `task_id`, no leading zeros: `TASK-004` is `phase-4`. It links `backlog.json`, `task.json`, the phase log, commits and docs.
- `<slug>` = 2-5 lowercase words `[a-z0-9-]` naming the outcome, not the activity. Chosen once at DESIGN, never renamed.
- Record the path in `task.json` `design.path` (later `report.path`).
- A later task that changes an earlier phase's behaviour gets its own phase doc and links back (`Supersedes: phase-2-... §2.1`); never rewrite a DONE phase's doc.
- Enforced by `workflow-check.sh`.

## Design doc structure
```markdown
# Phase <N> - <name>
Task: TASK-00N · Status: draft | approved by user (<date>, "<quote>")
## Goal (user-visible outcome, and how we know it happened)
## Constraints (invariants touched, compatibility, trust boundary)
## Known incidents (matching rows of `docs/notes/incidents.md`, or "none")
## Plan modes (optional: one line per mode, impact or why not affected)
## Design
### <N>.1 <component> (owner: <file/function>)
Responsibilities, interfaces (signatures, flags, data shapes), state transitions. No code beyond signatures and shapes.
### <N>.2 ...
## Failure modes (| Failure | System response | Operator sees |)
## Unit tests (what each deterministic test asserts)
## Verification (| Item | exact command -> expected output | with its cost tier, lowest that proves it; written before implementation)
## Decisions (chosen option - rejected options - why)
## Out of scope
```
- Item ids `<N>.1`, `<N>.2`... are the acceptance criteria: one item = one verifiable behaviour = one `Verification` row. Two checks: split the item. `task.json` `acceptance_criteria` lists them as `"<N>.1 <behaviour>"`.
- A doc is done when someone else could implement it without asking. An open question is not answered by guessing: ask the user, record the answer under `Decisions`.

## Closing the DESIGN phase
Update `.claude/state/task.json`: `requirement`, `acceptance_criteria`, `design.status = "completed"`, `design.path`, `design.summary`, `design.reuse`, `design.risks`, `updated_at` (ISO8601 UTC), `updated_by`, and a concrete `next` (never empty).
Append a `## DESIGN - <task_id> - <ts>` entry to `.claude/state/phase-log.md` (Action, Result, Decision, Next; append-only), run `.claude/scripts/workflow-check.sh` and confirm PASS. Commit `docs(design): <summary>` with `Task:`/`State: DESIGN` trailers (`commit` skill).
`state=DESIGN` with `design.status=completed` and a clear `next` is a valid resumable handoff when implementation needs approval.
