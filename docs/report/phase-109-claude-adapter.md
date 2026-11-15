# Phase 109 – Fix-B Claude adapter report (TASK-109, REQ-0116)

**Verdict: adopted.** Review-triage bugs 110-F001 and 110-F002 fixed in `src/exam_engine/adapters/claude.py`.

## Results
- 109.1 `_classify`: HTTP codes count only after `API Error:`/status/HTTP or at line start; service/login/connection
  phrases narrowed. "Prompt is too long: …" is now `other` (one question fails, the run continues) instead of a
  run-stopping `service`; a `401` inside reply JSON is no longer `auth`.
- 109.2 `extract_json`: unfenced fallback returns the single parseable object when the braces before it balance,
  so `\frac{1}{2}` in prose no longer loses the answer. Fenced-first, two-object rejection, retraction unchanged.
- Tests: 12 in tests/unit/test_claude_fixes_109.py (5 bite on old code); --fast 1998 ran, NEW 0 (KNOWN 4).
- Oracle (observed by the coordinator): old vs new on 252 stored real replies = 0 changed; 8 real stop messages
  (5-hour limit, 529, 401, invalid key, 500, connection, timeout, credit) keep their class.

## Spend
designer + coder + tester; no paid run. No cache-key change (only ok raw replies are cached).

## Needs your go
Fix-C (review pack: 111-F004/F006/F007/F005) is next in the approved plan.
