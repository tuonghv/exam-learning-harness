# Report phase 56: solve-run metrics, history and compare (TASK-056; REQ-0060)

Verdict: adopted. Every real solve now prints a 3-line metrics block (answered / declined / malformed / retry; accuracy; cost) and `report.md` gets a `## Metrics` section. Each real run (or any run with `--history`) appends one line to `reports/run-history.jsonl` (git-ignored; holds answer letters): run id, time, exam sha256, git commit/dirty, prompt version, model, config, metrics. Mock runs are not appended. `exam.py run-stats` has `stats RESULT_DIR`, `compare A B`, `trend`, `backfill DIR...`.

## How to read the numbers
- Accuracy only with an answer key (`key k/K`). Agreement with the QA line is printed as a proxy (same model family, not accuracy). Pass rate is NOT progress on DGNL: every question ends UNCERTAIN with `no_independent_check`.
- Health (answered, declined, malformed, retry, QA flips) and cost (calls, $, LLM seconds) are tracked separately; missing sources are null, never 0.
- `compare` refuses two different exams (exit 2), lists fixed / regressed / changed questions, and calls a change signal only when `|fixed-regressed| >= 2*sqrt(fixed+regressed)` and `fixed+regressed >= 4`; otherwise `within noise`. Exit 1 = regression signal.
- Workflow after any change: `exam.py solve ... --real`, then `exam.py run-stats compare <before> <after>`; `trend --exam ID` for the series.

## Evidence (docs/report/evidence/TASK-056/)
Independent jq/awk recount of 3 real DGNL runs equals `run-stats` on all fields (only English cost 0.3417 vs 0.3418, log rounding); compare, noise and exit-code checks; mutations (wrong denominator, QA shown as accuracy, noise rule off, mock appended) killed; suite failures identical to baseline 083d0e4 (baseline-failures.txt vs suite-final.txt).

## Limits
Tokens are not recorded anywhere (cost in $ and bytes only). Backfilled runs have no commit or timestamp beyond file mtime, so `trend` treats them as repeats. An answer that flips inside a retry cannot be recovered from result.json. No paid run of the new path; verified on fixtures and real result.json only. Two low defects (cli.py:679, engine.py:115) noted in the design.

User instructions honoured: RAW-00170, RAW-00171.
Evidence files for crosscheck: docs/report/evidence/TASK-056/ (index: docs/report/INDEX.md).
