# Phase 138 – Scorer fixes from review batch 4 (TASK-138, REQ-0145)

Source: triage `docs/design/phase-137-review-triage-b4.md`, rows in `work/TASK-137/handoff/design-a.md`.

## Plan modes
Scoring of every keyed run (`apply_key`, `exam.py score`, run-stats `key_letters`). No solve, prompt or cache change.
Scores change only for the answer shapes below.

## Design
- 138.1 137-F001: `_numparse` returns None when the tail starts `\s*/\s*\d`; in `match`, when either side is a
  fraction, compare `_exact_value` of both (relative 1e-9): `28/6` = `14/3`, bare `14` no longer matches.
  No decimal-for-fraction acceptance (`4.67` stays wrong; open user question).
- 138.2 137-F002: in `_unit_ok`/match, reject when the answer's tail holds a standalone digit and the key's does not
  (`8 hoặc 9`, `8; 9` vs `8` -> wrong; `62 host`, `1.8e-19 J`, `m/s2`, `m^2` unchanged).
- 138.3 137-F003: before `_NUMX`, drop thousands separators when the number has two or more `.ddd` (or `,ddd`) groups.
- 138.4 137-F004: the trailing `= value` search runs on `a.replace("−", "-")`.
- 138.5 137-F008: `key_letters` regex `\b` -> `(?![\w-])` (ordering key -> None; `B`, `B. 2`, `B)` -> B).
- 138.6 136-F004 + 137-F009: in `apply_key`, `open_key = final is None or norm(final) == "open (rubric)"`; skip
  scoring an `is_open` answer only when `open_key`; otherwise call `score()` (`Open` vs `B` -> 0 differs_from_key;
  gap-fill `open` vs key `open` -> 1).
- 138.7 137-F010: `score_file` parses with `legacy=True`; a question with `final is None` is `manual`.

## Verification ($0)
`tests/unit/test_scorer_fixes_138.py`, one test per id failing on old code (repro R1, R3, R4 values flip);
`test_scorer_sign.py`, `test_eval_stats.py:92-98`, `test_benchmark_fixes.py` stay green; `--fast` NEW 0; 8 ledger rows fixed.
