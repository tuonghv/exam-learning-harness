# Phase 111 – Review of pipeline/review.py and pipeline/report_kinds.py

## Findings

### F001 – [MEDIUM] Null superseded note crashes the index or hides a superseded file

- File: src/exam_engine/pipeline/report_kinds.py
- Lines: 103, 117, 141, 262-263, 292
- Issue: `run_superseded` validates only `glob`; `sup.get("note", "")` returns None when the key exists with null. `nested_superseded` then returns None, which `render_index` reads as "no match"; `superseded_note` returns None and `desc.replace` raises AttributeError.
- Case: A run manifest has `"superseded": [{"glob": "*", "note": null}]`. Nested run: its files are listed `standard`. Folder's own manifest: `render_index` crashes.
- Fix: In lines 117 and 141 return `sup.get("note") or ""` (always a str).

### F002 – [LOW] _has_text gives up after the first broken option run

- File: src/exam_engine/pipeline/report_kinds.py
- Lines: 200-208
- Issue: The loop `break`s at the first non-option line after any run, even a run of one letter, so a later real option list is never scanned.
- Case: The stem has a line starting with `A. ` (for example `A. Fleming found ...`) followed by normal text, then options `A.`..`D.`. `run` stays `["A"]`, the function returns False and `with_text` undercounts.
- Fix: On a non-option line, when `len(run) < 2` reset `run = []` and `first = None` and continue; `break` only when `len(run) >= 2`.

### F003 – [LOW] expected() raises or duplicates names for subjects whose slug is empty or "all"

- File: src/exam_engine/pipeline/report_kinds.py
- Lines: 155-156, 160
- Issue: `slug(s)` may return `""` or `"all"`; `name()` then raises ValueError (bad part, or scope `subject` with subject `all`), and for scope `both` the `all` name is listed twice.
- Case: `expected("x", ["数学"], "run-1")` raises ValueError; `expected("x", ["All"], "run-1")` raises for the scope `subject` kinds.
- Fix: Before the kind loop, compute the subject slugs once and raise one clear ValueError naming the subject when a slug is `""` or `"all"` or repeats.

### F004 – [MEDIUM] Re-run drops marks of sections with no number or a duplicate number

- File: src/exam_engine/pipeline/review.py
- Lines: 323-324, 337, 376
- Issue: `olds` is keyed by `n`; rows with `n is None` are skipped and a repeated `n` keeps only the last row. `lost` never sees them, so the subject file is overwritten and their marks vanish.
- Case: The user damages a heading to `## Question 5 ...` (LOOSE_RE fails, n None) or renumbers Q12 to Q13, both marked; `review-pack` runs again.
- Fix: Count marked rows (`_is_marked`) with `n is None` or a repeated `n`; when any exist, take the `lost` branch (write `<subject>.new.md`, keep the old file) and name them in the message.

### F005 – [MEDIUM] The `.old.md` backup is read as a subject

- File: src/exam_engine/pipeline/review.py
- Lines: 301-303, 331
- Issue: `pack` saves legacy marks to `<subject>.old.md`, but `_subject_files` excludes only `.new.md`, so `write_index` and `apply` treat the backup as a subject `<subject>.old`.
- Case: A file with previous-format ticks is re-packed. INDEX.md and `review-apply` then report every question twice, and improvements.md lists the backup's lines as `unparsed (fix the line)`.
- Fix: In `_subject_files` also skip names ending with `.old.md`.

### F006 – [MEDIUM] review-apply crashes on a defect ticked in an unnumbered section

- File: src/exam_engine/pipeline/review.py
- Lines: 453-460
- Issue: `"Q%d" % r["n"]` runs for every `defect` row, also when `r["n"]` is None (unnumbered `## ` heading); `%d` with None raises TypeError. The same row puts `Q None` tags in the other lists.
- Case: A heading is edited to `## Question 7 ...` and its review line has `[x] defect`; `apply` raises TypeError and writes no improvements.md.
- Fix: When `r["n"] is None`, append to `secbad` and `unp` (tag `"<sub> Q?"`) and `continue` before the defect and solution lists.

### F007 – [LOW] False "Answer changed" line after an edited heading

- File: src/exam_engine/pipeline/review.py
- Lines: 240-244, 357-361
- Issue: For a heading that fails HEAD_RE the old row keeps `answer` `"-"`. `pack` compares it with the new answer and writes `Answer changed: was - now A`, counting it in `changed`, though the answer is the same.
- Case: A marked section's heading is edited (number kept, for example a double space removed), then `review-pack` is re-run.
- Fix: In line 359 require `not o["bad"]` before reporting a change; for a bad row keep `o["changed"]` if present.

### F008 – [LOW] _guard does not neutralise `QA: ` and `Answer changed:` lines of the exam text

- File: src/exam_engine/pipeline/review.py
- Lines: 87, 247-256
- Issue: `parse_subject` reads `QA: ` and `Answer changed:` lines anywhere in a section, but `_guard` escapes only `#`, `Your review:`, `Engine:`, `Flags:`.
- Case: A stem line `QA: B conf high | differs | x` in a question with real line `QA: -`: `qa` and `verdict` stay `B`/`differs`, INDEX.md shows a QA table and wrong verdict counts. A stem line `Answer changed: ...` sets the `answer_changed` flag.
- Fix: Add `"QA:"` and `"Answer changed:"` to the prefix tuple in line 87.

### F009 – [LOW] Reserved subject names overwrite or hide review files

- File: src/exam_engine/pipeline/review.py
- Lines: 34, 302-303, 313, 318
- Issue: `_check_name` accepts `INDEX`, `improvements` and names ending in `.new` or `.old`. Their files collide with generated files or are skipped by `_subject_files`.
- Case: `pack(..., subject="improvements")` writes improvements.md, which `apply` later overwrites (marks lost); subject `INDEX` is overwritten by `write_index` in the same call while the message says `wrote`.
- Fix: In `pack`, after `_check_name`, raise ValueError when `subject + ".md"` is in SUBJECT_SKIP or subject ends with `.new` or `.old`.

## Summary

- Total findings: 9
- Critical: 0
- High: 0
- Medium: 4
- Low: 5
