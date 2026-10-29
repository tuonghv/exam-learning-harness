---
name: report
description: Generate concise engineering reports from persisted task state and evidence.
---

# Report

Use `.claude/state/task.json` and evidence files.

Include: task and requirement, design decision, implementation, reuse, tests, verification, limitations,
final status, and `User instructions honoured: RAW-a, RAW-b` (every `user_notes` raw; one not honoured is
named with why; workflow-check warns at DONE when the line is missing).

Never invent results. Every count comes from an evidence file saved at the final code (`save-evidence.sh`,
re-saved after the last code change); cite that file. A check with no file (a live reply you saw) is marked
"observed by the coordinator" and names where it was seen. Have the verifier compare report rows to the
files before VERIFIED. Prefer Action → Result → Decision → Next.

Write the report to `docs/report/phase-<N>-<slug>.md` (the same basename as `design.path`), record it in
`.claude/state/task.json` under `report.path`, set `report.status = completed`, then run
`.claude/scripts/workflow-check.sh`: it rejects DONE without both.

## Results
- Lead with the verdict in one line: adopted, rejected (why) or kept as an option.
- Spend: actual vs estimate; say when it went over and why.
- Tell the user what changed for them (defaults, settings) and what still needs their go.
