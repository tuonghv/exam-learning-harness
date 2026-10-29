---
name: report
description: Generate concise engineering reports from persisted task state and evidence.
---

# Report

Use `.claude/state/task.json` and evidence files.

Include:
- task and requirement
- design decision
- implementation
- reuse
- tests
- verification
- security considerations
- limitations
- final status
- `User instructions honoured: RAW-a, RAW-b` (every `user_notes` raw; one not honoured is named with
  why; workflow-check warns at DONE when the line is missing, REQ-0059)

Never invent results.
Every count in the report comes from an evidence file saved at the final code (`save-evidence.sh`,
re-saved after the last code change); cite that file. A check with no file (a live reply you saw) is
marked "observed by the coordinator" and names where it was seen. Have the verifier compare report
rows to the files before VERIFIED (TASK-069: counts older than HEAD).
Prefer Action → Result → Decision → Next.

Write the report to `docs/report/phase-<N>-<slug>.md` — the same basename as
`design.path` (`design` skill path convention) — and record its path in `.claude/state/task.json`
under `report.path`, then set `report.status = completed`.

Run `.claude/scripts/workflow-check.sh` - it rejects DONE without a
non-empty `report.path` and `report.status = completed`.

## Results and evidence (lessons TASK-044..046)
- Lead with the verdict in one line: adopted, rejected (why) or kept as an option.
- A/B table: each arm's $, time, turns and the quality metric, next to the baseline and the noise.
- Spend: actual vs estimate. Say when it went over and why.
- Record every tried option (adopted or rejected) as a row in the area's tried-options log
  (`docs/notes/phase0-tried-options.md`): run dir, $, accuracy, verdict and the reopen condition.
  The log exists so nobody pays to verify the same option twice.
- Closing an area: write a Conclusion section (one choice, cost, accuracy, fallback, reopen condition)
  and a one-line pointer in CLAUDE.md.
- Tell the user what changed for them (defaults, settings to set) and what is left that needs their go.
