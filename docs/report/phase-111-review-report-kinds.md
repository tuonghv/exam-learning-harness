# Phase 111 – Review of pipeline/review.py and pipeline/report_kinds.py

Scope note: only `src/exam_engine/pipeline/report_kinds.py` was reviewed. The Read of
`src/exam_engine/pipeline/review.py` (498 lines) was blocked by the PreToolUse hook, which points to
`rtk bulk-read`; the reviewer has no shell tool, so that file is NOT reviewed and needs another batch.

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

## Summary

- Total findings: 3
- Critical: 0
- High: 0
- Medium: 1
- Low: 2
- Not reviewed: `src/exam_engine/pipeline/review.py` (read blocked by hook); another review batch is required for it.
