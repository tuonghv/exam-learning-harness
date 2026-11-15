# Phase 107 – Code-review triage (TASK-107, REQ-0114)

## Premise
Five code-review reports (`docs/report/phase-107..111-*.md`, 41 findings, model Fable) were deep-dived
against the current source by three designers (`work/TASK-107/handoff/design-{cli,ingest,pipeline}.md`).
Reviews are advisory, not requirements (RAW-00330): every class below is judged from the code, and the
review's own Fix is not adopted blindly. No source or test file is changed in this phase.

Classes: **BUG** = wrong result, crash or aborted run on a reachable input. **IMPROVEMENT** = hardening;
real inputs give no wrong result. **NOT-A-DEFECT** = claim wrong, unreachable or intended.
Evidence: **R** = reproduced by the coordinator ($0, 2026-11-15); **T** = code-traced by the designer.

## Plan modes
None in this phase: triage only, no code path changes. Each fix task states its own impact on
single-source and pipeline plans (Fix-A and Fix-B touch both; Fix-C..E touch neither solve path).

## Result: 17 BUG, 21 IMPROVEMENT, 3 NOT-A-DEFECT

| ID | Class | Impact | Ev |
|---|---|---|---|
| 107-F001 | BUG | `--write-recipe` over an unreadable recipe drops other exams' entries (git restores) | T |
| 107-F002 | BUG | `run-stats --exam <missing>` prints ERROR, exits 0, metrics without exam | R |
| 107-F008 | BUG | `--help` exits 2 in 11 subcommands (report listed 5) | R |
| 107-F003..F007, F009, F010 | IMPROVEMENT | traceback instead of exit 2 / silent skip; nothing wrong written. F009: do NOT use the review's fix (breaks glob backfill); warn per skipped ref | T |
| 108-F001 | BUG | refine aborts (`invalid_reply`) on a page reply `cut:true` with A,B only; window re-read runs only after | R |
| 108-F002 | BUG | `Câu 31-35: ...` intro becomes an extra question 31; passage lost | R |
| 108-F004 | BUG | unreadable question with empty text silently dropped | T |
| 108-F005 | BUG | `_INTRO` misses `... câu 31 đến câu 35`; intro+passage glued to option D | R |
| 108-F010 | BUG | stem `Phần I của ...` read as a part heading, stem erased (review's fix still eats line 1) | R |
| 108-F003, F006..F009 | IMPROVEMENT | prompt-violating replies, lost carried context, false `gap` flag | T |
| 109-F002 | BUG | shared_ref penalises linked questions for an unextracted sibling (supersedes phase-69 §41 formula) | T |
| 109-F004 | BUG | board_delta `n` counts run B, not compared pairs (verdict text only) | R |
| 109-F003, F005, F006 | IMPROVEMENT | label basis, crash on malformed TSV/result.json | T |
| 109-F001 | NOT-A-DEFECT | attempt_rate ≡ score is by definition | T |
| 110-F001 | BUG | `_classify("Prompt is too long: 215003 tokens…")` → `service`: run stops on a per-question error | R |
| 110-F002 | BUG | a `{` in prose before the JSON (`\frac{1}{2}`) → answer lost as malformed_output | R |
| 110-F004, F005 | IMPROVEMENT | locale encoding, misleading "empty" reason | T |
| 110-F003, F006 | NOT-A-DEFECT | unreachable / validated upstream | T |
| 111-F004 | BUG | re-run drops review marks of a section with no/duplicate number (user data) | R |
| 111-F006 | BUG | review-apply TypeError on a defect ticked in an unnumbered section | T |
| 111-F007 | BUG | edited heading → false "Answer changed", wrong `changed` count | R |
| 111-F005 | BUG | `S.old.md` backup listed as a subject | T |
| 111-F002 | BUG | `_has_text` undercounts INDEX with_text (cosmetic) | R |
| 111-F001, F003, F008, F009 | IMPROVEMENT | null note crash, unclear error, QA line guard, reserved names | T |

## Priority plan (proposed fix tasks, one area each; all items size S unless noted)

**P1 – wrong exam content or aborted run on real inputs**
- **Fix-A ingest boundaries** (`ingest/segment.py`, `ingest/refine.py`): 108-F001, F002, F005, F004, F010.
  F002+F005 share the `_Q`/`_INTRO` root cause; fix together with segment fixtures for both phrasings.
- **Fix-B Claude adapter** (`adapters/claude.py`): 110-F001 (narrow `_classify` patterns), 110-F002
  (scan for the first parseable `{`). No cache-key change (raw reply is cached).
- **Fix-C review pack** (`pipeline/review.py`): 111-F004, F006, F007 (one root cause: section identity by
  number/heading), plus F005.

**P2 – wrong exit code / misleading metric**
- **Fix-D CLI exits** (`cli.py`): 107-F001, F002, F008 (all 11 `--help` sites).
- **Fix-E metrics** (`pipeline/metrics.py`): 109-F002 (needs a design item superseding phase-69 §41), 109-F004.

**P3 – cosmetic bug + hardening (optional batch, only if cheap)**
- 111-F002 and the 21 IMPROVEMENTs, grouped by file into the task of that area when it is open, else one
  hardening task. 109-F003 is size M; skip unless the label matters to a report reader.

Order: Fix-A → Fix-B → Fix-C → Fix-D → Fix-E. Each fix task gets its own REQ, regression test from the
repro above (Ev R rows already have a $0 one-liner in the handoff), and the normal workflow.

## Not done
- T rows are not executed; each fix task starts by turning its trace into a failing test.
- 107 and 108 hit the 10-finding cap: a second review batch of `cli.py` and `ingest/` may find more.
