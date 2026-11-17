# Phase 139 – Engine image/adjudicate/retry fixes from review batch 4 (TASK-139, REQ-0146)

Source: triage `docs/design/phase-137-review-triage-b4.md`, rows in `work/TASK-137/handoff/design-a.md`.

## Plan modes
Solve path: retry round (all plans) and the `--pdf` image check / `--adjudicate` path. Fewer paid calls (no QA of an
unchanged retry answer, no adjudication of a value that equals the letter); no prompt or cache-key change.

## Design
- 139.1 136-F003: move solver.py:174-180 (option value -> letter, records `answer_mapped`) into one helper
  `solver.map_option(q, a, findings)`; solve_round keeps its behaviour through it; `apply_image` calls it before the
  compare (engine.py ~214) and `adjudicate` before `same_answer` (~272).
- 139.2 136-F002: in `adjudicate`, after mapping, when not `keep_fail`: `review = None`,
  `code_checks = verifier.det_checks(q, g, exam)`, `checks = list(code_checks)` (same reset as `apply_image`).
- 139.3 136-F001: in the retry loop keep `prev = {i: recs[i]["ans"] for i in ids}` before `solve_round`; pass
  `qa_round` only ids whose `ans` object changed (`is not prev[i]`).
- 139.4 136-F005: in `image_check`, for marker-skipped ids pass the marker reason first in the flags given to
  `apply_image` (`[skip[i]] + flags`), so the reason keeps `missing_text (options cut)`; no string surgery.

## Verification ($0)
`tests/unit/test_engine_fixes_139.py` (pattern: test_engine_fixes_2025.py fakes), one test per id failing on old
code: adjudicated C with old `disagree` review + key C is not FAIL reviewer_disagrees; image `12` with option B=12
agrees with text B; failed retry gets no second QA prompt; skipped id + image miss keeps the marker reason.
Existing engine/solver tests green (adjust only mock queues that relied on the extra QA call, named in the handoff);
`--fast` NEW 0; 4 ledger rows fixed.
