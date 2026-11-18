<!-- fable-status -->
> **Status (2026-11-18):** 10 finding(s): 10 fixed (TASK-114, TASK-124, TASK-125). Nothing open.
>
> **Action rule (RAW-00368):** check every finding against the code. A true positive is FIXED through a task; a warning or a note alone does not close it. A false positive is recorded with its reason in `docs/review/findings.tsv` and ignored. Update the Status line at each task transition.
<!-- /fable-status -->

# Phase 114 – Ingest segment.py and refine.py (batch 2)

## Findings

### F001 – [MEDIUM] Heading or group intro after a no-option question is glued into its stem

- File: src/exam_engine/ingest/segment.py
- Lines: 282-290
- Issue: A context (`pending`) opens only when `qs[-1]["options"]` is non-empty; otherwise `_INTRO` / `_READ` / `_PART_ANY` lines fall to line 288.
- Case: `Câu 5. Viết đoạn văn ...` (no options), then `PHẦN II. ĐỌC HIỂU` or `Questions 6-10: Read ...` plus the passage: all appended to question 5's text; question 6 gets no context.
- Fix: Open `pending` for those three strong matches without options; at 290 append to `qs[-1]["text"]` when options are empty.

### F002 – [MEDIUM] `_INTRO` is case-sensitive while `_Q` is not

- File: src/exam_engine/ingest/segment.py
- Lines: 14, 21, 27, 51-53
- Issue: `_Q` uses `re.I` and accepts `Cau`; `_INTRO` has no flag and its group word is `[Cc]âu` / `Questions?` only, so `_q_start` does not skip such intros.
- Case: `CÂU 31 - 35: ĐỌC ĐOẠN VĂN` or `Cau 31-35: ...` becomes question 31 with text `- 35: ...`; `QUESTIONS 31-35` after option D is glued into option D.
- Fix: Compile `_INTRO` with `re.I` and add `Cau` to the `grp` alternatives.

### F003 – [MEDIUM] Non-string `figures` entries pass validation and crash `_native_tables`

- File: src/exam_engine/ingest/refine.py
- Lines: 211-212, 245-246, 283-285
- Issue: `validate_refined` / `_continues_errors` only check that `figures` is a list; line 283-285 joins the entries as strings and line 293 folds them.
- Case: Reply has `"figures": [{"description": "bảng số liệu"}]` on a page with a native table block: `TypeError` after all calls are paid, no output.
- Fix: In both validators require `all(isinstance(f, str) for f in figures)` and report an error otherwise (triggers the retry).

### F004 – [MEDIUM] Failed backward re-run discards the finished first pass

- File: src/exam_engine/ingest/refine.py
- Lines: 662-669
- Issue: The recursive `refine()` call is unguarded; any `RefineError` inside it propagates although `out` is already complete.
- Case: First pass succeeds with a `no_owner` orphan on page 5; the re-run call for page 4 times out (`call_failed`) or hits the reduced cap `max_cost - cost`: exit 3, all paid results lost.
- Fix: Wrap the re-run in `try/except RefineError`; on failure add `getattr(e, "calls"/"cost")` to `out["refined"]`, append a warning and continue to the normal return of `out`.

### F005 – [LOW] `question_end` / continuation hint applied while a context is pending

- File: src/exam_engine/ingest/segment.py
- Lines: 222-228, 261-273
- Issue: Both hint branches append the line to the last option of `qs[-1]` without checking that `pending` already holds the next question's context.
- Case: After `Read the following passage` opened `pending`, a passage line hinted `question_end` is appended to question 5's option D and is missing from question 6's context.
- Fix: When `pending` is non-empty, append the line to `pending` (note the hint as `boundary_ai_overruled`) instead of the option text.

### F006 – [LOW] Native table judged "already carried" by substring match of short cells

- File: src/exam_engine/ingest/refine.py
- Lines: 281, 286-288
- Issue: `fold(c) in hay` is a substring test; one-digit data cells match inside any longer number.
- Case: Table cells `1`, `2`, `3`, `4`, `5`; refined text contains `2025` and options `13`, `45`: 100% "found", the table is silently skipped though the refined question does not carry it.
- Fix: Match whole tokens: `re.search(r"(?<!\w)%s(?!\w)" % re.escape(fold(c)), hay)`.

### F007 – [LOW] Table label matching fails for labels ending in a non-word character or all-numeric tables

- File: src/exam_engine/ingest/refine.py
- Lines: 293-296
- Issue: `\b...\b` cannot match a label that starts or ends with punctuation; with no non-numeric cells `labels` is empty and `best` stays `None`.
- Case: Labels `(kg)`, `%`, or a table of numbers only, with one matching figure entry: `native_table_unplaced` is raised and the table text is not appended.
- Fix: Use `(?<!\w)` / `(?!\w)` instead of `\b`; when `labels` is empty and exactly one figure exists on `on`, choose its question.

### F008 – [LOW] Orphan warning advises page 0 or an already selected page

- File: src/exam_engine/ingest/refine.py
- Lines: 689-693
- Issue: The message lists `o["page"] - 1` for every orphan, whatever its kind and page.
- Case: `continues` on page 1 gives `add page(s) 0 to --pages`; a `starts_with_number` / `owner_has_options` orphan on page 5 advises adding page 4, which is already selected.
- Fix: Build the "add page(s)" list only from `no_owner` orphans with `page - 1 >= 1` and not in `pages`; de-duplicate; omit the advice when the list is empty.

### F009 – [LOW] Out-of-order window question is flagged without a reason code

- File: src/exam_engine/ingest/refine.py
- Lines: 548-549, 615-617
- Issue: `_review` sets `needs_review=True`, but `needs_review_why` is written only from `why`, which has no code for it.
- Case: Window reply lists question 12 after the completed question 14: the stored question has `needs_review: true` and no `needs_review_why`.
- Fix: At 616-617, when `q.get("_review")` is set, add a code (for example `"order"`) to `why` before storing `needs_review_why`.

### F010 – [LOW] Window result overwrites the passage carried into the fragment's context

- File: src/exam_engine/ingest/refine.py
- Lines: 559, 589-591
- Issue: `context=whole.get("context") or f["context"]` replaces the fragment's context, which may hold the `carried` passage of a page outside the window.
- Case: Passage on page 3 (`carry`); page 4's only question 31 is cut; window 4-5 returns question 31 with context `Questions 31-35 ...`: the page-3 passage is lost.
- Fix: When both exist and `fold(whole context)` is not in `fold(f["context"])`, join `f["context"] + "\n" + whole context`; when it is contained, keep `f["context"]`.

## Summary

- Total findings: 10
- Critical: 0
- High: 0
- Medium: 4
- Low: 6
- The 10-finding limit was reached; further lower-priority candidates (an entry with a digit-free id plus options treated as a continuation in `validate_refined` / `_cont`, unvalidated `carry` / `context` types, `numbering()` rejecting a first run that does not start at 1) need another review batch.
- Batch 1 (phase 108) F003, F006, F007 and F009 still appear unfixed in the current source (refine.py lines 411, 413-425, 598, 563); not repeated here.
