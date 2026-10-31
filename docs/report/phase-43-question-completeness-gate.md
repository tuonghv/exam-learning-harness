# Report phase 43: question completeness gate, gap analysis and design (TASK-043; REQ-0045)

Verdict: adopted as the design for the guide `tmp/QUESTION_COMPLETENESS_GUIDE.md`. Deliverable: `docs/design/phase-43-question-completeness-gate.md` (gap table with path:line evidence, designs 43.1-43.7 with options and why, measurement plan) and the queued tasks TASK-044..048. No code in this task.

## Gap result
Already in place after TASK-040/041: question-centric assembly (continuation bridge, owner rule), completeness gate before the solver (`missing_text` decline), numbering gaps, referenced-part check, DOCX text boxes. Remaining, in task order: text-path boundaries (furniture filter, passage after option D) TASK-044; completeness reasons (truncated formula, merge suspect, unreadable stored, same-id join) TASK-045; measurement of the guide's metrics (split layout fixtures, boundary / cross-page / false-merge / incomplete-to-solver rates) TASK-046; Python cut detector + bounded automatic recovery + page cache TASK-047 (cost of a 22-page exam from about $0.9 to about $0.3-0.5, plus at most $0.16 recovery); provenance sidecar + two prompt lines TASK-048. Pictures: TASK-042 / REQ-0046.

## Evidence
`work/TASK-043/evidence/gap_table_claims_spotcheck.txt`: the design's path:line claims resolve to existing files and lines within their length (coordinator spot check; it checks existence, not meaning). Designer handoff `work/TASK-043/handoff/design.md`.

## Limits
The 99.9% targets are measured with Wilson intervals and never claimed (about 3000 error-free samples needed). Paid steps (real vision on scanned gold about $16) only with the user's go.

User instructions honoured: RAW-00146, RAW-00133, RAW-00142.
