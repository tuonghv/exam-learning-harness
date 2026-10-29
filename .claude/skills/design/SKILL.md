---
name: design
description: Design non-trivial software changes before implementation, with emphasis on reuse, simplicity, interfaces and testability. Owns the phase design doc path convention (docs/design/phase-<N>-<slug>.md) and its section structure.
---

# Design

Before coding:
1. Understand requirements and acceptance criteria.
2. Inspect existing implementation and similar functionality
   (`ls docs/design`, `git log --oneline -- docs/design`, the docs/guide/toolkit-reference.md sections
   the change touches — `grep -n '^#' docs/guide/toolkit-reference.md` first, read only those).
3. Identify reusable modules, helpers and interfaces.
4. Define the smallest design that satisfies the requirement.
5. Identify affected components, compatibility risks and failure modes.
6. Define unit and real verification strategy.

Reuse order:
existing component → extend → extract reusable component → create new.

Avoid speculative abstractions and unnecessary dependencies.

**Scope: this toolkit and its scan engine only** (user, 2026-09-27). Never design, propose or depend
on work by another team or tool (e.g. the tool that prepares the source trees): no "ask team X",
no reader for files another tool might write, no notes for them. If the toolkit cannot solve it
itself, drop it under `Out of scope` in one line and spend the effort on the current engine.

## Premise first — prove the defect before designing the fix

Phases 14–18 showed that the cheapest design step is proving that the failure happens:

1. **Reproduce it on HEAD** on a scratch kit with a fake `claude`, and record the
   actual outcome: the repo status, `attempts`, the abort class and the scheduler state. If you
   cannot reproduce it, say so and shrink the phase or drop it. Don't build a guard for
   a failure that has never been seen (memory: value-over-effort).
2. **Use real inputs, not guessed ones.** For CLI wording (limit or error text),
   extract strings from the installed binary
   (`strings -n 12 ~/.local/share/claude/versions/<v> > cs.txt`, then search it
   with a Python regex). Ask the user for a live sample when you have one; a
   phase 18 pattern written from memory missed the current CLI's
   `You've hit your session limit · resets 10:50am (Asia/Ho_Chi_Minh)`.
   Never `grep -aoE '.{0,90}'` a 200 MB+ binary, because it hits grep's complexity limit.
3. **Check the real manifest read-only** for repos the defect has already hit
   (for example `jq '[.repos[] | select(.last_error|test("…"))] | length'`). That
   count sizes the fix and tells you whether anything needs re-queueing.
4. **Value/effort table:** list each sub-item with its value (repos lost or
   attempts charged) and its effort. Keep the high-value, low-effort items and write
   each dropped item and its reason under `Out of scope`. Examples: phase 18 dropped
   the 429-in-CLI item, and phase 17 dropped lock cleanup.
5. **Look beside the reported bug.** The same line often hides a bigger bug. In phase 16,
   the task was a " null" suffix, and the real defect was an object `.error` that
   dropped the whole envelope from classification.

Design for this repo's failure economics: every wrong classification either
**charges an attempt** (and after `MAX_ATTEMPTS` the repo drops out of the scan) or
**parks the scheduler**. In the `Failure modes` table, state which of the two each row causes.

Also answer, for every non-trivial change (user, 2026-09-26): **what can this break, how will we
detect it, and does every scan finding still reach the reports?** A change on the overlay →
conclude → report path gets a Verification row for `coverage_check.py` (`verify` skill) with the
real run's counts. Don't propose new work (other models, A/B) until the change is finished and
checked.

**Always think about both plan modes (user, 2026-09-27: "so we never miss").** A plan is reviewed in
one of two modes, and each is used on purpose:
- **single-source:** `scan_batch.sh` → `results/*.json` (overwritten on re-scan) → reports and gate
  with **no flag** (`summarize_report.sh`, `summarize_exec.sh`, `check_deliverables.sh`).
- **pipeline (multi-phase):** `pipeline.sh` → `runs/<id>/` → the same scripts with **`--run`**, plus
  run-only tools (`evaluate_run.sh`, `engine_review.py`, `coverage_check.py`/D10).

For every design, state the impact on each mode in a `## Plan modes` section:
- What changes in that mode.
- How it is verified in that mode.
- If a mode is not affected, the reason.

A feature that makes sense in both modes follows the phase 47 pattern:
- one mode-specific **source** per mode, feeding one mode-agnostic core or renderer (no `if mode`
  inside the renderer);
- the same flag rule (no flag = single-source, `--run` = pipeline);
- a Verification row per mode.

A "pipeline only" or "single-source only" feature is a decision, and it goes under `Decisions` with its
reason. `workflow-check.sh` fails a design from phase 47 on that has no `Plan modes` section.

## Analyze, propose, recommend (cost or tuning work; lessons TASK-043..046)

**Analyze ($0 first)**
- Read `docs/notes/phase0-tried-options.md` (or the area's tried-options log) before any idea.
  A listed option is not re-proposed unless its reopen condition holds.
- Size the prize: which share of today's cost does the target touch? Take it from saved data
  (`p0_cost.py`, envelopes, `card_ab.py`). Upper-bound saving < the helper's own cost → drop it.
  Example: a Haiku trim of recon.json saves ≤ $0.02/repo, but the call costs $0.04.
- Check feasibility by shape: compare the input's keys with the output fields it must fill
  (`jq -c keys`, names only). A model cannot fill fields its input does not carry. It guesses, and that is noise.
- Predict second-order effects and name the metric that shows them. Fewer bytes per read can mean more
  reads and turns (TASK-046: whole-file reads −47 %, cost +29 %). Measure totals: $, turns, result chars.
- Know the noise (a same-config repeat in a sibling plan) before judging any delta.

**Propose**
- Design every item first when the user asks, including optional arms. Put paid arms last and gate
  each one on the result before it.
- Each proposal states its value (the $ or quality it moves), its cost (the $ of the paid step) and the
  risk that fails it. Ask once for the paid go. Then chain the arms and don't stop again.
- Respect standing user rules. Use Haiku only for simple jobs with small context. Never add a budget cap
  that stops or pauses a scan. Frozen prompts: new flagged section, off = byte-identical (`cmp`).
- Answer "have we tried X?" with yes or no first, with the run and the numbers. Then give the option.

**Recommend**
- Give one choice, plus at most one fallback with its trade-off. Don't give a menu.
- State the cost per repo and its range, the time, and the accuracy with what it measures (agreement
  with the reference, not ground truth). Add the noise and a planning figure (per 100 repos).
- Say plainly when more tuning is not worth it and why. Then close the area with a reopen condition.

## Path convention — one task, one phase, one path

| Artifact | Path |
|---|---|
| Design | `docs/design/phase-<N>-<slug>.md` |
| Design split by component (past ~300 lines) | `docs/design/phase-<N>-<slug>-<component>.md` |
| Report (at DONE) | `docs/report/phase-<N>-<slug>.md` — **same basename** as the design |

- `<N>` = the number in `task_id`, no leading zeros: `TASK-004` → `phase-4`.
  The number is the link between `backlog.json`, `task.json`, the phase log,
  commits (`git log --grep="Task: TASK-004"`) and the docs — never pick another.
- `<slug>` = 2–5 lowercase words from the task title, `[a-z0-9]` joined by `-`,
  naming the *outcome*, not the activity: `shellcheck-baseline`, not
  `fix-shellcheck-stuff`. Chosen once at DESIGN; never renamed afterwards.
- Record the path in `task.json` `design.path` (and later `report.path`), not
  only in prose. `design.summary` restates the decision in one line and may
  cite the path.
- A later task that changes an earlier phase's behaviour gets its own new
  phase doc and links back (`Supersedes: phase-2-... §2.1`); never rewrite a
  DONE phase's doc.
- Enforced by `workflow-check.sh` (phase 5). Pre-convention
  `docs/DESIGN-*.md` / `docs/REPORT-*.md` were moved to phase-1..3 in phase 5
  (`git log --follow` traces them); old phase-log entries still name the old
  paths.

## Design doc structure

```markdown
# Phase <N> — <name>

Task: TASK-00N · Status: draft | approved by user (<date>, "<quote>")

## Goal
One paragraph: the user-visible outcome, and how we know it happened.

## Constraints
- docs/guide/toolkit-reference.md invariants touched (by number) and how each is preserved.
- Compatibility: CLI flags, manifest.json / results/*.json schema, config.sh
  defaults, bash 3.2 (no mapfile/assoc arrays, `set -u`-safe arrays).
- Trust boundary for anything security-relevant: what is untrusted (repo
  content, manifest fields, model output), where it is validated, what
  happens on rejection.

## Known incidents
Rows from `docs/notes/incidents.md` that match the files or steps this design touches, each with how this design
avoids it; or "none". `workflow-check.sh` WARNs when a matching row exists and this section is missing.

## Plan modes
| Mode | Impact (what changes, or why not affected) | Verified by (row) |
|---|---|---|
| single-source (`scan_batch.sh`, `results/`, no flag) | | |
| pipeline (`pipeline.sh`, `runs/<id>/`, `--run`) | | |

## Design
### <N>.1 <component> (owner: <file/function>)
Responsibilities, interfaces (function signatures, flags, JSON shapes) and
state transitions — each names the file that owns the state. No code beyond
signatures and data shapes.

### <N>.2 ...

## Failure modes
| Failure | System response | Operator sees |

## Unit tests
What each deterministic test asserts (function-level, fixture-driven).

## Verification
| Item | Command / observable |
|---|---|
| <N>.1 | exact command → expected exit code / output / file state |
Give each row its cost tier (`verify` skill, "Save cost": 0 static, 1 snippet,
2 scratch kit, 3 real `claude`) and use the lowest tier that proves the row.
Written before implementation; runnable on a scratch tree (docs/guide/toolkit-reference.md
"Testing a change"), never on the real manifest.

## Decisions
One bullet each: chosen option — rejected options — why (one sentence).

## Out of scope
```

- Item ids `<N>.1`, `<N>.2`… are the acceptance criteria: one item = one
  verifiable behaviour = one row in `Verification`. Two checks → split the item.
  `task.json` `acceptance_criteria` lists them as `"<N>.1 <behaviour>"`.
- A doc is done when someone else could implement it without asking anything.
  An open question is not answered by guessing: ask the user, record the answer
  under `Decisions`.

## Closing the DESIGN phase (do all of these before handing off)

A later session or a different role only sees what you wrote to `task.json` and
`phase-log.md`. Leave the task self-describing so anyone can resume without
guessing. Update `.claude/state/task.json`:

- `requirement` and `acceptance_criteria` — not just the summary.
- `design.status = "completed"`, `design.path`, `design.summary`,
  `design.reuse`, `design.risks`.
- `updated_at` — current time as ISO8601 UTC (`date -u +%Y-%m-%dT%H:%M:%SZ`).
- `updated_by` — your role/session (e.g. `"design-role"`).
- `next` — the concrete next action (e.g. the first IMPLEMENTING item).
  Never leave it empty.
- A design (or a decision between options) that changes the engine flow also updates
  `docs/guide/architecture.md` (flow, step table, "Chosen standard") in the DESIGN commit (RAW-00299).

Then append a `## DESIGN - <task_id> - <ts>` entry to
`.claude/state/phase-log.md` (Action → Result → Decision → Next; append-only)
and run `.claude/scripts/workflow-check.sh` — confirm **PASS** before you stop.
Commit: `docs(design): <phase N summary>` with `Task:`/`State: DESIGN`
trailers (`commit` skill).

Leaving `state=DESIGN` with `design.status=completed` and a clear `next` is a
valid, resumable handoff when implementation needs approval. `workflow-check.sh`
treats one phase of lag as an expected boundary and only fails when `state`
falls two or more phases behind the recorded evidence.
