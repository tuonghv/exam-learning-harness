# Report phase 49: quote check tolerant of missing diacritics and elisions (TASK-049; REQ-0047)

Verdict: adopted. `verifier._quotes` keeps the exact match unchanged and, only when it fails, accepts a quote whose folded form (diacritics removed, case and spacing normalised) is in the source, including quotes abbreviated with an elision marker (`(...)`, `[...]`, `...`, `…`): segments shorter than 4 folded characters are dropped, at least one segment of 8 or more must remain, and the segments must occur in order. Fabricated quotes, quotes from another question, out-of-order segments and all-short quotes still fail. Detail text says `verbatim (diacritics-insensitive)` or `(elided, diacritics-insensitive)`.

## Why two steps
The first version (diacritics only) did not fix the real case: the stored quotes of printed 22 and 24 also carry an elision marker. The coder's real regression exposed this; the design was amended (phase-49 Amendment) and re-run. Synthetic tests alone would have passed.

## Evidence (work/TASK-049/evidence)
`final_unit_suite.txt` 672 tests, only the 3 known failures (identical at base); `final_quote_tests.txt` 12 tests OK, 6 of the first 11 fail on the base code; `t049-oracle.txt` independent 300-case oracle 0 mismatches; `t049-perf.txt` linear (worst 0.7 s on 1 MB); `real_regression_run_21_25.txt`: printed 22 and 24 fail -> pass, 21, 23, 25 unchanged; 0 old assertions removed; no schema, solver or ingest change. The tester found two mutations that survived the coder's tests (drop the 8-char rule, allow overlapping segments) and added a test that kills both.

## Limits
The folded route can accept a quote that differs from the source only by a diacritic (a different word); this check does not judge answer correctness. The stored evidence in result.json is cut to 80 characters, so the real regression ran on truncated quotes (a full-quote check would need the solver output to keep full evidence).

User instructions honoured: RAW-00144, RAW-00133 (quality), RAW-00142 (short roles).
