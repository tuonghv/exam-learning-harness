# Phase 137 – Code-review triage, batch 4 (TASK-137, REQ-0144)

## Premise
Batch 4 (`docs/report/phase-136..139-*-b4.md`, 28 findings, Fable, prompt v2) deep-dived against HEAD by two designers
(`work/TASK-137/handoff/design-{a,b}.md`). Reviews are advisory (RAW-00330). No source or test change in this phase.
R = reproduced by the coordinator ($0, 2026-11-17, `work/TASK-137/repro_a.run.out`, `repro_b.out`); T = traced.

## Plan modes
None: triage only. Fix tasks touch scoring (all keyed runs), solve image/adjudicate/retry paths, ingest text of PDFs,
and the publish guard.

## Result: 26 BUG, 2 IMPROVEMENT, 0 NOT-A-DEFECT (+ designer extras D: 2 BUG, 3 IMPROVEMENT, 3 NOT-A-DEFECT)

| ID | Class | Impact | Ev |
|---|---|---|---|
| 137-F001 | BUG HIGH | fraction key `14/3` read as 14: answer `14` scored correct; 4 eval keys have this shape. Review case "`14/5` matches" is false | R |
| 137-F002 | BUG | hedged `8 hoặc 9` / `8; 9` vs key `8` scored correct | R |
| 137-F003 | BUG | `19.975.000` read as 19.975 (0 real keys) | R |
| 137-F004 | BUG | `x = −3` (U+2212) vs `-3` scored wrong | R |
| 137-F008 | BUG | ordering key `b-d-a-e-c` turned into letter B; run-stats counts it keyed+wrong (1 real key) | R |
| 136-F004 + 137-F009 | BUG | `is_open` on any task: gap-fill answer `open` unscored; MCQ answered `Open` excluded from accuracy | R |
| 137-F010 | IMPROVEMENT | `exam.py score` parses a legacy key without `legacy=True` (0 legacy keys) | T |
| 137-F005 | BUG | computed check: `x = 1/2` compares 1 -> FAIL + paid retry; `v2 = 10` reads 2 | R |
| 137-F006 | BUG | `√3/2` compared as 3 -> FAIL | R |
| 137-F007 | BUG | ordering format check knows only a-e letters (0 real 6-sentence inputs) | R |
| 136-F001 | BUG | failed retry still re-reviewed: extra paid QA call; an `agree` flips FAIL to PASS on the unchanged answer | T |
| 136-F002 | BUG | adjudicated answer keeps the replaced answer's review: correct key answer -> FAIL reviewer_disagrees | T |
| 136-F003 | BUG | image/adjudicated value `12` not mapped to option letter -> image_differs, extra adjudicate call | T |
| 136-F005 | BUG LOW | image miss overwrites the `missing_text (options cut)` marker reason | T |
| 139-F001 | BUG | `--out reports/<ex>/run-<id>` / `plans/<ex>/runs/<id>` skips the publish guard | R |
| 139-F002 | BUG LOW | line `reports` puts the manifest in the reports tree | R |
| 139-F003 | BUG LOW | >= 10 report runs in one second sort `-10` before `-2` | R |
| 138-F005, F007, F008, F009 | BUG | OCR route: table area keeps garbled native cells; garbage kept when OCR not longer; `ocr_doubt chars` follows native flags; cut detector reads suspect OCR | R (F008, F009), T |
| 138-F010 | IMPROVEMENT | broken page -> traceback, not `ERROR: ingest corrupt` | T |
| 138-F001, F002, F003, F004, F006 | BUG | text placement: table in the other column; cell `\n`/`\|` re-split; short-stem page read as 2 columns (C/D moved); group intro lines stripped as headers; stem above a table dropped | R (F002-F004), R+T (F001, F006) |
| D1 (scorer) | policy | integer key `5` accepts `5.5` / `4.5` (half-unit inclusive); 8 integer keys | R |
| D1 (pdf) | BUG LOW | tables/images ordered by top only on 2-column pages (folded into F001) | T |
| D2, D4 | IMPROVEMENT | score_main TOTAL counts unanswered open items; quote check passes a bare option label | T |
| D3, D5, 138-D2 | NOT-A-DEFECT | first-wins duplicate reviews (system rule); unfenced prompt context (system-wide choice); bare page numbers stripped on purpose | T |

Real-input reach for the pdf findings is unknown; the text-placement fix task re-ingests input/ PDFs before/after.

## Review fixes not adopted as written
- 137-F001: no fraction-vs-decimal acceptance (`4.67` for `14/3`): policy, open question. Fix: fraction keys compare
  exact values (`28/6` ok), bare `14` no longer matches.
- 137-F009: replaced by the 136-F004 change (skip scoring only when the key is none or `Open (rubric)`).
- 136-F005: pass the marker reason into `apply_image` flags instead of string surgery.
- 138-F001: side filter only when two-column (keeps single-column placement); 138-F002 also needs `parts.py:98`.
- 138-F005: keep `tbbox` for the crop filter; 138-F006: "Fix risk none" is wrong (needs line bboxes), fix only if the
  re-ingest shows a dropped stem line.

## Fix tasks
| Task | Pri | Ids | Files |
|---|---|---|---|
| TASK-138 | P1 | 137-F001, F002, F003, F004, F008, F010, 136-F004, 137-F009 (+D2) | pipeline/scorer.py, core/decision.py |
| TASK-139 | P1 | 136-F001, F002, F003, F005 | engine.py, solver.py |
| TASK-140 | P1 | 139-F001, F002, F003 | pipeline/runlayout.py |
| TASK-141 | P2 | 137-F005, F006, F007 (+D4) | pipeline/verifier.py (+scorer.py:60) |
| TASK-142 | P2 | 138-F005, F007, F008, F009, F010 | ingest/adapters/pdf.py (OCR branch) |
| TASK-143 | P2 | 138-F001, F002, F003, F004, F006 (+D1) | pdf.py text placement, parts.py:98; input/ re-ingest diff |

One unit test per id, failing on old code; `--fast` NEW 0. Open policy questions (user): D1 half-unit tolerance on
integer keys; decimal answer for a fraction key.
