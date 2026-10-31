---
name: advance
description: Advance a TASK one gated state with one command (advance.sh: fields, phase-log entry, view sync, REQ steps, workflow-check, gated commit) or catch up a REQ whose TASK is DONE. Use at every TASK transition DESIGN to DONE instead of hand-written state edits.
---

# Advance

Main session only. One step per call; the first failing gate stops it and restores every file it touched.
```
bash .claude/scripts/advance.sh <TASK> <STATE> --spec work/<TASK>/advance-<STATE>.json [--dry-run]
bash .claude/scripts/advance.sh req-catchup <REQ> [--ac-evidence "<text naming an existing file>"] [--dry-run]
```
Output `PASS: <T> -> <S> committed <sha>` or `FAIL [gate]: ...` + `fix:`. Unsure: `--dry-run` first (nothing stays changed).

## Spec (JSON under `work/<TASK>/`)
`set` (fields below), `next` (concrete step; `""` only at DONE), `log` {action,result,decision,next},
`commit` {subject,body?,paths[]}, `req` {evidence?,ac?,ac_evidence?,next?}, `quality` (DONE only).
| State | `set` must hold |
|---|---|
| DESIGN | design{status,path,summary}, acceptance_criteria |
| IMPLEMENTING | implementation{status,summary,files[]} |
| UNIT_TESTED | unit_test{status,command,result} |
| VERIFIED | verification{status,command,result,evidence[]}, security{status,result}; `req.ac: "all"` |
| DONE | report{status} (path derived), `quality` {kind: crosscheck/rendered/real-run/n/a, evidence[], reason} |
Write the report file only after VERIFIED (its path is accepted at DONE; earlier it fails the commit scope).
Add `roles` (handoff paths or `{"waiver": ".."}`) when the task needs them. Design/report paths and the REQ files are staged for you.

## Gates (first failure wins)
`spec` JSON or schema | `state` not one step from the current | `quality` evidence file missing or empty, or no `quality` at DONE |
`workflow` workflow-check line (fix the field it names) | `req` REQ more than one step behind (`req-catchup`) or its Design is empty
(write it first) | `backlog` | `commit` commit-check refused (undone, re-run after the fix). A re-run of a committed step is a no-op.

## Quality of the product (AC7)
Never leave out evidence: VERIFIED and DONE need real, non-empty evidence files. A report/content task needs a crosscheck,
rendered or real-run proof; `n/a` only with a reason on a non-content task. Never write `verification.status=passed` without it.

## Does not
Use `--force`, run paid or real runs, or touch settings, hooks, agent_setup or CLAUDE.md.
