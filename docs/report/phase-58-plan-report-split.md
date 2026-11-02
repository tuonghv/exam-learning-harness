# Report phase 58: plan/report split (TASK-058; REQ-0062)

Verdict: adopted. A solve now writes a PLAN run to `plans/<exam-id>/<plan-run-id>/` (git-ignored): config, input (exam text), every raw AI prompt and reply as it happens (`calls/`, secrets masked, sha256 of the unmasked reply kept), `plan.json` (commit, prompt version, model, config hash) and `result.json`. Reports are built from a plan run only, by `report_build.py`, into `reports/<exam-id>/<plan-run-id>/<report-id>/` (git-ignored): no AI call, no network, deterministic, many reports per plan run, many plan runs per exam. Changing the report engine means `exam.py report PLAN_RUN`, never a re-solve.

## Commands
- `exam.py solve EXAM` (no `--out`) -> plans/ + reports/; `--out` still honoured.
- `exam.py report PLAN_RUN [--view sheet|learn] [--no-pdf] [--report-id ID] [--out DIR]`; the old `report RESULT.json --out DIR` still works.
- `exam.py plan-import DIR [--exam EXAM.md] [--exam-id ID] [--ingest-cache DIR] [--trace FILE]...` wraps an old result dir (idempotent; raw solve replies are marked "not captured", old runs never stored them).
- `exam.py run-stats stats|compare|trend|backfill` accept plan runs; history lives with plans.

## Found and fixed on the way
D-4 a crash lost every paid reply (calls are now written per call); D-3 a rebuilt report lacked the exam-based metrics (solve and report now share one builder); D-2 same-second runs shared a dir; verifier D-V1 ids joined into paths unchecked (now validated; ids derived from file names are sanitized, diacritics folded); D-V2 import followed symlinks and an untrusted exam path (now skipped).

## Evidence (docs/report/evidence/TASK-058/)
suite-final.txt, head-failures.txt vs baseline-failures.txt (same 4 known failures as baseline 083d0e4), plan-import-real.txt (real run3-Math import then report, no AI), qa7-import-stats.txt (recount of imported numbers), test.md, verify.md.

## Limits
No paid run: the real-call capture path was verified with a mock LLM; it waits for the next approved paid run. Old runs have no raw solve replies. Refine traces and the ingest cache cannot be tied to an exam automatically (use `--trace` / `--ingest-cache`). The report engine may spawn a local PDF renderer; the no-AI guard tests run with PDF off.

User instructions honoured: RAW-00174, RAW-00175, RAW-00176.
Evidence files for crosscheck: docs/report/evidence/TASK-058/plan-import-real.txt, docs/report/evidence/TASK-058/verify.md (index: docs/report/INDEX.md).
