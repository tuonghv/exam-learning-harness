# Phase 136 – Review prompt v2 + code-review batch 4 report (TASK-136, REQ-0143)

**Verdict: done.** Prompt v2 is in use; batch 4 produced 28 findings, all `open` on triage task TASK-137.

## Results
- `docs/prompts/cost-efficient_code_review_instructions.md` v2: 270 -> 122 lines, fixes 1-9 (Reached via, Fix risk,
  Type BUG/HARDENING + Trigger, ~800-line scope with Not reviewed / Cap hit, duplicates via `docs/review/findings.tsv`,
  optional Test, project risk checklist, machine-parsed heading kept, one final checklist). Ledger regex still matches.
- code-reviewer reply now gives BUG/HARDENING counts and `CAP HIT`.
- Batch 4 (Fable, one run per scope), every finding in v2 format:
  | Phase | Scope | Findings |
  |---|---|---|
  | 136 | engine.py + core/decision.py | 5 (M4 L1) |
  | 137 | scorer.py + verifier.py | 10 (H1 M8 L1), cap hit |
  | 138 | ingest/adapters/pdf.py | 10 (M8 L2), cap hit |
  | 139 | runlayout.py | 3 (M1 L2) |
- Ledger: 108 ids, 28 open (TASK-137), 0 problems. No `src/` change.

## Issues
- The bind guard refused the first report Write of all 4 parallel reviewers ("several launches are waiting");
  2 reviewers still replied `REPORT:` as if saved. All 4 saved after the binds settled; reports were checked on disk.
  Lesson: launch parallel reviewers so each brief's Write can bind, and trust files, not replies.
- Two scopes hit the 10-finding cap; their `Not reviewed` lists name the leftovers for a later batch.

## Next
TASK-137: triage the 28 findings (repro or file:line, check each Fix and Fix risk), then fix tasks.

## Spend
$0 exam spend. 4 code-reviewer runs + 5 resumes.
