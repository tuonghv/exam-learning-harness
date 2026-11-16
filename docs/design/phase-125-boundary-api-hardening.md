# Phase 125 – P3-c boundary + api hardening (TASK-125, REQ-0132)

Sources (traced, with fixes and $0 repros): work/TASK-117/handoff/design-boundary.md (118-F002, F003, F004, F006,
F008), work/TASK-117/handoff/design-api.md (117-F006, line 66 fix, line 107 test), work/TASK-113/handoff/design-ingest.md
row F005 (114-F005). Designer waived: rows already designed.

## Plan modes
Boundary AI is opt-in (paid, never default); api `_gate` runs for `--refined` exams; segment change only on the hinted
path. No prompt change. Cache: old partial/corrupt boundary disk entries become misses and are re-asked once (bounded
by max_windows and the cap).

## Design
- 125.1 118-F002 `boundary._items`: after the loop, `if set(w["suspects"]) - seen: return None, "missing"`; validate()
  and the cached path share it.
- 125.2 118-F003 cached path (boundary.py ~320-325): rebuild `{"items": got}` through `_items`; TypeError/ValueError or
  an invalid result = miss (honours replycache "corrupt = miss").
- 125.3 118-F004 duplicate `window_id` in one reply -> invalid (`duplicate`).
- 125.4 118-F006 dry run: keep a set of estimated window keys on the Reviewer; a key already estimated is not counted again.
- 125.5 118-F008 trace: each row gets `"call": <call index>`; `cost_usd` stays the call's cost (documented as per call),
  so a reader sums by call. Update docs/guide/ingest-usage.md:59 wording only if it says per window cost.
- 125.6 114-F005 segment (S:222-228, S:268-270): when a context is pending (`pending` non-empty / an `_INTRO` or
  `_READ` line seen), a hinted non-start line appends to `pending`, not to `options[-1]`.
- 125.7 117-F006 `_gate(qs, config, refined, active=None)`; `_pick_refined` passes `active = any("verification" in q
  for q in all refined questions)` so a slice without its own verification keys is still gated.

## Verification ($0)
tests/unit/test_boundary_api_hardening_125.py, one test per item from the repros, each failing on HEAD; `--fast` NEW 0;
segment oracle (work/TASK-114/evidence/oracle.py) old vs new on real inputs = 0 changes (hint path is not used there).
