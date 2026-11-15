# Phase 109 – Metrics logic (src/exam_engine/pipeline/metrics.py)

## Findings

### F001 – [MEDIUM] attempt_rate duplicates score

- File: src/exam_engine/pipeline/metrics.py
- Lines: 280-281, 288
- Issue: `attempt_rate` is computed as `_rate(len(good), keyed_adj)`, the same expression as `score`, so it reports correct/keyed, not attempted/keyed.
- Case: 10 keyed, 8 answered, 5 correct: attempt_rate = 0.5 (equals score) instead of 0.8.
- Fix: Set `attempt_rate=_rate(len(ak), keyed_adj)` (`ak` = answered keyed rows); leave `score` unchanged.

### F002 – [MEDIUM] shared_ref penalises linked questions for an unextracted sibling

- File: src/exam_engine/pipeline/metrics.py
- Lines: 375-379
- Issue: `want` holds every gold id of the shared group, `got` only ids present in `qs`; a sibling missing from the parse makes `got != want` for all extracted siblings, double counting the extraction miss.
- Case: gold shared group {1,2,3}, exam lacks 3, 1 and 2 share the passage: both scored `unlinked`.
- Fix: Build `want` only from gold ids in `qs`: add `and x["id"] in qs` to the line-375 comprehension.

### F003 – [LOW] classify basis becomes "key" when flips come from QA

- File: src/exam_engine/pipeline/metrics.py
- Lines: 600-605, 685
- Issue: `out["basis"]` is set to "key" by any single keyed question, while fixed/regressed of unkeyed questions are decided by the QA letter; `verdict` then prints `better` instead of `better (proxy)`.
- Case: key covers 1 of 40 questions, QA covers the rest, 8 QA-based fixed, 0 regressed: verdict `better`, basis key.
- Fix: Track per-basis flip counts; report "key" only when the fixed/regressed ids were key-judged, else "QA" (or "mixed").

### F004 – [LOW] board_delta n counts run B questions, not compared pairs

- File: src/exam_engine/pipeline/metrics.py
- Lines: 592-594, 660, 687
- Issue: `classify` skips questions absent from B, and questions only in B are never visited, yet `n=mb["n"]` is reported as the sample size in `same (within noise n=...)`.
- Case: A has 40 questions, B has 50: verdict text says n=50 while 40 pairs were compared.
- Fix: Count matched pairs in `classify` (increment when `b is not None`), return it, and use it for `n` in `board_delta`.

### F005 – [LOW] causes_text crashes or miscounts on rows missing columns

- File: src/exam_engine/pipeline/metrics.py
- Lines: 887, 895-899, 901
- Issue: A short TSV row gives `r.get("primary")` None; `sorted(cnt.items())` then compares None with str and raises TypeError. Any row whose outcome is not `flagged_right` (including missing) is counted as wrong.
- Case: explain TSV with one row truncated before the `primary` column next to complete rows.
- Fix: Skip rows where `primary` or `outcome` is None/empty before counting.

### F006 – [LOW] backfill aborts midway on one unreadable result.json

- File: src/exam_engine/pipeline/metrics.py
- Lines: 480-482, 487
- Issue: `json.load` (ValueError) or a non-dict JSON (`compute` AttributeError) is not caught; the loop raises after earlier dirs were already appended, and `(added, skipped)` is never returned.
- Case: dirs = [ok1, truncated, ok2]: ok1 appended, exception, ok2 never backfilled.
- Fix: Wrap lines 480-482 in `try/except (OSError, ValueError)`, also skip when `res` is not a dict; count it as skipped and `continue`.

## Summary

- Total findings: 6
- Critical: 0
- High: 0
- Medium: 2
- Low: 4
