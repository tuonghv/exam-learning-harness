# Phase 119 – Fix-I api: cut merge, group restart, mention range, offset note (TASK-119, REQ-0126)

Source: docs/design/phase-117-review-triage-b3.md rows 117-F008/F004/F005/F007; draft work/TASK-119/handoff/design.md; repros work/TASK-117/repro_api.py. Only file: src/exam_engine/ingest/api.py (api.py:70 untouched).

## Goal
Exam text from refined/segmented questions keeps both parts of a cut question, ends a group at a numbering restart,
ignores a group mention that does not cover its carrier, and prints the `N + offset` note only when it is true.
## Constraints
No prompt, cached body or cache key touched. Python stdlib. Output for inputs without these cases stays byte-identical.
## Generality
All exam kinds and formats (PDF/DOCX/MD, refined or not); no literal added; GROUP_ANY (segment.py:36) unchanged.
## Plan modes
- refined (`--refined`): 119.1, 119.4 change it; 119.2/119.3 via `_pick_refined` -> `_share_context` (api.py:265).
- segmented (no refine): 119.2/119.3 only (`_share_context`); 119.1/119.4 not reached (refined-only functions).
- `--questions` slice: 119.4 is where gaps show; slice runs after sharing, unchanged.
- solve / genexam / paid runs: not touched (consume the exam text only).

## Design
### 119.1 cut-question merge keeps both parts (117-F008; owner: `refined_questions` api.py:184-197)
- Change in the `qs[-1]["id"] == q["id"]` branch (api.py:190-194), first part `a = qs[-1]`, second `q`:
  `options = {**(a.get("options") or {}), **(q.get("options") or {})}` (disjoint letters = union; same letter = 2nd
  wins, i.e. today's result); `figures = a.figures + [f for f in q.figures if f not in a.figures]` (set only if
  non-empty); `continued_pages = sorted(a.cp | q.cp | {q["page"]} if q.page and q.page != a.page)`. text/cut as now.
- Mirrors refine `_attach` (refine.py:432-435: figures appended, page n added to continued_pages). refine's
  `owner_has_options` (:421) refuses to merge; here the AI already gave the same id, so union is the safe merge.
- Minimal: 3 expressions in one branch; no new field.
- Test: repro F008 (ids 12/12, A-B p3 cut, C-D + figures ["f1"] p4) -> options `[A,B,C,D]`, figures `["f1"]`,
  continued_pages `[4]` (old: `[C,D]`, None, None). Plus: both parts A-D -> 2nd part's A-D (unchanged).
- Risk: a 2nd part that re-lists A-D with different text silently wins (as today). Low.
### 119.2 range closes at a numbering restart (117-F004; owner: `_share_context` api.py:146-179)
- Detection without a heading: `num <= cur["last"]` (a number not above the last member/carrier seen in the open range)
  means the numbering went back -> restart. New branch in the chain after the opening branch (see 119.3), before the
  member test (api.py:172): `elif cur and num is not None and num <= cur["last"]: close(); cur = None` (q appended
  as is). `close()` flags `range_overrun` on the carrier when the restart came before `hi` (true: the range ended early).
- Does not touch `range_cut_by_section`/ghost: ghost is only set at a section change, where cur becomes None, and is
  cleared when a range opens, so `cur is not None` implies `ghost is None`; the new branch needs cur, the ghost branch
  is unchanged and still reached when cur is None. The ghost is not set on a restart (a restart is a new numbering,
  not a cut range; flagging it would add false `range_cut_by_section`).
- Minimal: one elif, reuses `close()` and `cur["last"]` (already maintained at :164/:168/:173).
- Test: repro F004 (Q1 "Questions 1-5" + passage, 2-5, then 1-5 again, no heading) -> contexts of out[5:] all None
  (old: `[None, 'Questions 1-5' x4]`). Keep: existing range_cut_by_section and range_overrun tests green.
- Risk: a duplicate or out-of-order id inside a group (AI repeats id 47 after 48) ends the group early; carrier gets
  `range_overrun` (visible). Equal ids adjacent are merged before (119.1), so only non-adjacent repeats hit it.
### 119.3 a mention opens a range only when it covers its carrier (117-F005; owner: `_share_context` api.py:161-171)
- Change: compute `lo, hi = segment.group_span(m)` before the test; open/repeat branch only when
  `m and (num is None or lo <= num <= hi)`; else fall to 119.2 / member / ghost branches (member gets
  `instruction_override` with its own line leading the text, keeps the passage).
- Minimal and keeps TASK-116 widening: no `_INTRO` gate (review Fix rejected, triage :43, design-api.md:40-43).
- Test: repro F005 (10 "Questions 10-15" + passage, 11, 12 ctx "Use your answers to questions 3, 4 here.", 13-15)
  -> q13-15 context starts "Questions", q10 structure None, q12 structure ["instruction_override"]
  (old: q13-15 '', q10 ["range_overrun"]).
- Risk: a real carrier numbered outside its own span (e.g. q45 holds "Questions 46-52") no longer opens a range.
  The oracle below shows it; if found on the 4 PDFs, stop and ask (option: `lo - 1 <= num`).
### 119.4 offset note only when true (117-F007; owner: `_from_refined` api.py:293-300)
- Change: `seq = all(q["id"] == str(first + k) for k, q in enumerate(qs))`; mapping line when
  `skipped or not seq` (was `skipped`); offset line `elif first != 1` (only reached when seq). String compare: no new
  int() on later ids. Comment at :295 -> "kept ids not consecutive: the N + offset line would be wrong".
- Minimal: one boolean, existing two lines reused.
- Test: (a) ids 61,62,81, spec "61-62,81" -> line "printed numbers: 1=61, 2=62, 3=81.", no "N + 60" (old: "N + 60").
  (b) ids 1,3,5 no spec -> mapping line present (old: no note). (c) ids 61-63 -> "N + 60" line unchanged.
- Risk: none for consecutive runs (byte-identical); gap runs get a longer note line.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| carrier outside its span (119.3) | group not opened, members lose passage | oracle diff; review structure flags |
| repeated id mid-group (119.2) | group closed early | `range_overrun` on carrier |
## Unit tests
One test per item (the 4 repros above, in the existing api test module), each asserted failing on HEAD first
(git stash or the old assertion noted in the test docstring). Plus 119.1 full-A-D repeat and 119.4(c) no-change.
## Verification
| Item | command -> expected | tier |
|---|---|---|
| 119.1-119.4 | `python3 -I tools/run_tests.py --affected` -> new tests pass; on HEAD they fail | $0 |
| AC5 | `--fast` -> NEW 0 | $0 |
| AC5 oracle | `python3 -I work/TASK-116/evidence/share_oracle.py` (args as TASK-116) on the 4 input PDFs at HEAD -> `work/TASK-119/evidence/share_old.*`; after the change -> `share_new.*`; diff -> 0 lines, or only intended moves | $0 |
Intended oracle moves (each must be explained by id): (119.2) questions after a numbering restart with no heading lose
the previous group's context/`instruction_override`, and the carrier may gain `range_overrun`; (119.3) a question whose
group line does not cover its own number becomes a member (`instruction_override`) and later members keep the passage,
the earlier carrier loses `range_overrun`. Any other move (a carrier whose number lies outside its own span losing its
group, a section/ghost flag change) = regression, stop. 119.1/119.4 are not in the oracle (refined-only); their tests cover them.
## Decisions
- F005: span-covers-carrier, not `_INTRO.match` (review Fix wrong, triage :43). F004: `num <= last`, no ghost on restart.
- F008: union, 2nd part wins a clash; no new `cut_options_overlap` flag (coordinator: today's result, nothing new to flag).
## Out of scope
F001-F003, F006, F009, F010 (TASK-118/120); refine `_attach` itself.

## Defects
None new (the 4 findings above are the task).

## Coordinator changes after the real-data oracle (2026-11-16)
The first implementation moved 96 contexts on the 3 DGNL/DHQG PDFs. Cause: segment reads numbered passage lines and
year/formula lines (`1`..`6`, `1991`, `2020`, `0`) as questions, so a real group line often sits on a false carrier
outside its span, and stray low ids sit inside groups. Changes:
- 119.3: a mention that does not cover its own number is ignored only when the question is a member of the open range
  (`cur["lo"] < num <= cur["hi"]`); a non-member keeps opening the range as before.
- 119.2: a drop (`num <= last`) closes the range only when no later question falls in `(last, hi]` (the range never
  resumes); a carrier outside its span starts `last` at `lo - 1`.
Result: share oracle old vs new over the 4 input PDFs = 0 diff lines; the F004/F005 repros still fixed.

## Defects (new, follow-up)
- D1 MED segment.py: passage/year/formula lines (`1991 ...`, `2020 ...`, numbered passage lines) are read as questions;
  the real first member of a group (DHQG 106, 109, 112; DGNL 2025 q46) then gets no passage (`''`) before and after this
  task. Needs its own REQ (number plausibility in segment).
