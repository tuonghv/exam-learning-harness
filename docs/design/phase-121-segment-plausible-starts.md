# Phase 121 – Segment: reject implausible question starts (TASK-121, REQ-0128)

Source: D1 of docs/design/phase-119-api-cut-merge-ranges.md; evidence work/TASK-121/false_ids.txt; draft work/TASK-121/handoff/design.md.

## Goal
A rule `_Q` match whose number breaks the running sequence, while the expected next number still
comes later, is text, not a question start. Passage paragraphs (`1 The world of rap...`), years
(1991, 2020), figure/formula lines (`0`, `5000`, `3) + ac`) stop being questions; group intro +
passage reach the real first member (DGNL25 q46, DHQG q106/q109/q112). Seen in the segment oracle.

## Constraints
- `numbering()` / `numbering_warnings()` / `MAX_N` / pdf.py:693-706 unchanged (usable semantics kept).
- Consecutive exams byte-identical: the rule runs only when `n != prev + 1` (golden test holds).
- Hints path (boundary.py AI hints, segment.py:225-241) keeps its order; the new check runs after it.
- Cache: boundary replycache key = window text + prompt sha; `suspects()` and prompt unchanged, so no stale reuse. No ingest-result cache in pdf.py.

## Generality
All exam kinds using `segment()` (pdf + docx adapters); numbers only, no words or exam literals; one synthetic English non-DGNL test.

## Known incidents
None in incidents.md matched.

## Plan modes
- Rules only (`hints=None`): the new check applies; consecutive input unchanged.
- AI boundary hints (`segment_reviewed`): the hint branches run first, unchanged; a hinted line that reaches the append and is then rejected gets `boundary_ai_rejected` (reason `numbering`), a code `report_warnings` already handles. Never a new code: boundary.py:412 maps unknown codes to the subject-title message.
- docx adapter: same `segment()`, same effect.
- Selected exam pages (`parts.select_pages`) / key pages: api refuses a doc that holds a key (api.py:67); the rule does not look for keys.

## Design
### 121.1 `_implausible(n, prev, later)` (owner: segment.py, new helper beside `_next_n` :69)
`later` = numbers of the `_q_start` lines after line i, in order (precomputed once per call as
`cand = [(i, n)]`, so there is no O(lines^2) rescan). Returns True when the expected `prev + 1` starts a later line
and, only when n == 1, a run counted up from 1 over `later` (other numbers are skipped) has not reached `prev` first:
```
def _implausible(n, prev, later): -> bool
    run = 1 if n == 1 else None
    for x in later:
        if x == prev + 1: return run != prev
        if run is not None and x == run + 1: run = x
    return False
```
- No later `prev + 1`: kept (legit gaps `[1,150]`, `1. a / 3. c`, stray `2019` after the last one: unchanged).
- n == 1 whose own run passes through prev (a section restart, with or without a PHẦN/PART heading): kept.
- Passage `1..6` then `46`: the run stops at 6, then 46 = prev+1 arrives, so all are rejected.
### 121.2 wire-in (owner: segment.py `segment()` :220-249)
- Build `cand` before the loop. In the `if m:` block, after the hint branches (:225-241) and before
  `qs.append` (:242): if `qs and n != prev + 1 and _implausible(n, prev, later_of(i))`, then note
  `boundary_ai_rejected` when `hint` is set, set `hint = None`, and do not `continue`. The line then takes the
  existing free-line path (:250-303): into `pending` if a group intro is pending (so it becomes passage context of
  the next real start), else glued to the last option or the stem (as any wrapped line is today).
- `starts` gets only accepted starts (unchanged contract).
### 121.3 no change: pdf.py, numbering, api `_share_context` (they benefit through correct qs/context).

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| Paragraph number == prev+1 (e.g. passage `2.` right after q1) | taken as a start (as today) | numbering_gap/skipped as today |
| Cover lines `1.`/`2.` before PHẦN 1 (DGNL26) | kept: first start is always accepted | numbering_restarted, 122 q (residual) |
| Real question whose number repeats, with prev+1 later | merged into the previous question | count drops by 1; oracle diff |
| Group intro written mid-line (DGNL25 idx103/124/145 `... câu từ 70 đến 71`) | glued to the previous option (was a false q) | q70/q76/q85 context still '' (residual) |

## Unit tests (new tests/unit/test_segment_plausible.py, synthetic lines)
1. Passage: `45.`+A-D, `Questions 46-47: Read the passage.`, `1. Para one.`, `2. Para two.`, `46.`+A-D, `47.`+A-D -> ns [45,46,47]; q46 context holds the intro and both paragraphs; `starts` length 3.
2. Year: `108.`+A-D, `Questions 109-110: Use the text.`, `1991. In 1991 the ...`, `109.`, `110.` -> ns [108,109,110]; `1991` in q109 context.
3. Figures without intro: `62.`+A-D, `3) + ac`, `2) + bc`, `63.` -> ns [62,63]; fragments in q62 option D.
4. Restart at heading (non-DGNL): `PART I`,1..3,`PART II`,1..2 -> ns [1,2,3,1,2]; numbering usable, numbering_restarted.
5. Restart without heading, longer second run: 1..3 then 1..5 -> ns unchanged.
6. Duplicate: 1..4, `4) x`, 5 -> ns [1..5]; `[1,2,2]` unchanged (no later 3).
7. Hint: question_start hint on a rejected line -> report has `boundary_ai_rejected` reason `numbering`; `report_warnings` text ok.
8. `_implausible` table: (1,45,[2,3,46])->T, (1,4,[2,3,4,5])->F, (150,1,[])->F, (4,4,[1,2,5])->T, (1,2,[2,3])->F.
Unchanged and must stay green: test_numbering_gaps.py (all, incl. `[1..5,1,2,3,6]` skipped, `2019` skipped), test_generality_golden.py, test_ingest_fix_f.py, boundary tests.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 121.1-2 | `python3 -I tools/run_tests.py --affected` then `--fast` -> NEW 0 | $0 |
| AC1/AC3 | `python3 -I work/TASK-114/evidence/oracle.py <src> <input root>` old (HEAD) vs new -> per-PDF counts below | $0 |
| AC2 | `python3 -I work/TASK-116/evidence/share_oracle.py <src> <root>` old vs new -> only the context gains below | $0 |
| full gate | main runs `--full` once | $0 |

Expected oracle moves (segmented -> after; every removed id is one listed in false_ids.txt):
- DGNL 2025: 197 -> 120 (all 77 off-sequence rejected); ok, no segmentation_skipped.
- DHQG 2024: 141 -> 120 (all 21 rejected), incl. 1991, 2020.
- DGNL 2026: 147 -> 122. 25 rejected; idx2/idx3 (the real q1/q2 after `PHẦN 1`) kept as a restart; the residual is cover lines idx0/idx1. Runs [1-2],[1-120]: usable, numbering_restarted instead of skipped.
- math full PDF: 48 -> 46 (idx38, idx39 rejected: 5 follows). idx40 `1` stays a restart (its run reaches 5), idx47 `10` stays (no later 7): still segmentation_skipped. Key pages are refused at api.py:67 anyway. On exam pages only: 22 q, runs [12],[4],[6], unchanged.
Share oracle gains (context '' -> intro+passage, then shared to the group): DGNL25 q46, q53, q67, q74, q81, q83, q88; DHQG q36, q106, q109, q112; DGNL26 q53, q77. Any other diff is a defect.

## Decisions
- Lookahead "expected next still comes" was chosen over a hard `n > MAX_N` cut (that would break `test_stray_year_after_last_skipped`) and over "the next start must be n+1" (that breaks `[1,150]` and `1. a / 3. c`).
- A part-heading test for restarts was not needed: the run-through check covers DGNL26 PHẦN 1 and the math PHẦN II with no heading detected (ctx '').
- Reuse of boundary.py: its `NB` suspect (:95) is the same idea, kept for AI windows; its `_is_key` stop is not reused (key pages are api's job).

## Out of scope
Cover-instruction numbers, key pages inside segment, mid-line group intros, formula fragments glued to options.

## Coordinator decisions
- AC3 residuals accepted (REQ-0128 allows a listed residual): DGNL26 cover lines idx0/idx1 (122 instead of 120) and the
  mid-line group intros (q70/q76/q85 contexts stay ''). Follow-up REQ after this task.
- Pipeline effect to report: the 3 DGNL/DHQG PDFs stop being `segmentation_skipped`, so the free text path yields their
  questions; the refined path is still selected explicitly (`use_refined`) and is unchanged.

