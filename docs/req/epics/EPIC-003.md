---
id: EPIC-003
title: Exam-solving pipeline engine: INPUT, VALIDATE, SOLVE, QA, SCORE, REPORT (claude -p + deterministic checks)
source: [RAW-00025]
created: 2026-10-29 10:02
updated: 2026-10-31 10:05
---
## Original (verbatim, never edit)
> **[RAW-00025]** 2026-10-29 10:01
> please design phase solve exam workflow, we also develop engine python or bash to support you base on prompt you can review and apply tmp/exam-solving-workflow.md, about script to use claude -p or unit test, script you can reference from here and build on your own here, just inspect find what you need not copy it , just reference from source only /home/tuonghv/Documents/git/online-system/code-security-scanner

## Goal

A small stdlib engine (Python, Bash only where the harness already uses it) that runs INPUT, VALIDATE, SOLVE, QA, DECISION, SCORE, REPORT over exam files in `examples/FORMAT.md` form, using `claude -p` for reasoning and code for checks, scoring and schema validation; JSON is the source of truth, a readable PDF is the report. Spec: `tmp/exam-solving-workflow.md`. Reference only (read-only, not copied): `/home/tuonghv/Documents/git/online-system/code-security-scanner`.


## Decomposition
<!-- One line per child: "- REQ-0012" (auto-added) or "- [ ] TBD: <coarse item not yet specified>". TBD lines are tracked until converted into REQs. -->
- REQ-0008 (design phase, first)
- REQ-0010 (engine core + QA, mock-tested)
- REQ-0011 (report: JSON, Markdown, PDF)
- REQ-0009 (real-run benchmark, measured results only; was the TBD runner+benchmark item, RAW-00031)
- REQ-0012
- REQ-0034
- REQ-0035
- REQ-0036
- REQ-0047

## Notes
