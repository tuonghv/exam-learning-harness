# Phase 21: benchmark (REQ-0009)

## Goal
One command measures the unchanged engine on `evals/inputs` (15 items) against `evals/keys`; no change is justified without a measured failing item.

## Design
- `exam.py benchmark [--inputs D] [--keys D] [--subject S] --out DIR (--dry-run | --mock FILE | --real) [--budget-usd 3.00] [--max-cost-usd 1.00 per item] [--previous summary.json] [--prompt-version V]`. Never defaults to real; prints items, `calls <=` bound and the budget before any call; `--dry-run` and `--mock` cost $0.
- `pipeline/benchmark.py`: `discover` pairs `input-N.md` with `expected-N.md`; `run_all` calls the existing `engine.run(item, out/<subject>/<N>, cfg+key, llm)` per item (solve, checks, QA, decide, then key-only SCORE; the key is opened only by `scorer.apply_key`) with one shared budget (items after it is spent are `skipped`, exit 3); `summarize` -> per-subject and total pass/fail/uncertain/unresolved; `report_md`; `regression(prev, cur)` flags subjects whose pass count fell.
- Per question the summary records answer, verdict, reason, attempts, points, QA finding codes and `basis`: `key match`, `code oracle` or `claude review only` (the last is never verified).
- Failures list answer, reason and findings. Engine, prompts, schemas and decision logic are not changed (REQ-0009 AC6: tests assert the key text is absent from every solver prompt).
- Exit: 0 all pass, 1 any fail/unresolved or regression, 2 usage, 3 budget stop.

## Tests ($0)
discover pairs only; pass and fail counted per subject; key text absent from prompts; budget stops remaining items; regression flagged; CLI modes (dry-run, no-mode error, mock end to end).

## Limits
The real run (about 15 items x 2-5 calls, est. $2-3, cap $3.00) needs the user's go; few-shot items are not part of `evals/inputs` and never counted as accuracy.
