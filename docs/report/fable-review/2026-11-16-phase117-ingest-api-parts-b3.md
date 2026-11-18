<!-- fable-status -->
> **Status (2026-11-18):** 10 finding(s): 10 fixed (TASK-118, TASK-119, TASK-125). Nothing open.
>
> **Action rule (RAW-00368):** check every finding against the code. A true positive is FIXED through a task; a warning or a note alone does not close it. A false positive is recorded with its reason in `docs/review/findings.tsv` and ignored. Update the Status line at each task transition.
<!-- /fable-status -->

# Phase 117 – Ingest api.py and parts.py (batch 3)

## Findings

### F001 – [HIGH] Answer key that starts after the first 6 blocks of a page is never detected

- File: src/exam_engine/ingest/parts.py
- Lines: 10, 13-17
- Issue: `_starts_key` tests only `blocks[:_HEAD_BLOCKS]`. The DOCX and Markdown adapters emit one page (`n: 1`) holding every block.
- Case: DOCX with 40 questions followed by `ĐÁP ÁN` and `1.A 2.B ...`: `find_parts` returns one `exam` part, `to_exam_text` does not refuse, the key text reaches the exam file. Same for a PDF key heading mid-page.
- Fix: Scan all blocks of the page; when the match is not in the first 6 blocks still set `in_key` for that page.

### F002 – [MEDIUM] Page selection forgets that a kept page was an answer-key page

- File: src/exam_engine/ingest/parts.py
- Lines: 26, 104
- Issue: `select_pages` recomputes `find_parts(new)` on the kept pages only; a key page is known only by the heading on the first key page.
- Case: Pages 1-3 exam, 4-6 key, `ĐÁP ÁN` heading on page 4; `--pages 5-6` (or `1-3,5`): new parts are all `exam`, `has_key` is False, key pages are exported without `--allow-key-pages`.
- Fix: Before filtering, collect the page numbers of `answer_key` parts of `doc["parts"]`; build `new["parts"]` so every kept page in that set stays `answer_key`.

### F003 – [MEDIUM] Re-segmentation after `--pages` drops heading and list blocks of a DOCX

- File: src/exam_engine/ingest/parts.py
- Lines: 81-83
- Issue: Only `paragraph` blocks feed the lines, but the DOCX adapter segments from every `w:p` text (types `heading`, `list`, `paragraph`; docx.py 186-188).
- Case: DOCX whose options are Word auto-numbered list items (`numPr`) or whose `PHẦN II` is Heading-styled; `--pages 1`: questions lose their options / section headings, or `segmentation_skipped`.
- Fix: For `format == "docx"` take lines from blocks of type `paragraph`, `heading` and `list`; keep paragraph-only for PDF.

### F004 – [MEDIUM] A finished group range stays open and captures questions after a numbering restart

- File: src/exam_engine/ingest/api.py
- Lines: 153-156, 172-176
- Issue: `cur` is cleared only by a section change or a new group line, never when numbers pass `hi` or go backwards.
- Case: Part A questions 1-5 with `Questions 1-5: read the passage`; Part B restarts at 1 with no heading line in any context: Part B questions 2-5 get Part A's passage and figures.
- Fix: At loop start, when `cur` and `num is not None` and `num < cur["last"]`, call `close()` and set `cur = None`.

### F005 – [MEDIUM] Any range mention inside a context is taken as a new group line

- File: src/exam_engine/ingest/api.py
- Lines: 151, 161-168
- Issue: `GROUP_ANY.search(ctx)` matches anywhere in the whole context, not only an opening group line.
- Case: Group `Questions 10-15`; question 12 has own context `Use your answers to questions 3, 4 here.`: a new range 3-4 replaces `cur`, questions 12-15 lose the passage, the carrier gets `range_overrun`.
- Fix: Search only the first non-empty line of `ctx` and require `segment._INTRO.match` (as `split_guide` does); otherwise fall through to the member branch.

### F006 – [MEDIUM] Verification gate switches off when the selected slice has no `verification` key

- File: src/exam_engine/ingest/api.py
- Lines: 249-250, 266-269
- Issue: `_gate` decides "active" on the list after the `spec` slice, so "a missing key counts as unverified" is not applied.
- Case: Refined questions 1-60 carry `verification`, 61-70 carry none; `questions="61-70"`, `min_verification="verified"`: all ten are kept and `skipped()` is empty.
- Fix: In `_pick_refined` compute `any("verification" in q ...)` on the full list before slicing and pass it to `_gate` as the active flag.

### F007 – [MEDIUM] `N + offset` note is wrong when the kept refined ids are not consecutive

- File: src/exam_engine/ingest/api.py
- Lines: 293-300
- Issue: The per-question mapping is printed only when `skipped` is non-empty; otherwise one offset from `qs[0]` is assumed, or no note when `first == 1`.
- Case: `questions="61-70,81-90"` (or id 62 absent from `refined`), nothing skipped: note says `N + 60`, but question 11 is printed 81. `questions="1,3,5"`: no note at all.
- Fix: Use the offset line only when `[int(q["id"]) for q in qs] == list(range(first, first + len(qs)))`; otherwise print the `k=id` mapping.

### F008 – [MEDIUM] Merging a page-cut question drops the first part's options, figures and the second page

- File: src/exam_engine/ingest/api.py
- Lines: 190-194
- Issue: `options=q["options"] or qs[-1]["options"]` replaces instead of merging; `figures` and `page` of the second part are not carried.
- Case: Question 12 on page 3 with options `{A, B}` and again on page 4 with `{C, D}` and a figure: merged question has only C and D, no figure, `Source pages: 3`.
- Fix: Merge `dict(qs[-1]["options"], **q["options"])`; append the second part's `figures`; add `q["page"]` to `continued_pages` when it differs from `qs[-1]["page"]`.

### F009 – [LOW] `_KEY` prefix match marks ordinary text as the start of the answer key

- File: src/exam_engine/ingest/parts.py
- Lines: 9, 15
- Issue: `_KEY.match` accepts any block that begins with the words; `\b` also passes `loi giai` in `lời giải thích`.
- Case: Page 3 starts with the paragraph `Solutions to climate change require ...` or `Lời giải thích nào sau đây đúng?`: pages 3 to the end become `answer_key`, `to_exam_text` raises `answer_key_present`.
- Fix: Accept a block only when it is heading-like: `type == "heading"`, or folded text at most 60 characters with no `?` and not ending in `.`.

### F010 – [LOW] Refusal message reads `doc["parts"]` that `has_key` did not need

- File: src/exam_engine/ingest/api.py
- Lines: 67-71
- Issue: `parts.has_key` falls back to `find_parts(doc)` when `parts` is absent (`_finish` never sets it for Markdown), but the message indexes `doc["parts"]`.
- Case: Markdown file starting with `# Đáp án đề 01`: `to_exam_text` raises `KeyError: 'parts'` instead of `IngestError("answer_key_present")`.
- Fix: Compute `found = doc.get("parts") or parts.find_parts(doc)` once and build the message from `found`.

## Summary

- Total findings: 10
- Critical: 0
- High: 1
- Medium: 7
- Low: 2
- More actionable findings exist (e.g. `assembly` raising on a bad `questions` / `min_verification` value, unbounded range in `parse_pages`); they need another review batch.
