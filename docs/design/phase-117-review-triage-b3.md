# Phase 117 – Code-review triage, batch 3 (TASK-117, REQ-0124)

## Premise
Third review batch (`docs/report/phase-117-ingest-api-parts-b3.md`, `phase-118-ingest-boundary-b3.md`, 19 findings, model
Fable) deep-dived against the current source by two designers (`work/TASK-117/handoff/design-{api,boundary}.md`).
Reviews are advisory (RAW-00330). Classes and evidence tags as in phase-107. No source or test file changes in this phase.
Priority set by the coordinator without a user gate (RAW-00342).

## Plan modes
None: triage only. Fix-H/Fix-I touch the ingest path used by single-source and pipeline plans; Fix-J the opt-in boundary
AI and the solve cost-cap check.

## Result: 12 BUG, 6 IMPROVEMENT, 1 NOT-A-DEFECT
R = reproduced by the coordinator ($0, 2026-11-16, `work/TASK-117/repro_{api,boundary}.out`); T = traced.

| ID | Class | Impact | Ev |
|---|---|---|---|
| 117-F001 | BUG | key heading after block 6 of a page missed: DOCX/MD with an appended key leaks it into the exam | R |
| 117-F009 | BUG | `_KEY` prefix match: a page starting `Solutions to ...` / `Lời giải thích ...?` flips to answer_key (loud refusal) | R |
| 117-F010 | BUG | Markdown has no `doc["parts"]`: key refusal raises KeyError instead of answer_key_present | R |
| 117-F002 | BUG | `--pages` past the key heading drops the key guard | R |
| 117-F003 | BUG | re-segmentation after `--pages` reads only paragraph blocks: DOCX list/heading options lost | R |
| 117-F008 | BUG | refined cut-question merge drops the first part's options, the second part's figures and page | R |
| 117-F004 | BUG | a group range survives a numbering restart without a heading | R |
| 117-F005 | BUG | a `questions 3, 4` mention in a member's context opens a new range; the rest lose the passage | R |
| 117-F007 | BUG | `N + offset` note wrong for non-consecutive kept refined ids | R |
| 117-F006 | IMPROVEMENT | verification gate tests the slice; nothing writes `verification` today | T |
| 118-F001 | BUG | suspects past the 40-line cut of a merged span never asked, uncounted | R |
| 118-F007 | BUG | boundary summary mixes this pass's windows with cumulative calls/cost | R |
| 118-F009 | BUG | `--max-cost-usd nan` accepted; cap never fires (volume still <= 6 calls) | R |
| 118-F002, F003, F004, F006, F008 | IMPROVEMENT | partial/tampered/duplicate replies, safe-side estimate, trace cost per row | T |
| 118-F005 | NOT-A-DEFECT | missing tracked prompt fails loud before any call | T |
| D1 (designer) | BUG | solve `--max-cost-usd nan` same hole (cli.py:110, engine.py:84) | T |

Real-input reach (`work/TASK-117/reach_parts.out`): the 4 input PDFs detect parts correctly today (the math exam's key
heading is block 1 of page 5); F001 needs a DOCX/MD with an appended key. Key pages hold many `Lời giải: ...` blocks,
so F001 may only scan all blocks together with the F009 heading guard.

Review Fixes not to adopt as written:
- 117-F001: scan all blocks only with the F009 guard (first line, no `?`, heading type / mostly upper / <= 40 chars).
  Coordinator decision: a one-page DOCX/MD that holds a key becomes `answer_key` as a whole (export refuses; never leak
  a key); cutting the page at the key block is a P3 follow-up.
- 117-F005: open a new range only when the carrier lies in it (`lo <= num <= hi`), not `_INTRO.match`.
- 117-F009: test the block's first line, not a 60-char block cap (PDF merges the heading with the key lines).
- 118-F009: reject NaN at the cli (`not (x >= 0)`, exit 2) and keep the inverted cap test as defence; same for solve (D1).

## Priority plan
**P1 – key leak / wrong exam content**
- **Fix-H parts** (`ingest/parts.py`, api.py:67): 117-F001 + F009 + F010 (one `_starts_key` guard), F002, F003.
**P1/P2 – wrong question content after assembly**
- **Fix-I api** (`ingest/api.py`): 117-F008, F004, F005, F007.
**P2 – paid-path accounting**
- **Fix-J boundary + cost cap** (`ingest/boundary.py`, `cli.py`): 118-F001, F007, F009, D1.
**P3 – hardening**: 117-F006, 118-F002+F003 (shared `_items` coverage check), F004, F006, F008; batch-2 and phase-107 P3.

Order: Fix-H -> Fix-I -> Fix-J. Each its own REQ, regression tests from the repros, oracle = segment/parts dump of the
real inputs old vs new (work/TASK-114/evidence/oracle.py, work/TASK-117/reach_parts.out).

## Not done
- api.py/parts.py hit the 10-finding cap: a further review batch may find more.
