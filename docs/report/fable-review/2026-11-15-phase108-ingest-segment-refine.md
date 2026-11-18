<!-- fable-status -->
> **Status (2026-11-18):** 10 finding(s): 10 fixed (TASK-108, TASK-134). Nothing open.
>
> **Action rule (RAW-00368):** check every finding against the code. A true positive is FIXED through a task; a warning or a note alone does not close it. A false positive is recorded with its reason in `docs/review/findings.tsv` and ignored. Update the Status line at each task transition.
<!-- /fable-status -->

# Phase 108 – Ingest segment.py and refine.py (boundary, numbering, page-span logic)

## Findings

### F001 – [HIGH] A-D option check rejects a legitimately cut question

- File: src/exam_engine/ingest/refine.py
- Lines: 242-244
- Issue: `validate_refined` demands options A-D whenever the same-numbered source question has options; only `unreadable` is exempt, `cut` is not.
- Case: Question 12 has A, B on page 4 and C, D on page 5; the source question has options. The page-4 reply (`cut: true`, 2 options) fails twice, `_ask` raises `invalid_reply`, the refine run aborts.
- Fix: Skip the A-D check when `q.get("cut") is True`.

### F002 – [HIGH] Group intro `Câu 31-35: ...` is parsed as question 31

- File: src/exam_engine/ingest/segment.py
- Lines: 53-55, 204-206, 224
- Issue: `segment()` tests `_Q` before `_INTRO`; `Câu\s*(\d+)\s*[.:)]?` matches a range intro that starts with `Câu N`.
- Case: Line `Câu 31-35: Đọc đoạn văn sau` (or `Câu 31 đến 35 ...`) becomes question 31 with text `-35: ...`; the real `Câu 31.` duplicates it, numbering breaks, the passage is lost as context.
- Fix: In `segment()` and `_next_n`, treat a line as a question start only when `_Q.match(line)` and not `_INTRO.match(line)`.

### F003 – [MEDIUM] `starts_with_number` orphan check never matches multi-line continuation

- File: src/exam_engine/ingest/refine.py
- Lines: 404-405
- Issue: `segment._Q` ends with `(.*)$` without DOTALL/MULTILINE, so `_Q.match` fails on any text containing an inner newline.
- Case: Continuation text `13. Tính giá trị ...\nA. 2 ...` (a new question mis-reported as continuation) is not flagged and is appended to the open question of the previous page.
- Fix: Match only the first line: `segment._Q.match(cont["text"].split("\n", 1)[0])`.

### F004 – [MEDIUM] Unreadable question with empty text is silently dropped

- File: src/exam_engine/ingest/refine.py
- Lines: 588-589
- Issue: Entries with empty text and no options are skipped, but `validate_refined` (line 230) accepts exactly that shape when `unreadable` is true.
- Case: Reply entry `{"id": "7", "text": "", "unreadable": true}`: question 7 never reaches `qs`, so no `unreadable` / `needs_review` record exists for it.
- Fix: Change the skip condition to `not rest and not q.get("options") and not q.get("unreadable")`.

### F005 – [MEDIUM] `_INTRO` misses range forms that `GROUP_RE` accepts

- File: src/exam_engine/ingest/segment.py
- Lines: 22-23, 26-27, 277-281
- Issue: `_INTRO` requires `N <range> M` directly; `GROUP_RE` also allows `N đến câu M`, `N and M`, `N, M, K`.
- Case: After question 30's option D, the line `Đọc đoạn văn và trả lời câu 31 đến câu 35` is not an intro, so it and the following passage are glued into option D.
- Fix: In `_INTRO`, allow `(?:[Cc]âu\s*)?` after the range word and add the `\s+and\s+\d+` and `(?:\s*,\s*\d+)+` alternatives, mirroring `GROUP_RE`.

### F006 – [MEDIUM] Bridge refuses options split across two pages

- File: src/exam_engine/ingest/refine.py
- Lines: 406-407, 417-418
- Issue: `_attach` returns `owner_has_options` whenever both sides have options, even with disjoint keys; line 418 otherwise replaces instead of merging.
- Case: `window=False` or a window fallback (line 513); owner has A, B on page 4, continuation has C, D on page 5: C, D are never merged and the question stays incomplete as an orphan.
- Fix: Flag `owner_has_options` only when the key sets intersect; otherwise merge with `o["options"] = dict(o["options"], **cont["options"])`.

### F007 – [LOW] Carried passage lost on a page with no questions and no `continues` key

- File: src/exam_engine/ingest/refine.py
- Lines: 526, 591-592
- Issue: `carry` is overwritten at line 526; the old value is re-kept only if `"continues" in obj`.
- Case: Page 5 returns `carry` (passage); page 6 is empty or figure-only (`{"questions": []}`); page 7 holds the questions. The passage is dropped and question 1 of page 7 gets no context.
- Fix: Drop the `"continues" in obj` condition: keep `carried` whenever it is non-empty and `numbered` is empty.

### F008 – [LOW] Carried passage consumed by a heading-only entry that is then skipped

- File: src/exam_engine/ingest/refine.py
- Lines: 582-589
- Issue: `carried` is put into the first numbered entry and cleared (585) before the empty-entry skip (588-589).
- Case: First numbered entry of the page is only a part heading (`text: "PHẦN II"`, no options): it is skipped, and the passage carried from the previous page is lost for the next question.
- Fix: Evaluate `split_part` and the skip condition first; assign and clear `carried` only for an entry that is kept.

### F009 – [LOW] False `gap` on a window-completed question after non-adjacent pages

- File: src/exam_engine/ingest/refine.py
- Lines: 555-556, 599
- Issue: Page items use `_gaps(items)` (per page), but the window path uses `_gaps(qs[:pending["qi"] + 1])` across all earlier pages.
- Case: Pages 2 and 7 selected; page 2 ends at question 5; question 20 is first on page 7 and cut. After the window, question 20 gets `needs_review_why: ["gap"]` though nothing is missing.
- Fix: Pass only questions with `page >= pending["pages"][0]` (up to index `qi`) to `_gaps` at line 556.

### F010 – [LOW] Question text starting with `Phần I` / `Part II` loses its first line

- File: src/exam_engine/ingest/refine.py
- Lines: 170, 173-176, 586-589
- Issue: `PART_RE` (case-insensitive) takes any first line starting with the part word plus a Roman numeral as a heading and removes the whole line.
- Case: Text `Phần I của văn bản nêu nội dung gì?`: the stem becomes empty and `part` switches to `I`; without options the question is dropped at 588-589.
- Fix: In `split_part`, strip the heading only when text remains after the heading line; otherwise return `(None, text)`.

## Summary

- Total findings: 10
- Critical: 0
- High: 2
- Medium: 4
- Low: 4
- The 10-finding limit was reached; further lower-priority candidates (e.g. `question_end` hint while a context is pending in segment.py, label matching in `_native_tables`) need another review batch.
