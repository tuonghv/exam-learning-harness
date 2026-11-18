<!-- fable-status -->
> **Status (2026-11-18):** 9 finding(s): 8 fixed (TASK-120, TASK-125); 1 false positive(s), marked and skipped: F005 (triage TASK-117: a missing tracked prompt fails loud before any call). Nothing open.
>
> **Action rule (RAW-00368):** check every finding against the code. A true positive is FIXED through a task; a warning or a note alone does not close it. A false positive is recorded with its reason in `docs/review/findings.tsv` and ignored. Update the Status line at each task transition.
<!-- /fable-status -->

# Phase 118 – Ingest boundary.py (batch 3)

## Findings

### F001 – [MEDIUM] Suspects past the 40-line cut of a merged span are dropped silently

- File: src/exam_engine/ingest/boundary.py
- Lines: 163-165, 170-171, 175-178
- Issue: Merged spans are cut to `max_lines`; suspects beyond `end` are filtered out of `mine` and never get a window. `skipped` counts only whole windows over `max_windows`.
- Case: Suspects at lines 10, 22, 34, 46, 58 merge into one span 2-66; `end` = 41; lines 46 and 58 are never sent, `skipped` = 0, no `boundary_ai_skipped` warning.
- Fix: When a span exceeds `max_lines`, start a new span at the first suspect with `line > end` (`lo = line - span`) and repeat, instead of dropping them.

### F002 – [MEDIUM] A reply that omits a requested suspect line is accepted and cached

- File: src/exam_engine/ingest/boundary.py
- Lines: 216-231, 366-372
- Issue: `_items` never checks that every line of `w["suspects"]` is answered; the partial reply is valid and `cache.put` stores it.
- Case: Window `classify 12, 30`; reply holds only line 12 (or `"items": []`): no warning, line 30 gets no hint, and with `--cache DIR` it is never asked again on later runs.
- Fix: In `_calls`, when `set(w["suspects"]) - set(ln for ln, _l, _c in items)` is non-empty, treat the window as invalid (reason `missing`): warn, count `invalid`, skip `cache.put`.

### F003 – [MEDIUM] A cached entry read from disk is used without validation

- File: src/exam_engine/ingest/boundary.py
- Lines: 320-325
- Issue: `got` is unpacked as `[offset, label, conf]` triples directly; `ReplyCache.get` only guarantees valid JSON. Offset, label and confidence are not re-checked.
- Case: Cache file holding `[1]` raises `TypeError` (not caught by cli: traceback); `{"a": 1}` raises `ValueError` (ingest exit 2); `[[3, "question_start", "0.9"]]` raises `TypeError` at `conf < min_conf`.
- Fix: Rebuild `{"items": [{"line": w["start"] + r, "label": lab, "confidence": c}]}` inside `try/except (TypeError, ValueError)` and pass it to `_items`; on any failure append `w` to `todo` (a miss).

### F004 – [LOW] Duplicate `window_id` entries: the last one silently wins

- File: src/exam_engine/ingest/boundary.py
- Lines: 257-259
- Issue: `entries[e["window_id"]] = e` overwrites an earlier entry, while a duplicate line inside one entry rejects the window (`duplicate`, line 227).
- Case: Reply has `{"window_id": "w1", "items": [valid]}` followed by `{"window_id": "w1", "items": []}`: the empty entry is accepted and cached, the valid hints are lost.
- Fix: Collect ids seen twice in a set; in the `for w in wins` loop return `(None, "duplicate")` for such a window.

### F005 – [LOW] A missing prompt file aborts the whole ingest

- File: src/exam_engine/ingest/boundary.py
- Lines: 30, 317, 427
- Issue: `prompt_sha256()` reads the template unguarded; its `OSError` propagates through `segment_reviewed`, unlike call, JSON and budget failures, which keep the rule result.
- Case: `dev/ingest/boundary.md` missing or unreadable and one suspect window exists (also under `--dry-run`): ingest exits 2 instead of returning the rule segmentation.
- Fix: Catch `OSError` around line 317; append a `boundary_ai_invalid` warning (reason `prompt`) and `return {}`.

### F006 – [LOW] Dry-run estimate double counts windows under `--pages`

- File: src/exam_engine/ingest/boundary.py
- Lines: 331-333
- Issue: The reviewer runs twice with `--pages` (full document, then `parts.select_pages`). A dry run fills no cache, so the second pass estimates the same windows again.
- Case: `--pages 3-4 --dry-run`: full document 5 windows (2 batches), selection 2 identical windows: `est_calls` = 3; a real run makes 2 calls (the selection hits the cache).
- Fix: Keep a set of `self._key(w, sha)` already estimated; in dry run drop those from `todo` before batching and add the rest.

### F007 – [LOW] Summary warning mixes per-call windows with cumulative counters

- File: src/exam_engine/ingest/boundary.py
- Lines: 338-340
- Issue: `len(wins)` is for this call; `st["calls"]`, `st["cached"]` and `self.spent` are totals of all calls of the reviewer.
- Case: `--pages`: first pass 5 windows, 2 calls; second pass 2 windows, both cached. The warning kept in the selected document reads `2 window(s), 2 call(s), 2 cached, cost $0.0060`, though this pass made 0 calls at $0.
- Fix: Snapshot `st["calls"]`, `st["cached"]` and `self.spent` at the top of `__call__` and report the differences.

### F008 – [LOW] Trace repeats the full call cost on every window row

- File: src/exam_engine/ingest/boundary.py
- Lines: 359-362
- Issue: Each window row of a batch gets `"cost_usd": call.cost_usd`, the cost of the whole call.
- Case: One call for 4 windows costing $0.004 writes four rows of 0.004: the `--boundary-trace` file sums to $0.016 while `spent` and the cli line report $0.004.
- Fix: Write `call.cost_usd` on the first row of the batch and `0.0` on the others.

### F009 – [LOW] A NaN cost cap never stops calls

- File: src/exam_engine/ingest/boundary.py
- Lines: 346
- Issue: The cap test is `self.spent + EST_CALL_USD > self.max_cost`; every comparison with NaN is false. The cli check `args.max_cost_usd < 0` also lets NaN through.
- Case: `--boundary-ai haiku --real --max-cost-usd nan`: all batches are sent, no `boundary_ai_budget` warning.
- Fix: Invert the test to `if not (self.spent + EST_CALL_USD <= self.max_cost):`.

## Summary

- Total findings: 9
- Critical: 0
- High: 0
- Medium: 3
- Low: 6
