# Phase 114 – Fix-F ingest: option-less heading, upper-case intro, carried passage, failed re-run (TASK-114, REQ-0121)

S = src/exam_engine/ingest/segment.py, R = src/exam_engine/ingest/refine.py. Source: triage docs/design/phase-113-review-triage-b2.md; designer draft work/TASK-114/handoff/design.md.

## Plan modes
Both. segment.py runs in the single-source and the pipeline ingest path; refine.py (F004, F010) only on refined (page-image) ingest, which both plan modes use. No solve-path, prompt or cache-key change.

## Goal
The four BUG rows of phase-113 (114-F001, F002, F010, F004) keep every question, heading, intro and passage. A failed backward re-run no longer throws away the finished refine. Every other input gives byte-identical output (checked by the segdump oracle).

## Constraints
- GROUP_RE stays byte-identical (phase-108; api.py:107 uses it). Only `_INTRO` changes.
- No prompt, template or cache-key change: F004 and F010 are post-processing after `_ask`, so the refine cache (keyed on the prompt and images) still holds.
- Python stdlib only. Tests use synthetic text and fake `llm` replies (test_multipage_assembly.py:24-46 style).

## Generality
Covers every text-layer exam kind: option-less parts (short answer, essay, fill-in) and upper-case or diacritic-less intros. No exam-specific literal is added. The `Cau` word joins the existing vi/en defaults in `build()`. An empty langtable keeps `_Q`, GROUP_RE, `_PART` and `_PART_ANY` byte for byte.

## Design
### 114.1 F001 option-less question keeps the next heading/intro out (owner: S `segment`, S:282-290)
- Change: S:282 also opens `pending` when `not qs[-1]["options"]` and the line is a heading, i.e. `_PART_ANY.match(line)` or (`m = _INTRO.match(line)` and `group_span(m)[0] == qs[-1]["n"] + 1`). The `closed` / `_READ` / `_is_subheading` triggers stay options-only.
- S:289-290: if `qs[-1]["options"]`, append to `options[-1]` as today; otherwise append to `qs[-1]["text"]` (removes the IndexError path).
- Why minimal: the review's wider fix (every `_READ`/subheading) would empty `Question 50.` / `Read the text and write ...` stems (phase-113 note). Only the two forms that are never a stem are added.
- Test A (fails today): `['Câu 1. Viết đoạn văn','PHẦN II. ĐỌC HIỂU','Câu 2. q','A. a','B. b','C. c','D. d']` -> q[0].text `Viết đoạn văn`, q[1].context `PHẦN II. ĐỌC HIỂU`, ok True. Today: `Viết đoạn văn PHẦN II. ĐỌC HIỂU` and None (repro_ingest.out:1).
- Test B (fails today): `['Câu 1. Viết','Câu 2 - 3: Đọc đoạn văn sau','Para.','Câu 2. x',ABCD lines,'Câu 3. y',ABCD lines]` -> q[1].context `Câu 2 - 3: Đọc đoạn văn sau\nPara.`.
- Guard C (passes today and must keep passing): `['Câu 1.','Read the text and write a summary.','Câu 2. q',ABCD]` -> q[0].text keeps the Read line. A span that does not start at n+1 (`Câu 5 - 7 ...` after q1) stays in the stem.
- Guard D (end of input): `['Câu 1. Viết','PHẦN II. X']` -> no exception, q[0].text `Viết PHẦN II. X`.
- Risk: a wrapped essay stem line that starts with `Phần 2 ...` (`_PART_ANY` is re.I) now moves to the next question's context. Questions with options already behave this way. Detected by the segdump diff.

### 114.2 F002 upper-case / `Cau` group intro (owner: S `build`, S:13-27)
- Change: build a second span used only by `_INTRO`. Its group word is `(?i:` + `langtable.alt(r"(?:Questions?|C[aâ]u(?:\s*hỏi)?)", "group", table)` + `)`, with the same rng/number tail. `_INTRO = ^\s*(?:lead\b...)? + intro_span`. `span` and GROUP_RE are untouched.
- Scoped `(?i:)` instead of a global re.I: lead words (`Đọc`, `Read`) stay case-sensitive, so a lower-case wrapped option such as `read questions 3-5` is not newly turned into an intro.
- Why minimal: `_q_start` (S:51-53) already defers to `_INTRO`, so widening `_INTRO` is the only change needed. Group numbering (groups 1-4) is unchanged because `alt` gives non-capturing groups. Check this with test_langtable.py:53-62.
- Test E (fails today): `segment._q_start('CÂU 31 - 35: ĐỌC ĐOẠN VĂN')` and `_q_start('Cau 31 - 35: Doc doan van')` -> None. Today the first returns a match with group(3) `- 35: ĐỌC ĐOẠN VĂN` (repro_ingest.out:2).
- Test F (fails today): segment `['Câu 1. q',ABCD,'CÂU 2 - 3: ĐỌC ĐOẠN VĂN','Para.','Câu 2. x',ABCD,'Câu 3. y',ABCD]` -> 3 questions, ok True, q[1].context starts `CÂU 2 - 3`.
- Guard G: `segment.GROUP_RE.pattern` and `.flags` equal a literal snapshot taken from HEAD. test_text_boundaries_qa.py:125 (`see câu 3-5` is not an intro) stays green.
- Risk: api.py:107 GROUP_RE stays case-sensitive, so the `CÂU 31 - 35` intro becomes context of q31 but is not copied to q32-35. That is AC2 scope only; noted under Out of scope.

### 114.3 F010 window merges with the carried passage (owner: R `refine`, R:557-560)
- Change: R:559 `context=` becomes a merge, with `fc = f["context"] or ""` and `wc = str(whole.get("context") or "")`:
  - if `not fc` or `not _dedupe(wc, fc)` (fc already inside wc): use `wc or fc`.
  - otherwise: `"\n".join(x for x in (fc, _dedupe(fc, wc)) if x)`.
- Why minimal: it uses `_dedupe` (R:396) both ways and adds no new fold test. An empty or repeated window context keeps today's value.
- Test H (fails today), with `refine.refine(doc_of(3), "1-3", llm, None, all_pages=True, window=True)` and the fake llm returning in order:
  - p1 `{'questions':[],'carry':'PASSAGE TEXT LONG ENOUGH'}`
  - p2 `{'questions':[q(31,'Stem thirty one',{'A':'a','B':'b'},cut=True)]}`
  - window(2,3) `{'questions':[q(31,'Stem thirty one',ABCD,context='Questions 31-35')]}`
  - Expected: q31 context `PASSAGE TEXT LONG ENOUGH\nQuestions 31-35`. Today: `Questions 31-35`.
  - Path: the carried passage lands at R:591, the window at R:508, and the overwrite happens at R:559. Assert `windows[0]["result"] != "fallback"`. If similarity (R:518) rejects the window, make the stem longer and identical.
- Guard I: window context `PASSAGE TEXT LONG ENOUGH\nQuestions 31-35` -> the same string, with no duplicate PASSAGE.
- Risk: a window context that does not contain the fragment's context is now appended instead of replacing it, which can repeat the passage in a paraphrased form. Only windowed questions are affected, and stored docs are not re-derived (see Verification).

### 114.4 F004 failed backward re-run keeps the first pass (owner: R `refine` `ask` R:482-495, back R:662-669)
- Change 1, in `ask`: set `e.run_calls, e.run_cost = calls, cost` on the cost_cap error before raising it (R:485), and after the increments in the except branch (R:492-495). These are new attribute names, so `e.calls`/`e.cost` (per call) and the R:509 window catch do not double-count.
- Change 2: wrap R:664-669 in `try/except RefineError as e`. Codes outside `call_failed`, `invalid_reply`, `cost_cap` are re-raised. Otherwise:
  - add the inner run's totals: `calls += getattr(e, "run_calls", 0)` and `cost += getattr(e, "run_cost", 0.0)`.
  - rewrite `out["refined"]["calls"]` and `["cost_usd"]` from those totals.
  - append the warning `{"level":"warning","code":"recover_failed","message":"backward re-run of page(s) <back> failed (<e.code>): first pass kept"}` to `wwarn`.
  - fall through to R:670. The existing orphan_continuation warning still advises adding the page.
- Why minimal: one try block plus two attribute writes. The successful path is unchanged.
- Test J (call_failed, fails today: RefineError):
  - Fake llm counts its calls. The p2 reply is `{'questions':[],'continues':{'text':'tail'}}`, which gives a `no_owner` orphan. Every later call returns `C(False, "", 0.0, ...)`.
  - Run `refine.refine(doc_of(2), "2", llm, None, window=True)`.
  - Expected: returns normally; `refined.pages == [2]`; orphans `[{page 2, no_owner}]`; a warning with code `recover_failed`; `refined.calls ==` the llm call count.
- Test K (cost_cap, proves run totals and not the failing call only):
  - doc_of(3), spec "2", `max_cost=1.0`.
  - p2 reply: the orphan as above, cost 0.1.
  - Inner p1 reply (fresh call): `q(1,'s',cut=True)` with cost 0.95. The inner window(1,2) then hits cost_cap at R:485 (0.95 >= 0.9).
  - Expected: `calls == 2`, `cost_usd == 1.05`. Today: RefineError. A fix that counts only the failing call gives 1 / 0.1.
- Optional L: invalid_reply via 2 non-JSON replies, same assertions as J.
- Risk: a failure raised outside `ask` (the R:114 render error) has no run totals, so it counts 0 inner calls. Its code is call_failed, so the first pass is still kept. State this in the doc.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| backward re-run call_failed/invalid_reply/cost_cap | first pass returned | `recover_failed` + `orphan_continuation` warnings |
| other RefineError in re-run | raised as today | exit 3 |

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 114.1-114.4 | `python3 -I tools/run_tests.py --affected`, then `--fast` -> tests A, B, E, F, H, J, K pass; NEW 0 | 0 |
| tests bite | revert the S/R hunks (main does this) -> A, B, E, F, H, J, K fail | 0 |
| oracle | copy work/TASK-108/evidence/segdump.py to work/TASK-114/segdump.py (details below), run on old and new src, `diff` -> 0 lines, or only the A/B/F-style inputs | 0 |
| refine | $0 cached replay: run `ingest --refine` over input/dgnl/*.pdf with old and new src, cache dirs plans/{dgnl-window,dgnl2025,dhqg2024}/cache, an llm that fails on a cache miss (0 paid calls), diff refined docs -> 0 changes outside F010/F004 inputs; a cache miss is reported, not paid | 0 |

The segdump copy adds full `text`, `context`, option texts and `ok`; today's script dumps only text[:60] and the option count, so it would miss F001 context moves. Old src = `git show HEAD:` into the scratchpad.

## Decisions
- F002: scoped `(?i:)` on the group word, not a global re.I: lead words stay case-sensitive.
- F004: new `run_calls`/`run_cost` attributes, not an overwrite of `e.calls`: avoids double-counting at R:493 and R:509.

## Out of scope
F003 and F005-F009 (IMPROVEMENT). The S:262 hint `no_options` reject. Propagating an upper-case intro through api.py GROUP_RE. Upper-case lead words (`ĐỌC ... CÂU 31-35`).

## Defects
- D1 MED S:282/S:288-290 (F001), D2 MED S:27 (F002), D3 MED R:559 (F010), D4 MED R:662-669 (F004); evidence work/TASK-113/handoff/design-ingest.md rows and repro_ingest.out.
- D5 LOW work/TASK-108/evidence/segdump.py:10 dumps no context, so it cannot see F001-type changes (oracle gap).
