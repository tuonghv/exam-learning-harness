# Phase 136 – Review prompt v2 + code-review batch 4 (TASK-136, REQ-0143)

Source: RAW-00356 critique (lessons of the 80 batch 1-3 findings), approved in RAW-00357.

## Plan modes
Docs/prompt only plus 4 read-only reviewer runs; no `src/` change, no paid exam run. Findings are triaged and
fixed in later tasks (as TASK-107/113/117).

## Design
- 136.1 Rewrite `docs/prompts/cost-efficient_code_review_instructions.md` (v2, ~150 lines), fixes 1-9:
  1 `Reached via:` entry point, drop findings validated upstream; 2 grep callers/tests, `Fix risk:` line;
  3 `Type: BUG | HARDENING` + `Trigger:` normal input / malformed file / off-prompt LLM reply;
  4 scope <= ~800 lines, Summary `Not reviewed:` + `Cap hit:`; 5 duplicate check against
  `docs/review/findings.tsv` (no re-report of `not-a-defect` without new evidence); 6 optional `Test:` line;
  7 project checklist (untrusted exam text, no paid call before validation, stdlib only, Bash 3.2);
  8 heading `### Fnnn – [SEV]` is machine-parsed by `tools/review_ledger.py`, phase ID from the brief;
  9 sections 9/11/12 merged into one checklist, repo-relevant examples.
- 136.2 `.claude/agents/code-reviewer.md` reply line: add the `Cap hit` flag (counts by Type). Agent still reads the prompt.
- 136.3 Batch 4, one code-reviewer (Fable) run per scope, phase IDs reserved here:
  | Phase | Slug | Scope | Lines |
  |---|---|---|---|
  | 136 | engine-decision-b4 | src/exam_engine/engine.py, core/decision.py | 649 |
  | 137 | scorer-verifier-b4 | pipeline/scorer.py, pipeline/verifier.py | 565 |
  | 138 | pdf-adapter-b4 | ingest/adapters/pdf.py | 744 |
  | 139 | runlayout-b4 | pipeline/runlayout.py | 736 |
- 136.4 Ledger: one `open` row per batch-4 id on a triage task (queued TASK-137), `review_ledger.py` 0 problems.

## Verification ($0)
Prompt: `review_ledger.py` regex still matches the v2 sample heading; line count < 270. Reports: each has the v2
fields (grep `Reached via`, `Fix risk`, `Type:`, `Not reviewed`, `Cap hit`); ledger 0 problems.
