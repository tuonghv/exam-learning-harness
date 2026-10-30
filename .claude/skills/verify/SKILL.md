---
name: verify
description: Verify implemented work against acceptance criteria using real behaviour (for content tasks, the exam content oracle run), and prepare evidence for the verifier role.
---

# Verification

Unit tests prove isolated behaviour. Verification proves the real execution path. Before it: unit tests pass and the acceptance criteria are identified.

## What VERIFIED means
Run each row of the design doc's `Verification` table (`docs/design/phase-<N>-<slug>.md`) exactly as written.
- **Content tasks (EPIC-002):** the crosscheck exam oracle run is Tier 1 and is the evidence; Tiers 2-3 are N/A (no scratch kit, no `claude` call).
- **Workflow/kit changes:** run the gates on the real repo state, and replay real history in a clone (`git clone -q . <tmp>`; `git show <sha>:<path>`) to show a historic problem is now caught.
- Do not claim VERIFIED from code inspection or unit tests alone, and never mutate real state to verify.

## Save cost: the cheapest check that proves the item
Choose a tier per acceptance item and record it in `verification.evidence`.

| Tier | When | Evidence | Cost |
|---|---|---|---|
| 0 static | docs, comments, test-only or rename changes | static checks + the unit suite already run; `security.status=not_applicable` if no surface | none |
| 1 snippet | a small bug, one function, or a content oracle | a small real run with the exact output pasted (for content: the crosscheck oracle output) | seconds |
| 2 scratch kit | a cross-script flow or output change | one scratch kit running every Tier-2 row of the phase in a single script | minutes |
| 3 real call | only when no fake can stand in | one small throwaway run covering all pending Tier-3 items, after the user approves the spend | tokens |

Rules:
1. Batch, never one-by-one: one script runs all of a phase's Verification rows; build fixtures once.
2. No heavy run for a small item; Tier 1 proves a one-function fix.
3. Reuse evidence: a unit test that already runs the real script counts for its row (cite it). Run the full suite once per phase, in the background; filter while iterating.
4. Go up a tier only when the cheaper check could not see the failure; write down why.

## HEAD vs new, same inputs
For behaviour changes, build two scratch copies (`git archive HEAD | tar -x -C <old>` and the working tree), give both the same inputs, drive the real entry point, and compare the outputs side by side. Pin the base to a commit sha, not to HEAD, once the change is committed.

## Before calling the verifier role: save the evidence
The `verifier` has no Bash and judges only files in `work/<TASK>/evidence/`; a claim without a file is UNVERIFIED. Save each check with `.claude/scripts/save-evidence.sh <name> -- <cmd...>` (header with task, command, HEAD, time, rc; returns the command's rc; use `bash -c '...'` for pipes). One file per claim, and name each file in the verifier request:
- [ ] the unit suites the change touches: `unit-<suite> -- python3 -I -m unittest discover -s tests/unit`
- [ ] the real run for each acceptance item: `run-<item> -- ...`
- [ ] for a behaviour change, both sides with the same inputs: `before-<x>` and `after-<x>`

Evidence = action/command, input, expected result, actual result, pass/fail. Paste real output, never a paraphrase.
Record it in `task.json` `verification.evidence`, set `verification.status = passed`, then run `.claude/scripts/workflow-check.sh`; it rejects VERIFIED without both.

## On failure - fix, do not paper over
1. Set `verification.status = failed` and record the failing command and actual output (never discard it).
2. Move `state` back to `IMPLEMENTING`, append a phase-log entry (Action, Result, Decision, Next), and commit that revert before writing fix code.
3. Fix, re-run the unit tests to UNIT_TESTED, re-verify. After repeated failures, reconsider the design or the acceptance criteria instead of retrying blindly.
Run `workflow-check.sh` after each status change.

## Real exam PDF (ĐGNL or similar, multi-subject)
Do not read the PDF by hand or guess an extractor: follow `docs/guide/dgnl-real-exam.md` (vision `ingest-refine --all-pages` in batches, one exam file per section, solve per section, no question text in git). Without a key, status stays `uncertain`; verify math by hand computation and list the rest as unresolved.
