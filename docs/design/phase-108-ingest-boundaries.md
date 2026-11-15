PROGRESS: COMPLETE
SKILLS: design, token-efficiency, exam-extraction

# Phase 108 - ingest boundary fixes (draft for docs/design/phase-108-<slug>.md)
Task: TASK-108 · REQ-0115 · Source: work/TASK-107/handoff/design-ingest.md rows F001 F002 F004 F005 F010 (review Fix advisory, RAW-00330)

## Goal
5 ingest bugs fixed, each pinned by one $0 regression test from work/TASK-107/repro.py; all existing fixtures byte-identical.

## Constraints
- R = src/exam_engine/ingest/refine.py, S = src/exam_engine/ingest/segment.py. No prompt change (prompts/dev/ingest/refine.md untouched), no new inputs/flags.
- Reuse only: GROUP_RE body, _INTRO, segment._mostly_upper, split_part, existing PART_RE.
- `segment._PART.match(h) == refine.PART_RE.match(h)` (tests/unit/test_text_boundaries_qa.py:181) must hold: PART_RE stays as is.

## Generality
All exam kinds: regexes stay built from langtable words (S:13-17); no new literal. Default config: fixtures unchanged (tests listed per item). One synthetic non-DGNL case: English `Questions 5 and 6 refer to ...` / `Part II of the passage ...` in the new tests.

## Known incidents
none (docs/notes/incidents.md absent).

## Plan modes
- single-source plan: ingest feeds the exam file; same 5 behaviour changes, no plan-file schema change.
- pipeline plan: same ingest code path; no stage/schema change.
- Cache: refine page cache key = model + prompt sha + image shas (R:329); prompt unchanged so key holds. Validation runs on every hit (R:332), so F001 needs no key change; invalid cut replies were never cached (R:350-352), so they are re-asked once (paid, real runs only). Boundary cache (boundary.py:300-301) stores line labels, not rule output: still valid after the _INTRO change. Segment output is not cached.

## Design
### 108.1 cut reply with <4 options is valid (F001; owner: refine.validate_refined R:242-244)
- Condition R:243: add `and q.get("cut") is not True` -> `if orig and orig["options"] and not q.get("unreadable") and q.get("cut") is not True and not set("ABCD") <= set(opts)`.
- Effect: reply passes `_ask` (R:349), reaches window re-read / continuation bridge; incomplete result still declined by refcheck (cut flag, <4 options).
- Test `test_108_f001_cut_reply_valid`: (a) `validate_refined({'questions':[{'id':'12','text':'t','options':{'A':'a','B':'b'},'cut':True}]}, {'12':{'options':[{'key':'A','text':'a'}]}})` -> `[]`; same without `cut` -> 1 error (guard kept). (b) refine on doc_of(2) plus `doc["questions"]=[{"n":12,"options":[A..D]}]`, window=True, mock replies by call order [p1 cut q12 A,B; window q12 A-D; p2 empty] -> no exception, q12 options A-D. Coder confirms call order from R:490-523.
- Risk: none for uncut replies. Covered by tests/unit/test_multipage_assembly.py (doc_of has no `questions`, so unaffected).

### 108.2 group intro `Câu N-M` / `câu N đến câu M` is context, not a question (F002+F005; owner: segment.build S:22-27, segment._next_n S:51-56, segment.segment S:204)
- build: one shared string `span = grp + r"\s*(?:từ\s*)?(\d+)(?:\s*" + rng + r"\s*(?:[Cc]âu\s*)?(\d+)|\s+and\s+(\d+)|((?:\s*,\s*\d+)+))"`; `GROUP_RE=re.compile(span)` (byte-identical pattern), `_INTRO=re.compile(r"^\s*(?:" + lead + r"\b[^\n]{0,120}?)?" + span)`. _INTRO gains `(câu )M`, `and`, list forms (AC3); groups unused by `.match` callers.
- New helper `_q_start(line)`: `None if _INTRO.match(line) else _Q.match(line)`. Use at S:53 (`_next_n`) and S:204 (`segment`). The line then falls to S:235/S:277 -> pending -> context of the next question (or intro before the first question, as plural `Questions 1-5` today).
- Not changed: other `_Q` callers (boundary.py:91 keeps the `RC` suspect, refcheck.py:104, pdf.py:242/478/482/499, cross.py:74/77, S:164, R:404).
- Tests `test_108_f002_range_intro_not_question`: `segment(["Câu 30. x"]+O+["Câu 31-35: Đọc đoạn văn sau","Câu 31. Hỏi gì"]+O)[1]` -> n == [30, 31], q31 context == `Câu 31-35: Đọc đoạn văn sau`; same for `Câu 31 đến 35 ...`. Guards: `Câu 31. Hỏi`, `Câu 3: 1, 2` and `Câu 3 (0,5 điểm)` stay questions.
  `test_108_f005_intro_den_cau`: `_INTRO.match("Đọc đoạn văn và trả lời câu 31 đến câu 35")` truthy; `Questions 5 and 6 refer to the text` truthy; in segment after q30's D the passage lines are q31 context, D text unchanged. Guards from test_text_boundaries_qa.py:125 (`see câu 3-5 ...`) still not intro.
- Risk: a stem printed `Câu 3, 5...` / `Câu 3 - 5 ...` with no separator would become context (no fixture has one: grep `^(Câu|Question)\s*\d+\s*(-|–|đến|to|,|and)` over examples/ and tests/ = 0 hits). An intro after a question with no options is glued to that stem (S:277 needs options), before it made a bogus question. boundary._strong (boundary.py:43) sees more intros -> fewer SH/QE suspects, as intended. Coverage: test_boundary_qa.py:357 (`Câu 2-3. Dựa vào...` still gives context starting with the heading), test_group_slice.py:40, test_text_boundaries_qa.py, structure_gold.json tests, golden/segment tests.

### 108.3 empty `unreadable` question kept (F004; owner: refine.refine R:588-589)
- Condition R:588: `if not rest and not q.get("options") and not q.get("unreadable"): continue`.
- Effect: record appended at R:604 with text "", `unreadable: True` (R:613-614), `needs_review_why` unreadable (R:603); refcheck declines it (missing_text). Also stops F008's context loss for this case only.
- Test `test_108_f004_unreadable_kept`: run_refine (test_multipage_assembly.py:33 style) `[rep([q(1,'q',ABCD), q(2,'',unreadable=True)])]`, spec "1" -> ids [1,2], q2 unreadable True, refcheck.incomplete_reasons(q2) non-empty.
- Risk: a heading-only entry (`PHẦN II`, no options) is still skipped (unreadable false). Coverage: test_multipage_assembly.py.

### 108.4 stem starting `Phần I của ...` keeps text and part (F010; owner: refine.split_part R:173-176)
- Keep PART_RE. In split_part, after a match take `line = m.group(0).rstrip("\n")`, `tail = line[m.end(1):]`; strip only when the line is heading-shaped: `not tail.strip()` or `tail.lstrip()[:1] in ".:)–-"` or `segment._mostly_upper(line)`. Otherwise return `(None, text)`.
- Review Fix (strip if text remains) rejected: eats line 1 of `Part II of the passage\nmainly...`.
- Test `test_108_f010_part_word_stem`: `split_part("Phần I của văn bản nêu gì?")` -> (None, same text); `split_part("Part II of the passage\nmainly about")` -> (None, same text); headings still split: `PHẦN II\nbody`, `PHẦN II. TOÁN\nx`, `Phần IV: x\ny`, `PHẦN II TƯ DUY ĐỊNH LƯỢNG\nq` -> part + body.
- Risk: a title-case heading without separator (`Phần II Tư duy định lượng\n...`) no longer splits: part not switched, heading stays in stem (text kept, not lost). Coverage: test_langtable.py:74/77, test_generality_qa.py:180 (`PARTIE II\ncorps`), test_text_boundaries_qa.py:178-181.

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| cut question still <4 options after window/bridge | refcheck declines | missing_text decline, `cut` |
| unreadable question | kept, declined | `needs_review_why` unreadable, decline |
| intro mis-taken for a real stem | stem becomes next question's context, numbering gap | segment ok=False / refine `gap` |

## Unit tests
New file tests/unit/test_ingest_fixes_108.py with the 4 tests above (one per item, repro rows of work/TASK-107/repro.py). Gate: `python3 -I tools/run_tests.py --fast` green; no fixture/golden file edited.

## Verification
| Item | command -> expected | tier |
|---|---|---|
| 108.1 | `python3 -I work/TASK-107/repro.py` row 108-F001 -> `ok?` | $0 |
| 108.2 | repro rows 108-F002, 108-F005 -> `ok?` | $0 |
| 108.3 | `python3 -I tools/run_tests.py --affected` test_108_f004 passes | $0 |
| 108.4 | repro row 108-F010 -> `ok?` | $0 |
| all | `run_tests.py --fast` green; main runs `--full` once | $0 |

## Decisions
- F002+F005 one item: same root (_INTRO too narrow and checked after _Q).
- _INTRO reuses the GROUP_RE body string (all forms), not a second hand-written range regex.
- F010 heading-shape test over review's "strip if text remains".
- boundary.py RC suspect left as is (it flags the line; segment now handles it).

## Out of scope
F003, F006, F007, F008, F009 (IMPROVEMENT rows); `và` list form (not in GROUP_RE).

## Defects
- D1 HIGH R:242-244 valid cut reply rejected -> refine aborts invalid_reply (F001).
- D2 HIGH S:204/S:53 `Câu N-M:` parsed as question N (F002).
- D3 MED S:26-27 _INTRO misses `N đến câu M`/and/list -> passage glued to option D (F005).
- D4 MED R:588-589 empty unreadable question dropped (F004).
- D5 LOW R:170-176 stem `Phần/Part <Roman> ...` erased (F010).

Nova

## Real-data check (coordinator, 2026-11-15)
Refined DGNL stems in plans/ and work/ start with separated headings only: `PHẦN 1: SỬ DỤNG NGÔN NGỮ`,
`PHẦN 3. TƯ DUY KHOA HỌC`, `Phần 2. Toán học (30 câu).`, and one glued form `PHẦN 2. TOÁN HỌC. Một hình chữ nhật ...`
(heading + stem on one line). The title-case-without-separator limit of 108.4 has 0 hits. 108.4 MUST add a test
for each of these four shapes and keep today's split result for them (compare with the pre-change output).
