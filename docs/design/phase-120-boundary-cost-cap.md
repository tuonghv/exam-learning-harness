# Phase 120 – Fix-J boundary accounting and NaN cost caps (TASK-120, REQ-0127)

Source: docs/design/phase-117-review-triage-b3.md rows 118-F001/F007/F009, D1; draft work/TASK-120/handoff/design.md (D2 adopted as 120.3b); repros work/TASK-117/repro_boundary.py.

## Premise
- Boundary AI is opt-in: `--boundary-ai haiku` + exactly one of --mock/--dry-run/--real (cli.py:1029). Paid volume per pass is
  bounded by max_windows 12 / MAX_BATCH 4 = 3 calls (boundary.py:144); --pages runs 2 passes. No wrong content from any of these bugs.
- Current $0 repro output (repro_boundary.out): F001 `[(2, 41, [10, 22, 34])] 0`; F007 `... 1 call(s), 1 cached, cost $0.0030`;
  F009 nan → 1 call, no `boundary_ai_budget`.
## Plan modes
- ingest without --boundary-ai: not affected (Reviewer not built; NaN check is in the same `if` at cli.py:1029, so `--max-cost-usd nan`
  without --boundary-ai also becomes exit 2; today it is accepted and unused. Harmless.)
- ingest --boundary-ai --mock / --dry-run / --real: 120.1 + 120.2 + 120.3 apply; dry-run never calls `ask` (boundary.py:332).
- solve single-source and solve pipeline: both go through `solve_main` (cli.py:37) → the one check at cli.py:110; 120.3 only.
- refine, cross, benchmark, genexam: same `< 0` check (cli.py:1222, 1332, 1437, 1538); not changed (see Open question).
## Design
### 120.1 F001 no lost suspects (owner: boundary.py `windows`, :163)
- Change: merge condition `if spans and lo <= spans[-1]["end"] + 1 and hi - spans[-1]["start"] + 1 <= max_lines:`; else open a new
  span at `lo` (may overlap the previous window's lines; each suspect is in exactly one window's `suspects`). Keep the cut at :170 and
  the `mine` filter at :171 unchanged (now a no-op for defaults: one span = 2*8+1 = 17 <= 40).
- Excess windows go through the existing max_windows path (:176-178) → `skipped` + `boundary_ai_skipped` warning (AC1 "counted").
- Minimal: one condition; no new parameter, no split loop, no new counter.
- Test (test_boundary.py): `windows(["x"]*80, QE at 10,22,34,46,58)` → `[(2,30,[10,22]), (26,54,[34,46]), (50,66,[58])], 0`.
  Old: `[(2,41,[10,22,34])], 0` → fails. Second test: 13+ far-apart chained spans with max_windows=2 → every suspect is either in a
  window or its window is counted in `skipped` (sum check: suspects in windows + suspects of dropped windows = sent).
- Risk: overlapping windows send some lines twice (context only, small cost). `_items` must accept only the window's own suspects
  (check in impl; else a reply label for an overlap line from the other window could override). More windows → may hit max_windows
  sooner (visible warning, not silent).
### 120.2 F007 per-pass summary (owner: boundary.py `Reviewer.__call__`, :303-340)
- Change: after `self.warnings = []` (:304) snapshot `c0, k0, s0 = st["calls"], st["cached"], self.spent`; message at :339-340
  uses `st["calls"] - c0, st["cached"] - k0, self.spent - s0`. `self.stats` stay cumulative (cli.py:1110-1116 total line unchanged).
- Minimal: 1 snapshot line + 1 format line; no stats schema change.
- Test: repro F007 (fake ask, same lines twice) → 2nd summary `1 window(s), 0 call(s), 1 cached, cost $0.0000`; old says
  `1 call(s) ... $0.0030` → fails. 1st pass message unchanged (`1 window(s), 1 call(s), 0 cached, cost $0.0030`).
- Risk: none for consumers (grep: only boundary.py:338 emits it; no test or doc parses the text).
### 120.3 F009 + D1 NaN cost cap (owners: cli.py:1029 ingest, cli.py:110 solve, boundary.py `_calls` :346)
- cli.py:1029: `... or modes > 1 or not (args.max_cost_usd >= 0):` (message unchanged, exit 2).
- cli.py:110: `if a.max_attempts < 1 or not (a.max_cost_usd >= 0) or a.timeout <= 0:` (message unchanged, exit 2).
- boundary.py:346: `if not (self.spent + EST_CALL_USD <= self.max_cost):` (identical for finite caps; stops on NaN; defence for
  library callers that build Reviewer directly).
- engine.py:84 not changed: CLI is the only solve entry that sets max_cost_usd from user input; engine.call_cap still bounds volume.
- Minimal: 3 expressions; reuse existing usage messages and exit codes.
- Tests: (a) `ingest_main([<tiny md>, "--boundary-ai","haiku","--dry-run","--max-cost-usd","nan"])` → 2, stderr has `--max-cost-usd >= 0`;
  old → 0. (b) `solve_main([<example exam>, "--dry-run", "--max-cost-usd", "nan"])` → 2, stderr `--max-cost-usd >= 0`; old → passes
  the check (not 2). (c) `Reviewer(ask, max_cost=float("nan"))(lines)` → 0 calls, `boundary_ai_budget` present; old → 1 call.
  (d) guard: `max_cost=0.0` still 0 calls; default cap still 1 call.
- Risk: `inf` still accepted (`inf >= 0`); bounded by call caps, same as today. Budget message prints `$nan` only on the library path.
### 120.3b D2: the same guard on every paid entry (coordinator, REQ-0127 AC3 widened)
- cli.py:1222 (refine), :1332 (cross), :1437 (benchmark: `max_cost_usd` and `budget_usd`), :1538 (genexam):
  `x < 0` -> `not (x >= 0)`; messages and exit 2 unchanged.
- Test: one parametrised test calls each of the six entries with `--max-cost-usd nan` (benchmark also `--budget-usd nan`)
  in a dry/mock mode and expects exit 2 before any work; old code: not 2.

## Cache keys (120.1)
- Key = sha256 of the window's raw lines + prompt sha + model (boundary.py:191-193, :300-301). Windows change only where a merged span
  would exceed 40 lines (the buggy case); all other windows are byte-identical → same key → old entries still hit.
- Changed windows miss once and are asked; old entries for the 40-line cut windows are simply never looked up. Not stale: an entry
  is keyed by its exact lines, so its answer stays valid for those lines. 120.2/120.3 change no key.
- Cost: only dense documents (>=5 suspects chained <=17 lines apart) gain windows; per pass still <= 12 windows / 3 calls and the cap,
  so worst case unchanged (~$0.01/pass est. EST_CALL_USD x 3).
## $0 oracle (no network)
1. Repro on new code: `python3 -I work/TASK-117/repro_boundary.py > work/TASK-120/repro_new.out` → expect
   `F001 [(2, 30, [10, 22]), (26, 54, [34, 46]), (50, 66, [58])] 0`; `F007 1 ['1 window(s), 0 call(s), 1 cached, cost $0.0000']`;
   `F009 0.0 0 [...budget, ...summary]`; `F009 nan 0 ['boundary_ai_budget', 'boundary_ai_summary']`. Uses only the fake `ask`.
   (Run from repo root; script does `sys.path.insert(0, "src")`, which `-I` allows since it is explicit.)
2. Dry-run estimate, old vs new: run BEFORE the edit (HEAD) and after, same command:
   `python3 -I scripts/exam.py ingest input/exam/math/math_12_graduation_2026_001.pdf --boundary-ai haiku --dry-run > work/TASK-120/dry_{old,new}.txt`
   then `grep boundary-ai: work/TASK-120/dry_*.txt` → compare windows / skipped / `est. N`. Expect equal unless the PDF has a
   chained dense span (then new windows >= old, est. <= 3/pass). No network: with --dry-run `ask` stays None (make_real_ask only
   under --real, cli.py:1061-1062; mock only under --mock) and `Reviewer.__call__` takes the `dry_run` branch (:332-333), never `_calls`;
   ReplyCache gets None (no --real) so no disk cache. Plus `python3 -I scripts/exam.py ingest <same> --boundary-ai haiku --dry-run
   --max-cost-usd nan; echo $?` → 2.
## Unit tests / gate
- Tests above in tests/unit/test_boundary.py (120.1, 120.2, 120.3c/d), test_boundary_qa.py or test_exam_run.py (120.3a/b).
- `python3 -I tools/run_tests.py --affected`, then `--fast` NEW 0 (AC4).
## Open question
- Q1: refine/cross/benchmark/genexam (cli.py:1222, 1332, 1437, 1538) have the same `< 0` NaN hole. Recommend: out of scope here
  (AC3 names ingest + solve), record as a follow-up row; it is a 4-line same-pattern change if main prefers to include it.
## Defects
- D2 (P3): cli.py:1222 refine, :1332 cross, :1437 benchmark (`budget_usd` too), :1538 genexam accept `--max-cost-usd nan`
  (`x < 0` False for NaN). Volume still bounded by each command's call bound. Evidence: grep `max_cost_usd < 0` in cli.py.
