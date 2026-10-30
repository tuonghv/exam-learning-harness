# Phase 33: one-line UserPromptSubmit hook output (TASK-033; REQ-0006 AC4)
Problem: `.claude/req/hook_capture.py` printed 2-4 lines per prompt (saved-RAW notice + brief lines); REQ-0006 AC4 wants one line.
Design (smallest): collect the notice and the `req.brief_text()` lines into `parts` and print `" | ".join(parts)` once. Same information, same substrings (existing tests 1.1/1.2 unchanged); no change to `req.py`, settings, hooks wiring or guard.
Tests: `.claude/tests/req_kit_test.sh` section 9 (captured prompt = exactly one line, keeps notice + brief; bare slash command <= one line); mutation: the old hook fails 9.1 and 9.3.
Risk: a long single line (focus title + next + counts + gaps, about 300-500 B). Bytes are unchanged; the line count is what AC4 specifies.
Out of scope: AC6 (post-fix compaction count) needs a later session transcript; PreToolUse output already 0 B (inspector measurement 2026-10-31).
