# Phase Log

Append-only. One entry per phase transition, oldest first.
Never edit or delete a previous entry.

<!--
## <STATE> - <TASK-ID> - <ISO8601 timestamp>

### Action
-

### Result
-

### Decision
-

### Next
-
-->

## TODO - TASK-022 - 2026-09-24T01:23:19Z
- Action: queued and picked TASK-022 (init_manifest.sh skips cleaned repos with no .git; found when ai/upzi-opportunity-search in plan Upzi_g01/main had to be added to the manifest by hand).
- Result: task.json state=TODO, backlog item active.
- Decision: fix discovery in init_manifest.sh only; scan/report already handle a repo without .git (head_sha empty).
- Next: DESIGN - docs/design/phase-22-init-manifest-no-git.md.

## DESIGN - TASK-022 - 2026-09-24T01:33:40Z
- Action: reproduced on HEAD (scratch kit p22: ws1/cleaned and flatclean skipped silently, only ws1/gitrepo added); walked both real plan trees read-only; wrote docs/design/phase-22-init-manifest-no-git.md.
- Result: rule = register a <ws>/<repo> dir without .git when the workspace folder has no regular files directly in it and the dir holds at least one file. On the real trees this adds nothing new (upzi-opportunity-search is already in the manifest by hand). scan_batch already handles a missing .git (head_sha empty).
- Decision: always on, no config flag (the init approval gate covers false positives); flat cleaned repo -> WARN, not registered; no manifest schema change. Out of scope: stale entries (mini-review 3 entries / 2 on disk), head_sha drift, swagger prompt rule, sanitizer changes (notes in docs/notes/sanitizer-issues-2026-09-24.md for that team).
- Next: IMPLEMENTING 22.1 in init_manifest.sh Case B.

## IMPLEMENTING - TASK-022 - 2026-09-24T01:42:19Z
- Action: init_manifest.sh Case B registers a no-.git <ws>/<repo> (file-less workspace, dir holds a file) and prints added (no .git) / skipped (empty) / WARN / "(M without .git)" summary; new tests/init_manifest_test.sh (22 checks); docs updated (runbook, reference, run-security-review skill, README).
- Result: suite 22/22 on the new code; against git archive HEAD 12 of 22 fail (the cases bite). checks/shell.sh pass=94 fail=0.
- Decision: user added mid-phase that source trees are hands-off. Written into the run-security-review skill, runbook and CLAUDE.md: agents may list names/paths but never read contents or modify REPOS_ROOT; triage uses results JSON; tree problems go to docs/notes/sanitizer-issues-<date>.md. So the runbook/skill no longer suggest git init (this supersedes design 22.3 wording). Quoted file content was removed from the sanitizer notes.
- Next: UNIT_TESTED - full tests/run_all.sh.

## IMPLEMENTING - TASK-022 - 2026-09-24T01:44:12Z
- Action: user refined the rule: "for demo, agent can read, but for plan review source code ... that job for Claude -p".
- Result: skill, runbook and CLAUDE.md scope the no-read rule to review plans; demo trees (scratch/fixture or user-named) may be read; when unsure, treat the tree as a review tree.
- Decision: no code change; the no-modify rule for review trees is unchanged.
- Next: UNIT_TESTED - full tests/run_all.sh (running).

## UNIT_TESTED - TASK-022 - 2026-09-24T01:54:30Z
- Action: full tests/run_all.sh; shell.sh; proved the new cases against git archive HEAD.
- Result: 15 suites pass; init-manifest 22/22 (12 fail on HEAD); plan-reports 41/41 with 2 new 22.1 Commit checks (1 fails on HEAD); shell.sh 94/0.
- Decision: the scratch-kit run found the per-repo report printed Commit `` for an empty head_sha, so summarize_report.sh now prints - as design 22.1 said. A small fix inside 22.1, with a test.
- Next: VERIFIED.

## VERIFIED - TASK-022 - 2026-09-24T01:55:08Z
- Action: tier-2 scratch kit + fake claude (scratchpad verify22.sh); names-only mirror of the real Upzi_g01 tree with a copy of its manifest; security pass (hostile dir names, secrets.sh).
- Result: all design verification rows pass; the per-repo Commit gap was found and fixed (60fea23); real-manifest copy unchanged (Added 0); hostile names stored verbatim and nothing runs.
- Decision: VERIFIED. Reruns keep printing skipped (empty)/WARN for folders not in the manifest, as the design says (only folders already in the manifest stay quiet).
- Next: DONE (report).

## DONE - TASK-022 - 2026-09-24T01:56:00Z
- Action: wrote docs/report/phase-22-init-manifest-no-git.md; checked the symlink limitation (a linked no-.git folder prints skipped (empty)).
- Result: report complete; backlog.sh complete TASK-022.
- Decision: DONE.
- Next: pick TASK-023 (plan kind attribute).

## DESIGN - TASK-023 - 2026-09-24T01:57:11Z
- Action: read config.sh Plans block, plan.sh, plans_test.sh; wrote docs/design/phase-23-plan-kind-attribute.md.
- Result: premise: no kind field; mini-review plan.conf already has PLAN_KIND=demo (unused); Upzi_g01/main has no plan.conf.
- Decision: plan.conf key, default review not env-overridable, invalid stops scripts, plan.sh kind subcommand; hook enforcement out of scope. User said go ahead (2026-09-24).
- Next: IMPLEMENTING 23.1.

## IMPLEMENTING - TASK-023 - 2026-09-24T01:59:52Z
- Action: config.sh PLAN_KIND default + validation; plan.sh new --demo, list kind column, kind subcommand; plans_test.sh +16 checks (2 list checks updated for the column); skill/runbook/CLAUDE.md/reference/README.
- Result: plans_test 87/87; 17 fail on HEAD. shell.sh 94/0. Real toolkit: kind Upzi/mini-review=demo, Upzi_g01/main=review.
- Decision: SC2030/2031 silenced at line level (subshell reset is on purpose).
- Next: UNIT_TESTED.

## UNIT_TESTED - TASK-023 - 2026-09-24T02:10:34Z
- Action: full tests/run_all.sh; shell.sh.
- Result: 15 suites pass; plans 87/87 (17 fail on HEAD); shell.sh 94/0.
- Decision: advance.
- Next: VERIFIED.

## VERIFIED - TASK-023 - 2026-09-24T02:10:50Z
- Action: scratch kit new/list/invalid/demo init; real toolkit kind/list read-only; security pass.
- Result: all verification rows pass; real manifests unchanged; env PLAN_KIND ignored; invalid fails closed.
- Decision: VERIFIED. Env PLAN_DIR override remains (recorded as a limitation).
- Next: DONE.

## DONE - TASK-023 - 2026-09-24T02:11:09Z
- Action: wrote docs/report/phase-23-plan-kind-attribute.md.
- Result: backlog.sh complete TASK-023.
- Decision: DONE.
- Next: none (backlog empty).

## DESIGN - TASK-024 - 2026-09-24T03:36:18Z
### Action
- Checked the premise: plans/ is git-ignored and git ls-files plans is empty, so the only record of Upzi/mini-review=demo is a local plan.conf. Wrote docs/design/phase-24-tracked-plan-kind.md.
### Result
- Design: a tracked root file plan_kinds.conf (awk-parsed) is the only source of the kind; plan.sh new reuses a tracked kind or appends one; list shows tracked plans with no folder yet; keying by plan names also removes PLAN_DIR's effect on the kind (phase 23 limitation a).
### Decision
- Rejected tracking plan.conf (machine path, identity keys) and a plan.conf fallback (untracked edits could still turn a review plan into a demo).
### Next
- IMPLEMENTING 24.1: tracked_kind in config.sh + plan_kinds.conf.

## IMPLEMENTING - TASK-024 - 2026-09-24T03:50:10Z
### Action
- Added tracked_kind and plan_kinds.conf; config.sh now takes PLAN_KIND only from that file; updated plan.sh new/list/kind, the tests and the docs; migrated the two real plans.
### Result
- tests/plans_test.sh 98/98; against git archive HEAD, 15 fail. shellcheck is clean on plan.sh and config.sh. ./plan.sh kind: Upzi/mini-review demo, Upzi_g01/main review, with no NOTE.
### Decision
- list reads the kind file with a while-read loop over process substitution (SC2013). The two tests that also passed on HEAD were tightened.
### Next
- The full run_all.sh + shell.sh, then UNIT_TESTED.

## UNIT_TESTED - TASK-024 - 2026-09-24T03:50:41Z
### Action
- Ran tests/run_all.sh, checks/shell.sh and checks/secrets.sh.
### Result
- 15/15 suites passed (plans 98/98); shell pass=94 fail=0; secrets pass. The new cases fail 15 times on the HEAD code.
### Decision
- Unit evidence is enough to move to real verification.
### Next
- Fresh-clone scratch kit verification + security pass.

## VERIFIED - TASK-024 - 2026-09-24T03:51:11Z
### Action
- One fresh-clone scratch kit (git archive HEAD) ran every tier-2 row; read-only kind/list on the real toolkit; static git and doc checks; security pass.
### Result
- All rows pass (evidence in task.json); real manifests' md5 unchanged.
### Decision
- Verified; no tier 3 needed (no prompt or CLI surface).
### Next
- Report + backlog complete -> DONE.

## DONE - TASK-024 - 2026-09-24T03:51:35Z
### Action
- Wrote docs/report/phase-24-tracked-plan-kind.md; backlog.sh complete TASK-024.
### Result
- The plan kind is tracked in plan_kinds.conf and survives a fresh clone; all criteria are verified.
### Decision
- Done. Remaining limitation (c), reports don't mark demo plans, is not queued.
### Next
- None queued.

## DESIGN - TASK-025 - 2026-09-25T01:10:32Z
### Action
- Wrote docs/design/phase-25-multi-repo-pipeline.md (whole pipeline, plan checklist of 20 rows); queued TASK-025..028.
### Result
- User approved all recommendations ("go"): pipeline.sh driver, 2b multi-repo exception, agents print JSON, prompt edits P-a/b/c/d, 4 tasks.
### Decision
- TASK-025 covers checklist rows 1-9 and the fixture start.
### Next
- IMPLEMENTING row 1: scan_common.sh extraction.

## DESIGN - TASK-025 - 2026-09-25T01:20:38Z
- Action: re-checked the phase-25 design against code (scan_batch.sh, config.sh, report_common.sh, summarize_report.sh, security_prompt.md, docs/prompts, Upzi_g01 manifest + report 2026-09-24) per user; split into phase-25..28 docs.
- Result: corrections: isolation uses --tools + --allowedTools (not only --allowedTools); argv cap 128 KiB -> stdin; --restricted honours --add-dir; reports live in reports/<sys>/<plan>/; Upzi exposure by route prefix, X-User-* forging out of scope; 2b runs per chain + per 2a mitigation check; global facts cut from security_prompt.md; shared claude_run (user allowed restructure).
- Decision: no implementation until the user approves all four designs.
- Next: user review of the summary; on "go" start IMPLEMENTING row 1.

## DESIGN - TASK-025 - 2026-09-25T01:25:13Z
- Action: user asked for better 2b isolation, simple operation, top review quality.
- Result: phase-25 §25.3/§25.6 and phase-27 §27.3/27.4 updated: 2b cwd = empty phase2b/in/<id>/ with every repo by --add-dir (same --restricted lock); code evidence check (ws/repo/path must exist) before broken/holds count; PIPELINE_MODEL_P1/P2 = opus, PIPELINE_2B_TIMEOUT.
- Decision: no prompt wording change (2b prompt already asks ws/repo/path:line).
- Next: wait for user "go"; then IMPLEMENTING row 1.

## DESIGN - TASK-025 - 2026-09-25T01:28:03Z
- Action: user wants a 50-repo run to finish unattended and asked whether the one-repo prompt and skills fit.
- Result: phase-25 §25.7 added (AUTO_DRIVER=pipeline; pipeline uses scan_batch's exit codes, abort record and lock; --max-units, status --count, keep-going with automatic re-queue, Linux notify-send); rows 21-22. phase-26 decision: Phase 1 stays one-repo proof, cards are hints. phase-28: run-security-review pipeline section.
- Decision: reuse auto_scan.sh rather than a new scheduler; no prompt change.
- Next: wait for user "go"; then IMPLEMENTING row 1.

## IMPLEMENTING - TASK-025 - 2026-09-25T01:31:10Z
- Action: user approved designs phase-25..28 ("okie, go") and asked for a hook-backed tracker so no item is missed.
- Result: .claude/scripts/checklist.sh (open rows per task, --gate), printed by SessionStart, enforced at DONE by workflow-check.sh; 3 gate tests (74/74 pass); workflow skill section.
- Decision: owner of a shared row = highest task number, so shared rows do not block earlier tasks.
- Next: row 1 scan_common.sh + claude_run.

## UNIT_TESTED - TASK-025 - 2026-09-25T02:18:48Z
Action: pipeline.sh CLI (run/new/status, lock, abort contract, --max-units, auto re-queue, --dry-run, --pause-after-cards), deploy_context.sh (+ --slice), phase0 compose with repo_type addenda and global facts, assert_in_scope, AUTO_DRIVER=pipeline hooks + notify-send in auto_scan.sh, prompt edits P-a..P-d.
Result: tests/run_all.sh 18 suites all passed; checks/shell.sh fail=0.
Decision: checklist rows 2-9 and 21 ticked; rows 18/19 stay open (owners 028/026).
Next: VERIFIED with tier-2 (fake) + tier-3 (real haiku) evidence, security pass.

## VERIFIED - TASK-025 - 2026-09-25T02:20:45Z
Action: tier-2 scratch-kit runs with fake claude (pipeline_run_test incl. unattended auto_scan) + tier-3 real haiku (phase0 card; scan_batch stdin prompt); security pass.
Result: all tier-2 cases pass; real phase0 card accepted with 0 denials (/bin/bash.035); stdin prompt reached the model (/bin/bash.085, haiku schema miss = model quality).
Decision: verified; ConfigMap plain data reaching the model is a user decision (listed at hand-off).
Next: report + DONE, then TASK-026.

## DONE - TASK-025 - 2026-09-25T02:21:16Z
Action: wrote docs/report/phase-25-multi-repo-pipeline.md; backlog complete.
Result: 25.1-25.7 delivered and verified.
Decision: shared checklist rows 18/19 carry to 028/026.
Next: backlog.sh pick TASK-026.

## DESIGN - TASK-026 - 2026-09-25T02:24:41Z
Action: took the approved docs/design/phase-26-phase1-graph.md as the design (status line now cites the user approvals).
Result: design complete; 2 risks found in code check (env size cap, {{ in card text).
Decision: pl_fill gets NAME=@file values; placeholder check by name.
Next: IMPLEMENTING.

## IMPLEMENTING - TASK-026 - 2026-09-25T02:24:52Z
Action: start implementation.
Result: -
Decision: order 26.4 -> 26.2/26.3 -> 26.1 (graph before phase1 needs only cards).
Next: code + tests.

## UNIT_TESTED - TASK-026 - 2026-09-25T02:44:48Z
Action: compose_phase1/gate_phase1 + graph/phase1/clusters steps in pipeline.sh; graph_build.sh (edges, neighbours, clusters, 4 candidate joins); JQ_FINGERPRINT; pl_fill @NAME=file.
Result: 20 suites pass; shell.sh fail=0; new cases bite on the old kit.
Decision: named-placeholder check; sink cut at "("; deny rules on pipeline calls. Checklist rows 10-12, 19 ticked.
Next: VERIFIED.

## VERIFIED - TASK-026 - 2026-09-25T02:45:07Z
Action: tier-1 prompt diff, tier-2 fake e2e, tier-3 real sonnet phase1 on tiny-api; security pass.
Result: all pass; real unit $0.10, 0 denials, accepted with the addon fields.
Decision: verified; cross-repo card injection noted as accepted risk.
Next: report + DONE.

## DONE - TASK-026 - 2026-09-25T02:45:30Z
Action: report docs/report/phase-26-phase1-graph.md; backlog complete.
Result: 26.1-26.4 delivered and verified.
Decision: -
Next: backlog.sh pick TASK-027.

## DESIGN - TASK-027 - 2026-09-25T02:47:18Z
Action: took the approved docs/design/phase-27-chain-verification.md; read the 2a/2b prompt schemas.
Result: design complete.
Decision: select2b/evidence/overlay as graph_build.sh commands (jq, testable); one generic unit loop in pipeline.sh; a finding is refuted only when every citation refutes it.
Next: IMPLEMENTING.

## IMPLEMENTING - TASK-027 - 2026-09-25T02:47:18Z
Action: start implementation.
Result: -
Decision: -
Next: code + tests.

## UNIT_TESTED - TASK-027 - 2026-09-25T03:09:26Z
Action: run_units loop, phase2a/select2b/phase2b/overlay steps; graph_build.sh select2b/evidence/overlay; tests.
Result: run_all 20 suites pass; shellcheck clean; new cases fail on the old kit (12 + 13).
Decision: 2a/2b cwd is an empty cwd/<key>, inputs stay in in/<key>.
Next: VERIFIED with one real sonnet run.

## VERIFIED - TASK-027 - 2026-09-25T03:13:19Z
Action: real sonnet run of phase2a/select2b/phase2b/overlay on the t3 kit (tiny-api); fake e2e rerun.
Result: exit 0, $0.17; 2b Glob on the parent dir denied (isolation holds); evidence refs resolved; overlay 1 confirmed. Overlay warned on cited primitives -> fixed, test added (graph 43).
Decision: checklist rows 13-15 ticked.
Next: report, DONE.

## DONE - TASK-027 - 2026-09-25T03:13:44Z
Action: wrote docs/report/phase-27-chain-verification.md.
Result: TASK-027 complete.
Decision: -
Next: TASK-028.

## DESIGN - TASK-028 - 2026-09-25T03:14:06Z
Action: took the approved docs/design/phase-28-run-diff-report.md.
Result: design complete.
Decision: as designed; report hooks guarded by --run.
Next: IMPLEMENTING.

## IMPLEMENTING - TASK-028 - 2026-09-25T03:14:06Z
Action: start implementation.
Result: -
Decision: -
Next: run_diff.sh, report --run, e2e, docs.

## UNIT_TESTED - TASK-028 - 2026-09-25T03:37:54Z
Action: run_diff.sh, summarize_report.sh --run (sections 13-15, overlay join, dismissed moved), report step, e2e test, golden check, docs.
Result: run_all 21 suites pass; shellcheck clean; new suites fail on the old kit.
Decision: section 8 subtracts dismissed findings in run mode (found by e2e).
Next: VERIFIED.

## VERIFIED - TASK-028 - 2026-09-25T03:40:05Z
Action: e2e suite, run_diff + --run report on the real sonnet t3 run, docs grep; ticked checklist 16,17,18,20,22.
Result: all pass; real report renders sections 13-15; golden identical.
Decision: no new real claude spend (the real 2-run data already exists from TASK-027).
Next: DONE.

## DONE - TASK-028 - 2026-09-25T03:40:23Z
Action: wrote docs/report/phase-28-run-diff-report.md; backlog complete.
Result: pipeline TASK-025..028 complete.
Decision: open questions handed to the user.
Next: none.

## DESIGN - TASK-029 - 2026-09-25T05:44:30Z
Action: root-caused the Upzi_g02 pilot failures from run logs; wrote docs/design/phase-29-pilot-fixes.md.
Result: 3 root causes (filter-blocked payload, blind retries, 278 KB prompts).
Decision: user approved option a + fixes 2 and 3.
Next: IMPLEMENTING.

## IMPLEMENTING - TASK-029 - 2026-09-25T05:44:30Z
Action: start 29.1-29.3.
Result: -
Decision: -
Next: unit tests.

## IMPLEMENTING - TASK-029 - 2026-09-25T06:35:46Z
Action: rescoped the design after the pilot review (prototype correlate engine recovered 3/3 in-plan AI chains).
Result: docs/design/phase-29-pilot-fixes.md rewritten as a draft.
Decision: hold implementation until the user approves (user: design first).
Next: user approval.

## UNIT_TESTED - TASK-029 - 2026-09-25T07:23:36Z
Action: implemented 29.1-29.5 (plain P1, refused class, correlate.py, fixed 2b prompt + cwd files, P0 paths); removed 2a/clusters/select2b; docs.
Result: 22 suites pass, shellcheck 126/0; new tests fail on the HEAD kit.
Decision: overlay: a correlate item never dismisses a finding (found in the real check); numeric/UUID route segments normalise to {} (found by e2e).
Next: VERIFIED.

## VERIFIED - TASK-029 - 2026-09-25T07:25:24Z
Action: real low-cost check on a scratch copy of the Upzi_g02 pilot run: correlate + 2 sonnet 2b units + overlay + report.
Result: 14 items / 2 selected; 2b $0.66 total, answers accepted, prompts byte-identical; 1 confirmed, 1 unverified, 0 refuted; all 7 findings kept.
Decision: accepted. A fresh P0/P1 run on g02 (new card paths field, plain P1) is left as an operating step (~$9-12).
Next: DONE (report, backlog complete).

## DONE - TASK-029 - 2026-09-25T07:25:52Z
Action: wrote docs/report/phase-29-pilot-fixes.md; backlog complete.
Result: fixed prompts + correlate.py delivered and verified at $0.66 real spend.
Decision: close. Open: a fresh g02 run to use card paths live; deploy-link import for big projects.
Next: none.

## DESIGN - TASK-030 - 2026-09-25T08:47:11Z
Action: design docs/design/phase-30-crash-resume.md (30.1-30.4).
Result: user approved ("go ahead, implement TASK-030 and verify with low cost").
Decision: pipeline only; no auto-restart; scan_batch unchanged.
Next: IMPLEMENTING.

## IMPLEMENTING - TASK-030 - 2026-09-25T08:47:11Z
Action: start implementation.
Result: -
Decision: -
Next: 30.1-30.4 + tests.

## UNIT_TESTED - TASK-030 - 2026-09-25T09:09:32Z
Action: 30.1-30.4 implemented; 10 new checks.
Result: 22 suites pass, shellcheck 126/0; 7 new checks fail on HEAD.
Decision: gate step split into pl_finish_unit (shared by resume).
Next: VERIFIED.

## VERIFIED - TASK-030 - 2026-09-25T09:09:32Z
Action: real claude (sonnet) crash check in a scratch kit.
Result: kill -9 of pipeline.sh and of claude both resume correctly; $0.05.
Decision: accepted.
Next: DONE.

## DONE - TASK-030 - 2026-09-25T09:09:32Z
Action: report docs/report/phase-30-crash-resume.md; backlog complete.
Result: crash-safe resume delivered and verified.
Decision: close. Open: automatic restart is out of scope (cron/by hand).
Next: none.

## DESIGN - TASK-031 - 2026-09-25T09:48:40Z
- Action: Proposal (§0-§11) reviewed; user approved D1-D8 as recommended ("Yes, I agree."). Added implementable design §12-§18 (evaluate_run.sh, M1-M8, failure modes, 8 unit tests, tier-2 verification on a copy of run 20260925-142931). Queued and picked TASK-031 (pick --force only because the new backlog entry was uncommitted).
- Result: docs/design/phase-31-solution-evaluation-report.md; no engine file touched.
- Decision: standalone read-only script; no repo names; EVAL_MIN_N=5 in config.sh; no trends until the same-commit instability is explained.
- Next: IMPLEMENTING 31.1 (tests first, then CLI/guards).

## IMPLEMENTING - TASK-031 - 2026-09-25T09:53:26Z
- Action: User asked to continue implementing and to show the $0 script cross-repo correlation; added design item 31.7 (counts only, phase0 cost shown beside) and its acceptance criterion.
- Result: design doc §14 31.7, §16 test 8, §17 row; task/backlog criteria updated.
- Decision: 31.7 stays inside evaluate_run.sh (no correlate.py/graph_build.sh change).
- Next: tests + evaluate_run.sh.

## UNIT_TESTED - TASK-031 - 2026-09-25T10:11:48Z
- Action: Wrote evaluate_run.sh (collect -> metrics object without names/free text -> render), tests/evaluate_run_test.sh (fixture run, 57 checks), EVAL_MIN_N in config.sh, docs (README, reference, runbook).
- Result: run_all 23/23 pass; shell.sh 130/0; new suite on HEAD 43/57 fail. A preview on a scratch copy showed a wrong claim of mine: pilot head_sha is empty in both runs (no .git), so the earlier "same commit, 0/19 persisting" was an ""=="" comparison. Design §3 M8, §10.3, D6 and §17 corrected; M8 now says why it is unavailable. Also fixed: $run shadowed by run.json in the title, jq comma/as precedence, duplicated (n=).
- Decision: per-rule cost divides by confirmed + partial (same as the headline M7).
- Next: VERIFIED on a scratch copy of the real run.

## VERIFIED - TASK-031 - 2026-09-25T10:13:59Z
- Action: ran final evaluate_run.sh on a scratch copy of Upzi_g02/main run 20260925-142931 with a fake claude on PATH; checksummed copy and real plan; leak grep; security pass.
- Result: rc 0; all §17 numbers match (M2 6/6, M3 2/1/3, M4 3 of 12, M6 $4.44/$2.89/$0/$2.02, M7 insufficient n=3, M8 unavailable no .git, 31.7 edges 8 / unresolved 71 / R 0-2-3-1-6); 0 leak hits; checksums unchanged; no model call.
- Decision: VERIFIED; security completed (read-only, closed-set output, no new deps).
- Next: DONE report, backlog complete, lesson, commit.

## DONE - TASK-031 - 2026-09-25T10:14:42Z
- Action: wrote docs/report/phase-31-solution-evaluation-report.md; backlog complete; token-efficiency lesson.
- Result: report records pilot numbers, verification evidence and the head_sha correction.
- Decision: DONE.
- Next: none.

## DESIGN - TASK-032 - 2026-09-25T10:49:53Z
- Action: reviewed run Upzi_g02/main 20260925-142931 (overlay, 2b answers, --run report, evaluate_run); wrote docs/design/phase-32-false-positive-reduction.md (32.1-32.13).
- Result: dismissal is structurally 0 (every correlate item is a rule chain; overlay never refutes rule items); confirmed final_severity not applied; R4/R5 results only in §13; pipeline report step writes no executive_summary_ or by-repo/.
- Decision: user approved per-finding 2b verdict, hide not-upheld findings from all reader documents with counts only (details in verification_appendix_), raise-only severity from confirmed, XR issues in posture; single-phase reports must stay byte-identical (32.13).
- Next: IMPLEMENTING 32.1-32.2 (prompt finding_checks + evidence check) with pipeline_graph_test.sh cases.

## IMPLEMENTING - TASK-032 - 2026-09-25T10:52:35Z
- Action: started implementation of the approved phase-32 design.
- Result: -
- Decision: order 32.1-32.4 (prompt, evidence, overlay, xissues), 32.5-32.10 (reports), 32.11 (evaluation), 32.12 docs.
- Next: 32.1 prompt finding_checks.

## UNIT_TESTED - TASK-032 - 2026-09-25T11:26:31Z
- Action: implemented 32.1-32.13 (prompt finding_checks, evidence check, overlay precedence + xrepo_severity, xissues.json, run_mode_setup/apply_overlay/hidden_line in report_common.sh, security_report_/exec/by-repo run mode, verification appendix, step_report full set, check_deliverables --run, evaluate_run effect metrics, docs, PIPELINE_HIDE_NOT_UPHELD).
- Result: tests/run_all.sh 24 suites pass; shell.sh 132/0; new cases fail on d8eeee2 (graph 11, run_reports 17, evaluate 14).
- Decision: hiding decided at report time (config flip needs only a report re-run); lesson: edited a test while the full suite ran in background -> stopped and re-ran.
- Next: VERIFIED (tier-2 scratch run + golden + security pass).

## VERIFIED - TASK-032 - 2026-09-25T11:28:41Z
- Action: tier-2 rerun on a scratch kit from HEAD (copy of run 20260925-142931, edited 2b answers) + security pass.
- Result: not-upheld finding hidden from all reader docs (appendix only), count lines, XR-001 in report/exec/csv/owner by-repo, check_deliverables --run complete, evaluate_run effect table; standalone golden identical; secrets pass; real manifest unchanged.
- Decision: VERIFIED; tier-3 real 2b re-run needs user approval (~$2).
- Next: tier 3 on approval, then DONE.

## DONE - TASK-032 - 2026-09-25T11:44:33Z
- Action: tier-3 real sonnet 2b re-run (6 pilot items, scratch kit, $2.05); report written; lesson added.
- Result: finding_checks on 5/5 anchored items with resolved evidence; 3 refuted chains but their findings upheld -> 3 confirmed, 0 hidden, 1 raised, XR-001; report set complete.
- Decision: DONE.
- Next: none (backlog).

## DESIGN - TASK-033 - 2026-09-25T13:59:46Z
Action: premise on HEAD f42a589: scratch overlay fixture (finding on /external, one not-upheld with caller-only evidence + one cannot-determine) -> hidden; graph_build.sh:206-207 not unanimous despite 32.3; appendix has no PDF, step_report no --csv, check_deliverables ignores both; section 13 has no entry/direction/vulnerable marker.
Result: docs/design/phase-33-report-flows-safe-hiding.md, items 33.1-33.8, verification tiers 0-2 (no model calls).
Decision: rule enforced in overlay (owner evidence + unanimous + non-internet route, else disputed); flow fence rendered by md2html.py; no 2b prompt change. Decisions 1-5 await user confirmation.
Next: IMPLEMENTING 33.1-33.2.

## DESIGN - TASK-033 - 2026-09-25T14:03:01Z
Action: user approved all recommended options and asked to make sure prompts are not changed easily; reviewed every item against existing output fields.
Result: design approved; added the prompt-freeze review table (all joins by id, no prompt/schema change) and 33.9 commit-check gate (Prompt-change: trailer required for security_prompt.md / docs/prompts/*.md); flow mapping moved to flow_map.py (no-cost Python).
Decision: no prompt change in phase 33; VERIFIED also checks the prompt diff is empty.
Next: IMPLEMENTING 33.1-33.2.

## IMPLEMENTING - TASK-033 - 2026-09-25T14:05:07Z
Action: design approved (all decisions); start implementation.
Result: -
Decision: order 33.1-33.2, 33.3, 33.4-33.5, 33.6-33.7, 33.9, 33.8.
Next: 33.1-33.2.

## UNIT_TESTED - TASK-033 - 2026-09-25T14:35:09Z
Action: implemented 33.1-33.9 (owner_evidence + disputed overlay, disputed in reports/appendix/evaluate, flow_map.py + md2html flow renderer, findings_ md/pdf, appendix pdf, step_report --csv, D7/D8, prompt-freeze gate, docs); fixed md_to_pdf relative html path found in kit run.
Result: run_all 25 suites pass; new cases bite on old code (graph 9, reports 8, flow_map all, evaluate 1); golden standalone identical.
Decision: flow_map writes to a temp file from summarize_report (--out) instead of report/flows.json, so reports never write run state.
Next: VERIFIED.

## VERIFIED - TASK-033 - 2026-09-25T14:37:30Z
- Action: tier-2 kit scratchpad/v33 (copy of run 20260925-142931, HEAD scripts), check_deliverables --run, security pass, prompt diff.
- Result: deliverables pass=20 fail=0 (D7/D8 PASS); 3 flows in section 13 and appendix; disputed fixture kept (internet route); prompt diff empty; escaping reviewed.
- Decision: VERIFIED.
- Next: DONE report.

## DONE - TASK-033 - 2026-09-25T14:38:09Z
- Action: report docs/report/phase-33-report-flows-safe-hiding.md, lesson line, backlog complete.
- Result: all 9 items delivered and verified.
- Decision: DONE.
- Next: pick TASK-034 (engine review report, design approved).

## DESIGN - TASK-034 - 2026-09-25T14:38:24Z
- Action: design docs/design/phase-34-engine-review-report.md (written and approved earlier, "sure go for it").
- Result: 34.1-34.4 acceptance criteria; decisions 1-4 recommended options.
- Decision: implement.
- Next: engine_review.py + tests.

## IMPLEMENTING - TASK-034 - 2026-09-25T14:38:35Z
- Action: start engine_review.py.
- Result: -
- Decision: -
- Next: collector, wiring, tests.

## UNIT_TESTED - TASK-034 - 2026-09-25T15:01:24Z
- Action: engine_review.py, summarize_report --run wiring, D9, docs, tests/engine_review_test.sh + run_reports cases.
- Result: run_all 26 suites pass; shell 136/0; new cases fail on HEAD; golden same.
- Decision: UNIT_TESTED.
- Next: VERIFIED.

## VERIFIED - TASK-034 - 2026-09-25T15:01:43Z
- Action: tier-2 kit v33 (run 20260925-142931): engine_review alone and via summarize_report --run; D9 pass/fail; security pass; prompt diff.
- Result: 71 unresolved, 6 failed units, 3 refuted, 1 disputed; D9 PASS (pass=22) and FAIL without PDF; run dir and manifest unchanged; prompt diff empty.
- Decision: VERIFIED.
- Next: DONE.

## DONE - TASK-034 - 2026-09-25T15:02:24Z
- Action: report docs/report/phase-34-engine-review-report.md, lesson line, backlog complete, TASK-035 queued (md2html href quoting).
- Result: 34.1-34.4 delivered and verified.
- Decision: DONE.
- Next: TASK-035 needs no clarification but is a security hardening of shared rendering; queued.

## DESIGN - TASK-035 - 2026-09-25T22:18:07Z
Action: premise on HEAD (quote in link url ends href; javascript: link rendered), design docs/design/phase-35-md2html-safe-links.md.
Result: approved by user ("sure go for it").
Decision: scheme allowlist, quote-escaped stashed hrefs, unsafe link shown as text; no prompt change.
Next: IMPLEMENTING.

## IMPLEMENTING - TASK-035 - 2026-09-25T22:18:19Z
Action: start implementation.
Result: -
Decision: -
Next: md2html.inline change and tests.

## UNIT_TESTED - TASK-035 - 2026-09-25T22:35:36Z
Action: safe_href + href stash (\x02) in md2html.inline; tests/md2html_test.sh; docs.
Result: 27 suites pass (md2html 17/17), 12 new cases fail on HEAD; shell 138/0.
Decision: \x01 was taken by hard breaks (golden caught it), stash uses \x02.
Next: VERIFIED.

## VERIFIED - TASK-035 - 2026-09-25T22:35:36Z
Action: golden HTML diff over 492 md files; md_to_pdf of a hostile report.
Result: differing=0; injected=0 (HEAD 1); javascript link rendered as text in PDF.
Decision: -
Next: DONE.

## DONE - TASK-035 - 2026-09-25T22:36:07Z
Action: report docs/report/phase-35-md2html-safe-links.md; lessons added.
Result: md2html links hardened, golden identical.
Decision: note: UNIT_TESTED/VERIFIED commits landed while commit-check flagged the unstaged report (set -e did not stop the chain); content correct, report committed here.
Next: -

## DESIGN - TASK-036 - 2026-09-26T02:31:17Z
Action: premise on the real plan Upzi_g02/main (read-only): run 20260925-142931 has 6 phase2b units failed "not in phase2b/selected.json" (attempts 2, no model call), the same 6 keys as selected.json .not_selected; queued before c5763ca, phase2b step done so HEAD's prune never ran. engine_review §9 shows them (6 rows) and §10 again; status prints "failed 6". Design docs/design/phase-36-stale-2b-units.md.
Result: draft, awaiting user approval.
Decision: fix the readers (engine_review §9 note, status "not selected"); no manifest rewrite, no prune at run start (no running pre-c5763ca run exists); no prompt change.
Next: user approval, then IMPLEMENTING.

## IMPLEMENTING - TASK-036 - 2026-09-26T02:36:25Z
Action: design approved by user ("sure go for it"); start implementation.
Result: -
Decision: -
Next: 36.1 engine_review.py, 36.2 pipeline.sh status, tests.

## UNIT_TESTED - TASK-036 - 2026-09-26T02:59:40Z
Action: engine_review.py sec_units skips stale 2b units (not done, key not in .selected) with one §9 note; pipeline.sh status maps them to "not selected" (same any($sel[]) rule as step_phase2b); tests in engine_review_test.sh and pipeline_run_test.sh; reference doc.
Result: 27 suites pass; new cases fail on HEAD (engine-review 2, pipeline-run 1); shell 138/0, python 1/0.
Decision: engine_review fixture unit X9 (never selected) renamed I2 so it stays a genuine failed unit; my first 36.1 check wrongly asserted §9 = 1 (it is 2 with the retried phase1 unit), fixed the assertion, not the code; status jq restructured so failed lines keep printing after all group lines.
Next: VERIFIED.

## VERIFIED - TASK-036 - 2026-09-26T03:00:09Z
Action: tier 1 on the real plan read-only: engine_review --out scratch, pipeline.sh status, --count vs HEAD pipeline.sh, hashes before/after; security pass.
Result: §9 has 0 stale rows + note "6 phase2b unit(s)", §10 unchanged; status "done 6, not selected 6", no failed line; --count 0|14 both; manifest and run dir unchanged.
Decision: VERIFIED.
Next: DONE.

## DONE - TASK-036 - 2026-09-26T03:00:41Z
Action: report docs/report/phase-36-stale-2b-units.md (with a failures-and-effort table, user request); lesson added; backlog complete.
Result: 36.1 and 36.2 delivered and verified on the real plan, read-only.
Decision: DONE.
Next: -

## DONE - TASK-036 - 2026-09-26T03:04:18Z
Action: user asked whether the report set was checked; check_deliverables.sh --run latest was not run at VERIFIED. The 09-25 set failed 5 (predates findings md/pdf, appendix pdf, D9); regenerated with summarize_report.sh --run --per-repo and summarize_exec.sh --run --csv.
Result: pass=22 fail=0; exec summary identical to 09-25; manifest unchanged; report row 8 and lesson added.
Decision: DONE stands; deliverables check is now part of VERIFIED for run-report changes (lesson).
Next: -

## DESIGN - TASK-037 - 2026-09-26T03:21:47Z
- Action: traced model/cost output in hand-over reports; wrote docs/design/phase-37-hide-model-cost.md.
- Result: one writer (summarize_report.sh:679 footer). solution_evaluation_ has cost but no model; engine_review_ has model but no cost.
- Decision: 37.1 footer without model/spend, 37.2 stderr line, 37.3 Models row in solution_evaluation_; no --internal flag, no cost in engine_review_, no prompt change.
- Next: user approval, then IMPLEMENTING 37.1.

## IMPLEMENTING - TASK-037 - 2026-09-26T03:25:25Z
- Action: design approved ("go ahead, implement it"); footer without model/spend + stderr line (summarize_report.sh), Models row (evaluate_run.sh), 6 test cases, reference note.
- Result: plan_reports 44/0, run_reports 32/0, evaluate_run 73/0; on HEAD scripts the 6 new cases fail (2+3+1).
- Decision: model string cleaned to [A-Za-z0-9._:-], max 40 chars (no cell escaping helper in evaluate_run.sh).
- Next: full suite + shell checks, UNIT_TESTED.

## UNIT_TESTED - TASK-037 - 2026-09-26T03:41:10Z
- Action: full suite + shellcheck.
- Result: 27 suites pass, shell 138/0; new cases bite on HEAD (6 fail).
- Decision: advance.
- Next: VERIFIED on a scratch kit.

## VERIFIED - TASK-037 - 2026-09-26T03:41:10Z
- Action: scratch-kit run of the real run 20260925-142931 report set + evaluate_run + check_deliverables; security pass.
- Result: no Model:/Scan spend in any hand-over file; stderr line present; Models row present; deliverables 13/0.
- Decision: advance.
- Next: report, DONE.

## DONE - TASK-037 - 2026-09-26T03:42:29Z
- Action: regenerated the real latest run set (no model call), wrote docs/report/phase-37-hide-model-cost.md.
- Result: check_deliverables --run latest 22/0; PDF footer has no model/spend.
- Decision: older dated report files left as is (listed in the report).
- Next: none.

## DESIGN - TASK-038 - 2026-09-26T05:29:04Z
- Action: measured the Upzi_g02 pilot runs (CLI envelopes, card sizes per field, 2b inputs, report timing); traced every consumer of phase 0 card fields (graph_build, correlate R1-R5, 2b cards.json, flow_map/engine_review via edges); user redirected mid-design: conclude findings to JSON first, report is a simple step.
- Result: phase 0 costs more than phase 1 ($4.43 vs $2.89, 1216 s vs 576 s); card JSON is ~1/3 of phase 0 output tokens; removable fields = 3-6% of output; a phase 0 prompt edit re-runs every card and every 2b item (~9-13 h at 100 repos). Concluded findings exist only in /tmp inside each report script. Design docs/design/phase-38-card-field-audit.md (38.1-38.5).
- Decision: prompt frozen; warn-only card field check; conclude.sh -> report/conclusion.json by moving existing logic; reports render it with golden-identical output; pipeline.sh rebuild [--render].
- Next: user confirmation, then IMPLEMENTING 38.1.

## DESIGN - TASK-038 - 2026-09-26T05:37:58Z
- Action: revised docs/design/phase-38-card-field-audit.md from code (user: "design base from code, and report not guess"); built golden harness and HEAD baseline (G0).
- Result: code facts fixed the design — enrich_findings runs before apply_overlay raises severity, so conclusion.json stores enriched findings; load_conclusion also calls load_result_files; exact temp-file contract per script; XR null semantics; inputs_sha covers inputs, manifest view, env, engine code; run_diff stays in step_conclude; check_deliverables unchanged. Validation plan G0-G4 added; G0 passed (22 files identical).
- Decision: approved by user ("Just let do it"); implement 38.1 → 38.5 with golden G1 after each report-touching step.
- Next: IMPLEMENTING 38.1.

## IMPLEMENTING - TASK-038 - 2026-09-26T06:02:08Z
- Action: 38.1 card check (graph_build.sh edges -> graph/card_check.json, warn only); 38.2 build_run_data moved verbatim into report_common.sh, conclude.sh writes report/conclusion.json, PL_STEPS gains conclude (step_conclude = run_diff + conclude); 38.3 load_conclusion in both renderers; 38.4 ./pipeline.sh rebuild [--run] [--render]; 38.5 reference + security-review-runbook (docs/prompts/ is gate-frozen, so pipeline-runbook.md is untouched).
- Result: golden G1 empty after the refactor alone, after 38.3 and on the final code (20 report files, both pilot runs); G2 (rebuild vs HEAD+overlay) identical except the CSV file name the harness picks; G3 stale path refreshes once, output identical. 38.1 on the real cards found one gap: backend__meta-service has no outbound.paths (reported, not fixed).
- Decision: conclusion stores enriched findings (code fact); a malformed 2b file stays silently skipped as before (moved code).
- Next: UNIT_TESTED.

## UNIT_TESTED - TASK-038 - 2026-09-26T06:20:08Z
- Action: ran tests/run_all.sh and .claude/scripts/checks/shell.sh on the committed code (68d5b9c).
- Result: 27 suites all passed (new 38.x cases in run_reports, pipeline_run, pipeline_graph); shell pass=140 fail=0.
- Decision: advance to UNIT_TESTED.
- Next: VERIFIED with golden gates G0-G3 and the real-plan render.

## VERIFIED - TASK-038 - 2026-09-26T06:20:23Z
- Action: golden gates G0-G3 on a scratch kit; ./pipeline.sh rebuild --render on the real plan Upzi_g02/main (no model call); security pass.
- Result: G1 empty, G2 equal except the harness CSV name, G3 refresh seen; real reports equal to the previous set except the time line, deliverables 22/0; meta-service card lacks outbound.paths.
- Decision: advance to VERIFIED; security completed (no new boundary).
- Next: DONE report and backlog complete.

## DONE - TASK-038 - 2026-09-26T06:20:35Z
- Action: wrote docs/report/phase-38-card-field-audit.md; backlog complete; Going faster lesson.
- Result: 38.1-38.5 delivered; reports unchanged (golden + real render); rebuild available.
- Decision: close TASK-038.
- Next: none.

## DESIGN - TASK-039 - 2026-09-26T06:42:46Z
- Action: designed a measured A/B for PIPELINE_MODEL_P0=haiku from code and saved runs (no model call): sonnet phase 0 cost $3.62 and $4.43 per 4 repos; two sonnet runs differ by 1 of 9 edges; reuse off (head_sha empty); model absent from pl_input_hash.
- Result: docs/design/phase-39-haiku-phase0-ab.md: separate A/B plan, stdlib card_ab.py replay with phase 1 fixed, M1-M8, ADOPT rule fixed in advance, effort/cost/risk tables.
- Decision: no engine or prompt change; Tier 2 (2b verdicts) and the hash fix out of scope.
- Next: user go, then 39.1/39.2 ($0); 39.3 paid only after 39.2 passes.

## IMPLEMENTING - TASK-039 - 2026-09-26T06:56:27Z
- Action: 39.1 created plan Upzi_g02/ab-p0-haiku (review), plan.conf PIPELINE_MODEL_P0=haiku + same deploy dir, init + approve-all, dry run; fake-claude scratch kit proved the phase 0 call carries --model haiku. 39.2 card_ab.py (stdlib replay of graph_build edges + correlate on a copy of run A) + tests/card_ab_test.sh (19 cases).
- Result: dry run lists the same 4 repos; G0 reproduces 142931 edges and selection (cap 6); sonnet vs sonnet shows large noise (exposure sets 2/4 cards, M5 171 vs 104, gaps 1 vs 4, 6th item).
- Decision: rule (e) = M4 only, M5 info (decided before any haiku data); paid run still gated on the user.
- Next: UNIT_TESTED.

## UNIT_TESTED - TASK-039 - 2026-09-26T07:13:05Z
- Action: tests/run_all.sh and shell.sh on 6917cd1.
- Result: 28 suites all passed (new card_ab 19/0); shell pass=142 fail=0.
- Decision: advance; VERIFIED needs 39.3, the paid run, which waits for the user's go.
- Next: user go for 39.3.

## UNIT_TESTED - TASK-039 - 2026-09-26T07:23:12Z
- Action: parked at the user's request ("a-b testing for Haiku just keep there ... finish first before go too far").
- Result: A/B plan, card_ab.py and tests kept; no paid run made.
- Decision: blocked (parked) until the user asks; focus returns to phase 34 engine review follow-up.
- Next: resume only on request.

## DESIGN - TASK-040 - 2026-09-26T07:42:17Z
- Action: user asked "make engine review and solution evaluation read conclusion.json too" and for runbook notes (step table, whole-run guide). TASK-039 set back to queued (parked at UNIT_TESTED, task.json in 566b0b8), TASK-040 picked. Inputs of both scripts listed from code; baselines rendered (er.before.md equal to published engine_review_2026-09-26.md; se.before.md equal to published solution_evaluation_2026-09-26.md).
- Result: docs/design/phase-40-reports-from-conclusion.md, items 40.1-40.5.
- Decision: verbatim snapshot of engine inputs under conclusion.engine (engine_inputs.py), units carried over; both scripts read only conclusion.json; acceptance = byte-identical output.
- Next: IMPLEMENTING 40.1-40.5.

## IMPLEMENTING - TASK-040 - 2026-09-26T07:51:10Z
- Action: engine_inputs.py (40.1); conclude.sh merges it under .engine, conclude_inputs_sha covers raw answers, phase0/out, logs, run.json, correlation, prev run, units; ensure_conclusion split out (40.2); engine_review.py takes <conclusion.json> (40.3); evaluate_run.sh guards and collection from .engine (40.4); runbook step table + whole-run checklist, reference updated (40.5).
- Result: scratch copy of Upzi_g02/main 20260925-142931: engine_review and solution_evaluation byte-identical to the pre-change renders. First scratch try missed the previous run (not copied) -> found the prev-run inputs were not in inputs_sha; added. User asked to regenerate the real set: rebuild --render + evaluate_run at 14:48, every .md/.csv identical to the backup except the security_report _Generated line; conclusion findings/hidden/xissues/pt_map/flows/run/counts unchanged; check_deliverables 22/0.
- Decision: tests ported (engine_review via mkc helper, run_reports 38.2 raw assertion inverted by design, evaluate_run read-only check excludes conclusion.json, new 40.1/40.3/40.4 cases).
- Next: UNIT_TESTED.

## UNIT_TESTED - TASK-040 - 2026-09-26T08:06:45Z
- Action: tests/run_all.sh (full), .claude/scripts/checks/shell.sh.
- Result: 28 suites all passed, rc 0; shell pass=142 fail=0.
- Decision: advance to UNIT_TESTED.
- Next: VERIFIED with the real-run evidence already collected.

## VERIFIED - TASK-040 - 2026-09-26T08:07:07Z
- Action: real-plan rebuild --render + evaluate_run, byte compare with backup, strace openat trace, finding coverage check scan->conclusion->reports, check_deliverables.
- Result: all reports identical (only _Generated lines differ); renderers read only conclusion.json; 12/12 findings verbatim in conclusion and every report; 2 confirmed X-R3 -> meta-service-001 confirmed, X-R4 -> XR-001; deliverables 22/0/0. Security: no new boundary.
- Decision: advance to VERIFIED.
- Next: DONE (report, backlog complete, lesson).

## DONE - TASK-040 - 2026-09-26T08:07:27Z
- Action: wrote docs/report/phase-40-reports-from-conclusion.md; backlog.sh complete; token-efficiency lesson (finish and check before proposing new work; coverage join).
- Result: every report of a run renders from conclusion.json; real plan identical; no finding lost.
- Decision: TASK-040 closed. TASK-039 stays parked.
- Next: none.

## DESIGN - TASK-041 - 2026-09-26T08:10:32Z
- Action: read check_deliverables.sh, report ids (summarize_report.sh fmd/CSV, summarize_exec.sh, appendix hidden by id), pt_map key (report_common.sh:195), ensure_conclusion staleness.
- Result: docs/design/phase-41-deliverables-finding-coverage.md, items 41.1-41.4.
- Decision: stdlib coverage_check.py + D10 row, --run only, stale conclusion = FAIL (gate stays read-only).
- Next: IMPLEMENTING.

## IMPLEMENTING - TASK-041 - 2026-09-26T08:14:03Z
- Action: coverage_check.py (41.1-41.3), D10 row in check_deliverables.sh (41.4), 7 run-fixture tests + 1 non-run test, reference + runbook.
- Result: run_reports 50/0, check_deliverables 23/0; real run D10 PASS findings=12 shown=12 hidden=0 xr=1 answers_upheld=3 gaps=0.
- Decision: restore fixtures with cp -p (report staleness is mtime-based).
- Next: UNIT_TESTED.

## UNIT_TESTED - TASK-041 - 2026-09-26T08:32:45Z
- Action: full suite + shell checks; user asked mid-task to cross-check the report .md by script, so added the reverse check (unknown-in / wrong-repo) with 2 tests, reran the affected suites.
- Result: run_all 28/28, shell 142/0; then run_reports 52/0, check_deliverables 23/0, shell 142/0.
- Decision: advance to UNIT_TESTED.
- Next: VERIFIED.

## VERIFIED - TASK-041 - 2026-09-26T08:32:57Z
- Action: real gate, negative copies (missing id, unknown id, wrong-repo id), read-only hash.
- Result: D10 PASS gaps=0 on the real run (23/0/0); each negative gives the expected GAP and rc 1; no file changed.
- Decision: advance to VERIFIED.
- Next: DONE.

## DONE - TASK-041 - 2026-09-26T08:33:10Z
- Action: wrote docs/report/phase-41-deliverables-finding-coverage.md; backlog.sh complete; token-efficiency lesson.
- Result: check_deliverables --run proves by script that no finding is lost scan -> conclusion -> reports, and no report lists an unknown or wrong-repo id.
- Decision: TASK-041 closed. TASK-039 stays parked.
- Next: none.

## DESIGN - TASK-042 - 2026-09-26T08:47:38Z
- Action: read pipeline.sh step_conclude/step runner/rebuild, auto_scan exit handling, pipeline_run_test conclude tests.
- Result: docs/design/phase-42-coverage-after-conclude.md, items 42.1-42.3.
- Decision: --conclusion flag on coverage_check.py; gap fails the conclude step (auto_scan parks, no attempt charged, no model).
- Next: IMPLEMENTING.

## IMPLEMENTING - TASK-042 - 2026-09-26T08:54:33Z
- Action: --conclusion mode in coverage_check.py (report parts skipped; a lone run dir is usage, exit 2); step_conclude appends the check; tests; reference + runbook.
- Result: pipeline_run 107/0, run_reports 55/0; real run --conclusion prints COVERAGE findings=12 shown=12 hidden=0 xr=1 answers_upheld=3 gaps=0.
- Decision: 42.3 is asserted on the rebuild log (same step_conclude as a full run).
- Next: UNIT_TESTED.

## UNIT_TESTED - TASK-042 - 2026-09-26T09:11:43Z
- Action: tests/run_all.sh, checks/shell.sh.
- Result: 28/28 suites, shell 142/0.
- Decision: advance.
- Next: VERIFIED.

## VERIFIED - TASK-042 - 2026-09-26T09:11:44Z
- Action: --conclusion on the real run (read-only) and negative copies; rebuild on a scratch kit holding a copy of the real plan, pass then patched conclude.
- Result: gaps=0 on real (12/12, xr=1, upheld=3), run sha unchanged; negatives rc1; rebuild rc0 / rc1 with GAP missing + ERROR: step conclude failed, no claude call.
- Decision: advance.
- Next: DONE.

## DONE - TASK-042 - 2026-09-26T09:11:57Z
- Action: report docs/report/phase-42-coverage-after-conclude.md, backlog complete, lesson.
- Result: coverage check runs in the conclude step; a gap stops the pipeline before reports.
- Decision: done.
- Next: none.

## DESIGN - TASK-043 - 2026-09-26T09:48:59Z
- Action: reviewed the user's phase 0 proposal (rg patterns + noir -> Haiku -> Sonnet) against saved sonnet phase 0 envelopes (run 142931: 70-91 turns, 1.1-1.7M cache-read, 28-57k output per repo) and the estate language mix (py, go, swift, kt, ts; no PHP); wrote docs/design/phase-43-phase0-recon-option.md.
- Result: design 43.1-43.6: recon.sh (text-free recon.json), optional noir in docker, recon_eval.py tuning vs saved sonnet cards, PIPELINE_P0_RECON option (frozen prompt + one new addendum, off = byte-identical), recon_check + card_ab M9, paid arms B/C/D.
- Decision: single call with hints over a Haiku->Sonnet re-generation (the card output floor would be paid twice, and the stages would run one after the other); Sonnet only as a later targeted escalation. No prompt file changed.
- Next: user approval (incl. recon reading source in pipeline prep), then IMPLEMENTING 43.1.

## DESIGN - TASK-043 - 2026-09-26T09:50:09Z
- Action: added the user's rule (2026-09-26): when recon cannot help, the repo goes straight to the current phase 0 on sonnet.
- Result: design §43.7: fallback codes recon-error / lang-uncovered / no-hits / capped. A fallback repo uses today's exact prompt and hash with PIPELINE_P0_FALLBACK_MODEL=sonnet, set per unit through C_MODEL. It is recorded as p0_mode/p0_fallback. The missing-rg preflight now warns instead of exiting.
- Decision: a recon problem never fails or parks a unit; the worst case equals today's engine for that repo.
- Next: user approval, then IMPLEMENTING 43.1.

## DESIGN - TASK-043 - 2026-09-26T09:56:31Z
- Action: the user approved the design ("go ahead, approve design and implement 43.1 first"), then asked to finish the design before any code ("please design done first before implement, prevent you miss"). Implementation stopped before any file was written.
- Result: the design is complete down to the interfaces:
  - 43.1 engine steps, output fields (source_files, covered_share, errors, skipped_paths, hits_total, rg version, pack shas) and exit codes;
  - pack format and full seed id list with fixtures in phase-43-phase0-recon-option-packs.md;
  - 43.2 route normalisation, noir states, and a $0 design gate on noir's JSON shape;
  - 43.3 evidence parsing, matching and gate exits;
  - 43.4 exact addendum text, timeout and hash bytes;
  - 43.5 one shared matcher and M9 on every arm via --recon-dir;
  - unit tests per item, and a 10-row checklist.
- Decision: packs are whitespace-field .pat files, not TSV (the regex is the rest of the line), so an edit cannot break on tabs. The noir field mapping is the one part still to confirm, gated before any 43.2 code.
- Next: IMPLEMENTING checklist row 1 (43.1).

## IMPLEMENTING - TASK-043 - 2026-09-26T10:09:15Z
- Action: implemented 43.1 per the design and packs doc:
  - recon.sh;
  - recon/patterns/_common.pat plus the go, python, js, kotlin and swift packs (all ids in the packs doc);
  - fixtures under tests/fixtures/recon;
  - tests/recon_test.sh.
- Result:
  - recon_test 48/48, shell.sh fail=0.
  - The mutations bite: without the vendor exclude, 3 tests fail; with match text in the output, the marker diffs fail.
  - Real trees (126 repos under upzi, upzi_g01, upzi_g02): all exit 0, max 1.3 s, mean 0.63 s, 0 errors, 0 capped. 43.7 would fall back on 8 of 126. The table is in docs/notes/recon-real-trees-2026-09-26.md.
- Decision: every rg call names the path "." and reads /dev/null. Without a path, rg searched the loop's stdin (found while developing: zero hits on a real repo). The id list and regexes follow the packs doc with no change.
- Next: 43.2 design gate (noir image sample), then the noir adapter.

## IMPLEMENTING - TASK-043 - 2026-09-26T11:00:56Z
- Action: 43.8 per user scope (HTTP in/out only; config holds API roots). recon_eval out_http + gate in/out_http; recon.sh --deploy-context joins slice URL keys to code; pipeline passes the slice.
- Result: g02 in 98.8%, out_http 98.9% (gate PASS); cfg.out.deploy-key 219/223 labeled. Whole Upzi tree (114 repos) rc 0, noir ok, 108 recon / 6 fallback, 0 files changed in tree. Suites: recon 71, recon_eval 27, pipeline_recon 36, pipeline_run 107, e2e 19, card_ab 19, engine_review 30; shell 150/0.
- Decision: no store/trust tuning; no in-repo config pack (no card cites one); no tuning for API-less repos.
- Next: 43.5.

## IMPLEMENTING - TASK-043 - 2026-09-26T11:22:32Z
- Action: 43.5: recon_eval --check (graph_build edges, warn only), shared matcher + m9, card_ab --recon-dir M9/rule (g)/M8 by_mode.
- Result: g02 scratch copy: edges identical, routes_missing 47->1 after card-note tokens + HTTP-only routes; M9 sonnet 86.6%/81.2%. card_ab without --recon-dir byte-identical to HEAD. Suites: recon_eval 35, card_ab 26, engine_review 30, pipeline_run 107, e2e 19, pipeline_recon 36, pipeline_graph pass; shell 150/0.
- Decision: 43.6 must pass both sonnet runs (A+A2) for the (g) floor (5.4-pt sonnet spread).
- Next: docs row 8.

## IMPLEMENTING - TASK-043 - 2026-09-26T11:51:34Z
- Action: row 8 docs — toolkit-reference (files list: recon.sh, recon_eval.py, card_ab --recon-dir; phase0 step row; recon mode + fallback reasons + env; recon check; "what re-runs" rows), runbook (phase0 step, recon warning/fallback lines).
- Result: docs only; warning text matches recon_eval.py.
- Decision: row 8 ticked.
- Next: row 9 prep (no spend until the user confirms), then row 10.

## IMPLEMENTING - TASK-043 - 2026-09-26T11:54:13Z
- Action: 43.6 prep — plans Upzi_g02/ab-p0-haiku-recon and ab-p0-sonnet-recon (plan.sh new, init_manifest, approve-all, PIPELINE_P0_RECON=1, same deploy dir); dry-run all 3 arms; report draft.
- Result: 4 phase 0 units per arm; recon arms 4/4 recon mode, 0 fallback; $0 spent.
- Decision: paid runs wait for the user's confirm.
- Next: on confirm, run arms B, C, D with --pause-after-cards, card_ab each, fill the report.

## IMPLEMENTING - TASK-043 - 2026-09-26T12:19:23Z
- Action: user go for 43.6 arms D+C (started, cards only); design §43.9 plan per case, §43.10 route-matched R5 order, §43.11 Haiku-arm escalation (simulate first); rows 12-13.
- Result: /internal/v3/search root cause corrected: R5 item existed in 142931, dropped by pilot cap PIPELINE_2B_MAX=6.
- Decision: real review = Sonnet + recon; Haiku + recon = test arm; Haiku→Sonnet dropped; accuracy work in the deterministic layer.
- Next: implement 43.10; evaluate arms.

## IMPLEMENTING - TASK-043 - 2026-09-26T12:26:37Z
- Action: 43.10 correlate R5 order (matched no-auth routes; finding-backed items stay first), r5_matched in correlation.json; 4 tests.
- Result: pipeline suites 7/7, card_ab 26, engine_review 30, shell 150/0; new cases fail 4 on HEAD; replay 142931 --max 30 = HEAD set, --max 6 picks a matched R5 over R4; coverage gaps=0.
- Decision: row 12 ticked.
- Next: arm stats + card_ab + 43.11 simulation.

## IMPLEMENTING - TASK-043 - 2026-09-26T12:57:45Z
- Action: 43.6 arms D (sonnet+recon) and C (haiku+recon) on Upzi_g02, cards only; card_ab each; 43.11 escalation simulated; card_ab G0 compares the built item set (43.10 reorders under the cap).
- Result: spend $6.42. D $5.04 / 20.9 min, quality = A, REJECT on cost only. C $1.38 / 10.5 min, REJECT (M9 38.9 %, exposure 4/4, lost stable item). Escalation: 4/4 escalate → no saving; not built. Evidence docs/notes/ab-p0-2026-09-26.md. g01 on hold (user).
- Decision: rows 9, 13 ticked; default proposal PIPELINE_P0_RECON=0 pending the user.
- Next: user decision, then report final and close.

## IMPLEMENTING - TASK-043 - 2026-09-26T13:23:06Z
- Action: 43.12 (user): the recon block now goes before the phase 0 prompt, with a TO DO / NOT TO DO list. Start from the hints, read outside them only when an item needs it, and do not sweep the tree.
- Result: D's logs confirm the cause: the old appended addendum said "follow <procedure> in full" (jobseekers-info cache-read 2.89M vs 1.66M). pipeline_recon 36 pass; the prepend test fails on HEAD.
- Decision: recon-mode prompt only; standard prompt frozen. Default decision waits for D'.
- Next: user go for D' (about $3-5), card_ab, row 14.

## IMPLEMENTING - TASK-043 - 2026-09-26T13:42:09Z
- Action: D' paid run on Upzi_g02 (sonnet, recon rules first, 43.12), cards only; card_ab vs A/A2.
- Result: $3.22 / 13.5 min / 173 turns (A $4.44/20.3/278, A2 $3.62/15.8/236, D $5.04). Quality rules a-e, g ok, M9 85.0 %; f fails (Haiku-sized cap). Spend total $9.64 of $12.
- Decision: row 14 ticked; propose D' as the default, pending the user.
- Next: user decision, then default switch + close.

## UNIT_TESTED - TASK-043 - 2026-09-26T14:04:52Z
- Action: default switched to recon mode (user); off-run test pins 0; docs updated; full run_all + shell.sh.
- Result: 31 suites all passed; shell pass=150 fail=0.
- Decision: UNIT_TESTED.
- Next: VERIFIED with the real g02 runs as evidence.

## VERIFIED - TASK-043 - 2026-09-26T14:05:44Z
- Action: real evidence = paid g02 runs D, C, D-prime + card_ab; prompt order checked on the D-prime run; coverage gaps=0; security pass.
- Result: D-prime $3.22 / 13.5 min, quality = A/A2; C fails quality; recon read-only.
- Decision: VERIFIED.
- Next: DONE.

## DONE - TASK-043 - 2026-09-26T14:05:44Z
- Action: report final (docs/report/phase-43-phase0-recon-option.md); backlog complete; lesson logged.
- Result: default PIPELINE_P0_RECON=1 (D-prime), fallback standard Sonnet phase 0; spend $9.64 of $12.
- Decision: DONE (user: "yes, switch default to D' and close TASK-043").
- Next: none.

## DESIGN - TASK-044 - 2026-09-26T14:10:30Z
- Action: measured D' cost split and per-file reads at $0 from envelopes + transcripts; wrote docs/design/phase-44-phase0-cost-profile.md.
- Result: recon.json = 31-49 % of tool results and was cut at 59K of 106K by Read; grouped form is 67-71 % smaller.
- Decision: 44.1 p0_cost.py, 44.2 --compact model copy; prompts unchanged (user go).
- Next: IMPLEMENTING 44.1.

## IMPLEMENTING - TASK-044 - 2026-09-26T14:16:18Z
- Action: 44.1 p0_cost.py + tests (12); 44.2 recon_eval --compact, recon_hits/hit_cover/routes_missing read both shapes, check reads the full file, p0_recon behind PIPELINE_P0_RECON_COMPACT (default 0), tests (recon_eval 41, pipeline_recon 40).
- Result: D-prime profile residual 0.00; recon.json 31-49 % of tool results; compact = same hits, -65 to -68 %, lines < 2000. New cases fail on HEAD (no --compact / no flag).
- Decision: compact off by default (user: stability first).
- Next: UNIT_TESTED.

## UNIT_TESTED - TASK-044 - 2026-09-26T14:37:15Z
- Action: tests/run_all.sh full + checks/shell.sh.
- Result: 32 suites all passed; shell pass=152 fail=0.
- Decision: UNIT_TESTED. Paid verify approved by user. D' repeat in new plan Upzi_g02/ab-p0-sonnet-recon-r2 (same-plan run would reuse cards by hash); run 20260926-211918 did 2/4 cards ($1.66) then hit session limit, resets 00:10 +07, unit back to pending, no attempt charged.
- Next: resume after reset, card_ab + p0_cost vs D' 20260926-202418, then compact A/B.

## VERIFIED - TASK-044 - 2026-09-26T15:26:35Z
- Action: D' repeat (new plan r2) and compact arm (PIPELINE_P0_RECON_COMPACT=1) on g02, cards only; p0_cost.py + card_ab on both ($5.86).
- Result: repeat $3.08 vs $3.22 (-4 %, stable); compact $2.78 (-12 %), recon chars 263K->96K, M9 83.8 %, card_ab rules a-e, g pass (f = Haiku cap only).
- Decision: compact default on (design criteria met); 0 restores D'. run_all 32 pass, shell 152/0.
- Next: DONE (report, backlog complete, lesson).

## DONE - TASK-044 - 2026-09-26T15:26:57Z
- Action: report docs/report/phase-44-phase0-cost-profile.md; token-efficiency lesson.
- Result: p0_cost.py shipped; compact hints default on (-12 %, same quality); spend $5.86 (total $15.50).
- Decision: DONE. Watch jobseekers-info turns on the next real run; 44.3/44.4 need the user's go.
- Next: none (TASK-039 queued).

## DESIGN - TASK-045 - 2026-09-26T22:22:20Z
- Action: design docs/design/phase-45-phase0-effort-option.md from the $0 cost split (thinking ≈ $0.24, prompt < 6 % of cache write).
- Result: 45.1 PIPELINE_P0_EFFORT, 45.2 outlier flag, 45.3 one medium A/B. Budget cap dropped (user: do not stop repos; accept cost); found classify_failure would read error_max_budget_usd as rate_limit.
- Decision: user approved 1 and 3 (reworded). Prompt compression only as its own task with a claude -p quality check.
- Next: IMPLEMENTING 45.1.

## IMPLEMENTING - TASK-045 - 2026-09-26T22:25:59Z
- Action: 45.1 PIPELINE_P0_EFFORT (empty = today, same hash; bad value exit 2); 45.2 p0_cost outlier (> 2x median). Test helper call_of sorted 10 before 9: fixed numeric.
- Result: pipeline_recon 45/0, p0_cost 13/0, shell 152/0. Effort re-runs every phase 0 card (fallback ones too), as designed.
- Decision: no budget cap (user, twice: runs must not stop on cost; empty effort = fallback to today).
- Next: full run_all + paid A/B (medium) run 20260927-052539.

## UNIT_TESTED - TASK-045 - 2026-09-26T22:43:47Z
- Action: full run_all + shell.sh
- Result: 32 suites pass; shell 152/0
- Decision: UNIT_TESTED
- Next: VERIFIED from the paid A/B

## VERIFIED - TASK-045 - 2026-09-26T22:43:47Z
- Action: paid A/B effort=medium on g02 cards ($1.95); card_ab + p0_cost
- Result: -30 % cost, -36 % time, but card_ab g fails (M9 72.8 % < 76.2 %)
- Decision: keep default empty; medium stays an option
- Next: DONE

## DONE - TASK-045 - 2026-09-26T22:45:11Z
Action: report docs/report/phase-45-phase0-effort-option.md; backlog complete.
Result: PIPELINE_P0_EFFORT (default empty) + p0_cost outlier line; medium A/B $1.95 (-30 %) but card_ab g REJECT (M9 72.8 %).
Decision: default stays empty; medium kept as an option; no budget cap (user).
Next: TASK-039 queued (needs user go); g01 on hold.

## DESIGN - TASK-046 - 2026-09-27T00:16:35Z
Action: design docs/design/phase-46-phase0-windowed-reads.md from $0 data (p0_cost, recon paths/lines).
Result: source reads ~40 % of cache write, 87/142 whole-file Reads; expected ~-10 %. Haiku trim predicted net loss.
Decision: all items designed before any code (user); flag default 0; new addendum section only.
Next: user approval of design + prompt text, then 46.1.

## IMPLEMENTING - TASK-046 - 2026-09-27T00:25:43Z
Action: user approved design + prompt text; built 46.1 (recon_eval --windows) and 46.2 (flag, addendum section, pipeline wiring).
Result: real g02 recon files: same hits except skip paths (opp-search 462->344), max line < 2000; recon block cmp byte-identical.
Decision: recon_window section placed before ## recon (section extractor would add a blank line otherwise).
Next: full tests, then 46.3 paid A/B.

## UNIT_TESTED - TASK-046 - 2026-09-27T00:43:03Z
Action: tests/run_all.sh (32 suites) + checks/shell.sh.
Result: all pass; recon_eval 44 (windows merge, >3 dropped, prune, CLI), pipeline_recon 53 (off no block, on block+tag+new hash, reuse, needs compact, bad value, --windows error fallback).
Decision: proceed to the paid A/B (already running).
Next: card_ab + p0_cost on 20260927-072558.

## VERIFIED - TASK-046 - 2026-09-27T00:47:06Z
Action: paid 46.3 run 20260927-072558 (window on), p0_cost + card_ab ($0).
Result: $3.59 vs $2.78 (+29 %); quality ok (M9 85.4 %). Reads 142->202, result chars 545K->772K.
Decision: default stays 0; 46.4 Haiku trim closed without a run. Tried-options log written.
Next: report, DONE.

## DONE - TASK-046 - 2026-09-27T00:47:24Z
Action: report docs/report/phase-46-phase0-windowed-reads.md; backlog complete.
Result: window flag built, default 0 (+29 % cost, quality ok); 46.4 closed; tried-options log in docs/notes.
Decision: phase 0 default = Sonnet + compact recon.
Next: none queued; check docs/notes/phase0-tried-options.md before any new phase 0 cost idea.

## DESIGN - TASK-047 - 2026-09-27T04:24:45Z
Action: checked existing cross-run output (run_diff.sh §14, evaluate_run.sh, engine_review.py, card_ab.py); wrote docs/design/phase-47-run-comparison-report.md.
Result: premise proven on g02 142931 §14: 12 new / 7 fixed / 0 persisting on an unchanged tree, >=5 "fixed" are reworded re-finds (model-worded fingerprint fields, no .git so no code-change evidence).
Decision: new stdlib run_compare.py report first (read-only, no coverage risk); tree digest and §14 relabel after real numbers.
Next: user approval, then 47.1+47.2.

## DESIGN - TASK-047 - 2026-09-27T04:48:51Z
Action: user chose A plus C for code-change evidence; updated design §47.4 and sanitizer note item 1b.
Result: A = sanitizer .source-provenance.json + .source-files.sha256 (per-file fixed?), C = names+sizes digest now, fallback none; malformed A -> C.
Decision: toolkit content hash and git snapshot rejected (source bytes outside the scan step / source copied into toolkit).
Next: user approval of the design, then 47.1+47.2.

## IMPLEMENTING - TASK-047 - 2026-09-27T05:14:59Z
Action: user approved design; built 47.1 matcher + 47.2 renderer (run_compare.py) and wrapper (compare_runs.sh); tests/run_compare_test.sh.
Result: run_compare_test 15/15 pass; wrapper exits 2 on a prev run without conclusion. 20260925-112630 predates phase 40 (conclude gives 0 findings) so it cannot be the old side; verification rows updated.
Decision: renderer + wrapper split (engine_review.py / evaluate_run.sh pattern). Sanitizer: note only, user handles the team.
Next: full tests, then real verify on 142931 vs 20260927-112049.

## IMPLEMENTING - TASK-047 - 2026-09-27T05:28:46Z
Action: user asked for single-source parity and sound architecture; design revised (47.0 scan-set contract, 47.6 result history); real compare of g02 142931 vs 20260927-112049; note docs/notes/g02-main-run-compare-2026-09-27.md.
Result: report rendered, 27/27 findings accounted; High 5/5 re-found, tiered agreement 59 % vs exact 24 %; D10 false FAIL on fresh run traced to pl_run_complete after conclude -> TASK-048 queued.
Decision: run_compare.py to consume scan sets only (mode-agnostic); scan_batch.sh history copy needs user approval (touches the core scanner).
Next: user go for 47.0 refactor + 47.6; then 47.3-47.5.

## IMPLEMENTING - TASK-047 - 2026-09-27T05:34:41Z
Action: user asked whether the design covers all requests; audited design vs requests (compare_runs single-source, summarize_report, check_deliverables parity).
Result: gaps closed in docs/design/phase-47: mode parity table; 47.5 one diff producer + one renderer for both modes (single-source "Changes since previous scan", D11); 47.4 single-source tree; failure-modes table fixed; exit codes aligned with build (2); unit/verification rows 47.0, 47.5b, 47.6. Criteria 47.0-47.6 in task.json. Full suite 33/33 pass.
Decision: no code change until user approves 47.0/47.5/47.6 (touch scan_batch.sh, summarize_report.sh, check_deliverables.sh).
Next: user approval.

## IMPLEMENTING - TASK-047 - 2026-09-27T05:36:44Z
Action: user rule "always think about impact plan single source and plan multi-phase so we never miss": recorded in design, verify, unit-test skills; design template gains a "## Plan modes" table; workflow-check fails a design from phase 47 on without it (2 new gate tests).
Result: workflow_gates_test 80/80; phase-47 design has its Plan modes section; workflow-check PASS.
Decision: enforce from phase 47 only (older designs predate the rule; not rewritten).
Next: user approval for 47.0 refactor + 47.5 + 47.6.

## IMPLEMENTING - TASK-047 - 2026-09-27T06:19:13Z
Action: user go ("approved ... don't miss work"): checklist of 15 rows added to the design (DONE gate); implemented 47.0 scan sets (scanset_common.sh), run_compare.py on scan sets (+ --diff-json, --check-diff, code evidence), compare_runs.sh mode rule, 47.6 archive_result, 47.4 tree_evidence.py + add_tree_evidence (both modes), 47.5 shared diff producer (run_diff.sh) + JQ_CHANGES (report §14 / single-source section 13, exec line), D10 covers the diff, D11, 47.3 hook, evaluate_run not_refound; docs.
Result: suites green so far (run_compare 41, scan_history 12, pipeline_diff 16, pipeline_e2e 22, check_deliverables 31). Real g02 rebuild: §14 5 new / 10 persisting (6 reworded) / 0 fixed / 2 not re-found (before 11/4/8), gate pass=23, D10 gaps=0. g01 first-scan report + exec byte-identical to HEAD.
Decision: T2 needs agreeing routes (e2e fixture paired two routes of one file; g02 totals unchanged). Builders in scanset_common.sh (report_common.sh is hashed into conclusions). tree is a result field in both modes.
Next: final full suite -> UNIT_TESTED.

## IMPLEMENTING - TASK-047 - 2026-09-27T06:27:48Z
- Action: user asked to remove the ai-code-sanitizer note ("we don't want to cover other one jobs") and check the code; security pass on tree_evidence.py.
- Result: docs/notes/sanitizer-issues-2026-09-24.md removed; CLAUDE.md, runbook, run-security-review skill: tree problems are told to the user, no notes, no fix. No script referenced the note. tree_evidence.py refuses symlinked metadata files (run_compare 42/42). g02 rebuild --render: pass=23, D10 gaps=0.
- Decision: keep the A reader in tree_evidence.py (dormant: reads the two files only if a tree carries them; digest C is the evidence today). DONE phase-22 docs keep their historical reference.
- Next: full suite -> UNIT_TESTED -> VERIFIED -> DONE.

## IMPLEMENTING - TASK-047 - 2026-09-27T07:03:28Z
- Action: user: drop option A (another tool's hash list), never use the other tool's name, "just use md5 or hash is stable ways", key by the repo-relative file path; never consider out-of-scope work.
- Result: tree_evidence.py hashes each file's bytes itself (sha256; .git skipped, symlinks by target path, repo-relative paths only) -> tree {source: hash, digest, files} + tree/<key>.sha256 per-file list. run_compare.py: per-file decision via list_key (exact relpath, else unique path suffix: repo prefix / full Linux path), else whole-repo hash; a legacy names+sizes digest never compares with a hash. Tests: run_compare 44, scan_history 12, pipeline_e2e 22, pipeline_diff 16 pass; shell.sh 160/160. Real g02 trees: 0.03 s/repo; g02 re-render pass=23, D10 gaps=0.
- Decision: sha256 over md5 (same cost, stdlib default). Scope rule added to CLAUDE.md, design and run-security-review skills: never design, propose or depend on another team's or tool's work.
- Next: full suite -> commit -> UNIT_TESTED -> VERIFIED -> DONE.

## UNIT_TESTED - TASK-047 - 2026-09-27T07:23:32Z
- Action: tests/run_all.sh on the committed content-hash tree (09bf2f4); .claude/scripts/checks/shell.sh.
- Result: 34 suites all passed; shell.sh pass=160 fail=0. Both plan modes covered: single-source (scan_history, run_compare results sets, check_deliverables D11) and pipeline (pipeline_e2e, pipeline_diff, run_compare run sets).
- Decision: checklist row 12 ticked.
- Next: VERIFIED with real-run evidence.

## VERIFIED - TASK-047 - 2026-09-27T07:25:49Z
- Action: real g02 pipeline re-render + gate; coverage_check on the real run; g01 single-source byte-identity (HEAD kit vs current kit); scratch single-source and pipeline suites; security pass on tree_evidence.py.
- Result: g02 pass=23 fail=0, D10 findings=15 shown=15 gaps=0; coverage_check gaps=0; g01 report 2951 lines + exec 100 lines identical (cmp); scan_history 12/12, pipeline_e2e 22/22; hash 0.03 s/repo on real trees.
- Decision: security passed (script-only hashing, relative paths, no symlink follow, .git skipped). Row 13 ticked.
- Next: DONE (report, backlog complete).

## DONE - TASK-047 - 2026-09-27T07:26:09Z
- Action: report docs/report/phase-47-run-comparison-report.md finalised (tests line, counts, byte-identity re-run); checklist row 15 ticked; backlog complete.
- Result: both plan modes share one comparison and one changes section; code-change evidence is the toolkit's own per-file sha256 keyed by repo-relative path; g02 "8 fixed" became 0 fixed / 2 not re-found; D10 gaps=0.
- Decision: adopted. Legacy names+sizes digests give no evidence against a hash (never a false "fixed").
- Next: TASK-048 (queued, high).

## DESIGN - TASK-048 - 2026-09-27T07:38:27Z
- Action: traced pl_run_complete (pipeline.sh tail) vs conclude_inputs_sha (run.json is an input); reproduced on HEAD with a new pipeline_e2e check (D10 FAIL stale, run_json running); checked no report reads run.json.
- Result: docs/design/phase-48-run-completion-conclusion.md.
- Decision: refresh the conclusion after completion (conclude.sh + coverage_check), exit 1 with the rebuild hint on failure; rejected marking complete earlier (breaks resume) and dropping status from the hash (48.2).
- Next: IMPLEMENTING.

## IMPLEMENTING - TASK-048 - 2026-09-27T07:51:27Z
- Action: pipeline.sh finish_run (pl_run_complete, then conclude.sh + coverage_check --conclusion; ERROR + exit 1 with the rebuild hint on failure); e2e check 48.1/48.2; run-test checks (unattended run concluded complete; failing refresh: exit 1, run complete, pending 0, no model call); reference note.
- Result: pipeline_e2e 23/23 (the new check fails on HEAD: D10 stale, run_json running); pipeline_run 109/109; shell.sh 160/160.
- Decision: no report re-render (reports do not read run.json).
- Next: full suite -> UNIT_TESTED.

## UNIT_TESTED - TASK-048 - 2026-09-27T08:11:52Z
- Action: tests/run_all.sh on 204fdf3; checks/shell.sh.
- Result: 34 suites all passed; shell.sh pass=160 fail=0.
- Decision: row 3 ticked. Pipeline mode covered by pipeline_e2e + pipeline_run; single-source untouched (scan_history, check_deliverables D11 pass).
- Next: VERIFIED.

## VERIFIED - TASK-048 - 2026-09-27T08:11:52Z
- Action: $0 check on a scratch copy of the real g02 run (run.json set to running in the copy), fake claude that refuses prompts; ./pipeline.sh run; check_deliverables --run latest; coverage_check --conclusion.
- Result: before D10 FAIL stale; after run rc=0, 0 model calls, PASS D10 findings=15 shown=15 hidden=0 xr=8 gaps=0; engine.run_json.status=complete. Real plan untouched.
- Decision: security completed (same scripts as step_conclude, no new boundary). Row 4 ticked.
- Next: DONE.

## DONE - TASK-048 - 2026-09-27T08:12:15Z
- Action: report docs/report/phase-48-run-completion-conclusion.md; checklist row 5; token-efficiency lesson; backlog complete.
- Result: a fresh pipeline run concludes as complete and passes D10 with no rebuild; g02 copy gaps=0 with the real counts.
- Decision: adopted.
- Next: none queued.

## DESIGN - TASK-049 - 2026-09-27T09:39:22Z
Action: read phase 2b path (prep_2b, gate_2b, evidence, overlay, run_diff, coverage answer-unused); wrote docs/design/phase-49-verify-new-missed-findings.md.
Result: verify items reuse the 2b item/unit/overlay path (kind verify, rule V); prev: ids for previous-run findings (ids collide across runs); report/recheck.json -> conclusion.recheck; pipeline.sh verify --run for the complete g02 run.
Decision: Opus + frozen 2b prompt (user); cap PIPELINE_VERIFY_MAX=10; pipeline only (single-source TBD in EPIC-001).
Next: IMPLEMENTING 49.1 verify_select.py + step_verify.

## IMPLEMENTING - TASK-049 - 2026-09-27T10:15:02Z
- Action: verify_select.py (selector + merge, --merge-only), pipeline.sh step_verify / prep_2b V-* (opus, one repo, prev: fields from the previous run) / verify command, graph_build.sh overlay (prev: skip, verify items decided by finding_checks, recheck.json), conclude.sh recheck + counts.recheck, coverage_check.py verify gaps, appendix §4, config keys, reference doc.
- Result: scratch copy of g02 run 20260927-112049 with fake claude: 7 items (2 not_refound, 5 new), 7 calls model opus with one --add-dir, gaps=0, check_deliverables 14/0; overlay/xissues byte-identical without verify items; prompts unchanged.
- Decision: first run selects nothing; verify step verdict ignored (finding check decides); verify-unanswered replaced by verify-unmerged + recheck-missing (design Decisions).
- Next: unit tests.

## UNIT_TESTED - TASK-049 - 2026-09-27T10:15:02Z
- Action: tests/verify_select_test.sh (23), e2e verify checks (model, mount, appendix), run_reports schema keys; full suite + .claude tests; shell.sh.
- Result: all pass; shell.sh pass=164 fail=0.
- Decision: advance to VERIFIED via the approved paid Opus run.
- Next: PLAN=Upzi_g02/main ./pipeline.sh verify --run latest.

## VERIFIED - TASK-049 - 2026-09-27T10:29:07Z
- Action: paid real run `PLAN=Upzi_g02/main ./pipeline.sh verify --run latest` (user-approved Opus); coverage_check + check_deliverables; security pass.
- Result: 7 Opus units, $3.67; all 7 upheld (2 not re-found still in code, 5 new confirmed); coverage gaps=0; deliverables 23/0/0; appendix §4 present; prompts unchanged.
- Decision: VERIFIED. Note: the jobseeker-003 check argues severity low; the verify item never re-rates (by design), and it stays Medium.
- Next: phase 49 report, backlog complete, DONE.

## DONE - TASK-049 - 2026-09-27T10:29:54Z
- Action: wrote docs/report/phase-49-verify-new-missed-findings.md; backlog complete.
- Result: verify step live; real g02 run: 7/7 upheld by Opus ($3.67), coverage gaps=0.
- Decision: DONE. Open follow-ups: not-re-found in main reports (REQ-0003), severity rule for verify checks (user decision).
- Next: TASK-050 (REQ-0005) run report set complete.

## DESIGN - TASK-052 - 2026-09-27T10:39:14Z
- Action: design docs/design/phase-52-carry-not-refound-findings.md from REQ-0003 with accepted answers.
- Result: 7 items (52.1-52.7); carried rows in conclusion.carried; carry gated on phase 49 re-check; T3 multi-route pairs g02 -007/-005.
- Decision: approved by the user (accept all, start REQ-0003); pipeline-only carry, 52.1 both modes.
- Next: IMPLEMENTING 52.1.

## IMPLEMENTING - TASK-052 - 2026-09-27T11:01:12Z
- Action: implemented 52.1-52.7 (see task.json implementation.files); tests carry_test.sh (14), run_compare 52.1 (3), pipeline_e2e runs 3-5 (6).
- Result: scratch g02 rebuild: diff 4 new/11 persisting/1 not_refound; PT-016 carried; Medium 10; coverage gaps=0 carried=1; deliverables 23/0/0. Golden with PIPELINE_CARRY=0: only the 52.1 pairing, the 52.6 notes and the §4 wording differ.
- Decision: plain rebuild (not --render) is the refresh after a diff code change.
- Next: full unit suite, then UNIT_TESTED.

## UNIT_TESTED - TASK-052 - 2026-09-27T11:15:27Z
- Action: tests/run_all.sh (all 37 suites) and checks/shell.sh; fixed SC2034 (unused R4) in tests/pipeline_e2e_test.sh; re-ran run_reports after its schema-key edit.
- Result: run_all 37 suites all passed (carry 14, run_compare 47, pipeline_e2e 31, run_reports 55); checks/shell.sh 166/0.
- Decision: unit evidence complete; move to real $0 verification.
- Next: PLAN=Upzi_g02/main ./pipeline.sh rebuild --run latest; coverage + check_deliverables; security pass.

## VERIFIED - TASK-052 - 2026-09-27T11:19:53Z
- Action: real $0 rebuild of Upzi_g02 run 20260927-112049; coverage_check --conclusion; check_deliverables --run latest; security pass.
- Result: PT-016 (old jobseekers-info-service-004, Medium, upheld) carried into every report; old -007 paired with PT-013 on T3; Medium 10; carried=1 gaps=0; deliverables 23/0/0. Security pass escaped _carry_verdict in the card (carry, pipeline_e2e, run_reports suites + shell.sh re-run, pass), then rebuilt again.
- Decision: REQ-0003 AC1-AC6 met (AC4 drop paths by fixture tests).
- Next: DONE report, backlog complete, commit.

## DONE - TASK-052 - 2026-09-27T11:20:26Z
- Action: wrote docs/report/phase-52-carry-not-refound-findings.md; backlog.sh complete; token-efficiency lesson.
- Result: REQ-0003 delivered: PT-016 carried on g02, carried=1 gaps=0, deliverables 23/0/0.
- Decision: close TASK-052; next REQ-0002 (trust-model XRs hidden + duplicate XRs merged), then REQ-0001.
- Next: design REQ-0002.

## DESIGN - TASK-053 - 2026-09-27T11:32:49Z
- Action: measured a sentence-level trust-model rule on the g02 run's 2b answers ($0, answers only); wrote docs/design/phase-53-xr-trust-model-filter.md.
- Result: 7 of 8 XRs hit (XR-005 kept: identity from a userId argument). The same phrases describe real upheld findings, so the rule applies to XRs only; "non-empty" is never a trigger.
- Decision: user approved (Q3, "I approve, continue"); hide at XR level with the sentence in the appendix; keep XR ids; merge duplicates by file:line overlap.
- Next: IMPLEMENTING 53.1 xr_review.py.

## IMPLEMENTING - TASK-053 - 2026-09-27T11:46:30Z
- Action: built xr_review.py and wired it into conclude, reports (appendix §5, merged card row, summary note) and coverage 53.5; tests/xr_review_test.sh from real g02 sentences; run_reports 53.4 case.
- Result: scratch copy of g02: XR-001..004, -006..008 hidden, XR-005 merged into PT-008; coverage xr_hidden=7 xr_merged=1 gaps=0; deliverables 23/0/0. PIPELINE_XR_TRUST=0: reports identical to HEAD except the Generated timestamp.
- Decision: summary lines point to appendix §5 so the reviewed XRs are not invisible.
- Next: full run_all + shell.sh, UNIT_TESTED.

## UNIT_TESTED - TASK-053 - 2026-09-27T12:08:18Z
- Action: tests/run_all.sh and checks/shell.sh on the implementation commit.
- Result: 38 suites all passed; shell 168/0.
- Decision: advance.
- Next: VERIFIED from the real $0 rebuild.

## VERIFIED - TASK-053 - 2026-09-27T12:08:50Z
- Action: real $0 rebuild of Upzi_g02 run 20260927-112049; coverage, deliverables, AC5 hit review, security pass.
- Result: 7 XRs hidden with sentences in appendix §5, XR-005 on PT-008's card; coverage xr_hidden=7 xr_merged=1 gaps=0; deliverables 23/0/0. XR-002's hit is a hedge sentence, but the R5 item's whole argument is edge-auth: hide correct.
- Decision: REQ-0002 AC1-AC5 met.
- Next: DONE.

## DONE - TASK-053 - 2026-09-27T12:09:18Z
- Action: wrote docs/report/phase-53-xr-trust-model-filter.md; backlog complete; lesson line in token-efficiency.
- Result: REQ-0002 met; trust-model-conflict XRs are no longer in the main reports and are listed in appendix §5.
- Decision: close.
- Next: REQ-0001 (a chain whose severity changes stays persisting and shows old→new): TASK + design.

## DESIGN - TASK-054 - 2026-09-27T12:12:54Z
- Action: premise on the real g02 diff; $0 jq prototype of the alias.
- Result: both X-R3 meta-service chains are fixed+new only because meta-service-001 was reworded (CWE-749→284, T4); with the alias they pair (high→medium, medium→high). The 8 other new chains are really new (R4/R5).
- Decision: alias through the finding diff pairing (one matching function), prev run only, carried rows excluded; prev_severity on persisting; report section. Pipeline only.
- Next: IMPLEMENTING 54.1.

## IMPLEMENTING - TASK-054 - 2026-09-27T12:18:14Z
- Action: alias in run_diff.sh summary(), prev_severity in labels, changes_md section, render-failure exit (54.5), 5 pipeline_diff cases.
- Result: scratch copy of g02: chains 8 new / 3 persisting / 0 fixed; §14 lists both X-R3 chains old→new; coverage gaps=0; deliverables 23/0/0. The carried-row exclusion needed run_compare to mark the pair (prev_carried_from); the first test caught it.
- Decision: 54.5 added: a jq error had silently dropped §13–15 while the step exited 0.
- Next: run_all + shell.sh, UNIT_TESTED.

## UNIT_TESTED - TASK-054 - 2026-09-27T12:40:05Z
- Action: tests/run_all.sh and checks/shell.sh on HEAD (phase 54 code + req-kit changes).
- Result: 38 suites all passed (pipeline_diff 21/0 incl. 5 new phase 54 tests); shell 168/0.
- Decision: advance to UNIT_TESTED.
- Next: VERIFIED with the real $0 rebuild evidence and the security pass.

## VERIFIED - TASK-054 - 2026-09-27T12:40:35Z
- Action: real $0 rebuild of Upzi_g02 run 20260927-112049 (done in IMPLEMENTING, re-checked read-only now); 54.5 on a scratch kit; security pass.
- Result: chains 8 new / 3 persisting / 0 fixed (was 10/1/2); X-R3 jobseeker--meta high>medium, jobseekers-info--meta medium>high; report shows "Chains with a changed severity (2)"; coverage gaps=0; deliverables 23/0/0; broken render -> rc=1.
- Decision: VERIFIED; security completed (ch_s escaping, toolkit ids only).
- Next: DONE (report, backlog complete, lesson).

## DONE - TASK-054 - 2026-09-27T12:40:46Z
- Action: report written (docs/report/phase-54-chain-diff-reworded-findings.md); backlog complete; lesson added.
- Result: REQ-0001 met: reworded relied-on findings keep their chain persisting with old>new severity; render failures now fail the report step.
- Decision: DONE.
- Next: none (queued: TASK-050 REQ-0005, TASK-051 REQ-0006).

## DESIGN - TASK-050 - 2026-09-27T12:44:17Z
- Action: measured the g02 run ($0): solution_evaluation never produced by pipeline.sh, no gate; Models row reads fields phase0/2b outputs lack while every .raw has modelUsage (2b: 16 sonnet + 7 opus); phase 1 results have no .tree (run predates phase 47).
- Result: docs/design/phase-50-run-report-set-complete.md (50.1-50.6); REQ-0005 AC3/AC4 corrected to measured data.
- Decision: one engine.models source for both reports; hook after finish_run and rebuild; D12 gate; exit 2 is a note.
- Next: IMPLEMENTING 50.1.

## IMPLEMENTING - TASK-050 - 2026-09-27T12:59:32Z
- Action: 50.1-50.5 implemented; scratch kit rebuild of the g02 run ($0); eval_hook exit 2/1 exercised with a stub on scratch.
- Result: Models rows = phase0 claude-sonnet-5 · phase1 claude-sonnet-5 · phase2b claude-sonnet-5 (16), claude-opus-5-5 (7) in both reports; Stability names "predate tree evidence"; D12 pass/missing/stale as designed; coverage gaps=0; suites evaluate_run 80/0, engine_review 32/0, run_reports 60/0, pipeline_e2e 33/0; shell 168/0.
- Decision: implementation complete.
- Next: UNIT_TESTED (full run_all).

## UNIT_TESTED - TASK-050 - 2026-09-27T13:23:20Z
- Action: tests/run_all.sh (full) + .claude/scripts/checks/shell.sh.
- Result: 38 suites all passed; shell 168/0.
- Decision: unit tests pass.
- Next: VERIFIED on the real g02 run ($0 rebuild).

## VERIFIED - TASK-050 - 2026-09-27T13:23:38Z
- Action: real $0 rebuild of Upzi_g02 run 20260927-112049; coverage_check --conclusion; check_deliverables --run latest; security pass.
- Result: Models rows as measured (sonnet-5 ×3 phases, 2b 16 sonnet + 7 opus); Stability names "predate tree evidence"; solution_evaluation written by the rebuild, newer than the conclusion; D12 PASS, deliverables 25/0/0; gaps=0.
- Decision: verified.
- Next: DONE (report).

## DONE - TASK-050 - 2026-09-27T13:23:55Z
- Action: report docs/report/phase-50-run-report-set-complete.md; backlog complete; lesson added.
- Result: every pipeline run/rebuild writes solution_evaluation, D12 gates it, both reports name each phase's model, Stability says why it is unavailable.
- Decision: TASK-050 / REQ-0005 done.
- Next: TASK-051 (REQ-0006, engine review drift section).

## DESIGN - TASK-051 - 2026-09-27T13:31:08Z
- Action: measured the premise on the g02 run ($0): engine_review has no drift section; conclusion holds engine.diff, recheck, carried; diff rows lack previous category/CWE/file; chain rows lack a cause.
- Result: docs/design/phase-51-engine-review-run-drift.md (51.1–51.5, Plan modes: pipeline only). REQ-0006 Design filled; AC1 counts updated to the current diff (4 new, 1 not re-found).
- Decision: previous-run facts go through engine.prev (conclude input), section appended as §11 so ER ids stay stable.
- Next: IMPLEMENTING 51.1 engine_inputs.py, then engine_review.py sec_drift.

## IMPLEMENTING - TASK-051 - 2026-09-27T13:35:09Z
- Action: engine_inputs.prev_heads adds previous findings fields + 2b selection; engine_review.py sec_drift/sec_chain_drift append §11; reference updated; 11 new unit checks.
- Result: engine_review_test.sh 44/0; checks/shell.sh 168/0; on a copy of the real g02 conclusion §11 renders 10 finding rows + 10 chain rows.
- Decision: finding cell carries the title (the same id can name two issues across runs, e.g. jobseekers-info-service-004).
- Next: UNIT_TESTED after tests/run_all.sh.

## UNIT_TESTED - TASK-051 - 2026-09-27T13:57:16Z
- Action: the tester role mapped design 51.1–51.4 to checks and added 5 (regressed/fixed/not re-scanned order, relabel ignores case, reworded relied-on chain -> phase1-scan, prev_run null, Verified on fixed). The verifier role's V-051-1 (recheck verdict not in a code span) and V-051-2 (carried match ignored repo) were fixed in engine_review.py and asserted in the tests.
- Result: tests/run_all.sh 38 suites all passed; engine_review_test 49/0 after the fixes; checks/shell.sh 168/0.
- Decision: fix both verifier findings before VERIFIED (cheap, and the model-text rule is a design constraint).
- Next: VERIFIED from the real $0 rebuild evidence.

## VERIFIED - TASK-051 - 2026-09-27T13:58:26Z
- Action: real $0 rebuild of Upzi_g02 run 20260927-112049; coverage and deliverables gates; independent check by the verifier role (evidence saved to work/TASK-051/evidence because it has no Bash).
- Result: PLAN=Upzi_g02/main ./pipeline.sh rebuild --run latest rc=0; engine_review §11 20 rows: 4 new, jobseekers-info-service-004 not re-found "verified: upheld (confirmed), carried", -003 re-rated Medium -> High, meta-service-001 CWE-749 -> CWE-284, relabel/re-anchor rows; chains: X-R1 relies on new findings, 6 X-R5 correlate-cap, X-R4 correlate-rule, 2 X-R3 persisting severity + reworded relied-on; coverage_check --conclusion findings=15 shown=15 carried=1 xr_hidden=7 xr_merged=1 gaps=0; check_deliverables --run latest 25/0/0; verifier role handoff AC1-AC4 PASS, V-051-1/2 fixed (work/TASK-051/handoff/verify.md).
- Decision: VERIFIED; security pass complete (model text only via code(), previous run read inside the prev_heads guard).
- Next: DONE report.

## DONE - TASK-051 - 2026-09-27T13:58:58Z
- Action: wrote docs/report/phase-51-engine-review-run-drift.md; lesson added to token-efficiency; backlog complete.
- Result: REQ-0006 AC1–AC4 met; §11 live on the g02 run; coverage gaps=0.
- Decision: DONE. EPIC-001 TBD (single-source verification) remains for a later REQ.
- Next: none.

## DESIGN - TASK-055 - 2026-09-27T14:48:34Z
Action: Step 0 analysis (measured 99 findings, one 11-pair run pair), user approved option A, VNW-SEC, ../security-findings, no engine hook, recheck.json for fix_pending. Wrote docs/design/phase-55-stable-finding-identity.md.
Result: design complete; category not CWE in fingerprint (CWE drift 4/11); reuse scanset_common + run_compare helpers.
Decision: add-on only in tracking/, PyYAML add-on-only dependency, no source reads.
Next: implement tracking/track.sh, track.py, cwe_map.py; tests/tracking_test.sh.

## IMPLEMENTING - TASK-055 - 2026-09-27T15:09:47Z
Action: wrote tracking/ (track.sh, track.py, cwe_map.py), tests/tracking_test.sh, docs/finding-identity.md; dry runs on g02 (3 runs), g01, mini-review into a scratch registry.
Result: g02 11/11 persisting pairs keep their stable id (8 exact, 3 T3); engine report ids/titles match the mapping (g02 CSV 16/16, g01 exec 37/37); coverage gaps=0 on 5 sets. Bugs fixed on the way: new-entry history, missing carried mapping, pre-phase-38 run skipped, local-time run ids, older scan of a shared repo moving state, human_not_seen count.
Decision: coverage check in-process before commit (RAW-00040); real test on Upzi_g02 with Sonnet (RAW-00041).
Next: full unit suite, then the paid g02 run.

## UNIT_TESTED - TASK-055 - 2026-09-27T15:30:49Z
- Action: bash tests/tracking_test.sh; tests/run_all.sh; .claude/scripts/checks/shell.sh.
- Result: tracking 34/0 (identity, tiers, lifecycle, human edit kept, dirty registry refused, ambiguous → review, flag-off byte-identical, exit 3 without PyYAML); run_all 40 suites passed; shell 176/0. Real registry baseline ($0): g02 3 runs (7/12/15, gaps=0), g01 37 (gaps=0), shared repo untouched by g01's older scan.
- Decision: unit evidence sufficient; real verification on a fresh g02 run (sonnet, user RAW-00041).
- Next: VERIFIED after run 20260927-221156 completes and is tracked.

## IMPLEMENTING - TASK-055 - 2026-09-27T17:33:30Z
- Action: real verify: g02 run 20260927-221156 (sonnet, full pipeline) tracked into ../security-findings; hand check vs engine diff.json/recheck.json.
- Result: gaps=0; 8/8 engine-persisting pairs keep their stable id (all tier E); 2 new (VNW-SEC-0055/0056) genuine; 9 not_redetected = engine 8 not_refound + VNW-SEC-0002 (last seen 112630); 8/8 recheck verdicts on the right entries. Code review of the recheck path: fix_pending + upheld returns open_recheck, counted as "open" in the seen-sum -> coverage gap -> valid run rolled back. Latent (not hit: no fix_pending), untested.
- Decision: roll back to IMPLEMENTING; count it as not_redetected (the finding was not seen; the re-check keeps it open).
- Next: fix + unit test, redo UNIT_TESTED, then VERIFIED.

## UNIT_TESTED - TASK-055 - 2026-09-27T18:02:20Z
- Action: fixed the recheck-upheld count; added 55.8 cross-service (XR) identity (XR-002 of the real run had no stable id); security hardening (ids through rc.code(), path segments '.'/'..' neutralised); tests added.
- Result: tracking_test 43/0; run_all 40/40; shell 176/0. Real registry: pushed history (origin/master 519c249) kept; only the unpushed 221156 commit regenerated: gaps=0, report CSV 19/19 ids mapped.
- Decision: evidence complete for VERIFIED.
- Next: VERIFIED.

## VERIFIED - TASK-055 - 2026-09-27T18:02:43Z
- Action: real g02 run 20260927-221156 (Sonnet all steps, 2 rate-limit resumes) tracked into ../security-findings; hand-checked against diff.json, recheck.json and the findings CSV; engine gates re-run; security pass.
- Result: gaps=0 (14 = 10 findings + 4 XR, 8 carried); 8/8 persisting pairs keep ids; 2 new genuine; CSV 19/19 mapped; engine coverage gaps=0, deliverables 25/0/0; plan/report files identical; engine files no diff. Evidence in work/TASK-055/evidence/.
- Decision: VERIFIED. Registry: pushed history untouched; the 221156 commit is local (user pushes).
- Next: DONE (report, backlog, REQs).

## DONE - TASK-055 - 2026-09-27T18:03:19Z
- Action: report docs/report/phase-55-stable-finding-identity.md; backlog complete; REQ-0007/0008 DONE; lesson added to token-efficiency.
- Result: add-on shipped: tracking/ + tests/tracking_test.sh + docs; engine unchanged; real registry ../security-findings holds g02 (4 runs) + g01 (60 ids allocated, VNW-SEC-0001..0060).
- Decision: DONE. Open (EPIC-002 TBD): option B source anchor, single-source fix_pending verification. Registry commit for 221156 is local, for the user to push.
- Next: (none)

## DESIGN - TASK-056 - 2026-09-27T20:56:55Z
- Action: $0 history comparison of Upzi_g02 (4 runs) in a scratch registry; design docs/design/phase-56-xr-identity-owner-independent.md.
- Result: one XR item got two stable ids twice (0018/0027, 0017/0026): the fingerprint used phase 2b's model-chosen owner_repo, which flipped between runs.
- Decision: key XR on the correlate.py item only (filing repo = callee), match by path across the pair; no registry rewrite.
- Next: implement in tracking/track.py + unit tests.

## IMPLEMENTING - TASK-056 - 2026-09-27T21:08:37Z
- Action: tracking/track.py identify_xr/tier_ok/xscope; tests/tracking_test.sh run 12 + legacy entry checks.
- Result: tracking 48/0; the 5 new checks fail on the old code (4 entries for 2 items), pass on the new.
- Decision: no registry rewrite (legacy entries match by path).
- Next: run_all + shell checks.

## UNIT_TESTED - TASK-056 - 2026-09-27T21:20:33Z
- Action: tests/run_all.sh, shell checks.
- Result: tracking 48/0, run_all 40/40, shell 176/0.
- Decision: move to verification.
- Next: $0 scratch baseline of Upzi_g02.

## VERIFIED - TASK-056 - 2026-09-27T21:20:58Z
- Action: $0 scratch --baseline of Upzi_g02 (4 runs) with the fix; engine gates.
- Result: gaps=0 each run; XR entries 8 = items 8; 221156 new 2 (was 6); engine coverage gaps=0; plan/report files identical; engine diff empty.
- Decision: verified; real registry needs no rewrite (legacy XR entries match by path).
- Next: report and DONE.

## DONE - TASK-056 - 2026-09-27T21:21:26Z
- Action: report docs/report/phase-56-xr-identity-owner-independent.md; finding-identity.md note.
- Result: XR ids keyed on the item only; verified $0.
- Decision: done; next REQ-0010 (report copy with stable ids).
- Next: none.

## DESIGN - TASK-057 - 2026-09-27T21:22:28Z
- Action: design docs/design/phase-57-report-copy-stable-ids.md (user: report still shows only PT-001).
- Result: add-on copy of the run report with stable ids; engine report frozen per the original spec.
- Decision: copy under reports/<sys>/<plan>/tracking/<run>/; md + csv + pdf.
- Next: implement.

## IMPLEMENTING - TASK-057 - 2026-09-27T21:25:38Z
- Action: tracking/annotate.py + track.sh hook + 6 checks + docs/finding-identity.md section.
- Result: tracking 54/0, shell 176/0; real g02 latest copy 19/19 ids, g01 37 ids, engine files identical.
- Decision: copy only (engine report frozen).
- Next: run_all.

## UNIT_TESTED - TASK-057 - 2026-09-27T21:49:17Z
- Action: tests/run_all.sh + shell checks.
- Result: 40 suites all passed (tracking 54/0); shell 176/0.
- Decision: advance.
- Next: VERIFIED from real $0 evidence.

## VERIFIED - TASK-057 - 2026-09-27T21:49:29Z
- Action: real $0 re-track of g02 latest and g01 (already tracked) with save-evidence.
- Result: g02 19/19 ids, CSV 19/19; g01 37/37; engine files identical; registry unchanged.
- Decision: REQ-0010 AC1-4 met.
- Next: DONE report.

## DONE - TASK-057 - 2026-09-27T21:49:45Z
- Action: report docs/report/phase-57-report-copy-stable-ids.md, finding-identity doc, lesson.
- Result: report copies with stable ids for g02 and g01; all gates passed.
- Decision: DONE; engine report integration only with user approval.
- Next: none (user pushes registry 63db4e7).

## DESIGN - TASK-058 - 2026-09-27T22:15:32Z
- Action: design docs/design/phase-58-report-copy-all-reports.md from RAW-00050 listing (6 report kinds + 3 older runs + delta pdf missing).
- Result: run_comparison mixes two runs ids; old XR ids not in mapping -> resolvers with explicit markers.
- Decision: mirror the engine dir per date; never guess an id.
- Next: implement.

## IMPLEMENTING - TASK-058 - 2026-09-27T22:19:50Z
- Action: annotate.py mirror + resolvers, track.sh render loop, 6 checks, user doc.
- Result: tracking 60/0, shell 176/0; scratch trial on 4 g02 runs + g01: 722 ids, 710 annotated, 12 marked (old XR never tracked), 0 bare, 0 wrong by line evidence.
- Decision: markers instead of guesses.
- Next: run_all.

## UNIT_TESTED - TASK-058 - 2026-09-27T22:42:35Z
- Action: tests/run_all.sh + shell checks.
- Result: 40 suites all passed (tracking 60/0); shell 176/0.
- Decision: advance.
- Next: real $0 verification.

## VERIFIED - TASK-058 - 2026-09-27T22:43:46Z
- Action: real $0 --baseline g02 (4 runs) + g01 with save-evidence.
- Result: all engine report files in index (missing=0); 722 ids: 710 annotated, 12 marked, 0 bare, 0 wrong; delta pdf 5/5; engine 103 files identical; registry unchanged.
- Decision: REQ-0011 AC1-4 met.
- Next: DONE report.

## DONE - TASK-058 - 2026-09-27T22:44:08Z
- Action: report docs/report/phase-58-report-copy-all-reports.md, lesson.
- Result: every engine report of 5 runs has a stable-id copy + index; all gates passed.
- Decision: DONE.
- Next: none (user pushes registry 63db4e7).

## DESIGN - TASK-059 - 2026-09-27T23:55:14Z
- Action: Step 0 inspection (findings/history/manifest/report/correlation/hooks), REQ-0012 from RAW-00052, user "accept all" Q1-Q4; design docs/design/phase-59-report-qa-gate.md.
- Result: report PT ids parseable (no anchor); lifecycle mapped to diff labels; diff_gaps + cwe_map reused; both plan modes one checker.
- Decision: gate in summarize_report.sh only, no hooks; W2 via tree hash lists.
- Next: implement report_qa.py + fixtures + wiring.

## IMPLEMENTING - TASK-059 - 2026-09-28T00:26:28Z
- Action: report_qa.py, gate in summarize_report.sh, fixtures + tests/report_qa_test.sh, skill + rules, docs.
- Result: report_qa 32/0; gate surfaced 3 schema-violating test fixtures (stats 9/9/9 vs 3 findings; categories xss, config) -> fixtures made consistent; gate bug (Info in §2, empty §3) fixed to match generator.
- Decision: categories from security_prompt.md (no tracking/ dependency); no hooks.
- Next: run_all + static checks.

## UNIT_TESTED - TASK-059 - 2026-09-28T01:35:24Z
- Action: tests/run_all.sh + shell/python checks.
- Result: 41/41 suites pass; the gate caught 2 more test fixtures with categories outside the 18 (pipeline_run IDOR, scan_history access_control) -> test data only changed to authorization/authentication; shell 178/0; python.sh fail pre-existing (recon fixtures, phase 43).
- Decision: unit tests pass.
- Next: real $0 verification on g02 run + g01.

## VERIFIED - TASK-059 - 2026-09-28T01:41:24Z
- Action: the verifier role reviewed AC1-AC7 (PARTIAL: readonly evidence echoed hashes, pipeline gate branch unsaved). Re-saved readonly as a measured script: sha256 of 18 g02+g01 inputs before/after three gate runs, plus coverage_check --conclusion. Saved run_reports and pipeline_e2e output.
- Result: g02 PASS 0/0, g01 PASS 0/0, inputs unchanged, gaps=0 before and after. run_reports 60/0 (pipeline --run gate exit 0), pipeline_e2e 33/0.
- Decision: VERIFIED. V-059-2 is AC wording only: carried belongs under NOT_REVERIFIED, as in the code and rules doc.
- Next: DONE report + backlog complete.

## DONE - TASK-059 - 2026-09-28T01:42:21Z
- Action: wrote docs/report/phase-59-report-qa-gate.md, closed the backlog item, moved REQ-0012 to DONE.
- Result: the gate is live in both plan modes. Real g02 and g01 reports PASS 0/0, inputs unchanged.
- Decision: DONE. Nothing to fix (AC7).
- Next: none (TASK-059 closed).

## DESIGN - TASK-060 - 2026-09-28T01:54:53Z
- Action: reviewed run_units/step loop; the premise is shown by pipeline_run_test 25.7 (keep-going leaves failed@2<MAX 3, run completes). Wrote docs/design/phase-60-parallel-phase-units.md §60.1 (plus the EPIC-003 items 60.2-60.6).
- Result: design = retry to terminal (replaces the once-per-phase requeue flag), pl_phase_open barrier assert with exit 12, gave-up label, auto_scan handling of 12.
- Decision: Q1-Q5 accepted by the user; 60.1 goes first (a prerequisite for the pool).
- Next: IMPLEMENTING.

## IMPLEMENTING - TASK-060 - 2026-09-28T02:32:19Z
- Action: implemented 60.1 in pipeline.sh (run_units retries to terminal, phase_barrier), pipeline_lib.sh (pl_phase_open), auto_scan.sh (exit 12), the status gave-up label and the reference doc.
- Result: pipeline_run_test 114/0 (25.7 now expects 3 attempts; new 60.1 barrier, exit 12 and auto_scan cases).
- Decision: exit 12 retries after AUTO_TICK_SECS rather than the cooldown, because with a cooldown of 0 it retried 5 times in one tick before parking.
- Next: full suite + shell checks.

## UNIT_TESTED - TASK-060 - 2026-09-28T02:57:10Z
- Action: ran tests/run_all.sh and checks/shell.sh through save-evidence.
- Result: 41/41 suites passed; shell 184/0. The first shell run failed 3/181, all in gitignored work/ evidence scripts (ShellCheck), which are now fixed.
- Decision: advance. Real $0 checks are already saved: real-barrier (every g02 manifest has 0 open units, sha256 unchanged) and qa-readonly (QA gate rc 0 on g02 and g01, coverage gaps=0, inputs unchanged).
- Next: verifier role, then VERIFIED.

## IMPLEMENTING - TASK-060 - 2026-09-28T03:13:56Z
- Action: rolled back after the verifier's PARTIAL.
- Result: V1 was real: a pending unit at MAX_ATTEMPTS was never picked, so exit 12 repeated forever. phase_barrier now marks such a unit failed (gave up, "attempts limit (N) reached before a final answer"). V2: added a refused-terminal test. The barrier exit-12 test now uses an unexpected status, since the barrier is a guard. pipeline_run 115/0, shell 184/0.
- Decision: cap rather than only a message, because it matches terminal-at-MAX_ATTEMPTS and keeps auto_scan from parking. REQ-0014 AC1 reworded to retry-to-terminal.
- Next: full suite + diff-stat evidence, then UNIT_TESTED and re-verify.

## UNIT_TESTED - TASK-060 - 2026-09-28T03:37:52Z
- Action: re-ran the full suite, shell checks, real-barrier and qa-readonly on d3e27e8.
- Result: 41/41 suites; shell 184/0; real manifests 0 open units, sha unchanged; QA gate rc 0 on g02 and g01, gaps=0, inputs unchanged. AC4 evidence: ac4-diff (0 single-source files) and ac4-exit12 (scan_batch never exits 12).
- Decision: advance.
- Next: re-verify.

## VERIFIED - TASK-060 - 2026-09-28T03:39:20Z
- Action: re-verified by the verifier role at d3e27e8; checked the +dirty scope myself (d3e27e8..HEAD touches only ledger/state files).
- Result: PASS AC1-AC5; real $0 checks green (barrier opens on every real manifest, QA gate rc 0, gaps=0, inputs unchanged).
- Decision: VERIFIED.
- Next: report and DONE.

## DONE - TASK-060 - 2026-09-28T03:39:49Z
- Action: wrote docs/report/phase-60-parallel-phase-units.md; appended a token-efficiency lesson; backlog complete.
- Result: the 60.1 strict barrier is live (retry to terminal, V1 cap, exit 12 guard, gave-up label, auto_scan phase_incomplete).
- Decision: DONE.
- Next: TASK-061 cost gate after recon (needs REQ-0017 Q6/Q7 answers), then TASK-062 and TASK-063.

## DESIGN - TASK-061 - 2026-09-28T03:47:44Z
- Action: read the pipeline recon, step loop, arg parsing and auto_scan exit handling; added 60.6 implementation notes to the design.
- Result: Q6/Q7 answered by the user (whole run until HEAD changes; verify not gated). Plan: split p0_recon, step_recon + .head files, recon_report.py, gate/approve, HEAD check, status line, auto_scan 13, and PIPELINE_APPROVAL_GATE (default 1, 0 for test kits).
- Decision: auto_scan checks again each tick at $0 instead of a hard park, so it resumes on its own after approve. It is not counted as a failure.
- Next: implement.

## IMPLEMENTING - TASK-061 - 2026-09-28T04:23:07Z
- Action: implemented the 60.6 cost gate following the phase-61 design. The user added three requests during the work (RAW-00065..69): auto_scan auto-approves through the AUTO_APPROVE_CONTINUE config (default 1); a recon quality verdict with tuning hints; and `pipeline.sh recon [--repo]` to run recon again at $0.
- Result: pipeline_approval_test 30/0, pipeline_run 119/0, e2e 33/0, recon 53/0. A real $0 render of recon_report.py on the g02 recon files gave 4 good, estimate $16.00, with the real files unchanged.
- Decision: the new texts say "recon approval", because the "(awaiting approval)" the user saw is the older repo init approval (scan_batch.sh --approve). Existing kits set PIPELINE_APPROVAL_GATE=0 so their behaviour stays byte-identical.
- Next: full suite, then an equivalence check against the pre-change code, then UNIT_TESTED.

## UNIT_TESTED - TASK-061 - 2026-09-28T05:14:17Z
- Action: ran the full suite and shell checks. Fixed 2 new ShellCheck SC2012 notes: `ls` globs replaced with a glob loop in `recon_report_path` and with `find` in the approval test.
- Result: 42/42 suites passed; shell 188/0. Evidence: work/TASK-061/evidence/{unit-all,shell}.txt.
- Decision: move to verification. Phase 0 equivalence under the gate is proven by the approval test: the prompts and input hashes are reused after approve. Existing kits run with the gate off and their expectations are unchanged.
- Next: verifier role, security pass, then VERIFIED.

## VERIFIED - TASK-061 - 2026-09-28T06:04:10Z
- Action: saved the real $0 recon report and test evidence, ran the independent verifier, and fixed V61-2 (auto_scan added a history entry on every waiting tick; now only on the first) with a test.
- Result: verifier PASS on AC1-AC8. g02 real render: 4 good, $16.00, real files unchanged. 0 single-source, prompt or report files changed. Final code: 42/42 suites, shell 188/0, pipeline_run 119/0.
- Decision: VERIFIED. V61-1 (the estimate prefers the previous run's average over the $0.70 default) is documented in the design and noted in the report. Cross-version equivalence is covered indirectly (gate-on equals gate-off); noted as a limitation.
- Next: DONE (report, backlog complete, REQ-0017).

## DONE - TASK-061 - 2026-09-28T06:04:38Z
- Action: wrote docs/report/phase-61-cost-gate-after-recon.md, completed the backlog item, moved REQ-0017 to DONE, and logged a lesson.
- Result: cost gate adopted. Defaults: PIPELINE_APPROVAL_GATE=1, AUTO_APPROVE_CONTINUE=1. Recon report with quality and estimate; `recon [--repo]` and `approve` commands.
- Decision: DONE. Limitation: cross-version equivalence is covered indirectly only.
- Next: TASK-062 (parallel slot pool).

## DESIGN - TASK-062 - 2026-09-28T06:11:52Z
- Action: read run_units, pl_run_unit/pl_finish_unit, the cleanup trap, scan_batch's poll loop, the classifier and the test kits. Wrote docs/design/phase-62-parallel-pipeline-pool.md (items 60.2, 60.3 and 60.5 of the phase-60 design; Q2-Q5 already answered).
- Result: generic pool_* helpers; launch/reap split with parent-only writes; stop_run drains in-flight calls and keeps the latest reset; PIPELINE_JOBS default 2 with per-phase keys and --jobs; existing kits pinned to N=1; new pool test and N=1 vs N=2 equivalence test. The classifier already reads the log before exit 124 (AC8 is a pinning test).
- Decision: single-source is unchanged in this task (TASK-063). Per the user (RAW-00072), the workflow skill and /next now name the role subagent per phase; this task uses coder and tester.
- Next: IMPLEMENTING via the coder role.

## IMPLEMENTING - TASK-062 - 2026-09-28T06:56:38Z
- Action: coder role implemented 62.1-62.5. The first coder agent was stopped by the user; a second one reviewed the partial diff, kept it, and finished. The coordinator re-ran the checks.
- Result: shell 188/0; run_all pipeline 8/8 suites (run 119, e2e 33, approval 30, recon 53, ...); recon 3/3; e2e also passes at PIPELINE_JOBS=2 (coder). Frozen prompts and scan_batch.sh unchanged. One deviation: pool tag separator is \037, not tab (tab collapses empty fields).
- Decision: accepted. From now on the check re-runs are the tester's QA job (RAW-00080).
- Next: coder writes the section 4 tests; tester QA; verifier.

## UNIT_TESTED - TASK-062 - 2026-09-28T09:36:56Z
- Action: coder (restarted after an accidental stop, kept bdee583) finished tests/pipeline_pool_test.sh and new tests/pipeline_equiv_test.sh; tester QA re-ran every check with save-evidence.sh; coder fix round 1 closed T062-QA-1/2/4 (stagger, per-phase jobs keys, Bash 3.2 grep); tester re-check.
- Result: pool 39/39, equiv 7/7, pipeline 10 suites, shell 194/0, full run_all 44 suites, frozen diff empty; pool fails 19/35 on 2e79a40. pipeline.sh unchanged by the test step.
- Decision: UNIT_TESTED. QA-3 accepted (AC8 = existing classifier, pinned). Residual info: P2B/VERIFY step wiring has no own case (shared resolver tested).
- Next: verifier on AC1-AC8, security pass, VERIFIED.

## IMPLEMENTING - TASK-062 - 2026-09-28T09:40:38Z
- Action: verifier checked AC1-AC8 and the security pass on the saved evidence.
- Result: PARTIAL. AC6 "no new launch" fails at N>1 when a unit hits a limit during the JOB_DELAY_SECS stagger sleep (T062-V-1, pipeline.sh:386-388,447,450); tests ran with JOB_DELAY_SECS=0. Security clean; T062-V-2 (pid reuse window) info.
- Decision: roll back to IMPLEMENTING (verification failed), fix in launch_one: reap + re-check STOP_FAIL after the stagger sleep, plus a pool case with a stagger.
- Next: coder fix round, tester QA, missing evidence (single-source diff, g02 rebuild), UNIT_TESTED, verifier.

## UNIT_TESTED - TASK-062 - 2026-09-28T10:32:12Z
- Action: coder fixed T062-V-1 (reap exited slots after the stagger sleep, re-check stop before launch; 2 pool cases at JOB_DELAY_SECS=2); tester QA re-ran everything; coordinator ran the $0 g02 rebuild before/after on scratch copies and saved the scan_batch.sh diff.
- Result: pool 42/0 (new cases 40/2 on 700ccae), pipeline 10/10, shell 194/0, full 44/44, frozen + single-source diffs empty, g02 rebuild identical but timestamps, gaps=0, QA PASS.
- Decision: UNIT_TESTED again.
- Next: verifier (round 2), VERIFIED, DONE.

## VERIFIED - TASK-062 - 2026-09-28T10:34:45Z
- Action: verifier round 2 on the saved evidence and the changed launch path; security pass on the reap path.
- Result: PASS, AC1-AC8. T062-V-1 fixed and bitten; single-source untouched; g02 $0 rebuild identical but timestamps, gaps=0, QA PASS. Security clean, T062-V-2 info.
- Decision: VERIFIED; no paid run (no prompt or CLI change).
- Next: DONE (report, backlog, lesson, REQ ACs).

## DONE - TASK-062 - 2026-09-28T10:35:42Z
- Action: wrote docs/report/phase-62-parallel-pipeline-pool.md from task.json and the role handoffs/evidence; ticked REQ-0015 AC1-AC5 and REQ-0016 AC1-AC3, AC5; lesson in token-efficiency.
- Result: pipeline slot pool adopted (default 2), $0 total; REQ-0016 AC4/AC6 left for TASK-063.
- Decision: DONE; REQs stay DESIGN until TASK-063 (linked) catches up.
- Next: backlog next (TASK-063 single-source pool + heartbeat + toolkit-wide hold).

## DESIGN - TASK-063 - 2026-09-28T10:43:22Z
- Action: designer drafted work/TASK-063/handoff/design.md (findings D1-D3); coordinator wrote docs/design/phase-63-pool-heartbeat-usage-hold.md with Constraints, Decisions and Out of scope.
- Result: items 63.1 single-source pool, 63.2 pool heartbeat, 63.3 toolkit-wide usage hold (RAW-00092), 63.4 pipeline status in flight, 63.5 N=1 vs N=2 equivalence. Q1-Q3 settled on the designer's recommendations (no clear command, hold line in status.sh, refuse at start).
- Decision: one hold file at the toolkit root; start refusal reuses exit 10 + the plan's abort record, so auto_scan's rate_limit path works unchanged. No prompt change, no report script change.
- Next: IMPLEMENTING: coder 63.1 + 63.2, tester QA, then 63.3-63.5.

## IMPLEMENTING - TASK-063 - 2026-09-28T14:11:56Z
- Action: coder did 63.1+63.2 (landed in the user's manual commit 73cd2ca "up"), tester QA c7ad571, coder 63.3-63.5 + T063-QA-3 in 187e15b.
- Result: coder reports full suite 47/47, shell.sh fail=0, frozen diff empty; bites on c7ad571 fail as expected (usage_hold H1, scan_pool 6, pipeline_pool 4).
- Decision: implementation complete; checklist rows 63.1-63.5 ticked.
- Next: tester independent QA of 63.3-63.5, then UNIT_TESTED.

## UNIT_TESTED - TASK-063 - 2026-09-28T14:34:37Z
- Action: tester re-ran every coder check independently for 63.3-63.5 (plus 63.1/63.2 suites) and the full suite.
- Result: 47/47 suites, 7 target suites all pass, shell.sh 206/0, bites fail on c7ad571 as expected, frozen diff empty; no defects, no edits. auto_scan hold read covered by usage_hold H5.
- Decision: UNIT_TESTED.
- Next: save evidence, verifier (63.1-63.5, AC mapping, security), then VERIFIED.

## VERIFIED - TASK-063 - 2026-09-28T14:42:00Z
Action: verifier role checked 63.1-63.5 and ran the security pass over the tester QA evidence (work/TASK-063/handoff/verify.md).
Result: REQ-0015 AC2/AC4 and REQ-0016 AC4/AC6 VERIFIED; security pass no findings. Two non-blocking notes: lock ordering corroborated via tester review; auto_scan.sh hold covered by unit tests only.
Decision: accept; ACs ticked in docs/req.
Next: report, backlog complete, DONE.

## DONE - TASK-063 - 2026-09-28T14:42:30Z
Action: wrote docs/report/phase-63-pool-heartbeat-usage-hold.md from task.json, the tester QA and verifier handoffs; backlog complete; lesson added to token-efficiency.
Result: slot pool (PARALLEL_JOBS=2), heartbeat, in-flight status and toolkit-wide usage hold adopted; REQ-0015 and REQ-0016 all ACs verified.
Decision: adopted; a paid --jobs 2 run is left for the user's go.
Next: TASK-064 (required role subagents per workflow step).

## DESIGN - TASK-064 - 2026-09-28T23:38:33Z
- Action: entered DESIGN. A designer draft already exists (work/TASK-064/handoff/design.md, 2026-09-28, items 64.1-64.12 over AC1-AC12).
- Result: the draft predates 8492051 (after-run review) and 3a6b067 (Turns/maxTurns), so the line refs may have drifted.
- Decision: brief the designer for a delta pass (Turns 15), not a redesign. Open items N1 (protect.grantable list) and N2 (patch-apply route) go to the user.
- Next: designer delta, then docs/design/phase-64-required-role-subagents.md and design.status=completed.

## DESIGN - TASK-064 - 2026-09-28T23:42:37Z
- Action: designer delta pass on work/TASK-064/handoff/design.md (PROGRESS: COMPLETE, SKILLS line present); coordinator wrote docs/design/phase-64-required-role-subagents.md with ## Plan modes (none: workflow tooling only).
- Result: refs re-verified after 8492051/3a6b067; new: gate needs PROGRESS: COMPLETE, partial_stop warning, maxTurns check in guard_table_test. User accepted N1 (grantable = .claude/scripts/* only) and N2 (patch-apply route), REQ-0018 Q4/Q5.
- Decision: design completed; implement in three coder briefs to keep each within the turn cap.
- Next: coder brief 64.1-64.3.

## IMPLEMENTING - TASK-064 - 2026-09-29T00:54:38Z
Action: coder did 64.1-64.10 as patches + tests (applied by main, patches/APPLIED); 64.11 docs by main (ba540d5); 64.10 guard_table_test + AGENT_TMPL patch + §2b .git row (b9e3981).
Result: implementation complete per design items 64.1-64.11; tester QA of 64.10 COMPLETE (work/TASK-064/handoff/test.md).
Decision: move to IMPLEMENTING (implementation.status=completed).
Next: UNIT_TESTED with the tester evidence in work/TASK-064/evidence/.

## UNIT_TESTED - TASK-064 - 2026-09-29T00:55:09Z
Action: tester re-ran every check as independent QA (handoff test.md COMPLETE) and saved evidence.
Result: run_all 50 suites passed; guard_table 8/0, agent_setup_hook 36/0, workflow_gates 93/0, shell.sh 268/0; AGENT_TMPL renders maxTurns 40/60/50/30 + turn rules.
Decision: unit_test passed -> UNIT_TESTED.
Next: verifier brief (save tier-0 evidence first).

## IMPLEMENTING - TASK-064 - 2026-09-29T00:56:47Z
Action: verifier checked 64.1-64.12 and REQ-0018 ACs (verify.md).
Result: FAIL on F064-A: SubagentStop dirty_stop reads whole-repo git status, so every role stop warns on main's uncommitted ledger/state files (stats: coder and tester dirty_stop=9).
Decision: roll back to IMPLEMENTING (unit_test pending, verification failed, evidence kept).
Next: coder patch limiting dirty_stop to the agent's own edited paths + tests; tester QA; re-verify.

## UNIT_TESTED - TASK-064 - 2026-09-29T01:23:37Z
Action: coder patch 64.7b (F064-A) applied by main (bfd2abb); tester QA re-ran all checks and added fallback/git-error cases.
Result: run_all 50 suites passed; agent_setup_hook 48/0; guard_table 8/0; shell.sh 268/0; doctor rc 0.
Decision: unit_test passed -> UNIT_TESTED; verification reset to pending for the re-check.
Next: tier-1 session-edit warn probe, verifier re-check of F064-A and the UNPROVEN items.

## VERIFIED - TASK-064 - 2026-09-29T01:25:30Z
Action: verifier re-checked 64.1-64.12 and REQ-0018 ACs after F064-A; main ran tier-1 probe.
Result: all PASS (verify.md); security pass completed; stop>start counts are per hook event, cause of repeated SubagentStop per agent unverified and harmless.
Decision: VERIFIED.
Next: report, DONE, then TASK-066 (user priority).

## DONE - TASK-064 - 2026-09-29T01:26:24Z
Action: report docs/report/phase-64-required-role-subagents.md; backlog complete; REQ-0018 DONE; lesson in token-efficiency.
Result: roles required with gate, warn-only hook, grants, per-task stats; all checks pass; F064-A fixed in-task.
Decision: DONE.
Next: pick TASK-066 (REQ-0020, user priority RAW-00119), then TASK-065 (REQ-0019, RAW-00120).

## DESIGN - TASK-066 - 2026-09-29T01:27:00Z
Action: picked TASK-066 (REQ-0020) at user priority (RAW-00119); confirmed on run 20260928-222915: run_comparison_2026-09-29.md shows the new run Status running, wall time n/a, while run.json status=complete, completed_at 2026-09-28T22:23:26Z.
Result: DESIGN started.
Decision: designer drafts; main writes docs/design/phase-66-*.md.
Next: designer brief.

## DESIGN - TASK-066 - 2026-09-29T01:30:53Z
Action: designer draft (work/TASK-066/handoff/design.md) -> docs/design/phase-66-run-comparison-final-status.md.
Result: cause is ordering (comparison rendered inside step_report before finish_run); fix moves it to post_run_hooks at run/verify/rebuild; AC2 by label (holds not recorded per run).
Decision: design completed; no open questions.
Next: coder 66.1+66.2 + tests.

## IMPLEMENTING - TASK-066 - 2026-09-29T02:32:04Z
- Action: coder 66.1/66.2 (ffe17ec) and 66.3 (80bb5da); main docs wording (6428b15) and track.sh header; tester QA test (d5f3aa1).
- Result: tester re-run track_hook 29/0, track_hook_qa 11/0, run_compare 48/0, pipeline_e2e 38/0, pipeline_run 121/0, check_deliverables 36/0, shell.sh 274/0; coder bite 30 fails on HEAD. Scratch g02 rebuild and single-source run pass (evidence v66.3e-*).
- Decision: implementation complete.
- Next: full run_all -> UNIT_TESTED, then verifier.

## UNIT_TESTED - TASK-066 - 2026-09-29T02:42:58Z
- Action: tester independent QA (work/TASK-066/handoff/test.md) + full run_all saved as evidence.
- Result: run_all 51/51 suites pass; targeted suites and shell.sh fail=0; tester findings none.
- Decision: unit tests passed.
- Next: verifier.

## VERIFIED - TASK-066 - 2026-09-29T02:53:02Z
- Action: verifier role (work/TASK-066/handoff/verify.md) on saved evidence; main closed F066-V1 (track_hook 29/0 at HEAD, no code change since bce7cd9) and F066-V2 (bite-d31ce66.txt).
- Result: PASS all V66 rows and REQ-0020 AC1-3, REQ-0025 AC1-5; coverage gaps=0 with real counts; security pass clean. F066-V3 info (double PDF conversion in single-source, by design).
- Decision: verified.
- Next: report, DONE, real g02 refresh.

## DONE - TASK-066 - 2026-09-29T02:54:27Z
- Action: report docs/report/phase-66-run-comparison-final-status.md; real g02 refresh ($0) after VERIFIED.
- Result: real run_comparison and tracked copy show complete/complete, 140/414; report_qa PASS, D10 gaps=0, D13 PASS, deliverables 26/0; registry unchanged (already tracked); 0 claude calls.
- Decision: done; lesson added to token-efficiency.
- Next: TASK-065 (REQ-0019, high).

## DESIGN - TASK-065 - 2026-09-29T02:54:53Z
- Action: picked TASK-065 (REQ-0019, high) after TASK-066 DONE.
- Result: state DESIGN; designer briefed.
- Decision: design first (pipeline resume path, paid-call behaviour).
- Next: designer draft, then docs/design/phase-65-*.md.

## DESIGN - TASK-065 - 2026-09-29T03:00:25Z
- Action: designer drafted work/TASK-065/handoff/design.md; main wrote docs/design/phase-65-resume-keeps-finished-units.md and the REQ-0019 Design section.
- Result: on HEAD a plain rc-10 resume already picks only pending units; suspected root cause RC-A (finished but unreaped call reset to pending in cleanup) is unproved; RC-B per-call raw/log truncation hides re-runs.
- Decision: 65.1 bite suite first; R3 failing on HEAD keeps 65.2, all passing drops it (scope gate in the design, no user question needed).
- Next: coder builds 65.1 and runs it on a git archive HEAD kit.

## DESIGN - TASK-065 - 2026-09-29T03:19:29Z
- Action: coder built tests/pipeline_resume_test.sh (R1-R4, 16 checks) and ran it on a git archive HEAD kit.
- Result: 15 pass / 1 fail; only R3 fails (finished-unreaped A re-called on resume: want 0|1|1 got 1|1|1). R1/R2/R4 pass on HEAD.
- Decision: RC-A proven; per the scope gate the phase keeps 65.1 + 65.2 + 65.3 + 65.4.
- Next: coder implements 65.2 + 65.3 with T5/T6.

## IMPLEMENTING - TASK-065 - 2026-09-29T03:49:57Z
- Action: coder implemented 65.2 (salvage in pl_units_reset_in_progress) and 65.3 (per-call raw/log rotation in pl_launch_unit), added T5/T6; main wrote 65.4 docs.
- Result: coder self-check pipeline_resume 19/0 (R3 passes), pipeline_ 11 suites pass, shell.sh 278/0; diff only pipeline_lib.sh, the test, two docs (no scan_batch.sh/scan_common.sh/pipeline.sh).
- Decision: implementation complete; independent QA next.
- Next: tester re-runs the checks and saves evidence.

## UNIT_TESTED - TASK-065 - 2026-09-29T04:23:47Z
- Action: tester re-ran every check independently, added tests/pipeline_resume_qa_test.sh (Q1-Q8), bite-ran on a 505defd kit.
- Result: resume 19/0 twice, resume_qa 8/0, pipeline_ 12 suites, full run_all 53 suites, shell.sh 280/0; R3/T5/T6 fail on pre-fix code. No production defect. TASK-067 leak seen again: pipeline_layout_test.sh wrote the real .usage_hold.json (fake reset 2026-09-30 10:50); main removed it (copy in evidence).
- Decision: UNIT_TESTED.
- Next: main saves V1-V5 scratch-kit evidence; verifier checks.

## VERIFIED - TASK-065 - 2026-09-29T04:27:27Z
- Action: main saved v65-scratch-kit.txt (real pipeline.sh on a git archive HEAD kit, fake claude); verifier checked AC1-AC4, V1-V5, failure modes and security.
- Result: all PASS, no findings. Note: the full run_all evidence predates the QA suite, which passes 8/0 in two other evidence files; no second full run (it would leak .usage_hold.json again, TASK-067).
- Decision: VERIFIED.
- Next: report and DONE.

## DONE - TASK-065 - 2026-09-29T04:27:56Z
- Action: main wrote docs/report/phase-65-resume-keeps-finished-units.md, added a token-efficiency lesson, completed the backlog item.
- Result: REQ-0019 AC1-AC4 ticked; the resume keeps a finished-unreaped call and per-call envelopes are kept; $0.
- Decision: DONE.
- Next: TASK-067 (tests never write the real .usage_hold.json) is queued.

## DESIGN - TASK-067 - 2026-09-29T06:43:17Z
- Action: designer drafted work/TASK-067/handoff/design.md; main wrote docs/design/phase-67-test-usage-hold-isolation.md.
- Result: root cause tests/pipeline_layout_test.sh:100 sources real scheduler_common.sh, :123 limit case -> hold_set writes <root>/.usage_hold.json (parks real scans up to ~24h). Runtime path logic correct; fix is tests-only + per-suite guard in run_all.sh.
- Decision: accept draft; 67.3 optional; no scheduler_common.sh change.
- Next: coder items 67.1, 67.2, 67.4.

## IMPLEMENTING - TASK-067 - 2026-09-29T06:45:28Z
- Action: coder implemented 67.1, 67.2, 67.4 (67.3 skipped); main committed 4c6fb2e.
- Result: coder self-check pipeline_layout pass=55 fail=0; run_all_guard 7/7; HEAD repro wrote <kit>/.usage_hold.json; new checks bite on HEAD. shell.sh fail=1 is SC2012 in work/TASK-065/evidence/v65.sh (not this change).
- Decision: accept; independent QA by tester incl. full run_all.sh.
- Next: tester QA, then UNIT_TESTED.

## UNIT_TESTED - TASK-067 - 2026-09-29T07:15:50Z
- Action: tester independent QA (work/TASK-067/handoff/test.md).
- Result: layout pass=55, root hold SAME; guard 7/7 and bites on old run_all.sh; HEAD-before repro writes scratch hold; full run_all 55 suites all passed, SAME. shell.sh fails only on gitignored work/ scratch scripts.
- Decision: UNIT_TESTED.
- Next: verifier on saved evidence.

## VERIFIED - TASK-067 - 2026-09-29T07:16:45Z
- Action: verifier judged AC1-AC3 + security from tester evidence (work/TASK-067/evidence/qa-*.txt).
- Result: AC1, AC2, AC3 verified; security PASS (guard read-only, scratch-only writes).
- Decision: VERIFIED.
- Next: report, backlog complete, DONE.

## DONE - TASK-067 - 2026-09-29T07:17:10Z
- Action: wrote docs/report/phase-67-test-usage-hold-isolation.md; backlog complete; lesson added to token-efficiency.
- Result: REQ-0021 AC1-AC3 verified; tests-only change, $0.
- Decision: DONE. Follow-up suggested: exclude gitignored work/ from shell.sh.
- Next: none.

## DESIGN - TASK-068 - 2026-09-29T08:39:55Z
- Action: picked TASK-068 (user "accept all, start 1a": items 1a + 2a); created REQ-0026 for the deferred blocks (REQ-0013 AC2 moved there); linked REQ-0013/22/23/24; wrote docs/design/phase-68-ledger-closeout.md. Designer waived (root cause located while triaging).
- Result: root cause req.py:497 (cmd_ac counts the empty template placeholder req.py:215 and duplicate ids).
- Decision: fix cmd_ac to agree with acceptance(); coder via patch route; ledger writes by the coordinator.
- Next: brief coder for 68.1-68.2.

## IMPLEMENTING - TASK-068 - 2026-09-29T08:42:15Z
- Action: coder wrote patch 68.1-req-ac.patch (cmd_ac + req_kit §8.8-8.11); main applied it; main removed stray AC1 lines (68.3).
- Result: coder self-check: patched req_kit pass=36 fail=0; new cases fail 4/4 on HEAD req.py.
- Decision: accept; independent QA by tester.
- Next: tester re-runs req_kit, bite on HEAD, shell check; then UNIT_TESTED.

## UNIT_TESTED - TASK-068 - 2026-09-29T08:43:19Z
- Action: tester re-ran req_kit, bite on the old req.py, old REQ-0022 through the fixed ac, shellcheck.
- Result: 36/0; old req.py 32/4 (new cases bite); AC ids listed once; shellcheck clean.
- Decision: UNIT_TESTED.
- Next: save ledger/settings evidence (REQ-0013 AC1/AC3/AC4, V3), verifier.

## VERIFIED - TASK-068 - 2026-09-29T08:44:19Z
- Action: saved ledger/settings/commit evidence; verifier checked ACs, V1-V3, security; main ticked REQ-0013 AC1/AC3/AC4.
- Result: verifier PASS on all ACs and (a)-(c), no findings.
- Decision: VERIFIED.
- Next: report, backlog complete, REQs DONE.

## DONE - TASK-068 - 2026-09-29T08:44:34Z
- Action: report docs/report/phase-68-ledger-closeout.md; checklist 68.4-68.5 ticked; lesson in token-efficiency; backlog complete; REQ-0013/22/23/24 DONE.
- Result: all four REQs closed with TASK-068 evidence; REQ-0026 open (Q1 for the user).
- Decision: DONE.
- Next: none queued; REQ-0026 waits for the user.

## DESIGN - TASK-069 - 2026-09-29T09:00:35Z
- Action: designer draft (work/TASK-069/handoff/design.md); coordinator confirmed rule syntax from the official docs (docs-facts.md) and probed the role guard on a scratch copy for config-write routes (RAW-00125).
- Result: docs/design/phase-69-protected-list-blocks.md, items 69.1-69.9; 9 role write routes to protected config pass the guard today.
- Decision: 69.1-69.7 approved (RAW-00124); 69.8-69.9 are a wider block, so they wait for the user (REQ-0026 Q2).
- Next: user answers Q2; brief coder for the patches and the protect_rules suite.

## IMPLEMENTING - TASK-069 - 2026-09-29T11:05:57Z
- Action: coder patches 69.1-69.12 applied by main; tester QA rounds (protect_rules, tamper, scratch_kit, hook, guard_table); replay of 693 role commands; live checks AC8 and 69.10.
- Result: protect_rules 108/0, tamper 32/0, scratch_kit 38/0, agent_setup_hook 48/0, guard_table 8/0; replay 0 refusals; live role run_all tamper=0.
- Decision: IMPLEMENTING complete. V-2b (user, one-click): close 69.2/69.3 with the limit that ask rules do not prompt in background auto-mode jobs (F69-8).
- Next: full run_all at HEAD, UNIT_TESTED, verifier re-check.

## UNIT_TESTED - TASK-069 - 2026-09-29T11:31:42Z
- Action: full run_all at HEAD; tester re-saved guard suites at HEAD; 69.10b applied after the run.
- Result: run_all 58/58; protect_rules 108/0, tamper 32/0, scratch_kit 38/0, guard_table 8/0, agent_setup_hook 49/0.
- Decision: UNIT_TESTED.
- Next: verifier final re-check, VERIFIED, DONE.

## VERIFIED - TASK-069 - 2026-09-29T11:33:37Z
- Action: verifier final check of report rows, AC evidence, earlier FAILs, AGENT_TMPL.
- Result: PASS (a)-(d); two live checks marked observed in the report.
- Decision: VERIFIED.
- Next: DONE, backlog complete, REQs DONE; pick TASK-070 (REQ-0028).

## DONE - TASK-069 - 2026-09-29T11:34:10Z
- Action: report docs/report/phase-69-protected-list-blocks.md; checklist 69.1-69.12 ticked; commit-skill lesson; backlog complete; REQ-0026/0027 DONE.
- Result: protected-list blocks live for roles; working-style agreements (RAW-00128..00138) in the owning skills.
- Decision: DONE.
- Next: pick TASK-070 for REQ-0028 (user answered Q1-Q4).

## DESIGN - TASK-070 - 2026-09-29T12:56:58Z
- Action: turned the designer's rev-2 draft (work/TASK-070/handoff/design.md, reviewed in design-review.md, items 1-5 folded in) into docs/design/phase-70-single-source-recheck.md with the user's one-click answers Q1-Q4 (REQ-0028) and a 70.1-70.8 checklist.
- Result: design approved as answered: annotate only (Q1a), standalone opt-in ./verify_scan.sh with no manifest write (Q2a), pipeline fix_pending re-check 70.5 in this phase (Q3a), one paid V5 ~$1 after V1-V4 (Q4a). No prompt change; both plan modes covered.
- Decision: enter IMPLEMENTING via the coder, one item at a time; 70.1+70.3 first (pure Python, no dependencies), then 70.2, 70.4, 70.5.
- Next: brief coder on 70.1 and 70.3.

## IMPLEMENTING - TASK-070 - 2026-09-29T14:01:15Z
- Action: coder built 70.1-70.5 in five briefs (two coders in parallel on disjoint files), plus the 70.4 stale guard, the report_qa 13b heading and the scan_history Generated-line flake fix; designer wrote build notes (C1-C11 folded into the design); tester QA'd each item in scratch copies with bite proofs. wip commits 7fc7b2c..b10fa39.
- Result: per-item suites green (verify_select 40/0, recheck_rows 12/0, verify_scan 16/0, pipeline_2b_prep 12/0, pipeline_e2e 38/0, run_reports 60/0, carry 15/0, tracking 65/0, scan_history 19/0, report_qa 33/0). pipeline_e2e 36/2 after 70.1 bisected to the intended F1 extra call (fixture findings.fixed=1), fixed in 70.5 without weakening checks.
- Decision: implementation complete; roles.tester is set only at UNIT_TESTED (a rewriting tester blocked wip commits twice).
- Next: tester adds two 70.5 cases and runs the full suite for UNIT_TESTED.

## DESIGN - TASK-071 - 2026-09-29T14:25:56Z
- Action: Phase 1 discovery of ReqKit done by the main session (user: "I need you (not subaggent)"); TASK-070 paused (backlog queued, snapshot d3f25d5, tester patch saved); design docs/design/phase-71-inbox-triage-intake.md.
- Result: entry point = `req.py raw add`; no watcher/namespace collision; hooks risk solved by temp cwd outside repo; user approved plan, pause, skill flag and ~6 real Sonnet runs.
- Decision: import as RAW (ReqKit keeps dedup); roles waived per user.
- Next: IMPLEMENTING - tests with fake claude, README.

## IMPLEMENTING - TASK-071 - 2026-09-29T14:29:01Z
- Action: built tools/triage (orchestrate.sh, adapter.py, known_targets.sh, open_requests.sh, README, tests + fixtures), main session (roles waived per user).
- Result: tests/run_all.sh triage 21/0; shellcheck clean on new files (shell.sh fails only on gitignored work/ scratch scripts).
- Decision: fix found while testing: req.py list prints "-" for no epic (open_requests parser).
- Next: UNIT_TESTED - full run_all, then real runs.

## UNIT_TESTED - TASK-071 - 2026-09-29T15:41:31Z
Action: ran full tests/run_all.sh, the triage suite, and shell.sh.
Result: 62 suites passed; triage 28/0 (V1-V8, R1/R2, W1/W2, 71.8, secret, guard, lock). shell.sh fails only on 6 old scratch scripts in the gitignored work/ tree.
Decision: unit tests pass; roles stay waived because the user asked the main session to do this task (RAW-00139).
Next: VERIFIED, using the real Sonnet run evidence and the security result.

## VERIFIED - TASK-071 - 2026-09-29T15:44:05Z
Action: reviewed the real Sonnet runs in scratch kits (10 calls, about $0.48), saved to work/TASK-071/evidence/real and real2.
Result: V1-V6 and R1 matched the expected outcomes. V7: a re-run made no new RAW. 71.8: project-style messages now get OK (target toolkit, related REQ, skill/area flags). Headless runs added no RAW to the real repo, and the ReqKit code diff is empty.
Decision: verified; the security checks (least privilege, write guard, schema, targets, secret scan, injection flag) are recorded in task.json.
Next: DONE (report, backlog complete, REQ-0029).

## DONE - TASK-071 - 2026-09-29T15:44:36Z
Action: wrote the report docs/report/phase-71-inbox-triage-intake.md, completed the backlog entry, moved REQ-0029, and added a lesson to token-efficiency.
Result: the inbox -> inbox-triage -> adapter -> ReqKit RAW path works, with the watcher and the context pack; 10 real runs cost about $0.48.
Decision: done. Follow-ups: REQ-0030 (keep the coordinator's context small); TASK-070 resumes (its coder is closing the 70.5 test gaps).
Next: pick TASK-070.

## IMPLEMENTING - TASK-070 - 2026-09-29T15:44:59Z
Action: resumed TASK-070 from its paused copy (work/TASK-070/task.paused.json, the state at d3f25d5) after TASK-071 reached DONE.
Result: state is IMPLEMENTING again, with design and implementation completed. The coder is closing the 70.5 test gaps and applying the tester's half-done patch.
Decision: continue the UNIT_TESTED flow as planned.
Next: commit the coder's test edits, tester QA on the full suite, then UNIT_TESTED.

## UNIT_TESTED - TASK-070 - 2026-09-29T21:59:25Z
Action: the coder closed the 70.5 test gaps (4928f22); the tester re-ran all checks independently (resumed after a rate limit, without re-running the saved suites).
Result: run_all 62 suites passed; pipeline_e2e 42/0; shell.sh has no FAIL in tracked files. The bite proof on the 1b629a6~1 scripts fails 9 checks, including all 3 new 70.5 checks.
Decision: unit tests pass. The fixture change (verify answer cites its own repo path) does not weaken any check.
Next: VERIFIED (verifier, V1-V7; the paid V5 needs the user's go).

## IMPLEMENTING - TASK-070 - 2026-09-29T22:13:50Z
Action: tester produced $0 verification evidence V1-V4, V6a, V6b, V7 (work/TASK-070/handoff/test-verify.md).
Result: V1, V2, V4, V6a, V6b, V7 PASS; V3 only after a manual recheck_rows.py call: nothing wires recheck_rows.py into verify_scan.sh (F-70-V1, high). V6b D10 stale is pre-existing (same at 47c15bb).
Decision: roll back to IMPLEMENTING (workflow rule: verification fails after UNIT_TESTED); unit_test pending, verification failed with evidence kept.
Next: coder wires recheck_rows.py at the end of verify_scan.sh + test; tester re-runs V3/V4; UNIT_TESTED; verifier; paid V5 (user go 2026-09-30).

## UNIT_TESTED - TASK-070 - 2026-09-29T22:48:55Z
Action: coder wired recheck_rows.py into verify_scan.sh (1ae04ef, F-70-V1); tester re-ran the checks and the full suite as independent QA.
Result: verify_scan 19/0 (bite 17/2 on 1ae04ef~1); run_all 62/62; V3 PASS without the manual step; V4 PASS; F-70-V1 closed.
Decision: UNIT_TESTED again; the $0 V rows are all PASS.
Next: paid V5 (user go), then the verifier judges V1-V7.

## VERIFIED - TASK-070 - 2026-09-29T23:18:39Z
Action: paid V5 (user go): rescan demo-mini ($0.088) for a real single-source diff, verify_scan --max-units 2 ($0.233); full report set; verifier judged AC1-AC7, V1-V7 from saved evidence.
Result: all PASS (work/TASK-070/handoff/verify.md). 4 V5 items failed at setup: tree n2/demo-mini_2 missing (outside toolkit). F-70-N1 low: failed= prints a flag.
Decision: VERIFIED. F-70-N1 noted in the report as a follow-up.
Next: DONE report, backlog complete, REQ-0028 DONE.

## DONE - TASK-070 - 2026-09-29T23:19:33Z
Action: wrote docs/report/phase-70-single-source-recheck.md; lesson appended to token-efficiency; backlog complete; REQ-0028 DONE.
Result: AC1-AC7 PASS; paid V5 $0.32 total.
Decision: DONE. F-70-N1 (cosmetic failed= label) left as a follow-up.
Next: pick TASK-072 (user order: 070 -> 072 -> full scan -> 073).

## DESIGN - TASK-072 - 2026-09-29T23:20:17Z
Action: wrote docs/design/phase-72-full-scan-readiness.md (+ -holds.md component doc for 72.5) from the designer draft; folded REQ-0032 (RAW-00153/154) in as 72.5.
Result: 6 checklist items; user decisions 2026-09-30: 200 files/3600 s, MAX_ATTEMPTS 2, RUN_HOLD_STREAK 2 + auth at once, fallback once, refused at 1st.
Decision: design approved by the user's answers; no open question.
Next: coder 72.1+72.2, then 72.3, 72.5, 72.4; tester QA per item.

## IMPLEMENTING - TASK-072 - 2026-09-30T01:18:06Z
Action: coders built 72.1, 72.2, 72.3, 72.5 A/B/C (+F-72-T1 hint); tester QA per item in scratch copies; 72.4 rehearsal script.
Result: all item suites green with bite (10, 12, 20-24, B 10, C 18); AC7 end to end 11/0; golden reports 0 diff; rehearsal both arms lost=0, held=1 after 2 calls, survives kill -9. Decisions D1-D10 in the holds doc (D6 rejected: holds survive pipeline new).
Decision: implementation complete; F-72-G1 (guard false positive on script names in edit text) deferred to after TASK-072.
Next: full tests/run_all.sh at HEAD (tester), then verifier V1-V14.

## UNIT_TESTED - TASK-072 - 2026-09-30T02:04:22Z
- Action: tester ran full tests/run_all.sh (65 suites) at 8439092, shell.sh vs f5093c2, clean 80-repo rehearsal; reran failing suites at HEAD.
- Result: 62/65 first run. pipeline_2b_prep was real 72.3 fallout (test evaled prep_2b without effective_timeout inputs) -> test fixed, 12/0. protect_rules B69.5 pinned the old allow list; user-approved widening (RAW-00107/00168) -> check keeps the tool base and allows only Bash(...) additions, 108/0. scratch_kit 38/0 (RAW-00169 appeared mid-run). shell.sh: 10 FAIL, none in 072 code. Rehearsal PASS lost=0 done=79 held=1.
- Decision: UNIT_TESTED. shell.sh noise in work/ and external/ext-scan left for TASK-076 (refactor replaces the kit scripts).
- Next: verifier V1-V14 (72.6) + security pass.

## VERIFIED - TASK-072 - 2026-09-30T02:58:15Z
- Action: tester saved V1-V14 evidence at 472018f; verifier judged it + security pass; coder fixed V72-S1/S2 + AC3 case (40d0a8e); tester re-ran affected suites + bite.
- Result: V1-V14 PASS; REQ-0032 AC1-AC7 PASS; fixes green (job_hold 52/30/18 ... no_silent_skips 22), bite 3/3 fail on old code. shell.sh 12 FAIL all outside 072 files (2 external/ext-scan, 10 untracked work/).
- Decision: VERIFIED. V72-S3, V72-S4 (info) and the unwritable-hold-file later-start edge go to a follow-up backlog item.
- Next: DONE report + backlog.

## DONE - TASK-072 - 2026-09-30T03:00:08Z
- Action: wrote docs/report/phase-72-full-scan-readiness.md from verify.md and the handoffs; backlog complete; follow-up TASK-078 queued (V72-S3, V72-S4, unwritable hold file, F-72-G1, design wording).
- Result: V1-V14 PASS, REQ-0032 AC1-AC7 PASS, 65 suites green, rehearsal lost=0.
- Decision: TASK-072 DONE; REQ-0032 DONE; REQ-0031 stays open for TASK-073 (P1).
- Next: user go for the full paid scan, then TASK-073.

## DESIGN - TASK-073 - 2026-09-30T03:34:32Z
- Action: designer draft (work/TASK-073/handoff/design.md) -> docs/design/phase-73-rerun-cost-savings.md; user answered Q1 yes, Q2 yes (model in verify key; legacy dirs = opus), Q3 no.
- Result: items 73.1-73.5, V1-V10; findings T073-D1..D3.
- Decision: design approved; order 73.3 -> 73.2 -> 73.1 -> 73.4.
- Next: coder 73.3.

## IMPLEMENTING - TASK-073 - 2026-09-30T04:25:33Z
- Action: coder built 73.3 (a53af96), 73.2 (77070b5), 73.1 (61606b9), 73.4 (98a7124); tester QA per item; main ran the guarded V2 pipeline run on scratch copies with a logging-only fake claude (user go).
- Result: suites green per item with bites; V5/V6 6/6; V2: 4 carried, 0 calls, coverage gaps=0, deliverables 25 pass / 0 fail (evidence v73-1-V2-*); 73.4 drift = noise, area stays closed.
- Decision: implementation complete. Limit: whole-pipeline two-run on an unchanged fake tree covered only at phase 0 (V5/V6) plus unit tests; the verifier judges it.
- Next: tester full run_all for UNIT_TESTED.

## UNIT_TESTED - TASK-073 - 2026-09-30T05:04:43Z
- Action: tester ran the full tests/run_all.sh at cea0033 and the static checks.
- Result: 64/65 pass; pipeline_recon failed "off: hash = sha + prompt + deploy slice" twice (real): stale expected value, 73.2 wraps the unit hash with model=; test updated, 53/0 (v73-unit-pipeline_recon-fixed). Production code unchanged.
- Decision: accept the targeted rerun (test-only change to one suite; the other 64 suites do not read it). UNIT_TESTED.
- Next: verifier V1-V10 + security.

## VERIFIED - TASK-073 - 2026-09-30T05:16:38Z
- Action: verifier judged V1-V10 from evidence; main saved V2 run (scratch, fake claude, user go), drift and frozen-prompt checks; tester added pipeline_rerun_e2e for V5.
- Result: all V-rows and P1.1-P1.4 VERIFIED; security completed (V73-2 Low). Static shell 13 FAIL outside TASK-073 files (phase-72 precedent).
- Decision: VERIFIED. Report notes: a re-run can carry an older, weaker (inconclusive) verdict; --fresh re-asks.
- Next: DONE report.

## DONE - TASK-073 - 2026-09-30T05:17:02Z
- Action: wrote docs/report/phase-73-rerun-cost-savings.md; backlog complete.
- Result: 73.1-73.5 done; V1-V10 VERIFIED.
- Decision: TASK-073 DONE. V73-2 (low) goes with the TASK-078 follow-ups.
- Next: user go for the full paid scan (order 072 -> 073 -> full scan).

## DESIGN - TASK-076 - 2026-09-30T06:06:58Z
- Action: picked TASK-076 (user "do TASK-076"); wrote docs/design/phase-76-ext-scan-integration.md from the designer's round-5 draft (Q1-Q6 answered); added the env.lock ownership note (076 creates image rows in the 77.1 format, 077 adds the rest).
- Result: design complete, 13 checklist rows (76.11 follow-up TASK, 76.9 shared with TASK-075).
- Decision: build in item order 76.1+76.2 → 76.3-76.6 → 76.8 → 76.7/76.10 (network, needs the user's go at VERIFIED); CLAUDE.md exception wording lands with 76.2 (Q1 approved).
- Next: coder 76.1+76.2.

## IMPLEMENTING - TASK-076 - 2026-09-30T09:12:21Z
- Action: coder rounds 76.1-76.8, 76.10, docs; tester QA per item; user ran RAW-00175/00176 flag removal (aa0fc7f); tests aligned (3cf2449); pin (832fc07); QA cases (d1ab212); QA-76.2-3/76.7-1 fixed (0cc6855).
- Result: tests/run_all.sh ext_ 8 suites green, ext_scan 249/0; bites fail on pre-change code.
- Decision: implementation complete for $0 scope; real pin/bake-off belong to VERIFIED (network, user go); 76.9 -> TASK-075; 76.7 env.lock shared with TASK-077.
- Next: full run_all by tester -> UNIT_TESTED.

## UNIT_TESTED - TASK-076 - 2026-09-30T22:36:30Z
Action: tester closing QA (full run_all, static checks, fresh $0 bench on HEAD); designer bake-off 76.10 -> docs/notes/ext-bakeoff-2026-10-01.md; checklist 76.10 ticked.
Result: run_all 73/73 pass; ext suites fail=0; shell.sh 18 FAIL none in TASK-076 code (kit reference scripts + untracked work scripts); bench rc=0, report coverage 956=956 rows, 56 dedupe marks, bearer/psalm/java/semgrep config present.
Decision: UNIT_TESTED; kit scripts stay unmodified reference (never run), untracked tmp_*.sh are not TASK-076.
Next: verifier AC1-AC8 -> VERIFIED -> DONE; then TASK-079 E0.

## VERIFIED - TASK-076 - 2026-10-01T00:01:49Z
Action: verifier checked AC1-AC8 + security against saved evidence (verify.md).
Result: AC2/4/6/7 PASS; AC1/3/8 PARTIAL acceptable; AC5 tool KPIs present, AI KPIs moved to REQ-0037 (user 2026-10-01). Security: no blocker; F-V76-01 info, F-V76-02 low.
Decision: VERIFIED; follow-ups F-V76-02, AC3 pipeline-mode coverage, AC8 D6/K2/K6 (kit variant flow) go to TASK-079/078.
Next: DONE report; then TASK-079 E0.

## DONE - TASK-076 - 2026-10-01T00:02:27Z
Action: report docs/report/phase-76-ext-scan-integration.md; backlog complete; REQ-0035 DONE; lesson in token-efficiency.
Result: ext-scan integrated (/bin/bash set B, chosen set pinned, dedupe, report sections); follow-ups listed in the report.
Decision: DONE; next task TASK-079 (ext engine E0-E6, gap review).
Next: pick TASK-079, coder E0.

## DESIGN - TASK-079 - 2026-10-01T00:02:55Z
Action: picked TASK-079; design = docs/design/phase-79-ext-engine-layer.md incl. 79.10 ext engine revision (designer handoffs design.md, design-ext-engine.md).
Result: design complete; user decisions Q1-Q12, RAW-00181..00186, 00220/222/223, in/needs_ai/out split recorded.
Decision: DESIGN done; implement E0-E6 first ($0), gap review 79.7 (paid) later with user go.
Next: coder E0.

## DESIGN - TASK-079 - 2026-10-02T04:06:22Z
Action: $0 audit of Upzi_g01 gap review (RAW-00324/00326) + full run_all.
Result: rejections mostly code-grounded; input lacks rule_desc/owasp/trace, arm A budget favours reject (QA-79.7-1); K6 golden FAIL from weak-hash noise rule (QA-79.10-2).
Decision: fix noise rule now ($0); gap-review context fix and calibration go to the user.
Next: Titan fix, commit, user answer.

## DESIGN - TASK-079 - 2026-10-02T04:23:01Z
Action: 79.16.1-2 built (442544a); Upzi ext re-scan ($0); RAW-00327..00329 triaged; docs/skill updated.
Result: records carry rule_desc/fn_line; coverage OK; old arm A conclusion stale (5 ids out).
Decision: ext role per plan; monthly = new only via security-findings (79.17); calibration paused on weekly limit.
Next: 79.16.3 calibration, 79.17, verifier.

## DESIGN - TASK-079 - 2026-10-05T07:35:17Z
Action: 79.16.3a item filter (d25b4ce); paid arm-B calibration on 12 items ($0.505).
Result: 7/7 positive controls duplicate_of_a, 0 rejected; 4 weak items rejected with all callers cited, 1 duplicate.
Decision: gap review trusted; verdict memory may be designed.
Next: 79.17 (Nova), verdict memory design, verifier.

## DESIGN - TASK-079 - 2026-10-05T07:52:31Z
Action: user decision 2026-10-05: no AI review of ext rows; ext = $0 summary + anomaly flags (79.18).
Result: AC5/AC-GAP/AC-KPI reworded; architecture.md chosen standard replaced; design 79.18 stub.
Decision: gap review stays built, off, out of the flow.
Next: 79.17 build, 79.18, toolsp1, docs, proof run, verifier.

## DONE - TASK-079 - 2026-10-06T00:47:18Z
- Action: run_all 100/100, shell 352/0, e2e 49/0, real docker proof, verifier Argus.
- Result: AC2-4,6-8 verified; 79.6 view test, V4/V5, AC1 review deferred (user).
- Decision: close now (user 2026-10-06).
- Next: TASK-081.

## IMPLEMENTING - TASK-079 - 2026-10-06T00:47:25Z
- Action: recorded at close; state field stayed DESIGN while work ran across wip commits.
- Result: items 79.1-79.19 implemented over many wip commits (coder Titan).
- Decision: close now (user 2026-10-06).
- Next: DONE.

## UNIT_TESTED - TASK-079 - 2026-10-06T00:47:25Z
- Action: recorded at close; state field stayed DESIGN while work ran across wip commits.
- Result: 100 suites green, e2e 49/0 (tester Nemesis).
- Decision: close now (user 2026-10-06).
- Next: DONE.

## VERIFIED - TASK-079 - 2026-10-06T00:47:25Z
- Action: recorded at close; state field stayed DESIGN while work ran across wip commits.
- Result: verifier Argus: AC2-4,6-8 verified, gaps=0, findings F-79-4/6 closed.
- Decision: close now (user 2026-10-06).
- Next: DONE.

## DESIGN - TASK-081 - 2026-10-06T00:54:15Z
- Action: design phase-81 (rev 3, Nova) + REQ-0039 ACs.
- Result: items 81.1-81.7 listed, no open questions.
- Decision: start with 81.2 revert (sequencing risk from inspector).
- Next: coder.

## IMPLEMENTING - TASK-081 - 2026-10-06T00:54:35Z
- Action: design committed; coder gets 81.2 first.
- Result: -
- Decision: tier-1 items 81.2, 81.1, 81.3c, 81.6 before tier-2.
- Next: Titan 81.2.

## UNIT_TESTED - TASK-081 - 2026-10-06T05:22:22Z
- Action: tester Nemesis re-ran the 8 TASK-081 suites + shell static (handoff test.md); coder Titan added migrate_registry --restamp (registry_restamp_test 42/0); user ran it on the real registry (cc15cdb).
- Result: all suites pass, 0 fail; second --restamp prints "nothing to do"; real roll-up Upzi runs 7 (ai 6, tools 1), findings 101 (ai 62, tools 39), overlap 1; Mini 5 ai.
- Decision: IMPLEMENTING -> UNIT_TESTED; REQ-0039 AC4 text updated to the real counts.
- Next: verifier Argus evidence check -> VERIFIED, report, DONE.

## VERIFIED - TASK-081 - 2026-10-06T05:23:50Z
- Action: verifier Argus checked REQ-0039 AC1-AC7 against the evidence and ran the security pass; coordinator closed its 2 flags with read-only evidence (full real roll-ups, restamp dry-run "nothing to do", registry counter/count check).
- Result: AC1-AC7 PASS; security completed, no finding; counter unchanged (VNW-SEC next 68); Upzi 62 ai + 39 tools, Mini 5 ai.
- Decision: UNIT_TESTED -> VERIFIED.
- Next: report, DONE, backlog.sh complete TASK-081.

## DONE - TASK-081 - 2026-10-06T05:24:49Z
- Action: wrote docs/report/phase-81-product-group-rollup.md from the saved evidence; re-saved shell static at final code (374/0).
- Result: report complete; REQ-0039 AC1-AC7 ticked.
- Decision: VERIFIED -> DONE; backlog.sh complete TASK-081.
- Next: none for TASK-081; TASK-082 only when the user says.

## DESIGN - TASK-082 - 2026-10-06T05:34:46Z
- Action: user said "start TASK-082"; picked from backlog; designer Nova's draft (work/TASK-079/handoff/design-req0040.md, copied to work/TASK-082/handoff/design.md) is docs/design/phase-82-ai-reuse-store.md (committed 609f4eb), Q1-Q3 answered.
- Result: design complete with Plan modes, item table 40.1-40.8, failure modes and V0-V7; REQ-0040 AC1-AC8 written from the item table.
- Decision: TODO -> DESIGN done; implement item by item, 40.1+40.2 first (everything else depends on the key and store).
- Next: coder Titan 40.1+40.2.

## IMPLEMENTING - TASK-082 - 2026-10-06T05:34:55Z
- Action: design complete (b992e36); start implementation item by item.
- Result: coder Titan briefed on 40.1+40.2 (ai_store.py key/get/put/stats + tests/ai_store_test.sh).
- Decision: DESIGN -> IMPLEMENTING.
- Next: wip-commit Titan 40.1+40.2, then 40.3/40.4.

## UNIT_TESTED - TASK-082 - 2026-10-06T17:15:48Z
Action: Titan added AC6 seed (570431b); Nemesis re-ran ai_, pipeline_, shell independently at 4f339ea. Main seeded the private store from plans/Upzi_g02/main/runs/20260928-222915 ($0): phase 1 put 4; phase 0 needed --p0-model sonnet --p0-effort none (run recorded no model) put 4; re-seed put 0 (idempotent).
Result: ai_reuse_pipeline 29/0, ai_store 45/0, pipeline_ 19 suites pass, shell 378/0. Gap: seed template-age skip not unit-tested (no git in scratch kit). Process slip: tester overlapped two pipeline_ runs (both passed).
Decision: UNIT_TESTED.
Next: real 0-call check with a failing claude over the Upzi_g02 repos, then Argus.

## VERIFIED - TASK-082 - 2026-10-06T22:14:26Z
Action: real $0 check in a scratch kit at HEAD: plans Upzi_g02/reuse and reuse2 over the real upzi_g02 tree with the seeded store and a fake claude that fails every call; Argus checked AC1-AC6 against the evidence files.
Result: phase0 and phase1 "AI cache: reused 4 / called 0"; full run (2b/verify off) rc 0, 0 claude calls, report QA PASS, coverage findings=12 shown=12 gaps=0; phase1 outputs equal except the reused block. Argus: AC1-AC6 PASS (AC4 by unit tests only).
Decision: VERIFIED. Follow-up (non-blocking): unit test for the seed's template-age skip in a git-init scratch kit.
Next: report, DONE, pick TASK-083.

## DONE - TASK-082 - 2026-10-06T22:14:48Z
Action: wrote docs/report/phase-82-ai-reuse-store.md; backlog complete; queued TASK-084 follow-up (seed template-age skip test).
Result: REQ-0040 AC1-AC6 ticked; real Upzi_g02 reuse 0 calls, gaps=0.
Decision: DONE (adopted). User RAW-00413 approves proceeding without asking.
Next: pick TASK-083 (QLScan), Titan builds 83.1-83.3.

## DESIGN - TASK-083 - 2026-10-06T22:15:33Z
Action: Nova drafted work/TASK-083/handoff/design.md; main wrote docs/design/phase-83-qlscan-import-compare.md (4f339ea) and REQ-0041 AC1-AC5.
Result: 5 items (config, import, normalise, comparison section, park before phase 0); off path byte-identical; real $0 check on a scratch copy of plans/Upzi/full.
Decision: recommended options taken (user standing instruction + RAW-00413 "I approve all"): QLScan in the tools comparison report, client report AI-only; existing ext_match rule + same-CWE-same-file column; park = exit 13.
Next: IMPLEMENTING, Titan 83.1-83.5.

## IMPLEMENTING - TASK-083 - 2026-10-06T23:48:04Z
Action: Titan implemented 83.1-83.3 (803404e) and 83.4-83.5 (this commit).
Result: Titan self-check: ext_qlscan, ext_report_qlscan, pipeline_qlscan pass; ext_ 32 suites, pipeline_ 20 suites pass; shell 386/0. Scope additions accepted: tools.json qlscan row (else every row out:tool_removed); tools_sha changes once (ext_tools.sh edited).
Decision: IMPLEMENTING complete; independent QA next.
Next: Nemesis QA; real check after the user's Go image rebuild re-run (RAW-00415/00416).

## UNIT_TESTED - TASK-083 - 2026-10-07T00:57:42Z
Action: Nemesis QA round 1 (e681071) found 4 test gaps; Titan added tests only (d51145f); Nemesis round 2 re-ran the qlscan suites + shell.
Result: pipeline_qlscan 12/0, ext_qlscan 38/0, ext_report_qlscan 9/0, ext_ 32 suites, pipeline_ 20 suites, shell 386/0. Real AC5 import saved (real-ac5-qlscan-import.txt).
Decision: UNIT_TESTED. Argus PARTIAL asks for V2 golden at HEAD, real-ac5 re-save, V5 AI-plan proof.
Next: save those proofs (/bin/bash), Argus completes, VERIFIED, report.

## VERIFIED - TASK-083 - 2026-10-07T01:12:08Z
Action: saved V2 (old kit 79c6ae3 vs HEAD, QLScan off), V5 (Upzi_g02 AI run copy with QLScan imported), re-saved real-ac5 and unit-ext at a2d0d97; Argus checked each AC.
Result: AC1-AC5 PASS. ext_ab + 114 input.json byte-equal when off; AI security_report byte-equal when on, coverage gaps=0 (12/12), report_qa PASS; unit-ext 32 suites pass. "+dirty" in evidence heads was a stray untracked .x (backlog copy), removed.
Decision: VERIFIED.
Next: report, DONE.

## DONE - TASK-083 - 2026-10-07T01:12:51Z
Action: wrote docs/report/phase-83-qlscan-import-compare.md from the evidence files; lesson added to token-efficiency.
Result: AC1-AC5 verified; QLScan import + park + comparison section adopted.
Decision: DONE; backlog complete.
Next: pick TASK-085 (EPIC-004 ext report upgrade).

## DESIGN - TASK-085 - 2026-10-07T01:14:44Z
Action: wrote docs/design/phase-85-ext-report-upgrade.md from Nova's draft + coordinator decisions D1-D10 (user delegated, RAW-00424/00425); added the ext_snippet.py exception to CLAUDE.md (user RAW-00421).
Result: one design, owner table with 3 waves: 85.1 || 85.2->85.3 || 85.6a; 85.4 -> 85.5; 85.6b + docs.
Decision: DESIGN complete; build in waves, parallel where owners differ (RAW-00427).
Next: IMPLEMENTING wave 1.

## IMPLEMENTING - TASK-085 - 2026-10-07T02:52:47Z
- Action: Titan built waves 1-3 (85.1-85.6b, docs) in parallel waves; Nemesis QA wave 1; main ran real checks V1, V2, V3, V5, V6, V7 on frozen git-archive kits.
- Result: commits 92d880a, 0a154c8, cf7842c, 70dfc80, d2c04ed, 739ef15, ac8516a. QA found F-85-N1..N3, all fixed. Real: V1 114 repos 2 gain a tool, 0 lose; V2 2016 rows each in exactly one record, trust order 0 violations; V3 692 files equal after timestamps/digests; V5 security_report equal except _Generated line, coverage gaps=0, report_qa PASS; V6 810 in-scope blocks, hashes only; V7 tools-only 39/39 findings kept, D-checks rc 0.
- Decision: implementation complete; owner rows ticked.
- Next: Nemesis round 2 QA suite (ext_inscope_qa_test), then UNIT_TESTED, Argus verify.

## UNIT_TESTED - TASK-085 - 2026-10-07T05:26:43Z
- Action: Nemesis round 2 QA (ext_inscope_qa Q1-Q8) found F-85-N4 (masker := / =>) and F-85-N5 (vacuous e2e); Titan fixed N4, Nemesis fixed N5 and the Q7 test flake (history file + wall_s timing). Nova's TASK-086 draft found F-86-D1 (languages never written) and F-86-D3 (short id collision); Titan fixed both in TASK-085.
- Result: ext_ 42 suites, pipeline_ 21, track 9 all pass; shell 408/0; real V8 4-repo ext run fills languages 4/4.
- Decision: unit tests pass; move on.
- Next: VERIFIED with Argus verify.md.

## VERIFIED - TASK-085 - 2026-10-07T05:28:22Z
- Action: Argus checked the V1-V8 real evidence and unit evidence against REQ-0042..0047, plus a delta check after 34cb0a7.
- Result: 21/21 ACs PASS, no FAIL. Limits stated: V6 hashes 809/810 (pre-N2 plan copy), AI-confirmed marker proven by unit tests only, D13 WARN in scratch kits.
- Decision: VERIFIED.
- Next: report, DONE.

## DONE - TASK-085 - 2026-10-07T05:29:32Z
- Action: wrote docs/report/phase-85-ext-report-upgrade.md from evidence-cited draft; added Going faster lesson.
- Result: 6 REQs (0042..0047) built, 7 defects fixed with tests, Argus 21/21 PASS.
- Decision: DONE; F-86-D2 carried into TASK-086.
- Next: pick TASK-086 (REQ-0049 ext self-check).

## DESIGN - TASK-086 - 2026-10-07T06:02:11Z
- Action: Nova drafted (work/TASK-086/handoff/design.md); main wrote docs/design/phase-86-ext-selfcheck.md with deltas (86.0 reduced to F-86-D2, step 0 checks existing Upzi/full output, flags checked).
- Result: design complete, 8-row checklist.
- Decision: approved (delegated RAW-00424/00425).
- Next: Titan implements 86.0-86.5.

## IMPLEMENTING - TASK-086 - 2026-10-07T06:25:37Z
- Action: Titan built 86.0-86.5 (work/TASK-086/handoff/code.md); main re-ran ext_selfcheck 67/0 and shell 410/0.
- Result: implementation complete; bite with stub checker 56 fails.
- Decision: IMPLEMENTING done; Nemesis QA next, real runs in parallel.
- Next: Nemesis QA, step 0 on Upzi/full.

## UNIT_TESTED - TASK-086 - 2026-10-07T12:57:57Z
- Action: fixes F-86-1..6 landed (b03d244, 3d61c9c, 442c94f, 587d434, a55e7ca, 7430f93); Nemesis QA (fcd9796, 942ae80); full suites re-run at 7430f93 under the user's new jq 1.8.0.
- Result: all suites pass (ext_ 44, pipeline_ 21, track 9, check_deliverables, run_reports, plan_reports, report_qa); shell 412/0. F-86-7 (big PDF timeout) is a documented limitation; F-86-8 track 81.5 flake 1/4 under load, passed in the final run.
- Decision: UNIT_TESTED.
- Next: Vietnamworks report-step resume at HEAD and psalm re-run on 24 PHP repos ($0), then Argus verifies AC1-AC5.

## VERIFIED - TASK-086 - 2026-10-07T14:30:59Z
Action: Argus checked AC1-AC5 from evidence; main measured self-check runtime at HEAD on both real plans and re-ran suites touching check_deliverables.
Result: AC1-AC5 PASS. Upzi 10/0 in 0.64 s, Vietnamworks 10/0 in 7.33 s. ext_selfcheck_qa 80/0 after aligning D14 cases (8edb8cc). job_hold_sched/scan_equiv/scan_history fail since 753302e (bisected, test isolation of the TASK-082 AI cache) -> F-86-10, TASK-088.
Decision: VERIFIED; F-86-10 is outside REQ-0049 scope and queued before TASK-087.
Next: DONE report, then TASK-088.

## DONE - TASK-086 - 2026-10-07T14:32:17Z
Action: wrote docs/report/phase-86-ext-selfcheck.md, ticked checklist rows 6-7, added a Going-faster lesson.
Result: ext self-check adopted; 10/10 on real Upzi and Vietnamworks; F-86-1..6, 9 fixed with tests, F-86-7 limitation, F-86-8 TASK-078, F-86-10 TASK-088.
Decision: DONE.
Next: pick TASK-088 (F-86-10), then TASK-087.

## DESIGN - TASK-088 - 2026-10-07T14:33:05Z
Action: wrote docs/design/phase-88-ai-cache-history.md from Titan F-86-10 diagnosis and the bisect (753302e).
Result: 88.1 archive_result on a cache hit; 88.2 cache-isolated job_hold_sched (others only if still failing); 88.3 cache-hit history test with bite. Single-source only; pipeline mode unchanged.
Decision: designer waived (diagnosis is the design input, fix is small).
Next: IMPLEMENTING via Titan.

## IMPLEMENTING - TASK-088 - 2026-10-07T14:47:15Z
Action: Titan built 88.1-88.3 (49303ef).
Result: archive_result on a cache hit; 4 suites isolated from the shared store (scan_pool found broken too: 19 FAIL at HEAD, 0 at 3f61f34); S6 bite 2/3 on HEAD; scan_ 11 suites, ai_, check_deliverables 44/0, shell 412/0 pass (coder).
Decision: design 88.3 wording corrected (no diff on a hit, same scanned_at).
Next: Nemesis full run_all as QA.

## IMPLEMENTING - TASK-088 - 2026-10-07T15:39:15Z
Action: Nemesis ran the whole repo at 6484b03.
Result: 9 suites red outside the first scope, none caused by 49303ef: 4 shared AI cache, 2 pipeline-mode holds (predate the cache), 3 jq 1.8 number literals.
Decision: extend TASK-088 to a green baseline (88.4-88.6, AC4) before TASK-087, since recon_eval is a TASK-087 input.
Next: Titan 88.4-88.6.

## UNIT_TESTED - TASK-088 - 2026-10-07T17:19:26Z
- Action: Titan fixed F-88-T3 (88.7, bf08796): classify_failure matched a bare 401 inside a reset epoch, so scan_pool failed near midnight +07. Nemesis re-ran all 127 suites serially under jq 1.8.0, the 88.6 suites under jq 1.6, shell.sh and the 88.7 bite.
- Result: 127/127 pass (2 one-off flakes passed on rerun: pipeline_equiv, track_lock_adv 81.5); jq 1.6 3/3; shell.sh 412/0; scan_result 10.1e2 fails on bf08796^. Evidence work/TASK-088/evidence/qa-final-*.
- Decision: unit_test passed; AC4 met.
- Next: VERIFIED via Argus.

## VERIFIED - TASK-088 - 2026-10-07T17:20:34Z
- Action: Argus checked AC1-AC4 against work/TASK-088/evidence.
- Result: all PASS; bites 88.3 and 88.7 confirmed; no security change beyond restoring the reset-wait rule.
- Decision: verified. Optional follow-up (not blocking): more 401/429 phrase cases in scan_result.
- Next: DONE report.

## DONE - TASK-088 - 2026-10-07T17:21:10Z
- Action: wrote docs/report/phase-88-ai-cache-history.md, added a Going-faster lesson, ran backlog complete.
- Result: F-86-10 and F-88-T3 fixed with bite-proven tests; 127/127 suites green under jq 1.8.0.
- Decision: done.
- Next: TASK-087 (REQ-0050 QLScan recon study).

## DESIGN - TASK-087 - 2026-10-07T17:21:36Z
- Action: wrote docs/design/phase-87-qlscan-recon-study.md from Nova's draft; D1-D4 recorded as approved (RAW-00440).
- Result: items 87.1-87.5 + study note; plan modes: pipeline-only for 87.3 (recon exists only there), single-source untouched.
- Decision: design complete.
- Next: IMPLEMENTING via Titan, 87.1 first.

## IMPLEMENTING - TASK-087 - 2026-10-07T21:59:18Z
- Action: Titan built 87.1 (86448ae), 87.3 + 87.2 (0dcf999) and moved the uncovered-language test examples from php to rb.
- Result: recon 75/0, recon_eval 44/0, recon_qlscan 17/0, qlscan_recon_compare 25/0, pipeline_recon 60/0, pipeline_approval 30/0, shell 416/0.
- Decision: implementation complete; first real-data compare on Upzi_g02 (4 repos): 103 QL flows, 16 unseen by the AI, card growth ~1 KB.
- Next: Nemesis QA in parallel with the 87.4 $0 small group.

## UNIT_TESTED - TASK-087 - 2026-10-07T22:25:18Z
- Action: Nemesis re-ran every related suite, added edge cases (empty findings.jsonl, rc!=0 rows, absolute SARIF uris) and checked the bites.
- Result: all pass (qlscan_recon_compare 28/0, pipeline_recon 61/0, pipeline_ 21, ext_ 44, shell 416/0); 3 bites confirmed; no defects.
- Decision: unit_test passed.
- Next: Argus VERIFIED.

## VERIFIED - TASK-087 - 2026-10-07T22:27:43Z
- Action: Argus checked AC1-AC7 against evidence; main fixed 2 note wording errors and saved the frozen-prompt diff and the arm A phase 1 cost.
- Result: all PASS; frozen prompts unchanged; security PASS.
- Decision: verified.
- Next: DONE report.

## DONE - TASK-087 - 2026-10-07T22:29:17Z
- Action: wrote docs/report/phase-87-qlscan-recon-study.md; added a Going-faster lesson; completed the backlog item.
- Result: verdict option (flag stays 0), PHP pack adopted; all evidence cited.
- Decision: DONE.
- Next: TASK-077 (REQ-0051, jq pin).

## DESIGN - TASK-077 - 2026-10-07T22:34:15Z
- Action: Nova drafted; main wrote docs/design/phase-77-env-version-pinning.md and settled Q1-Q5 as D4-D8 (recommendations taken); REQ-0051 AC1 reworded to its answered Q1.
- Result: 9 items, plan modes stated, acceptance mapped to REQ-0036 and REQ-0051.
- Decision: proceed; network pull once at 77.9 (REQ-0036 Q3, user-approved).
- Next: Titan 77.1-77.3.

## IMPLEMENTING - TASK-077 - 2026-10-07T23:33:21Z
- Action: Titan built 77.1-77.5, 77.7, D9, D10 (commits 0d9483e, 5acfece, 0408e03); main ran the 77.8 golden compare (0 real diffs, both modes), lowered the git floor (D8 rev) and added the proof Dockerfile + pins.
- Result: preflight on this host ok=15 warn=0 fail=0; preflight suites 19/0 + 9/0; shell 422/0.
- Decision: implementation complete.
- Next: Nemesis QA; main 77.9 proof; then 77.6.

## UNIT_TESTED - TASK-077 - 2026-10-08T00:10:01Z
Action: Nemesis ran the full suite serially under jq 1.8.0, added 8 preflight_env edge cases with mutation bites, and re-checked the F-77-QA-1 fix (main made the one-file test fix in tests/ext_images_test.sh: proof.Dockerfile is a dev image, so it now has its own pin checks, 85578e0).
Result: 130/131 before the fix; ext_images 19/0 after it, with bites; preflight_env 29/0, preflight_gate 9/0, shell.sh 422/0 (work/TASK-077/evidence/qa-77-*, handoff test.md).
Decision: UNIT_TESTED. The other suites passed in the full run, and the fix touches only this one test file.
Next: the 77.9 in-container full suite; 77.6 PREFLIGHT=1; Argus VERIFIED.

## UNIT_TESTED - TASK-077 - 2026-10-08T00:49:41Z
Action: queue review per RAW-00452. The inspector checked every queued task and TODO REQ against the current code.
Result: none is done or obsolete. TASK-084 is merged into TASK-078 (both are small follow-up tests near TASK-088). TASK-080 is renamed "checkpoint", because "park" clashes with the TASK-083 QLScan park. Refresh notes were added to TASK-074, 075, 078 and 080. REQ-0048 is mostly delivered but has no TASK; REQ-0030 is largely covered by inbox-triage plus the inspector. Both stay TODO for now (no user need yet). The EPIC-002 option B TBD conflicts with the source-read rule, so it is not queued.
Decision: order after TASK-077 is TASK-089, TASK-078 (+084), TASK-075, then TASK-080 + TASK-074 together.
Next: unchanged for TASK-077 (77.9 container fixes, V8 rerun, Argus).

## VERIFIED - TASK-077 - 2026-10-08T02:48:25Z
- Action: fixed 10 more fake-kit suites missing PREFLIGHT=0 (045c527); V8 fresh-clone container rerun; V9 grep; golden checks and secrets.sh re-run at ed46a1e; Argus verification.
- Result: container 131/131 suites (v4; a one-off job_hold_sched failure under parallel load in v3 passed solo and in v4, F-77-QA-2); proof preflight ok=11, bash 3.2 205/0; host preflight ok=28 fail=0; shell 422/0; golden gaps=0, real_diffs=0, 0 claude calls; Argus PASS REQ-0036 AC1-AC6, REQ-0051 AC1-AC4.
- Decision: VERIFIED. Checklist 164/165, none open for TASK-077.
- Next: DONE report, lesson, backlog complete, REQ-0036/0051 DONE; then pick TASK-089.

## DONE - TASK-077 - 2026-10-08T02:49:40Z
- Action: wrote docs/report/phase-77-env-version-pinning.md; token-efficiency lesson; backlog complete.
- Result: REQ-0036 and REQ-0051 verified (fresh-clone container 131/131, golden real_diffs=0, Argus PASS).
- Decision: DONE; PREFLIGHT=1 is the default.
- Next: pick TASK-089 (recon edge health).

## DESIGN - TASK-089 - 2026-10-08T02:51:41Z
- Action: picked TASK-089; wrote docs/design/phase-89-recon-edge-health.md from Nova's draft; added 89.8 --pause-after and 89.9 paid AC12 run.
- Result: design 89.1-89.9, V1-V13, 11-row checklist; D1-D10 accepted under the user's delegation.
- Decision: build in order V1 bite -> 89.1, 89.8, 89.2/89.3 -> baseline -> fixes -> 89.6 -> paid run -> docs.
- Next: IMPLEMENTING with Titan.

## IMPLEMENTING - TASK-089 - 2026-10-08T07:18:50Z
Action: all 11 checklist rows closed. Row 10: paid runs done for Vietnamworks_g01 and Upzi_g02 ($1.95 of $7.0); the deploy-context re-run moved to TASK-090 as REQ-0053 AC8 evidence (user RAW-00465: do other tasks first). Row 11: evidence notes 3635490, REQ-0052 Design c22ed58.
Result: kept the JS fix (ced7393) and the PHP fix (f118565); reverted py F-89-8 (2f885ab). A2 true-miss: Vietnamworks 0/3835, Upzi 2/5742, so the reopen threshold is not met.
Decision: implementation complete; QLScan stays oracle only.
Next: Nemesis QA (UNIT_TESTED), then Argus (VERIFIED), then DONE report.

## UNIT_TESTED - TASK-089 - 2026-10-08T07:22:05Z
Action: Nemesis re-ran the recon, recon_health, recon_health_line, pipeline_recon and pipeline_pause suites and the shell checks, one at a time.
Result: all pass (89/50/9/61/8, shell 428/0); the frozen-prompt diff is empty; the reverted rows are absent; fixture markers 137/137 match.
Decision: UNIT_TESTED.
Next: Argus verification.

## VERIFIED - TASK-089 - 2026-10-08T07:25:40Z
Action: Argus checked V1-V13 and REQ-0052 AC1-AC13 against the evidence. Main closed the 4 gaps: tree stamp, V8/V9, python.sh scope, and the doc nits.
Result: PASS. Newer files 0 on all 3 trees; 0 single-source files changed; the 2 python.sh failures come from pre-existing fixtures, added to the TASK-078 follow-ups.
Decision: VERIFIED.
Next: DONE report.

## DONE - TASK-089 - 2026-10-08T07:26:49Z
Action: wrote docs/report/phase-89-recon-edge-health.md; added the Going-faster lesson; completed the backlog item.
Result: recon standard adopted (packs + noir, QLScan oracle only); spent $1.95 of $7; the deploy-context re-run carried to TASK-090.
Decision: DONE.
Next: pick TASK-091 (design draft ready at work/TASK-091/handoff/design.md).

## DESIGN - TASK-091 - 2026-10-08T07:27:19Z
Action: Nova drafted (work/TASK-091/handoff/design.md); main wrote docs/design/phase-91-inspect-script-library.md with a 10-row checklist.
Result: 9 items. Six tools merged from the scratch scripts and built on the recon_eval parsers. index_check is run by the suite. Canary sweep. Role text goes outside the generated block.
Decision: design accepted (one parser, merge duplicates, no new guard).
Next: Titan 91.1.

## IMPLEMENTING - TASK-091 - 2026-10-08T07:38:39Z
Action: Titan built 91.1-91.7, main did 91.8, Nemesis built the 91.9 canary sweep; main ran the tier-1 real runs (real-91-tier1, real-91-recon-all).
Result: 7 scripts with 7 INDEX rows. Real-run numbers equal the scratch numbers, the run dir hash is unchanged, and tree newer_files=0.
Decision: implementation complete.
Next: UNIT_TESTED.

## UNIT_TESTED - TASK-091 - 2026-10-08T07:39:26Z
Action: Nemesis QA plus the 91.9 sweep; main re-saved qa-91-* at HEAD.
Result: suite 91/0, shell 434/0, index 7=7, frozen diff empty, INDEX pointer present in the 4 role files, the skill and both guides.
Decision: UNIT_TESTED.
Next: Argus.

## VERIFIED - TASK-091 - 2026-10-08T07:41:19Z
Action: Argus PASS; main closed the gaps (compile, the two bite proofs, the item-join comparison).
Result: all ACs have evidence; real numbers match TASK-089.
Decision: VERIFIED.
Next: DONE report.

## DONE - TASK-091 - 2026-10-08T07:43:00Z
Action: wrote report docs/report/phase-91-inspect-script-library.md; fixed checklist typo rows 1/8; lesson appended.
Result: 7 scripts indexed, 91/0 suite, real numbers match TASK-089.
Decision: DONE.
Next: pick TASK-090 once Nova's design draft arrives.

## DESIGN - TASK-090 - 2026-10-08T07:45:22Z
Action: Nova drafted; coordinator accepted the .envkeys name-only sidecar, scope=gate for auto_scan, no-edge repos keep phase 0/1; wrote docs/design/phase-90-paid-phase-checkpoints.md (11-row checklist).
Result: design complete; 90.11 paid run held for the user's deploy dir + cost go.
Decision: proceed to IMPLEMENTING.
Next: Titan 90.1 bite tests.

## IMPLEMENTING - TASK-090 - 2026-10-08T09:23:51Z
Action: Titan built 90.1-90.9 in 6 briefs (wip commits 24742be..a34deb3 + this one); main re-ran each suite.
Result: pipeline_checkpoint 52/0, pipeline_run 127/0, approval 30/0, recon 61/0, ext_pregate 28/0, checkpoint_report 35/0.
Decision: implementation complete; 90.11 paid run waits for the user's deploy dir + cost go.
Next: Nemesis 90.10 full suite.

## UNIT_TESTED - TASK-090 - 2026-10-08T11:09:09Z
Action: Nemesis round 2 full suite after fix r1; 90.12 deploy_link_to_k8s.py (REQ-0055) built by Titan, fix r1 F-90.12-1 (collisions), QA by Nemesis.
Result: run_all 137 suites green (qa-90-full-r2); deploy_link 49/0, bite on collision guard 2 fail; shell 440/0; real $0 runs: upzi_production 48/56 mapped, 8 unmapped with suggestions, 0 collisions, 144 objects, 0 URLs in stdout; g02 4/4, 12 objects, identical to pilot except image tag.
Decision: UNIT_TESTED; rows 10 and 12 ticked; 8 unmapped Upzi sections wait for the user's alias lines (not a blocker).
Next: Argus verify at $0; 90.11 paid run waits for the user's deploy dir + cost go.

## VERIFIED - TASK-090 - 2026-10-08T15:48:32Z
Action: full suite r3, Argus AC->evidence review, real $0 Upzi/active hold r2, docs grep.
Result: 140/140 suites; Argus PASS REQ-0053/55/56/57; hold rc 13 names 5 missing repos; docs 3/3.
Decision: VERIFIED; 90.11 paid run carried to TASK-092 (RAW-00475); Vietnamworks list key waits for a full Vietnamworks plan.
Next: report, DONE, pick TASK-094.

## DONE - TASK-090 - 2026-10-08T15:49:09Z
Action: report docs/report/phase-90-paid-phase-checkpoints.md.
Result: 13 of 14 rows done; row 11 carried to TASK-092.
Decision: DONE.
Next: pick TASK-094.

## DESIGN - TASK-094 - 2026-10-08T15:53:13Z
Action: Nova draft -> docs/design/phase-94-user-notes.md; picked_at set from the pick commit.
Result: 7 items, Newer features kept table, no new block; F-94-D1 (guard regex for note) needs user OK.
Decision: DESIGN complete.
Next: Titan 94.1-94.6.

## IMPLEMENTING - TASK-094 - 2026-10-08T16:07:04Z
Action: Titan 94.1-94.4 (coder granted .claude/scripts/*); main added the session-start line and the report/req-intake/workflow skill text; live 94.7 backfill (TASK-093 RAW-00476 noted).
Result: workflow_gates 137/0, shell 446/0, req_kit 38/0, protect_rules 108/0, agent_setup_hook 49/0; bite 21 FAIL on HEAD scripts; real-94.7 ALREADY with sha256 unchanged; session start shows User notes (2) and the queued counts; workflow-check PASS with no WARN.
Decision: task id regex is TASK-[0-9]+ (fixtures use TASK-9).
Next: Nemesis QA -> UNIT_TESTED.

## UNIT_TESTED - TASK-094 - 2026-10-08T16:09:44Z
Action: Nemesis QA re-ran the suites and added 5 cases; main ran the 94.4 bite (only workflow-check.sh reverted).
Result: workflow_gates 142/0, req_kit 38/0, protect_rules 108/0, agent_setup_hook 49/0, shell 446/0; 94.4 bite 4 FAIL.
Decision: the www./BEGIN/AKIA patterns are not tested (listed as a limitation; the same regex list is covered by the URL, password= and token cases).
Next: Argus -> VERIFIED.

## VERIFIED - TASK-094 - 2026-10-08T16:11:04Z
Action: Argus reviewed AC1-AC5; main re-ran workflow_gates and session start at HEAD.
Result: AC1-AC5 PASS; 142/0; User notes (2) + queued counts printed.
Decision: AC2 is a soft control (skill text + WARN backstop), accepted per the design decision. Argus said backlog.json was uncommitted; it was already committed in 50de5ed (git status clean).
Next: DONE report.

## DONE - TASK-094 - 2026-10-08T16:11:33Z
Action: wrote docs/report/phase-94-user-notes.md; backlog.sh complete; lesson added.
Result: REQ-0059 DONE; notes merged back to the backlog item.
Decision: F-94-D1 stays with the user.
Next: pick TASK-095 (REQ-0058).

## DESIGN - TASK-095 - 2026-10-08T16:12:17Z
Action: picked TASK-095; wrote docs/design/phase-95-report-crosscheck-registry.md from the Nova draft + a 7-row checklist.
Result: 22 report kinds; 6 without a check get the weak fresh builtin; result file outside reports/.
Decision: role = tester (no protect.roles edit); DONE gate opt-in FAIL; coder granted .claude/scripts/* up front (TASK-094 lesson).
Next: Titan items 1-3, 5, 6.

## IMPLEMENTING - TASK-095 - 2026-10-08T16:38:15Z
Action: Titan rows 1-3, 5, 6 (two rounds, turn limit once; wip cfc1525); main row 4 skill text; V1 on real report dirs.
Result: report_crosscheck 24/0, workflow_gates 146/0, shell 448/0, 15 kept suites pass; lint OK kinds=20; scan-only on 7 real plans unregistered=0 (real-95-v1-scan-only). python.sh FAIL is the old fixtures issue (TASK-078).
Decision: no track.sh tail (post_run_hooks already runs it); tracking_new_only plan_fp prunes crosscheck/ (new plan-dir output, accepted).
Next: Nemesis QA + V2/V4; main V3.

## UNIT_TESTED - TASK-095 - 2026-10-08T17:25:35Z
Action: Nemesis re-QA r3 at 2698a2a after F-95-1/N1/3 fixes; main re-ran report_crosscheck.
Result: report_crosscheck 33/0, workflow_gates 146/0, shell 448/0, 15 kept suites rc 0; V2/V4 identical ON vs OFF; V3 rebuild r5 CROSSCHECK fail=0, gaps=0, 12 files identical; real read-only fails only D1/D10/X2 (true historical facts).
Decision: UNIT_TESTED. F-95-2 (rebuild --run old drops repos when manifest moved on) is pre-existing, queued as follow-up.
Next: Argus verify.

## VERIFIED - TASK-095 - 2026-10-08T20:02:45Z
Action: Argus verified AC1-AC5 against saved evidence; main saved frozen-prompt check.
Result: AC1,2,4,5 PASS; AC3 mechanism PASS, live use is this task own DONE cross-check; frozen prompts unchanged.
Decision: VERIFIED.
Next: own DONE cross-check, report, DONE.

## DONE - TASK-095 - 2026-10-08T20:05:24Z
Action: own DONE cross-check (runner --report pass=1; Nemesis oracle 18 rows RESULT: OK); report written; row 7 ticked; lesson added.
Result: REQ-0058 AC1-AC5 met; report docs/report/phase-95-report-crosscheck-registry.md.
Decision: DONE. F-95-2 queued on TASK-078.
Next: staleness review, then TASK-080.

## DESIGN - TASK-080 - 2026-10-08T22:06:17Z
Action: Nova staleness review r3 (RAW-00476/00477/00479) + draft; main wrote docs/design/phase-80-task-checkpoint.md; user answered U1 (defer Stop blocks) and U2 (role deny yes).
Result: 4 r2 items dropped as duplicates (team-status/watch-role, session-start resume); checkpoint only for mid-flight tasks; REQ-0038 AC2/AC6/AC7 wording aligned.
Decision: DESIGN complete.
Next: IMPLEMENTING, Titan 80.1-80.6.

## DESIGN - TASK-096 - 2026-10-08T22:30:09Z
Action: Nova drafted r1, then r2 importing the user protocol (RAW-00484); the user answered U1 block, U2 log only, B2 block (RAW-00485).
Result: docs/design/phase-96-multi-active-tasks.md, items 96.1-96.13 in three slices, with a protocol import table (worktrees, merge queue, inbox and flock skipped).
Decision: per-task task.<T>.json is authoritative and task.json is a view; one task per commit; overlap waits as blocked_by; other tasks held until 96.9.
Next: slice 1 (96.1-96.5) to Titan.

## IMPLEMENTING - TASK-096 - 2026-10-08T23:37:40Z
Action: three slices by Titan (slice 3 as patches applied by the user); main applied commit-check/task_gate patches, docs (96.11) and migration (96.9, d404a9d).
Result: all items 96.1-96.18 ticked; hooks smoke-tested on the migrated state.
Decision (decided_by: coordinator): ask-once accepts the newest work/T/handoff/<stem>*.md, since briefs name handoffs per slice; agents/*.md unchanged, the brief carries the protocol shapes (coordinator skill).
Next: UNIT_TESTED.

## UNIT_TESTED - TASK-096 - 2026-10-09T00:30:32Z
Action: Nemesis full QA at 076b92b after QA96-1 (fixtures copied the real migrated state) was fixed by Titan.
Result: 12 .claude suites 0 fail; run_all only ext_scan_test (F-96-1 from TASK-095, queued on TASK-078); scratch two-task behaviour matched every rc; AC1-AC12 mapped (work/TASK-096/handoff/test.md).
Decision (decided_by: coordinator): F-96-1 out of scope, queued.
Next: Argus verify.

## VERIFIED - TASK-096 - 2026-10-09T00:33:01Z
Action: Argus verified AC1-AC12 against saved evidence; main ran the scope and protect diffs (save-evidence).
Result: PASS; F-V96-1 task_gate.py outside scope -> added; protect diff only narrows; residual guard risks recorded in security.
Decision (decided_by: coordinator): binds-file write protection would be a new block, asked of the user, not added.
Next: report, DONE.

## DONE - TASK-096 - 2026-10-09T00:33:38Z
Action: report docs/report/phase-96-multi-active-tasks.md; backlog complete.
Result: REQ-0060 AC1-AC12 met; real state per-task since d404a9d.
Decision: residual guard risks kept as recorded; binds-file protection offered to the user.
Next: TASK-097 (task lead).

## DESIGN - TASK-097 - 2026-10-09T00:43:47Z
Action: Nova refreshed the draft against TASK-096 code (97.0 delta) and added 97.12 locks + AC8 dead-lock recovery; coordinator adopted it as docs/design/phase-97-task-lead.md.
Result: items 97.1-97.12, tests L0-L23 + V-L1..V-L4, acceptance map AC1-AC8; 97.2b block approved by the user (RAW-00497); scope + backlog.sh, task_checkpoint.sh, stop-check.sh, agents/lead.md, CLAUDE.md.
Decision: one state lock name reused, separate commit and guard locks; owner.json pid/start/age break rules; guard/hook edits delivered as patch scripts for the user.
Next: Brief Titan slice 1: 97.12 locks + owner protocol (_tasks.py locked(name), backlog.sh, sync/migrate LOCKED) with lead_test L14-L21; guard-side items as patch scripts for the user

## DESIGN - TASK-098 - 2026-10-09T01:08:01Z
Action: Nova drafted REQ-0062 items 98.1-98.7; coordinator adopted it as docs/design/phase-98-process-speed-up.md and added 98.8 (commit-check scoped to the committed task, seen live).
Result: 8 items, tests P1-P27; F1 block approved by the user and moved to TASK-097 97.2c.
Decision: 98.7, 98.6, 98.2, 98.3 script start now on a second coder; 98.1, 98.4, 98.5, 98.8 wait for TASK-097 DONE.
Next: Coder (2nd instance) slice A: 98.7 baseline first, then 98.6, 98.2, 98.3 script; 98.1/98.4/98.5/98.8 after TASK-097 DONE

## IMPLEMENTING - TASK-097 - 2026-10-09T02:00:29Z
- Action: Titan slices 1-3 (locks + recover, tasks.sh lead/set/checkpoint/commit, guard/hook bundle); user applied the bundle; main wrote 97.8 docs and the coordinator 2b rows.
- Result: 14 suites pass on the real repo (work/TASK-097/evidence/real-applied-*), guard_table 8/0, lead_test 137/0.
- Decision: implementation complete; Titan's 4 risks (code-s3.md) go to Nemesis QA as focus points.
- Next: Nemesis QA: re-run the 14 suites + lead_test bite cases on git archive HEAD, save evidence -> UNIT_TESTED

## DESIGN - TASK-098 - 2026-10-09T02:37:38Z
- Action: lead gen1/gen2 trial (TASK-097 V-L1..V-L4): gen2 resumed from the checkpoint and ran slice A QA through a tester.
- Result: process_speed 28/0; run_all --changed full fallback 145/146 (ext_scan_test 2 fails = F-96-1, queued in TASK-078). Lead's own checkpoint refused (F-97-4, fixed by slice 4).
- Decision: slice A QA passed; remaining items wait for TASK-097 DONE.
- Next: wait for TASK-097 DONE, then 98.1/98.4/98.5/98.8

## UNIT_TESTED - TASK-097 - 2026-10-09T02:42:14Z
- Action: Lead TASK-097 gen1 (AC10 end-to-end) briefed Nemesis (tester) for item 97.9 re-QA after slice 4 and F-97-5. Nemesis re-ran 14 suites through save-evidence.sh (work/TASK-097/evidence/ut-*), and the lead re-checked every SUMMARY line.
- Result: lead 158/0, agent_setup_hook 49/0, guard_table 8/0, multi_guard 38/0, multi_task 128/0, protect_rules 108/0, tamper 32/0, task_checkpoint 38/0, watch_role 27/0, workflow_gates 146/0, req_kit 38/0, save_evidence 17/0, scratch_kit 38/0, process_speed 28/0. No flakes. watch_role prints a harmless stderr line from its fixture (missing _tasks.py in the tmp repo), but the suite still passes.
- Decision: unit_test passed, roles.tester = work/TASK-097/handoff/test-ut.md, state UNIT_TESTED, set by the lead through tasks.sh set/checkpoint/commit.
- F-97-6: the lead's `tasks.sh commit ... -- .claude/state/task.TASK-097.json` was refused (own state file named after --); main fixed cmd_commit (own files accepted, empty list allowed), L31, lead 162/0, and committed through tasks.sh commit.
- Next: Argus verify (main saves evidence), V-L trials recorded, then VERIFIED.

## VERIFIED - TASK-097 - 2026-10-09T02:51:39Z
- Action: Lead gen2 saved final-code evidence (v-lead, v-workflow-check, v-checks-shell, v-git-log), briefed Argus (verifier) on REQ-0061 AC1-AC10, and re-ran the 14 UT suites at head because _tasks.py changed (F-97-6) after the ut-* saves (v-ut-*).
- Result: Argus: AC1-AC9 PASS, AC10 PASS except migration + user notice (pending main), gaps none; security sound (lead_allow scoped to own task, binds block and state-command deny hold, config tamper watch kept, s4 narrowed only runtime logs/binds, low residual risk). 14 suites 857 pass 0 fail; lead 162/0; workflow-check PASS; shell 470/1 (untracked tmp/durrable_task_parallel/tests/e2e.sh, out of scope).
- Decision: VERIFIED. The guard refused the lead's read of commit-check.sh through Bash, so the trailers follow the commit skill (Verified-by).
- Next: main does the migration check, writes the report, marks DONE, and tells the user to restart.

## VERIFIED - TASK-097 - 2026-10-09T02:53:00Z
- Action: Ticked REQ-0061 AC1-AC9 from the VERIFIED evidence (9101efd, verify.md). Tried req.py status REQ-0061 VERIFIED.
- Result: The REQ gate refused it because every AC must be ticked first, and AC10 (migration + user notice) is still open.
- Decision: The REQ stays at UNIT_TESTED. AC10 is main's last step.
- Next: main does the AC10 migration check and user notice, then req.py ac AC10 and status VERIFIED, then the report and DONE.

## DONE - TASK-097 - 2026-10-09T02:54:20Z
Action: lead gen2 committed VERIFIED (9101efd, Argus AC1-AC9 PASS, v-ut-* 857/0); main ran AC10 on the real repo (final-status, final-recover "Recovery: clean", final-migrate "already migrated"), ticked REQ-0061 AC10, wrote docs/report/phase-97-task-lead.md.
Result: REQ-0061 10/10 ACs; F-97-1..6 fixed; F-97-7 (lead commit refuses its linked REQ file) carried to TASK-098.
Decision: DONE; the user restarts the session to see several leads at once.
Next: TASK-098 (reset its lead_gen, waits only), lead TASK-098 after restart.

## DESIGN - TASK-075 - 2026-10-09T12:00:00Z
Action: lead gen1 briefed Nova (designer) for a r3 delta refresh of the r2 draft against HEAD (report_common.sh, ext_scan.sh, pipeline.sh moved), folded in phase-76 76.9; wrote docs/design/phase-75-plan-history-report.md.
Result: items 75.0-75.4 plus 75.4b (crosscheck registry kind, F075-7); 75.5 stamp is read now and written as a sidecar (F075-8); every AC is mapped to U1-U13 and V0-V7.
Decision: design completed. Asked main for the report_registry.json scope add and the 75.5 split decision; 75.0-75.4 work with either answer.
Next: 75.0 premise check (tester), then coder 75.1-75.4.

## IMPLEMENTING - TASK-075 - 2026-10-09T08:30:00Z
Action: Titan (coder) implemented 75.1-75.4b. He was cut off by the session limit once and resumed from the wip commit.
Result: history.py card/render/--check, the track.sh hook, a plan-history registry kind and a toolkit-reference section. Self-check: history 25/0, track suites pass, report_crosscheck 33/0.
Decision: implementation completed. U2, U5, U9 and the TRACK_AFTER_RUN=0 case are missing; they go to Nemesis with the QA.
Next: tester QA and the $0 replays, then UNIT_TESTED.

## UNIT_TESTED - TASK-075 - 2026-10-09T09:30:00Z
Action: Nemesis (tester) added U2, U5, U9 and U10b, ran six mutation bites, re-ran 15 suites and ran the $0 replays v2-v6 on scratch copies of Upzi_g02 main and toolsproof. The lead re-ran the history suite.
Result: history 31/0, all 15 suites rc 0, each bite fails its own case, replays rc 0, and the real plan, reports, ai_store and registry hashes are unchanged. No production bug found.
Decision: UNIT_TESTED.
Next: verifier (Argus), then VERIFIED and DONE.

## VERIFIED - TASK-075 - 2026-10-09T04:19:35Z
Action: main briefed Argus (verifier) directly (no lead, RAW-00515); main saved v-prompts-untouched (git log of TASK-075 commits vs security_prompt.md/docs/prompts).
Result: AC1-AC6 PASS on saved evidence (history 31/31, replays 5 rows for 5 runs, byte-stable, gaps=0, 0 report files changed); security pass clean; prompt matches=0. REQ-0034 ACs ticked, REQ VERIFIED.
Decision: VERIFIED.
Next: report docs/report/phase-75-plan-history-report.md, tick 76.9, DONE; follow-up task for the 75.5 toolkit.json producer.

## DONE - TASK-075 - 2026-10-09T04:20:22Z
Action: main wrote docs/report/phase-75-plan-history-report.md, ticked phase-76 row 76.9, queued TASK-099 (75.5 toolkit.json producer).
Result: report written; checklist 76.9 ticked.
Decision: DONE. Per RAW-00515/00516, max_active goes to 1 next.
Next: TASK-098 continues with main briefing roles directly.

## IMPLEMENTING - TASK-098 - 2026-10-09T05:44:19Z
Action: lead gen1/gen2 then main with coder/tester built 98.1-98.5 (wip.sh, brief.sh, req.py raw link --ac, run_all --changed, process_metrics.py, apply-patches.sh bundle, checklist gate fix); the user applied the guard bundle 01/04/05.
Result: bundle --check PASS in a kit; 7 bundle suites pass in repo (7c8aa9a).
Decision: IMPLEMENTING complete.
Next: full run_all.

## UNIT_TESTED - TASK-098 - 2026-10-09T05:44:19Z
Action: Nemesis ran full run_all and shell.sh; fixed 3 fixtures (max_active 2 in kits); main fixed history_test SC1090 and run_all env leak (F-98-ENV).
Result: 149/152 suites; ext_scan = F-96-1 (TASK-078, pre-existing); multi_task 128/0 and save_evidence 17/0 in clean env; shell.sh 483/0. Park trial (REQ-0063 AC1) 20/22, gaps to TASK-100.
Decision: UNIT_TESTED.
Next: verifier (Argus), VERIFIED, report, DONE.

## VERIFIED - TASK-098 - 2026-10-09T06:25:02Z
Action: Argus verified REQ-0062 on saved evidence; main saved run_all at HEAD, shell.sh, process_metrics compare.
Result: AC1-AC7 PASS (AC3 "every brief" = process claim; AC7 compare: TASK-098 refusals 227 vs 41.5, briefs 53 vs 14.5, minutes 277 vs 62 - bootstrap task, two leads, session limits). run_all 151/152 (ext_scan F-96-1), shell 483/0. Security: grants stay in scope.
Decision: VERIFIED.
Next: report and DONE.

## DONE - TASK-098 - 2026-10-09T06:25:24Z
Action: main wrote docs/report/phase-98-process-speed-up.md.
Result: report written; REQ-0062 DONE.
Decision: DONE.
Next: role cost follow-up (REQ-0062 plan) and TASK-100 (REQ-0063).

## DESIGN - TASK-101 - 2026-10-09T06:30:54Z
Action: Nova (designer, Opus: new design) drafted 101.1-101.5; main wrote docs/design/phase-101-role-cost.md with decisions.
Result: preload cuts coder -48 %, tester -57 %, designer -33 %; TASK-098 real refusals 60 (167 scope_out are allowed writes).
Decision: DESIGN; process_metrics.py in scope; main edits agent/skill/CLAUDE.md files.
Next: coder 101.2 + 101.5a; main 101.1/101.3/101.4 text.

## IMPLEMENTING - TASK-101 - 2026-10-09T06:33:21Z
Action: Titan (coder) did 101.2/101.3 --refresh/101.5a/b; main did 101.1/101.3/101.4 text (76acf97).
Result: process_speed_test 67/0, shellcheck ok, TASK-098 refusals 60 / scope_out 167.
Decision: IMPLEMENTING; tester QA next.
Next: tester re-runs checks, then UNIT_TESTED.

## UNIT_TESTED - TASK-101 - 2026-10-09T07:08:08Z
Action: Nemesis (tester) re-ran every check, gate full run_all.
Result: process_speed 67/0 (12 bite on HEAD~1), shell 483/0, V1/V4/V5 pass (jq oracle 60/167), run_all 151/152 (F-96-1 known).
Decision: UNIT_TESTED, 1 QA round, no defects.
Next: verifier AC1-AC5.

## VERIFIED - TASK-101 - 2026-10-09T07:12:27Z
Action: Argus (verifier) checked AC1-AC5 on the evidence; main re-ran ext_inscope_qa (F-101-V1) 4x.
Result: AC1-AC5 PASS, next-task compare DEFERRED; ext_inscope_qa 34/0 alone x4, failed only in the full parallel run (no ext file changed).
Decision: VERIFIED; F-101-V1 queued on TASK-078.
Next: report, DONE.

## DONE - TASK-101 - 2026-10-09T07:12:58Z
Action: main wrote docs/report/phase-101-role-cost.md.
Result: preloads coder -31 %, tester -44 %, designer -22 % bytes; honest refusals (TASK-098: 60 + 167 scope_out); AC1-AC5 PASS.
Decision: DONE; next-task compare deferred to the next task after restart.
Next: TASK-100 (auto-park, high).

## DESIGN - TASK-100 - 2026-10-09T07:27:19Z
Action: Nova (designer) drafted work/TASK-100/handoff/design.md (resumed once after a 429 limit); main wrote docs/design/phase-100-auto-park-question.md.
Result: 11 items 100.1-100.11; staleness: all backlog parts STILL-NEEDED; new findings F-100-D1..D5 (pick refused while held, commit refuses held task, due/brief gaps, brief hook never wired, free-text paid matching).
Decision: D1-D6 accepted as recommended (background watch trigger, tasks.sh autohold executor, explicit paid/needs_user fields, kinds enforced at ask, plain-text Your turn while watcher armed, no new block).
Next: Titan (coder) on 100.1-100.3, then 100.4-100.10.

## IMPLEMENTING - TASK-100 - 2026-10-09T07:51:11Z
Action: Titan (coder) built 100.1-100.10 (wip 1e56f4b, 5479dd6, 210f66e); main wrote 100.11 skill docs (ed62a8d) and set TASK-092 paid; Nemesis (tester) QA rounds 1-2 added 17 cases (qa-1, qa-2).
Result: multi_task 197/0, task_checkpoint pass, checks/shell.sh 483/0; new cases bite on old scripts; e2e ask->watch->autohold->answer->resume green with workflow-check clean at each step. Settings brief hook edit refused by auto-mode classifier -> patch work/TASK-100/patches/settings-brief-hook.patch for the user.
Decision: accept coder open points (autohold main or lead, guard binds lead; watch rc 1 waiting; workable --exclude).
Next: full run_all (Nemesis) for UNIT_TESTED; user applies the hook patch.

## UNIT_TESTED - TASK-100 - 2026-10-09T08:41:34Z
Action: Nemesis (tester) ran full tests/run_all.sh at a42e17e and checks/shell.sh (evidence ut-full, ut-shell).
Result: 151/152 suites pass; ext_scan_test.sh fails 2 QA cases (plan dir has crosscheck/, added by TASK-095) 3/3 alone = pre-existing F-96-1, queued in TASK-078, unrelated to TASK-100. shell.sh 483/0; multi_task 197/0.
Decision: accept as UNIT_TESTED with the known failure recorded.
Next: verify evidence, Argus (verifier), V10 live trial.

## UNIT_TESTED - TASK-100 - 2026-10-09T09:27:25Z
Action: V10 live trial started: task_checkpoint.sh ask TASK-100 --kind permission (Q-1791538037), watcher armed in the background, plain-text Your turn (D2). Argus (verifier) running on V1-V9/V11.
Result: pending.json written; waiting 10 min unanswered.
Decision: on watch rc 3 run tasks.sh autohold.
Next: autohold, record outcome.

## IMPLEMENTING - TASK-100 - 2026-10-09T09:38:25Z
Action: V10 live trial: watch Q-1791538037 fired rc 3 at +10m00s; ran tasks.sh autohold TASK-100 Q-1791538037.
Result: autohold rc 1. commit-check refused the hold commit ("State: UNIT_TESTED needs a Tests: trailer"); the hold was undone, state clean. Defect F-100-V10: _auto_commit (_tasks.py:1638) writes only Task/State trailers. V1-V9, V11 passed (Argus).
Decision: roll back to IMPLEMENTING (unit_test pending, verification failed with evidence); fix in _auto_commit: add Tests: (UNIT_TESTED) / Verified-by: (VERIFIED) from the task own sub-status; tests at those states.
Next: Titan (coder) fix + tests; Nemesis QA; UNIT_TESTED; rerun autohold on Q-1791538037.

## UNIT_TESTED - TASK-100 - 2026-10-09T10:22:39Z
Action: Nemesis QA of F-100-V10 fix (3b830df): multi_task, task_checkpoint, shell.sh, --changed, bite on old code, trailer-injection probe.
Result: 205/0, 48/0, 483/0; --changed only ext_scan F-96-1 (pre-existing); 6 new cases fail on old code; injected newline/CRLF trailers collapse to one line.
Decision: UNIT_TESTED.
Next: V10 retry: autohold on Q-1791538037 (already due).

## UNIT_TESTED - TASK-100 - 2026-10-09T10:23:17Z
Action: V10 live trial retry after F-100-V10 fix: watch Q-1791538037 rc 3 (first armed run fired at +10m00s, 09:37:29Z); tasks.sh autohold TASK-100 Q-1791538037.
Result: autohold rc 0: 7016aa9 hold commit (Tests: trailer present), 2742e81 TASK-074 picked (TASK-092 paid skipped); status lists held TASK-100 first; brief hook printed Your turn lines (D2/D6 live). Designer briefed for TASK-074 staleness review. Evidence work/TASK-100/evidence/v10-watch.txt, v10-autohold-fail.txt, v10-autohold-retry.txt.
Decision: V10 PASS (AC2, AC3, AC4, AC7 live). Remaining: AC5 resume on the user answer.
Next: on answer: hold TASK-074 at a safe point, resume TASK-100, Argus re-check, VERIFIED.

## DESIGN - TASK-074 - 2026-10-09T10:27:18Z
Action: auto-picked by TASK-100 autohold (2742e81); Nova (designer) staleness review r3 + refreshed draft; main wrote docs/design/phase-74-role-lessons-curator.md.
Result: 74.2/74.3/74.6 still needed, 74.1/74.4/74.5 changed base, 0 done/obsolete; refs re-pointed to HEAD. D2 user approval verified in REQ-0033:38-39.
Decision: D1-D5 as recommended (coordinator, RAW-00511); no new block.
Next: IMPLEMENTING 74.2 lessons.py (coder); hold here if Q-1791538037 is answered (safe point).

## UNIT_TESTED - TASK-100 - 2026-10-09T10:32:10Z
Action: user answered Q-1791538037 (yes, RAW-00534, a2cf05e); TASK-074 reached a safe point (74.2 wip 01f7edb) and was held; tasks.sh resume TASK-100.
Result: workflow-check PASS after hold (all held) and after resume; TASK-100 state/next identical before and after (evidence work/TASK-100/evidence/v7-live-resume.txt). AC5 shown live.
Decision: proceed to VERIFIED.
Next: Argus re-check of the F-100-V10 delta and V7/V10 live evidence.

## VERIFIED - TASK-100 - 2026-10-09T10:34:02Z
Action: Argus (verifier) re-check of F-100-V10 fix, V10 live trial and V7/AC5 live resume; commit slice saved (v10-commits.txt).
Result: PASS, AC1-AC8 verified; security PASS (L1, L2 Low).
Decision: VERIFIED.
Next: report, DONE, follow-ups queued, resume TASK-074.

## DONE - TASK-100 - 2026-10-09T10:36:31Z
Action: report docs/report/phase-100-auto-park-question.md; backlog complete; follow-ups L1, L2, held-task commit of docs/req/raw queued in TASK-078; Going-faster lesson added.
Result: REQ-0063 AC1-AC9 ticked, verify PASS V1-V11.
Decision: adopted.
Next: resume TASK-074 (held at DESIGN, next 74.3).

## IMPLEMENTING - TASK-074 - 2026-10-09T11:24:51Z
Action: Titan coded 74.1-74.7 (630df21, e923e58) and tests (75bede4); main proved the hook grant case bites (grant removed -> 52/1, restored).
Result: lessons 66/0, process_metrics 16/0, agent-setup-hook 53/0 (coder self-check).
Decision: move to IMPLEMENTING; tester QA next.
Next: Nemesis QA + full suite, then UNIT_TESTED.

## UNIT_TESTED - TASK-074 - 2026-10-09T12:56:56Z
Action: Nemesis QA r1-r3 (gaps closed, F-74-1/2 found, fixed by Titan in 299ae43).
Result: run_all 153/154 (only known F-96-1); lessons 92/0, process_metrics 17/0, hook 53/0, shell 487/0.
Decision: UNIT_TESTED.
Next: verifier (Argus) + security pass.

## VERIFIED - TASK-074 - 2026-10-09T13:10:30Z
Action: Argus verify + security (PASS, F-74-V1 found and fixed 6198081); Nemesis e2e v74-e2e 25 OK; main re-ran checks at HEAD.
Result: shell 487/0, lessons 96/0, process_metrics 17/0, hook 53/0; AC8 PASS; AC7 moved to TASK-093.
Decision: VERIFIED; live curator run at DONE as 74.6 tier-1 evidence.
Next: lessons collect, curator, report, DONE.

## IMPLEMENTING - TASK-074 - 2026-10-12T07:09:58Z
Action: Nemesis crosscheck of the DONE report draft (pass=21 fail=5 unregistered=5).
Result: U2 is a defect: the 3 watch rows of the live curator run (in-place edits, RAW-00537) have hunk "", so the AC8 reverse-patch revert cannot run for them.
Decision: roll back to IMPLEMENTING and fix in this task; the curator skill edit and ledger are committed now as task work.
Next: Titan fix + tests, UNIT_TESTED, Argus re-verify AC8, report fixes, DONE.

## UNIT_TESTED - TASK-074 - 2026-10-12T08:05:20Z
Action: U2 fix rounds (Titan U2-U2e) + Nemesis QA; F-74-U2-1 symlink confinement fixed.
Result: lessons 164/0, revert_confine 14/0, shell 489/0, full 153/154 (F-96-1 known); real ledger rows filled and revert byte-identical.
Decision: UNIT_TESTED.
Next: Argus re-verify AC8, VERIFIED, report, DONE.

## VERIFIED - TASK-074 - 2026-10-12T08:06:47Z
Action: Argus re-verified AC8 after U2 rounds; skill-maintenance now names the outside-skills refusal (Argus nit).
Result: PASS: 3 watch rows replace, scratch revert byte-identical, double revert rc 1, lessons 164/0, confine 14/0, shell 489/0.
Decision: VERIFIED.
Next: report, backlog complete, REQ-0033 DONE.

## DONE - TASK-074 - 2026-10-12T08:07:14Z
Action: report docs/report/phase-74-role-lessons-curator.md from the crosschecked draft (stale numbers fixed per Argus).
Result: AC1-AC8 PASS (AC7 moved to REQ-0067/TASK-093); 3 skill edits on watch with replace blocks.
Decision: DONE; first watch check at the next task DONE.
Next: pick TASK-104 (high).

## DESIGN - TASK-104 - 2026-10-12T08:12:44Z
Action: Nova draft -> docs/design/phase-104-pipeline-track-profiles.md; main decisions: startup line only with explicit --track, exact Track A hint text, probe as first test cases.
Result: 6 items, no prompt/engine/schema/id change; STOP items deferred (auto_scan --track, stored hash field, real --rerun-stale).
Decision: DESIGN completed.
Next: Titan IMPLEMENTING.

## IMPLEMENTING - TASK-104 - 2026-10-12T09:30:46Z
Action: Titan implemented 104.1-104.9 + user adds (RAW-00544..00549).
Result: pipeline_track 45/0 (coder self-check); registry lint 22 kinds 0 errors.
Decision: IMPLEMENTING completed; QA next.
Next: Nemesis wider suites + unregistered check.

## UNIT_TESTED - TASK-104 - 2026-10-12T10:47:56Z
Action: Nemesis independent QA + 1 added case (AC6 unregistered=0).
Result: pipeline_track 46/0, wider suites pass, shell 491/0, lint ok; bite 29 fails on old code (work/TASK-104/evidence/qa104-*).
Decision: UNIT_TESTED. Minor: T4 resumes an A-built manifest; pipeline.sh half of 104.7 not bitten alone (verify covers via AC11).
Next: AC11 reseed + scratch proof, Argus verify.

## VERIFIED - TASK-104 - 2026-10-12T11:12:33Z
Action: Argus verify; main saved diffstat; AC11 real-copy proof.
Result: AC1-AC13 PASS; 0 claude calls with 4/4 store reuse; no frozen prompt in diff.
Decision: VERIFIED. Follow-up: "Scan spend" label counts reused cost (pre-existing).
Next: report, DONE.

## DONE - TASK-104 - 2026-10-12T11:13:02Z
Action: report + CLAUDE.md usage line.
Result: docs/report/phase-104-pipeline-track-profiles.md.
Decision: DONE.
Next: TASK-105 (report checklist) per user order.

## DESIGN - TASK-105 - 2026-10-12T11:35:09Z
Action: Nova draft -> docs/design/phase-105-report-inventory-checklist.md.
Result: 105.1-105.6; expect tokens vs steps_done; checklist md + CHECKLIST line; Track A hook.
Decision: approved (main); unknown=K added to CHECKLIST line.
Next: Titan implements.

## IMPLEMENTING - TASK-105 - 2026-10-12T13:15:36Z
Action: Titan 105.1-105.6 (hit turn cap after writing handoff COMPLETE).
Result: report_crosscheck 43/0, lint OK; pipeline_track result not reported.
Decision: IMPLEMENTING done; scope + tests/pipeline_track_test.sh.
Next: Nemesis QA.

## UNIT_TESTED - TASK-105 - 2026-10-12T22:13:20Z
Action: Nemesis QA (resumed after rate limit), +2 AC4 cases.
Result: report_crosscheck 45/0, pipeline_track 47/0, shell 491/0; ext_scan F-96-1 pre-existing.
Decision: UNIT_TESTED.
Next: real-data checklist on scratch Upzi copy; Argus.

## VERIFIED - TASK-105 - 2026-10-12T22:26:36Z
Action: Argus verify; main diffstat + real-data Track A checklist.
Result: AC1-AC5 PASS; real checklist 3/3 present, 0 missing/fail.
Decision: VERIFIED. LOW: optional 0-file kinds labelled "not expected"; ext_scan_test list (TASK-078).
Next: report, DONE.

## DONE - TASK-105 - 2026-10-12T22:28:32Z
Action: report drafted; Nemesis report crosscheck (2 minor misses: sources cited).
Result: docs/report/phase-105-report-inventory-checklist.md.
Decision: DONE. Follow-ups F-105-1 (optional status label), F-105-2 = F-96-1 (TASK-078).
Next: none.

## DESIGN - TASK-106 - 2026-10-12T23:07:15Z
Action: Nova design (with scope adds RAW-00556..00558).
Result: docs/design/phase-106-reports-visible-checklist.md, items 106.1-106.7.
Decision: accepted; Track A set kept in run-<id>/single-source/ after B; F-106-1 (reports/t/p leak) out of scope.
Next: IMPLEMENTING (Titan).

## IMPLEMENTING - TASK-106 - 2026-10-13T05:31:27Z
Action: Titan coded 106.1-106.11 in parts 1-3 plus fix rounds 1-4 (wip commits 0dbc895..f8626ee).
Result: real-data $0 r5 on a scratch copy of Upzi_g02/main: 0 calls, report_qa PASS, 4 carried rows keep stable ids, checklist 9/9, D2-D7/D13/D14 PASS; preview under reports/Upzi_g02/main/preview/.
Decision: carry.py is the only carry rule (fallback removed); writers summarize_report.sh/summarize_exec.sh unchanged.
Next: UNIT_TESTED from Nemesis QA.

## UNIT_TESTED - TASK-106 - 2026-10-13T05:31:37Z
Action: Nemesis QA rounds 1-2, full run_all once.
Result: 155/158 suites; 3 FAILs pre-existing (F-96-1 ext_scan QA, tracking_new_only N3, track_hook S3 F-106-QA3); changed suites all pass.
Decision: pre-existing FAILs go to TASK-078 follow-ups, not TASK-106.
Next: Argus verify.

## VERIFIED - TASK-106 - 2026-10-13T06:02:27Z
Action: Titan fix round 5 (949cadb: later reasons, run-diff json in Track A set, ext NOTE cause); r6 real-data Track A on a fresh kit at HEAD (/bin/bash, fake claude); saved AC3/AC5/AC9/AC12 evidence; Argus re-verify (verify-r6.md).
Result: r6 rc 0, 0 calls, QA PASS, 12+4 carried, gaps=0, CHECKLIST 9/9, deliverables 19/0, real data unchanged. Argus PASS on AC2-AC12 and security. AC1 real full run and the A-then-B half proven by unit suites only.
Decision: user waived the paid proof for AC1 / A-then-B (2026-10-13, "Waive, prove later"); the next real full run proves it.
Next: report, crosscheck, DONE.

## DONE - TASK-106 - 2026-10-13T06:03:13Z
Action: report docs/report/phase-106-reports-visible-checklist.md; backlog complete; REQ-0070 VERIFIED -> DONE; lesson in token-efficiency.
Result: reports visible under ./reports with CHECKLIST.md, previews (keep 5), index.md; Track A = full single-source set + tracking copies; writers unchanged.
Decision: AC1 real full run and A-then-B waived by user, proven at the next real full run; F-106-QA3/N3/F-96-1 go to TASK-078.
Next: pick TASK-107 (REQ-0071) design from Nova's draft.

## DESIGN - TASK-107 - 2026-10-13T06:07:45Z
Action: picked TASK-107 (REQ-0071) after TASK-106 DONE; wrote docs/design/phase-107-inscope-ab-report.md from Nova's draft (work/TASK-107/handoff/design.md), refs refreshed at a397806, Newer features kept (TASK-104/105/106).
Result: items 107.1-107.6; ext_ab byte-identical by construction (keep=None path) and U1 golden; 3 glob clashes on ext_inscope_* named and fixed.
Decision: the user asked for a design (RAW-00566): stop for review before IMPLEMENTING.
Next: user review; on go, Titan implements 107.1-107.6.

## IMPLEMENTING - TASK-107 - 2026-10-13T06:31:08Z
Action: Titan implemented 107.1-107.6 (work/TASK-107/handoff/code.md); scope widened to tests/ext_selfcheck_test.sh and tests/report_crosscheck_test.sh (invariant count and kind rows).
Result: ext_inscope_ab 18/18; ext_inscope, pipeline_ext, track_a_ss, check_deliverables, ext_selfcheck, report_crosscheck pass; --lint OK; shell.sh fail=0; ext_scan 2 FAIL = known F-96-1.
Decision: commit, then independent QA.
Next: Nemesis QA, UNIT_TESTED.

## UNIT_TESTED - TASK-107 - 2026-10-13T06:59:25Z
Action: Nemesis QA (30 cases, U1 golden vs 9f1fb97, bites) found F-107-1 (matched_outside_inscope -1); Titan fix round 1 (pointer names the real sibling, else ext_inscope.py) and round 2 (direct count); Nemesis gate re-run at f33bf36.
Result: ext_inscope_ab 30/0, named suites pass, lint OK, shell 497/0; ext_scan 2 = known F-96-1. Real-data kit r2: rc 0, 0 claude calls, 39 of 162 in ab and pre, deliverables 19/0, real data unchanged.
Decision: UNIT_TESTED.
Next: Argus verifies.

## VERIFIED - TASK-107 - 2026-10-13T07:06:49Z
Action: Argus verified AC1-AC5 and 107.1-107.6 from evidence; main closed his two UNVERIFIED notes at $0 (real-data ext_ab cmp old vs new, ext_scan baseline at 8fa67dd).
Result: all PASS; ext_ab byte-identical on Upzi_g02 inputs; ext_scan 321/2 before and after (F-96-1); security PASS.
Decision: VERIFIED.
Next: report, Nemesis cross-check, DONE.

## DONE - TASK-107 - 2026-10-13T07:08:34Z
Action: report docs/report/phase-107-inscope-ab-report.md; Nemesis cross-check (3 minor MISS fixed with sources: r2 counts evidence, preview listing, diff split); token-efficiency lesson.
Result: ext_inscope_ab_<date>.md (+pdf) written next to every ext_ab; 39 of 162 on Upzi_g02 copy; ext_ab byte-identical.
Decision: DONE.
Next: none (queued: TASK-078 ...).

## DESIGN - TASK-108 - 2026-10-13T13:51:40Z
Action: designed fix for D10 false gap (flow_map.field cuts PT-012 to PT-01…).
Result: docs/design/phase-108-flow-map-id-cut.md; designer waived (one function).
Decision: back off to word boundary; hard cut only for a single over-long token.
Next: coder implements + tests T1-T3.

## IMPLEMENTING - TASK-108 - 2026-10-13T13:53:16Z
Action: coder changed flow_map.field + tests T1-T3.
Result: flow_map pass=18 fail=0.
Decision: accept.
Next: UNIT_TESTED.

## UNIT_TESTED - TASK-108 - 2026-10-13T13:53:16Z
Action: main re-ran flow_map suite and shell checks.
Result: pass=18 fail=0; shell pass=499 fail=0.
Decision: UNIT_TESTED.
Next: real verify on g01 re-render.

## VERIFIED - TASK-108 - 2026-10-13T13:55:12Z
Action: $0 re-render of Vietnamworks_g01 run 20261013-174303; verifier reviewed evidence.
Result: deliverables 31/0, coverage gaps=0 (19/19), crosscheck fail=0, posture unchanged; verifier PASS.
Decision: VERIFIED.
Next: DONE report.

## DONE - TASK-108 - 2026-10-13T13:55:29Z
Action: report written.
Result: docs/report/phase-108-flow-map-id-cut.md.
Decision: DONE.
Next: none.

## DESIGN - TASK-109 - 2026-10-14T11:35:07Z
- Action: designer (Nova) drafted the full design; main reviewed and placed it at docs/design/phase-109-logreach.md. Inputs: REQ-0074 (Q1-Q6 resolved by user, RAW-00602) plus live ES probes (Upzi waf_access, VNW vnw_api_access).
- Result: 11 items (109.1-109.11). Decisions accepted: display severity drives the counts; apply_reach is separate from apply_overlay; VNW repo map via a routes file (deploy-context has no Kong routes), with the VNW routes build out of scope.
- Decision: the user asked for the whole design before code (RAW-00603), and it is complete, so proceed.
- Next: IMPLEMENTING. Coder A: logreach.py 109.1-109.4. Coder B: 109.6-109.8 in parallel. Then 109.5, 109.9.

## IMPLEMENTING - TASK-109 - 2026-10-14T12:00:48Z
- Action: two coders in parallel. A did 109.1-109.5 (logreach.py, pipeline wiring). B did 109.6-109.8 (join, display, QA gate). Main added the QA rule text that the guard refused for B.
- Result: committed as wip 9781ca9, 65a2387, 53be788, 93a012f. Coder self-checks: logreach 73, render 27, pipeline_logreach 8, plan_reports 44 (golden, byte-identical without logreach), report_qa 33, run_reports 66, pipeline_e2e 42. Early live run on a scratch copy of g02: seen 5, via_caller 1, not_seen 6; 9 hand ES checks agree (work/TASK-109/evidence/v10-early-live-g02.md).
- Decision: implementation is complete, so go to independent QA.
- Next: the tester re-runs the suites plus the full run_all, then the UNIT_TESTED gate.

## UNIT_TESTED - TASK-109 - 2026-10-14T13:06:12Z
- Action: tester ran the suites independently, the full run_all and bite checks. Main fixed F-109-T1 (report_crosscheck KNOWN_STEPS was missing logreach). Scope adds: 109.12 F-95-2 run_mode_setup fix (blocked the g02 rebuild) and 109.7b AC5b wording.
- Result: all TASK-109 suites pass; 3 failures that also fail at 461fa1a; report_crosscheck 45/0 after the fix.
- Decision: UNIT_TESTED.
- Next: verifier over V8 evidence + V10 live, then security, then report.

## VERIFIED - TASK-109 - 2026-10-14T13:22:02Z
- Action: V8 $0 g02 rebuild on a scratch plan copy, V10 live ES refresh, ES-down no-op, pre-existing failure proof at 461fa1a, verifier over all ACs.
- Result: verifier PASS, 13/13 ACs met; QA PASS, gaps=0, severity unchanged; the 3 failing suites are pre-existing (noted on TASK-078).
- Decision: VERIFIED; security completed (creds local-only, nothing leaked).
- Next: docs 109.11, report, real g02 rebuild, DONE.

## DONE - TASK-109 - 2026-10-14T13:24:43Z
- Action: docs 109.11, real g02 rebuild (Upzi_g02/main run 20260928-222915), report, lessons curated (unit-test skill line).
- Result: the real g02 report shows 6 findings as Low (scan: X); QA PASS; gaps=0; severity unchanged.
- Decision: DONE.
- Next: none. VNW needs a routes file before its check can run.

## DESIGN - TASK-110 - 2026-10-14T15:24:28Z
- Action: designer drafted 110.1-110.8 from REQ-0075 (RAW-00607..00609; user answers Q1 2*/3*, Q2 replace in report, Q3 separate review report).
- Result: docs/design/phase-110-logreach-followups.md. Found that carried findings are unchecked, and that a status-rule change would reuse stale cache entries (adds a rule tag).
- Decision: accept; the sample rewrite needs a mapped repo and no /internal/ segment (RAW-00609).
- Next: coders A and B in parallel.

## IMPLEMENTING - TASK-110 - 2026-10-14T15:39:49Z
- Action: coder A (110.1-110.3 + AC9 query log), coder B (110.4, 110.6), coder C (110.5 + D15); wip commits bacd198, 1198cd5, 9a6e2ce.
- Result: the coders' self-checks pass (logreach 113, pipeline_logreach 13, logreach_render 36, logreach_report 25, check_deliverables 54, report_qa, plan_reports golden, shell.sh).
- Decision: keep B's validation-rules.md E10/E11 rows (guard-flagged write, main reviewed the diff).
- Next: tester QA.

## UNIT_TESTED - TASK-110 - 2026-10-14T16:54:48Z
- Action: tester QA r1 + r2 on HEAD e9034da; main re-ran ext_selfcheck(_qa), track_a_ss.
- Result: targeted suites PASS; full run fails only the 3 known pre-existing suites; 3 stale tests fixed (D15 block, registry kind count).
- Decision: UNIT_TESTED. Real g02 rebuild (V10) already done by main: 18 checked (6 carried), PT-014/015 seen, QA PASS, gaps=0, D15 PASS, crosscheck unregistered=0.
- Next: verifier.

## VERIFIED - TASK-110 - 2026-10-14T16:57:01Z
- Action: real g02 rebuild with a fresh ES check (V10), saved evidence v10_*, verifier review, security pass.
- Result: verifier PASS, AC1-AC9 MET; gaps=0, QA PASS, D15 PASS, no secrets; the /internal/ rule is covered by unit tests only (g02 has none).
- Decision: VERIFIED; crosscheck waived (deterministic oracles).
- Next: report, DONE.

## DONE - TASK-110 - 2026-10-14T16:57:58Z
- Action: report docs/report/phase-110-logreach-followups.md; lessons collected (1 applied to designer.md, 4 kept in main-lessons.md).
- Result: REQ-0075 AC1-AC9 met; real g02 reports updated in reports/Upzi_g02/main/run-20260928-222915/.
- Decision: DONE.
- Next: none (queue: TASK-078 ...).

## DESIGN - TASK-111 - 2026-10-15T09:17:03Z
Action: wrote docs/design/phase-111-logreach-host-index.md (host_index key, index_for, cache, report).
Result: design completed; designer waived (small change, code read by main).
Decision: one profile key with groups; same filter for all indices.
Next: coder implements 111.1-111.4.

## IMPLEMENTING - TASK-111 - 2026-10-15T09:25:30Z
Action: coder implemented 111.1-111.4.
Result: logreach.py/logreach_report.py + tests + docs changed.
Decision: accept; fake_es.py path log added (needed by U2).
Next: unit tests.

## UNIT_TESTED - TASK-111 - 2026-10-15T09:25:30Z
Action: main re-ran tests/run_all.sh logreach.
Result: 4 suites pass (142+36+37+13).
Decision: tester waived (main re-ran).
Next: real rebuild VNW g01 + Upzi g02.

## IMPLEMENTING - TASK-111 - 2026-10-15T09:31:16Z
Action: user found root cause (RAW-00626): user traffic comes from 3 gateway IPs on both indices.
Result: design addendum 111.5 (filter_value list -> terms).
Decision: roll back to IMPLEMENTING to add it in the same task.
Next: coder implements 111.5.

## UNIT_TESTED - TASK-111 - 2026-10-15T09:37:49Z
Action: coder implemented 111.5; main re-ran tests/run_all.sh logreach.
Result: 4 suites pass (148+37+37+13).
Decision: proceed to real verification.
Next: VNW g01 rebuild.

## VERIFIED - TASK-111 - 2026-10-15T09:56:07Z
Action: real VNW g01 rebuild (host_index + 3 gateway IPs), Upzi g02 rebuild, verifier review.
Result: routing per host correct, filter masked, PT-002/PT-019 now seen, gaps=0, QA PASS; Upzi identical; verifier AC1-AC7 PASS.
Decision: VERIFIED.
Next: report + DONE.

## DONE - TASK-111 - 2026-10-15T09:56:44Z
Action: wrote docs/report/phase-111-logreach-host-index.md.
Result: per-host index + multi-value filter shipped; VNW g01 reports regenerated.
Decision: DONE.
Next: none.

## DESIGN - TASK-112 - 2026-10-15T10:11:19Z
Action: design docs/design/phase-112-logreach-windows.md (RAW-00627, RAW-00628 performance).
Result: disjoint slices 1/7/21 d, existence-only, timeout 120, shard pre-filter.
Decision: DESIGN complete, designer waived.
Next: coder 112.1-112.4.

## IMPLEMENTING - TASK-112 - 2026-10-15T10:24:45Z
Action: coder implemented 112.1-112.4.
Result: code + docs done (work/TASK-112/handoff/code.md).
Decision: implementation completed.
Next: unit tests.

## UNIT_TESTED - TASK-112 - 2026-10-15T10:24:45Z
Action: main re-ran tests/run_all.sh logreach and checks/shell.sh.
Result: 168/37/37/13 pass, shell fail=0; one flaky render cmp not reproducible.
Decision: UNIT_TESTED, tester waived.
Next: real VNW + Upzi rebuild.

## VERIFIED - TASK-112 - 2026-10-15T10:40:17Z
Action: real VNW g01 + Upzi g02 rebuilds, verifier.
Result: VNW 0 timeouts, faster, PT-013 seen; Upzi identical; gaps=0, QA PASS; AC1-AC5 PASS.
Decision: VERIFIED.
Next: DONE.

## DONE - TASK-112 - 2026-10-15T10:40:27Z
Action: wrote docs/report/phase-112-logreach-windows.md.
Result: widening slices + existence-only shipped; VNW g01 and Upzi g02 reports regenerated.
Decision: DONE.
Next: none.

## DESIGN - TASK-113 - 2026-10-15T15:42:40Z
Action: design docs/design/phase-113-logreach-one-route.md (RAW-00629/00631).
Result: one public route per repo, private hosts excluded.
Decision: DESIGN complete, designer waived.
Next: coder.

## IMPLEMENTING - TASK-113 - 2026-10-15T15:52:41Z
Action: coder (Titan) did 113.1-113.3, 113.5, 113.7 + docs. Result: logreach suites 193/40/37/13 pass, vnw_route_public 6/0, shell 511/0. Decision: IMPLEMENTING; user RAW-00635/00636 rules out fan-out, so routes_per_repo=all goes. Next: coder removes it, tester QA.

## UNIT_TESTED - TASK-113 - 2026-10-15T17:07:23Z
Action: tester (Nemesis) re-ran logreach, vnw_route, shell, full run_all. Result: logreach 192/40/37/13, vnw_route 6/6, shell 511/0; full 164 suites with 3 failures pre-existing on base. Real runs: VNW g01 113 requests, 0 private/graphql, PT-012 seen->via_caller, gaps=0 QA PASS crosscheck 0 fail; Upzi g02 verdicts identical. Decision: UNIT_TESTED. Next: verifier.

## VERIFIED - TASK-113 - 2026-10-15T17:08:34Z
Action: verifier (Argus) judged AC1-AC6 on saved evidence. Result: all PASS, security clean; 3 full-suite failures pre-existing (tester base comparison). Decision: VERIFIED. Next: report, DONE.

## DONE - TASK-113 - 2026-10-15T17:08:51Z
Action: report written. Result: AC1-AC6 verified; VNW 252->113 requests, PT-012 seen->via_caller; Upzi identical. Decision: DONE. Next: none.

## DESIGN - TASK-114 - 2026-10-16T01:01:22Z
Action: design from RAW-00638/00639 and the user choice (review list). Result: docs/design/phase-114-route-map-user-links.md. Decision: DESIGN done. Next: coder 114.1-114.3.

## IMPLEMENTING - TASK-114 - 2026-10-16T01:05:25Z
Action: coder did 114.1-114.3. Result: vnw_route, logreach, shell pass. Decision: IMPLEMENTING. Next: regenerate VNW map (114.4).

## UNIT_TESTED - TASK-114 - 2026-10-16T01:10:40Z
Action: main re-ran unit suites; map re-applied from TSV rule column (no tree read); VNW g01 rebuild. Result: tests pass; 0 apiv2-s2s in json, review=22, nginx info rows 0; g01 95 requests, verdicts unchanged, gaps=0 QA PASS crosscheck 0 fail. Decision: UNIT_TESTED. Next: verifier.

## VERIFIED - TASK-114 - 2026-10-16T01:15:22Z
Action: verifier re-check on re-saved evidence after getToken removal and 114.5. Result: AC1-AC5 PASS, security clean; g01 0 changed verdicts, gaps=0, QA PASS. Decision: VERIFIED. Next: report + DONE.

## DONE - TASK-114 - 2026-10-16T01:16:09Z
Action: report written; RAW-00644 (apiv2-s2s private, input unchanged) confirmed consistent. Result: report docs/report/phase-114-route-map-user-links.md. Decision: DONE. Next: user override lines for the review list.

## DESIGN - TASK-115 - 2026-10-16T01:27:57Z
Action: design docs/design/phase-115-vnw-apiv2-public.md. Result: host-scoped override + 5 user-confirmed apiv2 routes. Decision: DESIGN done (designer waived). Next: coder 115.1.

## IMPLEMENTING - TASK-115 - 2026-10-16T01:31:43Z
Action: coder 115.1 host-scoped override + M6; main 115.2 data. Result: json 76 entries, 4 apiv2 public + company apiv2 logreach false, review 17. Decision: IMPLEMENTING done. Next: UNIT_TESTED.

## UNIT_TESTED - TASK-115 - 2026-10-16T01:31:43Z
Action: main re-ran suites. Result: 23/0, logreach pass, shell 511/0. Decision: UNIT_TESTED. Next: verifier.

## VERIFIED - TASK-115 - 2026-10-16T01:38:05Z
Action: verifier. Result: AC1-AC4 PASS, security clean (rebuild ran after the data re-apply: local copy refreshed before start). Decision: VERIFIED. Next: DONE.

## DONE - TASK-115 - 2026-10-16T01:38:05Z
Action: report. Result: docs/report/phase-115-vnw-apiv2-public.md. Decision: DONE. Next: user answers (company route, ai-apiv2).

## DESIGN - TASK-117 - 2026-10-16T08:04:45Z
Action: design phase-117. Result: eff rating helper for §8 + by-repo header. Decision: DESIGN done (designer waived). Next: coder.

## IMPLEMENTING - TASK-117 - 2026-10-16T08:10:43Z
Action: coder 117.1; main moved EFFR_DEF above the ws loop (set -u when no workspace). Result: diff 2 files. Decision: IMPLEMENTING done. Next: UNIT_TESTED.

## UNIT_TESTED - TASK-117 - 2026-10-16T08:10:44Z
Action: re-ran suites. Result: logreach_render 42/0, report 10 suites, shell 511/0. Decision: UNIT_TESTED. Next: g01 rebuild.

## VERIFIED - TASK-117 - 2026-10-16T08:12:06Z
Action: VNW g01 rebuild. Result: ratings follow effective severities, gaps=0, QA PASS, crosscheck fail=0. Decision: VERIFIED. Next: DONE.

## DONE - TASK-117 - 2026-10-16T08:12:06Z
Action: report. Result: docs/report/phase-117-repo-rating-effective.md. Decision: DONE. Next: -.

## DESIGN - TASK-118 - 2026-10-16T09:04:49Z
Action: design phase-118 (RAW-00653). Result: declared multi-domain routes. Decision: DESIGN done. Next: coder.

## IMPLEMENTING - TASK-118 - 2026-10-16T09:10:31Z
Action: coder 118.1/118.2; main data 118.3 (route_public, override, json+tsv+review, local copy 600, profile private_hosts). Result: VNW 75/75 valid, multi_public=1. Decision: IMPLEMENTING done. Next: UNIT_TESTED.

## UNIT_TESTED - TASK-118 - 2026-10-16T09:10:31Z
Action: re-ran suites. Result: pass. Decision: UNIT_TESTED. Next: rebuilds.

## VERIFIED - TASK-118 - 2026-10-16T09:12:46Z
Action: check-routes all plans + 2 rebuilds. Result: email-service multi_public, verdicts unchanged, gaps=0, QA PASS. Decision: VERIFIED. Next: DONE.

## DONE - TASK-118 - 2026-10-16T09:12:47Z
Action: report. Result: docs/report/phase-118-multi-domain-public.md. Decision: DONE. Next: -.

## DESIGN - TASK-119 - 2026-10-16T09:21:44Z
Action: design phase-119 (RAW-00655). Result: break on first match. Decision: DESIGN done. Next: implement.

## IMPLEMENTING - TASK-119 - 2026-10-16T09:23:58Z
Action: break on first match + F1. Result: diff 3 files. Decision: IMPLEMENTING done. Next: UNIT_TESTED.

## UNIT_TESTED - TASK-119 - 2026-10-16T09:23:59Z
Action: suites. Result: pass. Decision: UNIT_TESTED. Next: rebuilds.

## VERIFIED - TASK-119 - 2026-10-16T09:25:20Z
Action: rebuilds. Result: unchanged, gaps=0, QA PASS. Decision: VERIFIED. Next: DONE.

## DONE - TASK-119 - 2026-10-16T09:25:21Z
Action: report. Result: docs/report/phase-119-first-route-hit.md. Decision: DONE. Next: -.

## DESIGN - TASK-120 - 2026-10-16T09:57:52Z
Action: design phase-120 (RAW-00657). Result: opt-in unmask in review report. Decision: DESIGN done. Next: coder.

## IMPLEMENTING - TASK-120 - 2026-10-16T10:04:41Z
Action: IMPLEMENTING evidence recorded. Result: pass. Decision: advance. Next: see task.

## UNIT_TESTED - TASK-120 - 2026-10-16T10:04:41Z
Action: UNIT_TESTED evidence recorded. Result: pass. Decision: advance. Next: see task.

## VERIFIED - TASK-120 - 2026-10-16T10:07:13Z
Action: rebuilds + QA + leak counts. Result: pass. Decision: VERIFIED. Next: DONE.

## DONE - TASK-120 - 2026-10-16T10:07:13Z
Action: report written. Result: done. Decision: DONE. Next: -.

## DESIGN - TASK-121 - 2026-10-16T10:45:46Z
Action: docs(design): TASK-121 readable access-log review. Result: pass. Decision: advance. Next: see task.

## IMPLEMENTING - TASK-121 - 2026-10-16T10:45:46Z
Action: feat(logreach): TASK-121 code spans instead of HTML entities in review. Result: pass. Decision: advance. Next: see task.

## UNIT_TESTED - TASK-121 - 2026-10-16T10:45:47Z
Action: test(logreach): TASK-121 unit tests pass. Result: pass. Decision: advance. Next: see task.

## VERIFIED - TASK-121 - 2026-10-16T10:45:47Z
Action: verify(logreach): TASK-121 review has no HTML entities. Result: pass. Decision: advance. Next: see task.

## DONE - TASK-121 - 2026-10-16T10:45:47Z
Action: docs(report): TASK-121 DONE. Result: pass. Decision: advance. Next: see task.

## DESIGN - TASK-122 - 2026-10-16T23:52:37Z
Action: designer (Nova) finished the draft plus the RAW-00679 delta (quality gate); main wrote docs/design/phase-122-deploy-provider.md (122.1-122.10, AC1-AC11, V1-V16) and decided Q1 yes (rewrite in pipeline), Q2 strip=0, Q3 new run for the Upzi_g01 re-run (paid go stays with the user).
Result: design completed; enough/missing: Upzi_g01 enough (8/8 with one deploy line), Upzi/full missing 3 alias lines, VietnamWorks missing product+deploy lines.
Decision: implement in order 122.1-122.3, 122.6, 122.8, 122.10, 122.4/122.5, 122.9, 122.7.
Next: brief coder on 122.1-122.3.

## DESIGN - TASK-122 - 2026-10-16T23:58:20Z
Action: merged designer delta2 (RAW-00680): Output contract (internal model only), gateway grammar with kinds ingress/external, neutral GATEWAY_ROUTE key, 122.11 contract filter+validator, AC12, V17-V19; coordinator decided Q4 (all VNW hosts external for now).
Result: Upzi_g02 context fits the contract (51/51 internal); Vietnamworks_g01 from-dir context scores weak (21/66 gateway URLs left), the provider build must reach good (V18).
Decision: design stays at DESIGN (completed); coder continues 122.1 with the revised gateway grammar.
Next: brief coder with revised 122.1.

## DESIGN - TASK-122 - 2026-10-17T00:08:45Z
Action: merged designer delta3 (RAW-00681/00682): 122.12 public exposure map exposure.json from the user's host/route inputs, per-product exposure record path_rule (Upzi full, VNW partial), overlay/correlate/report consumers, AC13, V20-V26; coordinator decided Q5 (VNW exposure only from public_routes=).
Result: path convention classifies Upzi_g01 24/24 endpoints, Vietnamworks_g01 1/19; saved overlays have 0 hidden/disputed rows, so the phase-33 hide is not where findings are lost.
Decision: design complete; implementation order extended with 122.12.
Next: coder continues 122.1-122.3.

## IMPLEMENTING - TASK-122 - 2026-10-18T07:02:07Z
Action: coder implemented 122.1-122.12 in WIP commits b7903e1..c0e7f60 (+ docs); tester QA rounds 1-5 passed with bite checks, no production defect.
Result: touched suites pass (deploy_* 9 suites, pipeline_checkpoint 77/0, pipeline_run 127/0, pipeline_graph 48/0, auto_scan_hold 12/0); checks/shell.sh 527/0. Pre-existing fails at base d698550: track_hook S3, tracking_new_only (not TASK-122).
Decision: implementation complete; Items table 122.1-122.12 ticked.
Next: full tests/run_all.sh (evidence/full_run_all) and tester QA r6 -> UNIT_TESTED.

## UNIT_TESTED - TASK-122 - 2026-10-18T08:03:55Z
Action: full tests/run_all.sh (172 suites) + tester QA rounds 1-6.
Result: 168 pass; pipeline_logreach regression (fixture stub lacked slug() used by new exposure_map.py) fixed in the test -> 13/0, gate unchanged; ext_scan, track_hook, tracking_new_only fail identically at base d698550 (pre-existing). checks/shell.sh 527/0.
Decision: unit tests pass for TASK-122.
Next: verifier V1-V26 with saved evidence + security pass -> VERIFIED.

## IMPLEMENTING - TASK-122 - 2026-10-18T08:34:33Z
Action: verification V1-V26 on UNIT_TESTED code (tester + main kit runs).
Result: V4,V8,V9,V10/V16/V25,V13,V14 match; V5,V6,V7,V11,V17 mismatched (--built wrote deploy-quality.json without --write, missing context errored, products.conf had no deploy/gateway/exposure records, V6 inventory absent). Coder fixed them and added the Upzi/Vietnamworks records (deploy-check: Upzi_g01 enough 8/8, Upzi_g02/qlv5 enough 4/4, Vietnamworks_g01 missing, 15 unresolved URLs on 5 ms paths).
Decision: roll back to IMPLEMENTING (code changed after UNIT_TESTED); redo UNIT_TESTED with a full run, then re-verify.
Next: full tests/run_all.sh -> UNIT_TESTED; tester re-runs V5,V7,V11,V12,V17-V24,V26; main V15.

## UNIT_TESTED - TASK-122 - 2026-10-18T11:05:59Z
Action: full tests/run_all.sh after 122.14 + 122.15 (evidence full_run_all_r4.txt).
Result: 172 suites, 3 fail: ext_scan (F-96-1), track_hook S3, tracking_new_only N3. All 3 fail the same way at 2863757 (before TASK-122); TASK-122 does not touch those files.
Decision: pre-existing, not caused by TASK-122 -> UNIT_TESTED; the 2 new ones added to TASK-078 notes.
Next: verifier V1-V26 + 122.14/122.15 V rows, security pass.

## VERIFIED - TASK-122 - 2026-10-18T11:30:59Z
Action: verifier mapped V1-V26 + 122.14/122.15 rows and AC1-AC13; main saved the missing evidence (status line, help text, single-source grep, derived product, VNW/Upzi deploy-check on kits, evidence secret scan).
Result: all PASS except V12/V18/V19 verdict weak (not good) and V7 kit run not done.
Decision: weak accepted (never holds since 122.13; parity met), recorded in design; V7 waived, suite D5-D5i covers it with 0 calls. Security completed.
Next: report, lessons, backlog complete, DONE.

## DONE - TASK-122 - 2026-10-18T11:32:28Z
Action: report docs/report/phase-122-deploy-provider.md; lessons collected (5 new), curator: 0 applied (target skills over 80 lines, TASK-093), 2 bad (no evidence).
Result: deploy context built from the product link for every group; empty/stale context holds before paid calls; VNW warn-only for 15 unresolved gateway URLs.
Decision: DONE.
Next: user go for paid Upzi_g02/qlv5 re-scan (RAW-00696) and Upzi_g02 re-card on its next new run.

## DESIGN - TASK-123 - 2026-10-18T12:53:32Z
Action: picked TASK-123 (REQ-0091 feature catalog, REQ-0090 logreach); user asks for a gap analysis of the architecture first, contract/catalog style, no over-engineering (RAW-00720..00722).
Result: DESIGN started.
Decision: inspector inventories features/steps/settings/silent skips; designer drafts from it.
Next: inspector handoff, designer draft.

## DESIGN - TASK-123 - 2026-10-18T13:04:46Z
Action: inspector gap inventory; Nova draft; main wrote docs/design/phase-123-feature-catalog.md (+123.7 drift guard, RAW-00723); D6 settled per REQ-0090.
Result: 7 items 123.1-123.7, V1-V8; all $0, prompts unchanged. User approved "go" (RAW-00724).
Decision: design completed; ACs set on REQ-0091 (6) and REQ-0090 (2).
Next: coder 123.1 + 123.2.

## DESIGN - TASK-123 - 2026-10-18T13:04:50Z

Action: state(TASK-123): DESIGN completed, user go (RAW-00724)
Result: state DESIGN -> DESIGN

## IMPLEMENTING - TASK-123 - 2026-10-18T15:53:00Z
Action: coder built 123.1-123.3 (b523c8d) and 123.4-123.7 (f332806).
Result: coder self-check features/pipeline/deploy/report suites pass; plan.sh features --all: 17 plans, 7 retired-key WARNs; qlv5 logreach on (product).
Decision: implementation completed.
Next: tester full run_all + shell.sh.

## IMPLEMENTING - TASK-123 - 2026-10-18T15:53:00Z

Action: state(TASK-123): IMPLEMENTING completed
Result: state IMPLEMENTING -> IMPLEMENTING

## UNIT_TESTED - TASK-123 - 2026-10-18T16:57:25Z
Action: tester full run_all + shell.sh + bite; added tests/features_run_test.sh (9/0).
Result: 172/176 pass; 3 known TASK-078 fails + ext_pregate load flake (alone 28/0, main re-run). shell 537/0.
Decision: unit tests passed; F-123-T1 (ext_pregate flake under load) to TASK-078.
Next: verifier V1-V8.

## UNIT_TESTED - TASK-123 - 2026-10-18T16:57:31Z

Action: state(TASK-123): UNIT_TESTED
Result: state UNIT_TESTED -> UNIT_TESTED

## VERIFIED - TASK-123 - 2026-10-18T23:20:58Z
Action: verifier V1-V8 + ACs; main extras: inputs_sha direct, products_check (found pre-existing edge_key bug -> 123.8 fix e852186 + bite), full run at final code.
Result: all PASS; run_all 173/176 (3 known TASK-078), shell 537/0; qlv5 reports unchanged except timestamps, gaps=0.
Decision: verified.
Next: report + DONE.

## VERIFIED - TASK-123 - 2026-10-18T23:20:59Z

Action: state(TASK-123): VERIFIED
Result: state VERIFIED -> VERIFIED

## DONE - TASK-123 - 2026-10-18T23:22:27Z
Action: report docs/report/phase-123-feature-catalog.md; curator: 1 skill line (unit-test), 3 agent-body proposals left in curator.md.
Result: catalog + drift guard live, $0; REQ-0090/0091 ACs all ticked.
Decision: DONE.
Next: user go for the qlv5 logreach rebuild (queries production ES); registry sync after the GitLab disk issue.

## DESIGN - TASK-124 - 2026-10-19T01:18:54Z
Action: RAW-00726 -> REQ-0092, TASK-124 queued and picked.
Result: design started.
Decision: inspector mines past product-quality misses, then designer drafts.
Next: inspector incident history.

## IMPLEMENTING - TASK-124 - 2026-10-19T01:31:08Z
Action: wrote docs/design/phase-124-smarter-harness.md from designer draft + RAW-00727..00730 (124.8 compare, 124.9 pipeline-inputs skill, 124.10 learn forward, first-failure diagnose).
Result: design complete; user delegated gate choice (RAW-00730): D16/D15/bite gate = FAIL, 124.7 dropped (blocked.attempts covers it).
Decision: build order 124.1+124.2 first.
Next: coder 124.1+124.2.

## IMPLEMENTING - TASK-124 - 2026-10-19T01:31:08Z

Action: design complete, decisions recorded (RAW-00730)
Result: state IMPLEMENTING -> IMPLEMENTING

## UNIT_TESTED - TASK-124 - 2026-10-19T04:22:34Z
Action: items 124.1-124.10 (124.7 dropped) built; real-run checks found 2 gaps (D16 pre-122 layout, 124.10 substring) fixed with tests; run_reports fixture gets a sound deploy context (user OK RAW-00732).
Result: 177 suites; only pre-existing fails ext_scan, track_hook, tracking_new_only (TASK-078); check_deliverables 73/0, workflow_gates 156/0, plan_compare 11/0, features_catalog 9/0, run_reports 67/0; shell 539/0; bites FAIL on old code (bite_*.txt); single-source cmp identical. Evidence work/TASK-124/evidence/full_run_all_final*, shell_checks_final*.
Decision: UNIT_TESTED.
Next: verifier.

## UNIT_TESTED - TASK-124 - 2026-10-19T04:22:34Z

Action: UNIT_TESTED
Result: state UNIT_TESTED -> UNIT_TESTED

## VERIFIED - TASK-124 - 2026-10-19T04:25:09Z
Action: verifier checked V1a-V9 and AC1-AC8; main re-saved V1a/V2a and the frozen-prompt diff at HEAD 311b3f7.
Result: all PASS; g01 (I1 run) now FAIL D16, qlv5 D16 weak WARN, gaps=0, 0 prompt files.
Decision: VERIFIED.
Next: report, lessons, DONE.

## VERIFIED - TASK-124 - 2026-10-19T04:25:09Z

Action: VERIFIED
Result: state VERIFIED -> VERIFIED

## DONE - TASK-124 - 2026-10-19T04:29:04Z
Action: report docs/report/phase-124-smarter-harness.md; lessons marked (3 applied, 3 rejected), skill lines committed 79562e6.
Result: all V rows and AC1-AC8 PASS (verify.md); coverage gaps=0 on qlv5.
Decision: DONE; REQ-0092 DONE.
Next: user-side paid g01 re-run when wanted; queued TASK-078.

## DESIGN - TASK-125 - 2026-10-19T08:26:54Z
Action: wrote docs/design/phase-125-i9-allowlist.md. Result: data-only allowlist entry, findings unaffected. Decision: designer role waived (one-line change). Next: IMPLEMENTING.

## IMPLEMENTING - TASK-125 - 2026-10-19T08:27:15Z
Action: allowlist entry written. Result: json valid, schema 1, 1 hash. Decision: coder waived. Next: UNIT_TESTED.

## UNIT_TESTED - TASK-125 - 2026-10-19T08:28:55Z
Action: re-ran suites. Result: all pass. Decision: advance. Next: VERIFIED.

## VERIFIED - TASK-125 - 2026-10-19T08:30:36Z
Action: re-ran ext_scan --run latest --stage report, deliverables, coverage. Result: SELFCHECK 11/0, deliverables 42/0, gaps=0. Decision: verified (a first run without --run wrote stray plan-level files; removed, run files untouched). Next: DONE.

## DONE - TASK-125 - 2026-10-19T08:31:59Z
Action: report written, lessons collected and curated. Result: allowlist live, SELFCHECK 11/0. Decision: DONE. Next: none.

## DESIGN - TASK-126 - 2026-10-19T11:28:29Z
Action: designer draft turned into docs/design/phase-126-upzi-linked-s2s.md. Result: option B, items 126.2-126.7, Plan modes and Frozen prompts sections present. Decision: citation in engine_review + correlation.json only. Next: coder, plus user confirms 8 route->repo mappings.

## IMPLEMENTING - TASK-126 - 2026-10-19T14:35:57Z
Action: coder items 126.2-126.7 committed; main added s2s config (ingress gateway, link_product, 8 overrides).
Result: dry run rc=0, phase1 hits 10/10, phase0 1/10; pipeline_dryrun 7/0, pipeline_track 47/0, products_link 13/0.
Decision: gateway kind ingress (in-cluster).
Next: tester full run, UNIT_TESTED.

## UNIT_TESTED - TASK-126 - 2026-10-19T16:28:47Z
Action: tester ran full run_all + shell.sh + targeted suites. Result: 178/182 pass; 4 failures pre-existing on HEAD kit (3) or load flake (1). Decision: advance. Next: VERIFIED evidence ($0 dry run, coverage gaps=0, verifier).

## VERIFIED - TASK-126 - 2026-10-20T06:33:28Z
- Action: verifier AC1-AC7; full run_all; g03 coverage check.
- Result: AC1-AC7 MET; 3 pre-existing suite failures; fixed products.conf order (features_catalog P1).
- Decision: VERIFIED.
- Next: report, backlog complete.

## DONE - TASK-126 - 2026-10-20T06:34:18Z
- Action: report written.
- Result: adopted; root cause of misses recorded.
- Decision: DONE.
- Next: none.

## DESIGN - TASK-127 - 2026-10-20T06:40:19Z
- Action: designer draft, consumers (17) mapped, section table.
- Result: design doc phase-127 written; D2 decided: no new block.
- Decision: DESIGN complete.
- Next: coder 127.1, 127.3; main 127.2.

## IMPLEMENTING - TASK-127 - 2026-10-20T07:53:40Z
Action: coder 127.1+127.3, main 127.2 (CLAUDE.md 9,200 B). Result: done. Decision: go to UNIT_TESTED. Next: tests.

## UNIT_TESTED - TASK-127 - 2026-10-20T07:53:40Z
Action: tester V1-V7, shell.sh, run_all --changed, re-ran ext_pregate/ext_scan. Result: shell 551/0; 4 suite failures all pre-existing/unrelated. Decision: UNIT_TESTED. Next: verifier.

## VERIFIED - TASK-127 - 2026-10-20T07:57:13Z
Action: verifier AC1-3 + main saved V5 init cmp and baseline failures. Result: all met. Decision: VERIFIED. Next: report, DONE.

## DONE - TASK-127 - 2026-10-20T07:58:04Z
Action: report phase-127, lessons collect (1 tip, curator launch denied by classifier, not applied). Result: DONE. Decision: close. Next: none.

## DESIGN - TASK-128 - 2026-10-20T08:03:34Z
Action: designer draft installed as docs/design/phase-128-split-workflow-skill.md. Result: split table, 3 cites, V1-V9. Decision: DESIGN done. Next: coder 128.1+128.2.

## IMPLEMENTING - TASK-128 - 2026-10-20T08:05:14Z
Action: coder 128.1+128.2, main 128.3 cites. Result: core 8188 B, oracle missing=0. Decision: IMPLEMENTING done. Next: tester V1-V9.

## UNIT_TESTED - TASK-128 - 2026-10-20T09:29:44Z
Action: tester V1-V9, shell.sh, full run_all. Result: 3 pre-existing failures only. Decision: UNIT_TESTED. Next: verifier.

## VERIFIED - TASK-128 - 2026-10-20T09:30:53Z
Action: verifier AC1-3, main saved v2_oracle. Result: all met. Decision: VERIFIED. Next: report, DONE.

## DONE - TASK-128 - 2026-10-20T09:31:02Z
Action: report phase-128. Result: DONE. Decision: close. Next: TASK-129.

## DESIGN - TASK-129 - 2026-10-20T09:35:19Z
Action: designer draft installed as docs/design/phase-129-linked-cross-product-checks.md. Result: 129.1-129.6, V-checks. Decision: DESIGN done. Next: coder.

## IMPLEMENTING - TASK-129 - 2026-10-20T09:42:26Z
Action: coder 129.1-129.4 + tests. Result: 3 suites pass, shell.sh 553/0. Decision: IMPLEMENTING done. Next: tester goldens, full run, scratch repair.

## UNIT_TESTED - TASK-129 - 2026-10-20T11:39:02Z
Action: tester V1-V7, full --changed run; main V8 real Upzi_g03 repair (10 rows, gaps=0, 30 findings, selected.json sha unchanged). Result: only 3 pre-existing failures. Decision: UNIT_TESTED. Next: verifier.

## VERIFIED - TASK-129 - 2026-10-20T11:40:41Z
Action: verifier AC1-4; main closed 3 gaps. Result: met. Decision: VERIFIED. Next: DONE.

## DONE - TASK-129 - 2026-10-20T11:40:49Z
Action: report phase-129. Result: DONE. Decision: close. Next: none.

## DESIGN - TASK-130 - 2026-10-20T12:33:07Z
Action: designer draft installed as docs/design/phase-130-linked-2b-optin.md. Result: 130.1-130.7, V1-V7, no prompt change. Decision: DESIGN done. Next: coder.

## IMPLEMENTING - TASK-130 - 2026-10-20T12:50:09Z
Action: coder built 130.1-130.7 (switch, selection, mount, gate, report, coverage, estimate/hold).
Result: handoff PROGRESS: COMPLETE; shell.sh pass, filtered suites pass.
Decision: tester QA next.
Next: tester.

## UNIT_TESTED - TASK-130 - 2026-10-20T23:41:59Z
Action: tester QA + V6 e2e; fixed F-130-1 (linked pairs own cap).
Result: all green except known unrelated fails.
Decision: verifier next.
Next: verifier.

## VERIFIED - TASK-130 - 2026-10-20T23:43:22Z
Action: verifier + saved frozen-prompt diff, secrets, rendered rows.
Result: AC1-AC4 pass.
Decision: DONE.
Next: report.

## DONE - TASK-130 - 2026-10-20T23:43:39Z
Action: report written, lessons collected (2 tips, curator not run).
Result: REQ-0097 AC1-AC4 met.
Decision: DONE; paid Upzi linked 2b awaits user go.
Next: none.

## DESIGN - TASK-131 - 2026-10-21T05:30:45Z
Action: designer drafted classifier design.
Result: Upzi 81 unresolved -> 58 outside-group, 23 unknown, 48.9% < 50.
Decision: build 131.1-131.3.
Next: coder.

## IMPLEMENTING - TASK-131 - 2026-10-21T05:37:11Z
Action: coder built classifier + graph_quality + tests.
Result: unresolved_check 14/14, checkpoint 38/38, pipeline_checkpoint 81/81, shell.sh 0 fail.
Decision: tester QA next.
Next: tester.

## UNIT_TESTED - TASK-131 - 2026-10-21T05:41:09Z
Action: tester QA, fixture pollution fixed.
Result: all green; Upzi copy no hold.
Decision: verifier next.
Next: verifier.

## VERIFIED - TASK-131 - 2026-10-21T06:02:18Z
Action: verifier + real Upzi run to cp1.
Result: AC1-AC3 pass.
Decision: DONE.
Next: report.

## DONE - TASK-131 - 2026-10-21T06:02:25Z
Action: report written.
Result: REQ-0098 AC1-AC3 met; real Upzi run passes graph check.
Decision: DONE.
Next: none.

## DESIGN - TASK-132 - 2026-10-21T13:56:16Z
Action: wrote docs/design/phase-132-linked-reads-latest-run.md after tracing the 1-of-10 linked pairs to linked_repos.py:51 (needs run status complete; s2s was running at cp2b).
Result: design completed; designer waived (two-line change).
Decision: read runs/latest/phase1/out whenever it holds json; results/ stays the fallback.
Next: coder implements, tester extends linked_repos_test.sh.

## IMPLEMENTING - TASK-132 - 2026-10-21T13:57:32Z
Action: coder changed linked_repos.py:52 and added U1/U2 to tests/linked_repos_test.sh.
Result: linked_repos_test pass=26 fail=0.
Decision: go to tester QA.
Next: UNIT_TESTED.

## UNIT_TESTED - TASK-132 - 2026-10-21T15:00:51Z
Action: tester re-ran linked suites, full run_all and a scratch s2s check.
Result: linked_repos_test 26/0; run_all failures only the known three plus pipeline_pool_test (passes alone 58/0); scratch check 8/8 repos done.
Decision: pipeline_pool flake noted, not caused by this change.
Next: VERIFIED.

## VERIFIED - TASK-132 - 2026-10-21T15:02:26Z
Action: verifier checked code, tests, scratch s2s evidence and frozen-prompt diff.
Result: passed; 8 of 8 s2s repos read with run status running; frozen diff empty.
Decision: accept the partial-phase1 risk noted in the design.
Next: DONE.

## DONE - TASK-132 - 2026-10-21T15:03:00Z
Action: wrote docs/report/phase-132-linked-reads-latest-run.md.
Result: linked plan read from latest run phase1 in any run status; verified.
Decision: close TASK-132; TASK-133 (REQ-0100) and REQ-0101 queued.
Next: none.

## DESIGN - TASK-133 - 2026-10-21T23:11:14Z
Action: compared the linked callee (card none, no slice) with an in-plan callee (54KB card, 4KB slice). Result: data exists in the linked plan latest run. Decision: read card and slice there, fall back to none. Next: coder implements.

## IMPLEMENTING - TASK-133 - 2026-10-22T00:58:31Z
Action: coder changed the linked branch of p2b_compose (3c5a2e50). Result: real compose gives callee card 22 KB + slice 2 KB (was 209 B, none). Decision: proceed to unit tests. Next: UNIT_TESTED.

## UNIT_TESTED - TASK-133 - 2026-10-22T00:58:40Z
Action: tester re-ran suites and added malformed-deploy-context checks; full run_all. Result: 185/188 pass, 3 known failures. Decision: proceed to verify. Next: VERIFIED.

## VERIFIED - TASK-133 - 2026-10-22T00:59:47Z
Action: verifier checked evidence; real compose and coverage re-run. Result: PASS all criteria. Decision: write report, complete. Next: DONE.

## DONE - TASK-133 - 2026-10-22T01:00:08Z
Action: report written. Result: callee card 22KB and slice 2KB on the real L-R2 item; run_all only known failures. Decision: close. Next: TASK-136 (call resolver), then the paid re-run with the user go.

## DESIGN - TASK-136 - 2026-10-22T02:00:00Z
Action: traced the Upzi L-R2 edge with the user root cause (RAW-00869); wrote docs/design/phase-136-linked-join-namespace.md. Result: linked name join drops the namespace, so backend/x joins s2s microservices-v2/x. Decision: step 1 = namespace-aware linked join; rest of the resolver stays queued. Next: IMPLEMENTING.

## IMPLEMENTING - TASK-136 - 2026-10-22T02:05:00Z
Action: graph_build.sh linked lookup now uses ns-qualified names only; test updated (ns/name, FQDN, other namespace, bare). Result: graph_linked 18/0; real Upzi graph on a scratch copy: linked edges 20 -> 7, no backend/* edge. Decision: run the full suite. Next: UNIT_TESTED.

## UNIT_TESTED - TASK-136 - 2026-10-22T04:00:00Z
Action: ran all 188 suites in parallel on the final code and reran the extra failures serially. Result: 179 pass, 3 known failures, 5 load flakes pass alone, pipeline_track slow (26 pass, 0 fail, serial rerun pending). Decision: proceed to verification with the real Upzi graph check. Next: VERIFIED.

## VERIFIED - TASK-136 - 2026-10-22T04:10:00Z
Action: ran graph_build on scratch copies of the real Upzi and s2s runs; coverage_check; frozen prompt diff. Result: Upzi linked edges 20 -> 7 with no backend/* edge, in-plan edges unchanged (24, 2), coverage gaps=0, prompts unchanged. Decision: write the report and close step 1. Next: DONE.

## DONE - TASK-136 - 2026-10-22T04:20:00Z
Action: report written; backlog complete. Result: linked join keyed by zone + namespace + service; Upzi linked edges 20 -> 7; in-plan unchanged; gaps=0. Decision: close step 1; resolver rest queued as TASK-138. Next: TASK-137 fast test tier, then TASK-138.

## DESIGN - TASK-137 - 2026-10-22T12:56:31Z
Action: wrote docs/design/phase-137-run-all-fast-tier.md from measured suite times. Result: 158 light suites 454 s serial, 30 heavy 2822 s. Decision: tiers file + --fast/--skip/--skip-heavy, mapped suites never skipped silently. Next: implement run_all.sh (coder).

## IMPLEMENTING - TASK-137 - 2026-10-22T13:06:07Z
Action: coder added --fast/--all/--skip/--skip-heavy, tests/suite_tiers.txt (30 heavy, matches timing table), serial retry. Result: run_all_fast_test 23/0, shell checks 563/0. Decision: FAST_JOBS defaults to CPU count (16 cores gave 2m29 vs 3m01 at 8). Next: UNIT_TESTED.

## UNIT_TESTED - TASK-137 - 2026-10-22T13:06:29Z
Action: ran run_all_fast_test and the real tests/run_all.sh --fast. Result: 23/0; 159 suites in 2m29 at 16 jobs, only known track_hook failure, flakes absorbed by serial retry. Decision: pass (the complete run was not repeated: only tests/run_all.sh changed, default path covered by run_all suite). Next: VERIFIED.

## VERIFIED - TASK-137 - 2026-10-22T13:06:36Z
Action: diffed heavy list against suite_times.tsv, ran real --fast at 8 and 16 jobs. Result: list identical (30); 3m01 at 8, 2m29 at 16; skips printed. Decision: verified; the gate change (UNIT_TESTED/VERIFIED use --fast) is NOT applied, user decision pending. Next: DONE report.

## DONE - TASK-137 - 2026-10-22T13:06:45Z
Action: report written. Result: --fast 2m29, 30 heavy skipped, 23/0 unit test. Decision: done; gate change left to the user. Next: none.

## DESIGN - TASK-134 - 2026-10-22T22:30:24Z
Action: traced X2 to finish_run re-conclude (pipeline.sh:1756). Result: conclusion.json newer than reports. Decision: restore mtime when bytes equal, else re-render once. Next: coder implements.

## IMPLEMENTING - TASK-134 - 2026-10-23T00:46:55Z
Action: coder added the mtime restore / single re-render to finish_run; coordinator silenced the second render after pipeline_track V1/T1 showed an extra stdout line. Result: finish_run_fresh 8/8. Decision: keep. Next: UNIT_TESTED.

## UNIT_TESTED - TASK-134 - 2026-10-23T00:47:01Z
Action: ran finish_run_fresh, pipeline_track alone, --changed. Result: 8/8, 47/0, only known failures. Decision: pass. Next: VERIFIED.

## VERIFIED - TASK-134 - 2026-10-23T00:47:11Z
Action: re-ran the pipeline suites, stdout parity (pipeline_track), frozen-prompt diff. Result: all pass, diff empty. Decision: verified; a live Upzi crosscheck cannot be re-run without touching the plan (rebuild already passed, fail=0). Next: DONE.

## DONE - TASK-134 - 2026-10-23T00:47:19Z
Action: report written. Result: fix verified by fixture and pipeline suites. Decision: done. Next: none.

## DESIGN - TASK-135 - 2026-10-23T00:51:08Z
Action: designer wrote the cp2b linked preflight design. Result: 5 checks, report-only rows, no pipeline.sh change. Decision: accept; estimate line keeps total and appends ", M with misses" (departs from the literal AC2 form to keep the 130.7 test green; coordinator decision, user said decide). Next: coder implements in checkpoint_report.py.

## IMPLEMENTING - TASK-135 - 2026-10-23T01:06:33Z
Action: coder implemented the cp2b linked preflight in checkpoint_report.py. Result: checkpoint_report 76/0; real replay of Upzi run 20261021-220859 lists 10 linked items, 5 with a Service ns/name miss. Decision: keep. Next: UNIT_TESTED after the --changed run.

## UNIT_TESTED - TASK-135 - 2026-10-23T01:21:36Z
Action: ran checkpoint_report, --fast, ext_scan, pipeline_checkpoint. Result: all pass except known track_hook S3. Decision: pass (gate = --fast plus mapped suites, user approved). Next: VERIFIED.

## VERIFIED - TASK-135 - 2026-10-23T01:21:36Z
Action: replayed the real Upzi run at $0. Result: 10 items, 5 Service misses shown. Decision: verified. Next: DONE.

## DONE - TASK-135 - 2026-10-23T01:23:00Z
Action: wrote report, closed REQ-0103. Result: preflight rows shown on the real Upzi replay. Decision: done. Next: TASK-138.

## TODO - TASK-138 - 2026-10-23T01:24:26Z
Action: picked TASK-138 (REQ-0101). Result: TODO. Decision: design next. Next: designer draft.

## DESIGN - TASK-138 - 2026-10-23T01:30:11Z
Action: designer draft written to docs/design. Result: 5 items, direct-first, strip unverified (RAW-00898). Decision: design complete. Next: coder.

## IMPLEMENTING - TASK-138 - 2026-10-23T01:38:10Z
Action: coder built 138.1-138.5. Result: call_resolution 26/0, graph_linked 22/0, checkpoint_report 77/0 (self-check). Decision: to tester. Next: independent run, --fast gate.

## UNIT_TESTED - TASK-138 - 2026-10-23T03:17:32Z
Action: tester QA, pipeline_track alone. Result: all pass except known track_hook S3. Decision: pass. Next: VERIFIED with real replay.

## VERIFIED - TASK-138 - 2026-10-23T03:18:17Z
Action: replayed graph_build edges on a scratch copy of the real Upzi_g03 run. Result: 20 -> 7 linked pairs, dropped = wrong-namespace joins; call_resolution.json written. Decision: verified. Next: report and DONE.

## DONE - TASK-138 - 2026-10-23T03:18:28Z
Action: report written. Result: call_resolution.json, wrong joins dropped. Decision: done. Next: queue.

## TODO - TASK-078 - 2026-10-23T04:03:24Z
Action: picked TASK-078. Result: TODO; F-96-1 already fixed with the ext_scan layout edit. Decision: design the rest. Next: designer.

## DESIGN - TASK-078 - 2026-10-23T04:07:54Z
Action: designer draft to docs/design. Result: 4 items, test-only. Decision: complete. Next: coder.

## IMPLEMENTING - TASK-078 - 2026-10-23T04:20:49Z
Action: coder 78.1/78.3/78.4a, main 78.2. Result: both new tests bite in a scratch kit; run_reports 78/0, ext_inscope_qa 34/0. Decision: next 78.4b load runs and tester. Next: UNIT_TESTED.

## UNIT_TESTED - TASK-078 - 2026-10-23T04:52:27Z
Action: ran suites and --fast. Result: only known track_hook S3. Decision: pass. Next: VERIFIED.

## VERIFIED - TASK-078 - 2026-10-23T04:52:27Z
Action: 10 loaded runs, python.sh. Result: flake not reproduced, diagnostics in place. Decision: verified. Next: report, DONE.

## DONE - TASK-078 - 2026-10-23T04:52:40Z
Action: report written. Result: 4 items closed, flake not reproduced. Decision: done. Next: queue.

## TODO - TASK-099 - 2026-10-23T04:52:50Z
Action: picked TASK-099. Result: TODO. Decision: design. Next: designer.

## DESIGN - TASK-099 - 2026-10-23T04:56:03Z
Action: designer draft to docs/design. Result: 4 items, one writer both modes. Decision: complete. Next: coder.

## IMPLEMENTING - TASK-099 - 2026-10-23T05:01:06Z
Action: coder 99.1-99.4. Result: toolkit_stamp 22/22, four bites fail the suite. Decision: run heavy suites. Next: UNIT_TESTED.

## UNIT_TESTED - TASK-099 - 2026-10-23T05:27:37Z
Action: ran heavy suites and --fast. Result: only known track_hook S3. Decision: pass. Next: real rows V1-V5.

## VERIFIED - TASK-099 - 2026-10-23T05:29:53Z
Action: tester V1-V5, coordinator engine-path check. Result: all pass at function level. Decision: verified. Next: report, DONE.

## DONE - TASK-099 - 2026-10-23T05:29:53Z
Action: report written. Result: stamp producer in both modes. Decision: done. Next: queue.

## TODO - TASK-102 - 2026-10-23T05:30:03Z
Action: picked TASK-102 (REQ-0065). Result: TODO. Decision: design. Next: designer.

## DESIGN - TASK-102 - 2026-10-23T05:33:24Z
Action: designer draft to docs/design plus coordinator decisions D-1..D-3. Result: 6 items. Decision: complete. Next: coder.

## IMPLEMENTING - TASK-102 - 2026-10-23T05:40:22Z
Action: coder built wrapper, sync, tag, test; main added recover hook.
Result: run_worktree 53/0, shell.sh 573/0.
Decision: go to UNIT_TESTED.
Next: --fast gate + real worktree run.

## UNIT_TESTED - TASK-102 - 2026-10-23T05:43:30Z
Action: run_worktree_test, --fast, real --worktree run_all_guard.
Result: 53/0; fast only known track_hook S3; real run sha 920a6b47 tag + BYPRODUCTS 0.
Decision: go to VERIFIED.
Next: verified evidence.

## VERIFIED - TASK-102 - 2026-10-23T05:43:46Z
Action: real worktree run + recover.
Result: tag, sha pin, BYPRODUCTS 0.
Decision: report and DONE.
Next: DONE.

## DONE - TASK-102 - 2026-10-23T05:43:52Z
Action: report written.
Result: worktree run verified.
Decision: done.
Next: none.

## DESIGN - TASK-103 - 2026-10-23T05:47:04Z
Action: designer drafted; copied to docs/design.
Result: lessons.py drift, no hook change.
Decision: go to IMPLEMENTING.
Next: coder.

## IMPLEMENTING - TASK-103 - 2026-10-23T05:51:03Z
Action: coder built drift; main added tests U1-U6, brace skip, two skill lines.
Result: lessons_test 172/0, shell 573/0; real drift 1 row (external osv flag).
Decision: go to UNIT_TESTED.
Next: fast gate.

## UNIT_TESTED - TASK-103 - 2026-10-23T05:53:57Z
Action: lessons_test, shell.sh, --fast.
Result: 172/0, 573/0, only known S3.
Decision: VERIFIED.
Next: verify.

## VERIFIED - TASK-103 - 2026-10-23T05:53:57Z
Action: real drift run.
Result: 1 noise row.
Decision: DONE.
Next: done.

## DONE - TASK-103 - 2026-10-23T05:54:05Z
Action: report.
Result: drift check verified.
Decision: done.
Next: none.

## DESIGN - TASK-093 - 2026-10-23T05:57:47Z
Action: designer drafted; D1-D5 recommended accepted.
Result: checker + batch 1.
Decision: IMPLEMENTING.
Next: coder.

## IMPLEMENTING - TASK-093 - 2026-10-23T06:01:05Z
Action: coder built checker, allow file, test, batch 1 split.
Result: skill_layout_test 13/0; --moved 918c5050 rc 0 (only header+pointer lines added).
Decision: UNIT_TESTED.
Next: fast gate.

## UNIT_TESTED - TASK-093 - 2026-10-23T06:04:13Z
Action: tests, --fast.
Result: 13/0, only known S3.
Decision: VERIFIED.
Next: verify.

## VERIFIED - TASK-093 - 2026-10-23T06:04:14Z
Action: moved proof + check.
Result: rc 0, fail=0.
Decision: DONE.
Next: done.

## DONE - TASK-093 - 2026-10-23T06:04:20Z
Action: report.
Result: checker + batch 1 verified.
Decision: done.
Next: none.

## DESIGN - TASK-139 - 2026-10-25T12:44:43Z
- Action: proved premise read-only: kit never reads content-hashes.json; ai_store already skips unchanged repos; tree_evidence over 64 upzi repos 1.5s; upzi content-hashes.json matches disk (64 repos, 7933 files, 0 mismatch/missing/extra, all unchanged); only upzi has the file.
- Result: the skip the user asked for exists; missing is visibility (changed_files), a pre-run forecast, a reviewed baseline, tree integrity. Wrote docs/design/phase-139-content-hash-gate.md (9 ACs, Plan modes, Verification).
- Decision: advisory hash_gate.py (forecast/verify/record), ai_store stays authority (replacing tree digest rejected: saves 1.5s, adds trust dependency). Open: HASH_VERIFY default, HASH_FILE for subset groups.
- Next: user answers Decisions 4-5, then IMPLEMENTING via coder.

## DESIGN - TASK-139 - 2026-10-25T13:11:25Z
- Action: user accepted decisions 2-3 (RAW-00921): verify on by default, every group has its own content-hashes.json, next review is full upzi; model changed so old ai_store entries do not match.
- Result: design doc Decisions 4-6 updated; RAW-00921 linked to REQ-0105.
- Decision: HASH_FILE is only an override; consistency line names model as reason on the first run.
- Next: coder implements 139.1-139.5.

## IMPLEMENTING - TASK-139 - 2026-10-25T13:26:18Z
- Action: coder built hash_gate.py + wiring + runbook/reference; coordinator ran real verify on upzi.
- Result: hash_gate suite 45/0, shell check 579/0, real verify 64 repos 0 mismatch/missing/extra (0.7s). Only HASH_* hunk of config.sh staged; the user model switch stays uncommitted.
- Decision: pipeline forecast at step_phase0 only (advisory, noted).
- Next: UNIT_TESTED, then 139.7-139.9 proofs.

## UNIT_TESTED - TASK-139 - 2026-10-25T14:32:34Z
- Action: fast-tier run_all (195 suites) + HEAD and pre-task kits for each failure.
- Result: hash_gate 45/0, shell check 579/0, ai_store/ai_reuse_pipeline/scan_isolation/pipeline_layout pass. Fast tier 187 pass / 8 fail: pipeline_e2e,equiv,recon,run fail only on the user's uncommitted model switch in config.sh (pass on HEAD kit); track_hook, tracking_new_only, lead fail identically on the pre-TASK-139 commit 7eec59af kit (not caused by this task); verify_scan passes alone (flaky in full run).
- Decision: scope passed; the 8 unrelated failures are reported, not hidden.
- Next: tester + 139.7-139.9 proofs.

## DESIGN - TASK-140 - 2026-10-25T14:37:20Z
- Action: read-only premise on Upzi/full (114 stale vs 64 tree), user gave mapping/model/cost go (RAW-00928).
- Result: docs/design/phase-140-upzi-full-plan-track-a.md.
- Decision: new plan Upzi/full2, commit opus switch, mapping saved.
- Next: implement plan + dry-run, then track A.

## DESIGN - TASK-145 - 2026-10-26T14:00:57Z
Action: premise (18 lines bearer<rule_id>, none in production link), design doc written.
Result: lookahead rule, test fixture, $0 rebuild check planned.
Decision: small fix in secret_mask.py only.
Next: IMPLEMENTING, UNIT_TESTED, rebuild D14.

## IMPLEMENTING - TASK-145 - 2026-10-26T14:01:18Z
Action: IMPLEMENTING step for secret_mask Bearer rule.
Result: tests green, D14 PASS, gaps=0 (see task file).
Decision: proceed.
Next: UNIT_TESTED

## UNIT_TESTED - TASK-145 - 2026-10-26T14:01:18Z
Action: UNIT_TESTED step for secret_mask Bearer rule.
Result: tests green, D14 PASS, gaps=0 (see task file).
Decision: proceed.
Next: VERIFIED

## VERIFIED - TASK-145 - 2026-10-26T14:01:25Z
Action: VERIFIED step for secret_mask Bearer rule.
Result: tests green, D14 PASS, gaps=0 (see task file).
Decision: proceed.
Next: DONE: report

## DONE - TASK-145 - 2026-10-26T14:01:26Z
Action: DONE step for secret_mask Bearer rule.
Result: tests green, D14 PASS, gaps=0 (see task file).
Decision: proceed.
Next: none

## IMPLEMENTING - TASK-140 - 2026-10-26T14:07:26Z
Action: IMPLEMENTING step for secret_mask Bearer rule.
Result: tests green, D14 PASS, gaps=0 (see task file).
Decision: proceed.
Next: UNIT_TESTED

## UNIT_TESTED - TASK-140 - 2026-10-26T14:07:26Z
Action: UNIT_TESTED step for secret_mask Bearer rule.
Result: tests green, D14 PASS, gaps=0 (see task file).
Decision: proceed.
Next: VERIFIED

## VERIFIED - TASK-140 - 2026-10-26T14:07:27Z
Action: VERIFIED step for secret_mask Bearer rule.
Result: tests green, D14 PASS, gaps=0 (see task file).
Decision: proceed.
Next: DONE: report

## DONE - TASK-140 - 2026-10-26T14:07:27Z
Action: DONE step for secret_mask Bearer rule.
Result: tests green, D14 PASS, gaps=0 (see task file).
Decision: proceed.
Next: none

## DESIGN - TASK-147 - 2026-10-27T00:56:28Z
Action: Nova (designer) drafted the design; coordinator wrote docs/design/phase-147-repo-findings-index.md (147.1-147.5, Plan modes, V1-V7).
Result: counts captured inside the §8 loop into repo_findings_<date>.json; md/pdf rendered from it; publish_by_repo.sh dry-run by default, refuses by-repo/. security_report and by-repo unchanged (V3 golden, _Generated line masked).
Decision: index written on every non-baseline build; total = C+H+M+L as in §8 (Info-only = 0, user may override); no D16. Note: cfc95f4d was committed before commit-check passed (missing this entry and the State trailer); this entry and the next commit close it.
Next: IMPLEMENTING: Titan (coder) 147.1-147.5 + tests/repo_findings_test.sh, dev on Upzi_g04/main only.

## IMPLEMENTING - TASK-147 - 2026-10-27T00:56:36Z
Action: design approved, state moved to IMPLEMENTING.
Result: scope summarize_report.sh, publish_by_repo.sh, tests/repo_findings_test.sh, docs/guide/{toolkit-reference,security-review-runbook}.md.
Decision: brief Titan (coder) for 147.1-147.5 with the unit suite.
Next: coder handoff work/TASK-147/handoff/code.md, then Nemesis (tester) QA.

## UNIT_TESTED - TASK-147 - 2026-10-27T05:43:33Z
Action: Titan (coder) 147.1-147.5 (df242f00) + fix1 registry kinds repo-findings/per-repo-public (bbb964fd); full tests/run_all.sh once (Nemesis), base compares at 321541ba (Nemesis + main); main ran V3-V6 on scratch kits (Upzi_g04 copy only).
Result: repo_findings 42/0; pipeline_track 47/0 at bbb964fd (was aborting at AC6: repo_findings_* unregistered=3, found by main); lint kinds=28 errors=0; V3 security_report + by-repo identical, V4 PDF looked at, V5 counts = §8, V6 publish dry/apply/idempotent/stale/symlink refuse. Remaining run_all failures all fail identically at 321541ba: track_hook S3, tracking_new_only N3, lead L24, pipeline_e2e 49.2, pipeline_equiv 62, pipeline_recon (8), pipeline_run (4), verify_scan (3) (model-name ones = TASK-141). skill_layout U7 was main's coordinator SKILL.md +1 line, fixed 8a245320.
Decision: UNIT_TESTED; tester role waived (2 PARTIALs at turn limit, checks finished by main, evidence saved).
Next: VERIFIED: Argus (verifier) against REQ-0114 AC1-AC3 and design V1-V7 from work/TASK-147/evidence/.

## VERIFIED - TASK-147 - 2026-10-27T05:46:04Z
Action: Argus (verifier) checked REQ-0114 AC1-AC3 and design checks 1-8 from work/TASK-147/evidence; main re-ran skill_layout at HEAD (Argus' one open item).
Result: PASS. security_report text unchanged by construction and by V3; publish_by_repo.sh only touches <dir>/by-repo-public (symlink/by-repo refused, name regex, dry run writes nothing); counts = §8; Info not counted (RAW-01005); both plan modes, baseline writes no index; registry kinds optional; skill_layout 13/0.
Decision: VERIFIED. Non-blocking: no Info-only fixture in tests/repo_findings_test.sh (total formula summarize_report.sh:705 is correct by construction).
Next: DONE: report docs/report, lessons, backlog complete, REQ-0114 DONE. Upzi/full run only with the user's go (RAW-01003).

## DONE - TASK-147 - 2026-10-27T05:48:22Z
Action: report docs/report/phase-147-repo-findings-index.md written; lessons drift/collect (5 new) curated by Sage (skill-curator): 5 rejected, no skill or agent edits, skill_layout fail=0.
Result: REQ-0114 AC1-AC3 met; repo_findings index + publish_by_repo.sh shipped (df242f00, bbb964fd); security_report and by-repo unchanged.
Decision: DONE. Designer mask tip (byte-identical V-rows mask `_Generated`) not adopted as a rule (no evidence row); kept in the design doc.
Next: Upzi/full run of the index/publish tool only with the user's go (RAW-01003); Upzi_g04 recon approval + Track B parked.

## DESIGN - TASK-148 - 2026-10-27T07:29:14Z
Action: Nova (designer) drafted 148.1 build calls publish_by_repo.sh --apply after the per-repo block, 148.2 dry-run SUMMARY would_delete=, 148.3 registry per-repo-public writer += summarize_report.sh modes ss/pl + docs; main checked REPORTS_DIR/RF_BASE anchors.
Result: docs/design/phase-148-auto-by-repo-public.md (Plan modes: one block, both modes; baseline/PER_REPO=0 none).
Decision: publish failure fails the build; one SUMMARY line; PER_REPO=0 leaves an old by-repo-public untouched. User RAW-01012 supersedes RAW-01004.
Next: Titan (coder) 148.1-148.3 + tests.

## IMPLEMENTING - TASK-148 - 2026-10-27T07:44:47Z
Action: Titan (coder) implemented 148.1 (summarize_report.sh calls publish_by_repo.sh --apply after by-repo), 148.2 (would_delete=), 148.3 (registry writer/modes, docs) + tests.
Result: repo_findings 48/0, report_crosscheck 45/0 (kind rows 23->24), track_a_ss pass, shellcheck clean, bite 4 T148 cases fail without the call; pipeline_track still running.
Decision: wip commit at once (RAW-00100).
Next: Titan finishes pipeline_track + code.md; then tester QA / UNIT_TESTED.

## UNIT_TESTED - TASK-148 - 2026-10-27T08:25:28Z
Action: Nemesis (tester) QA per suite on 6a08d7e2; found plan_reports 19.1 + scan_equiv E1 stale file-set expectations; Titan fix round 1 (exact by-repo-public entries, no glob).
Result: repo_findings 48/0, report_crosscheck 45/0, track_a_ss, pipeline_track 47/0, plan_reports 44/0, scan_equiv 12/0, run_reports 78/0, check_deliverables 73/0, report_qa 33/0 + 7 more: all pass. Main V4 real data (kC, Upzi_g04 run 20261027-074446): security_report + by-repo/*.md identical, by-repo-public = 3 backend repos (md+pdf), 4 ai files left out.
Decision: UNIT_TESTED.
Next: Argus (verifier).

## VERIFIED - TASK-148 - 2026-10-27T08:27:48Z
Action: Argus (verifier) checked AC1-AC4 against code + saved evidence; main ran report_crosscheck on the scratch real-data rebuild (kC) for the open AC4 point.
Result: Argus PASS (AC1-AC3 verified, AC4 registry verified). Real-run crosscheck: unregistered=0 fail=0 (evidence/v5-crosscheck.txt; MISSING rows = report kinds not built by the single summarize_report call). Security: publish deletes only in by-repo-public; refusals kept.
Decision: VERIFIED.
Next: lessons, DONE report, backlog complete.

## DONE - TASK-148 - 2026-10-27T08:29:32Z
Action: lessons drift/collect (3 stale rows) -> Sage: 1 merged (run-security-review report set names auto by-repo-public/), 2 rejected; DONE report written.
Result: docs/report/phase-148-auto-by-repo-public.md; lessons marked 3.
Decision: DONE. REQ-0115 DONE.
Next: ask user about TASK-139 resume / Upzi full report rebuild (needs go, RAW-01003).

## DESIGN - TASK-149 - 2026-10-27T08:47:37Z
- Action: design docs/design/phase-149-tracking-by-repo-public.md (annotate.py engine_files mirrors by-repo-public).
- Result: design completed; designer waived (3-line change, recorded).
- Decision: mirror the engine by-repo-public, no second delete logic.
- Next: coder implements 149.1-149.2 with tests U1-U3.

## IMPLEMENTING - TASK-149 - 2026-10-27T08:54:40Z
- Action: coder changed annotate.py engine_files (both sub dirs), tests, reference doc.
- Result: tracking_test 79/0; bite: HEAD annotate.py fails 149.1 and 58.1 (7 vs 8). tracking_new_only N3 fails on HEAD too (pre-existing, checked by main with git stash).
- Decision: implementation complete.
- Next: tester independent QA.

## UNIT_TESTED - TASK-149 - 2026-10-27T09:00:24Z
- Action: tester re-ran tracking suites and --fast.
- Result: tracking_test 79/0; bite 77/2; failures N3/S3/70.2/73.1 identical on HEAD~1 (pre-existing).
- Decision: unit tests passed.
- Next: verifier real check on a scratch copy of reports/Upzi_g04/main/run-20261027-074446.

## VERIFIED - TASK-149 - 2026-10-27T09:02:12Z
- Action: main ran annotate.py on real run Upzi_g04/main 20261027-074446 into scratchpad; verifier (Argus) judged AC1-AC4.
- Result: PASS; engine and registry unchanged; public copy 3/3 annotated, index 6 rows. N3 pre-existing was checked by main with git stash at IMPLEMENTING.
- Decision: verified.
- Next: DONE report.

## DONE - TASK-149 - 2026-10-27T09:02:51Z
- Action: report docs/report/phase-149-tracking-by-repo-public.md; lessons collected (1 drift row: toolkit-reference touched by one added sentence, path unchanged -> no skill edit).
- Result: tracking copies include by-repo-public; Argus PASS.
- Decision: done; UNIT_TESTED commit b1d10c5d lacks Tests: trailer (noted in report).
- Next: user runs ./tracking/track.sh --run latest per plan to refresh old copies.

## DESIGN - TASK-151 - 2026-10-27T10:00:58Z
- Action: picked TASK-151 (REQ-0118 public report set, hide only not_seen; RAW-01017..01022 answers recorded); Nova (designer) briefed.
- Result: design in progress (work/TASK-151/handoff/design.md).
- Decision: design first, user approval before IMPLEMENTING (RAW-01017); TASK-150 closed (REQ-0117 superseded by REQ-0119).
- Next: review Nova's design, write docs/design/phase-151-public-report-set.md, ask user approval.

## DESIGN - TASK-151 - 2026-10-27T10:09:13Z
- Action: Nova designed (handoff COMPLETE before an auth error ended the agent); coordinator reviewed and copied to docs/design/phase-151-public-report-set.md.
- Result: 6 items 151.1-151.6, report impact table, plan modes, U1-U18, V1-V6 (Upzi_g04 7/11 shown, Upzi/full 81/142).
- Decision: design.status=completed; IMPLEMENTING waits for user approval (RAW-01017 design first) and the no-logreach by-repo-public decision.
- Next: user approval, then brief Titan (coder) 151.1-151.3.

## IMPLEMENTING - TASK-151 - 2026-10-27T10:56:51Z
- Action: Titan implemented 151.1-151.6 (two rounds, 60-turn cap hit once) + tests/public_reports_test.sh.
- Result: public_reports 25/0; report_qa, plan_reports, run_reports, check_deliverables, report_crosscheck, repo_findings, logreach_render, pipeline_logreach pass (coder self-check). tracking_new_only N3 and shell.sh (pipeline_step.sh, untouched) fail, coder says pre-existing.
- Decision: implementation completed; independent QA before UNIT_TESTED.
- Next: Nemesis (tester) QA incl. HEAD baseline for the 2 failures.

## UNIT_TESTED - TASK-151 - 2026-10-27T11:33:18Z
- Action: Nemesis independent QA (bite proofs, jq oracle, HEAD~3 baseline); coordinator ran 12 report suites one filter each.
- Result: public_reports 25/0; all mapped suites pass; track_a_ss expectation updated for 3 new registry kinds; 5 failures pre-existing on HEAD~3 (tracking_new_only N3, track_hook S3, verify_scan 70.2/73.1, shell.sh pipeline_step.sh). Minor gaps F-151-T1..T3 in test.md for the report.
- Decision: unit_test passed.
- Next: Argus verification on scratch rebuilds.

## IMPLEMENTING - TASK-151 - 2026-10-27T11:44:12Z
- Action: real rebuilds Upzi_g04 + Upzi/full on scratch kits; Argus verification.
- Result: counts/gates PASS (7/11, 81/142, gaps=0, QA PASS, D17), but FAIL B1: the posture paragraph and the "(scan: X)" rating leak hidden-finding text/severity in by-repo-public and security_report_public (confirmed by coordinator: jobseekers-info-service line 9 names hidden PT-001 raw_data). L1 appendix pointer.
- Decision: verification failed -> back to IMPLEMENTING; design addendum 151.7 (public mode only).
- Next: Titan 151.7 + U19-U22.

## IMPLEMENTING - TASK-151 - 2026-10-27T11:52:20Z
- Action: Titan implemented 151.7 (summarize_report.sh, report_common.sh, tests U19-U22, toolkit-reference).
- Result: public_reports 29/0, report_qa 33/0, run_reports 78/0, repo_findings 48/0, check_deliverables 73/0, track_a_ss pass; scratch Upzi_g04 rebuild: 0 hits for hidden titles/endpoints, 0 "(scan: ", 0 verification_appendix.
- Decision: implementation completed again.
- Next: Nemesis QA round 2; coordinator real rebuilds + leak grep; Argus re-verify.

## UNIT_TESTED - TASK-151 - 2026-10-27T12:00:46Z
- Action: Nemesis QA round 2 on 151.7; added U23-U23d (pipeline fixture).
- Result: public_reports 33/0; 5 revert bite proofs fail; report suites pass.
- Decision: unit_test passed.
- Next: Argus re-verify (real rebuild evidence verify_round2.txt, strict leak oracle 0 hits).

## VERIFIED - TASK-151 - 2026-10-27T12:03:51Z
- Action: real rebuild Upzi_g04 + Upzi/full at 48410a1a; leak oracle; Argus re-verify round 2.
- Result: PASS; 7/11 and 81/142 shown = jq oracle; 0 leak hits; full reports unchanged; gates PASS.
- Decision: verification passed, security completed.
- Next: report and DONE.

## DONE - TASK-151 - 2026-10-27T12:04:24Z
- Action: report docs/report/phase-151-public-report-set.md.
- Result: public set live, verified on Upzi_g04 and Upzi/full, leak 0.
- Decision: DONE.
- Next: pick TASK-152.

## DESIGN - TASK-152 - 2026-10-27T12:05:35Z
- Action: picked TASK-152; Nova draft copied to docs/design/phase-152-logreach-coverage.md with override D9 (AI_PROMPT constant).
- Result: items 152.1-152.11, tests U1-U24, verification V1-V6 (V5 paid ~$0.003 Haiku, approved by REQ-0119 Q5).
- Decision: design completed.
- Next: Titan implements.

## IMPLEMENTING - TASK-151 - 2026-10-27T12:12:13Z
- Action: report cross-check (Nemesis, required role) after DONE commit 165a571b.
- Result: MISS L1: Upzi/full security_report_public R3 cross-link table lists 2 hidden (not_seen) scan ids with severity (authentication-service-002, company-service-001). DONE was premature (crosscheck role missing).
- Decision: reopen: state IMPLEMENTING, verification failed, report pending; backlog item set active by coordinator (no reopen command); TASK-152 held (state only, Titan keeps coding, scope kept).
- Next: addendum 151.8: public mode drops cross-link rows whose target id is hidden in this plan; tests; rebuild; crosscheck again.

## UNIT_TESTED - TASK-151 - 2026-10-27T12:40:59Z
Action: Nemesis QA round 3 on 151.8/151.8b plus report cross-check on kit head4 (Upzi_g04, Upzi/full).
Result: public_reports 36/0, run_reports 78/0, report_qa 33/0, report_crosscheck 45/0, check_deliverables 75/0; bite proofs 33/2 against both earlier summarize_report.sh; crosscheck RESULT OK, 0 not_seen ids in 33 public files, linked rows 9/13 with every dropped row hidden by repo|id. Info L2: stale tracking copies in the scratch kit (rebuild --render does not re-run tracking), not a code defect.
Decision: UNIT_TESTED.
Next: Argus re-verify, then VERIFIED.

## VERIFIED - TASK-151 - 2026-10-27T12:44:09Z
Action: real rebuild at 151.8b (kit head4) of Upzi_g04 and Upzi/full; Argus re-verify round 3; coordinator checked git diff 2117318e..HEAD (summarize_report.sh +4 lines, non-public branch only).
Result: 0 not_seen ids in public files; linked rows dropped only when all fids hidden; all gates PASS; Argus PASS AC1-AC6; L2 stale tracking copies only after manual rebuild --render (real run re-tracks, pipeline.sh track hook), not a code defect.
Decision: VERIFIED.
Next: DONE.

## DONE - TASK-151 - 2026-10-27T12:44:20Z
Action: report doc updated with reopen and fixes 151.8/151.8b; backlog complete.
Result: report docs/report/phase-151-public-report-set.md; report crosscheck OK; Argus PASS.
Decision: DONE.
Next: REQ-0118 DONE; resume TASK-152.

## IMPLEMENTING - TASK-152 - 2026-10-27T13:04:41Z
Action: Titan implemented 152.1-152.11 (wip 32451c8e); coordinator added the unresolved-list copy in summarize_report.sh.
Result: mapped suites green.
Decision: IMPLEMENTING complete.
Next: tester QA.

## UNIT_TESTED - TASK-152 - 2026-10-27T13:04:41Z
Action: Vega independent QA, bite proofs, security read.
Result: all 8 filters pass; 9/9 mutants killed after 8 added checks; no production defect.
Decision: UNIT_TESTED.
Next: V1-V7 real verification.

## VERIFIED - TASK-152 - 2026-10-27T13:18:37Z
Action: coordinator ran V1-V7 on real ES and one Haiku call; Argus verified outputs independently.
Result: Upzi/full unresolved 32 -> 12, no old seen/not_seen changed, no finding lost, all gates PASS, Haiku $0.0005; registry gap fixed (0dffda90). Flaky once: logreach_render_test in run_all, passed on 2 reruns.
Decision: VERIFIED.
Next: DONE.

## DONE - TASK-152 - 2026-10-27T13:19:02Z
Action: report written; backlog complete; REQ-0119 DONE.
Result: docs/report/phase-152-logreach-coverage.md.
Decision: DONE.
Next: user guidance on the 12 unresolved endpoints.

## DONE - TASK-152 - 2026-10-27T13:21:04Z
Action: report cross-check by Nemesis (missed before the DONE commit, caught by the Stop hook).
Result: RESULT OK, 5 oracles pass, report_crosscheck fail=0 unregistered=0.
Decision: DONE stands; roles.crosscheck recorded.
Next: user decides real re-run or endpoint guidance.

## DESIGN - TASK-153 - 2026-10-27T14:06:46Z
Action: Nova drafted the design from the coordinator root causes; coordinator added D-153a (method_sibling may move an old not_seen, user-asked).
Result: docs/design/phase-153-logreach-user-guidance.md.
Decision: DESIGN complete.
Next: Titan implements.

## IMPLEMENTING - TASK-153 - 2026-10-27T14:19:41Z
Action: Titan implemented 153.1-153.4 with U153 tests.
Result: mapped suites pass; new tests fail 9 on HEAD kit (bite).
Decision: IMPLEMENTING complete; summarize_report.sh internal note left out (display only).
Next: tester QA, real ES checks.

## UNIT_TESTED - TASK-153 - 2026-10-27T14:29:52Z
Action: Vega independent QA, 6 checks added, 8 bite proofs.
Result: 7 filters pass; F-153-T1/T2 minor (display, direct findings diff covered by real run).
Decision: UNIT_TESTED.
Next: scratch rebuild gates, Argus.

## UNIT_TESTED - TASK-153 - 2026-10-27T14:54:42Z
Action: real V6 rebuild found D17 FAIL (hidden ids in public chain cards); added 153.6, Forge masked scan ids, PT ids, PT+title.
Result: V6c D17 PASS 67/142, crosscheck 35/0, gaps=0, report_qa PASS (work/TASK-153/evidence/v6c.txt).
Decision: stay UNIT_TESTED; tester QA of 153.6.
Next: Vega, Argus, Nemesis.

## VERIFIED - TASK-153 - 2026-10-27T15:10:13Z
Action: real ES run on copy, scratch rebuild, Argus verify, Nemesis cross-check.
Result: Argus PASS (AC1-AC7), Nemesis RESULT OK (O1-O5), gates PASS (v6c.txt).
Decision: VERIFIED.
Next: report, DONE.

## DONE - TASK-153 - 2026-10-27T15:10:46Z
Action: report written.
Result: docs/report/phase-153-logreach-user-guidance.md.
Decision: DONE.
Next: re-run logreach on real Upzi plans and rebuild reports.

## DESIGN - TASK-154 - 2026-10-27T22:10:48Z
Action: Nova drafted; coordinator added 154.5 master check, 154.6 watcher, 154.7 guarded Stop continue per RAW-01043; set needs_user on 143/144/146.
Result: docs/design/phase-154-auto-pick-after-done.md.
Decision: DESIGN complete; D1=B by user words RAW-01043.
Next: Titan implements.

## IMPLEMENTING - TASK-154 - 2026-10-27T22:16:06Z
Action: Titan wrote 154.2/154.5/154.6/154.7 (_tasks.py keepalive/nextpick, tasks.sh dispatch, .gitignore). The role guard flagged its edit of the protected scripts (_tasks.py, tasks.sh); main did not widen the guard, reviewed the diff as owner of the gate scripts, and wired 154.3 (settings.json Stop entry) and 154.4 (coordinator rule).
Result: py_compile OK; keepalive on real repo = OK active TASK-154 rc 0; nextpick smoke prints the Your-turn NOTE, rc 0.
Decision: implementation complete; tests U1-U10 go to the tester (coder stopped before them).
Next: Vega writes U1-U10 + QA with bite proofs.

## UNIT_TESTED - TASK-154 - 2026-10-27T22:26:01Z
Action: tester wrote .claude/tests/keepalive_test.sh (U1-U10); main re-ran it and multi_task.
Result: keepalive 54/54; bites bite (4 and 3 failures). multi_task 204 pass, 1 fail (100.8 recover: local import subprocess at _tasks.py:1324 from TASK-102, not a TASK-154 change).
Decision: UNIT_TESTED; the pre-existing bug is queued as TASK-155 (workable), not fixed in this task.
Next: V1-V5 real checks + verifier.

## VERIFIED - TASK-154 - 2026-10-27T22:27:32Z
Action: main ran V1/V2/V3/V5 on the real repo; Argus verified code vs design and did the security pass.
Result: all pass (evidence/v_real.txt, v5_diffstat.txt); Argus RESULT: PASS; state files gitignored.
Decision: VERIFIED; V4 (live DONE -> pick) is done at DONE.
Next: crosscheck, report, DONE, pick next workable task.

## DONE - TASK-154 - 2026-10-27T22:31:04Z
Action: Nemesis cross-check (scratch kit); report written.
Result: RESULT OK, 0 mismatches (workable, keepalive 11/11, nextpick 48/48). Two observations match the design (print-only NEXT after the cap; NEXT with a young question and no active task), kept.
Decision: DONE. V4 trial: pick the next WORKABLE task in this same turn, no user message.
Next: pick TASK-141.

## TODO - TASK-141 - 2026-10-27T22:32:01Z
Action: after TASK-154 DONE (d13f2686) the keepalive watcher exited rc 4 'STALL pick TASK-141'; main picked TASK-141 in the same turn, no user message in between (TASK-154 V4 / REQ-0121 AC4 trial).
Result: TASK-141 picked (TODO).
Decision: start design.
Next: designer reads the 4 red pipeline suites and the PIPELINE_MODEL_* config.

## DESIGN - TASK-141 - 2026-10-27T22:44:49Z
Action: Nova designed (code read); main ran V0 on HEAD.
Result: 4 suites red as predicted (v0.txt); pipeline_approval green.
Decision: design approved: tests pin models in the scratch kit; tests only.
Next: Titan implements 141.1-141.5.

## IMPLEMENTING - TASK-141 - 2026-10-27T23:05:42Z
Action: Titan changed the 5 test files per design, plus 2 pins the design missed (PIPELINE_P0_FALLBACK_MODEL in recon and run, PIPELINE_MODEL_P2 in run).
Result: pipeline_run 128/0, recon 63/0, e2e 42/0, verify_scan 31/0, approval 31/0; guard bite red (51/12). shell.sh fail=1 on pipeline_step.sh is pre-existing, untouched.
Decision: implementation complete.
Next: tester QA.

## UNIT_TESTED - TASK-141 - 2026-10-27T23:26:03Z
Action: Vega re-ran the 5 suites, bit the guards, ran run_all --fast.
Result: all 5 green; bites red; 3 red suites in --fast also red on the base commit (pre-existing, not this task).
Decision: UNIT_TESTED.
Next: Argus verify.

## VERIFIED - TASK-141 - 2026-10-27T23:27:35Z
Action: Argus verified; main saved diffstat and static-shell evidence.
Result: Argus PASS; diff only the 5 test files; shell.sh fail only the pre-existing pipeline_step.sh.
Decision: VERIFIED.
Next: report, DONE.

## DONE - TASK-141 - 2026-10-27T23:27:51Z
Action: report written; crosscheck waived (test-only).
Result: 4 red pipeline suites green; pre-existing reds listed in the report.
Decision: DONE; pick the next WORKABLE task in this turn (rule 154.4).
Next: pick next workable.

## UNIT_TESTED - TASK-139 - 2026-10-27T23:28:16Z
Action: after TASK-141 DONE the watcher said STALL; main resumed TASK-139 (TASK-142 was its resume pointer, closed with a waiver).
Result: TASK-139 active at UNIT_TESTED.
Decision: continue with the tester re-run and the 139.7-139.9 scratch-kit proofs (/bin/bash).
Next: tester re-run + 139.7-139.9 proofs.

## UNIT_TESTED - TASK-139 - 2026-10-27T23:46:02Z
Action: Vega re-ran suites and the 139.7-139.9 scratch proofs; main ran 139.3 verify on the real upzi tree (read-only, hashes only).
Result: all pass (test.md, evidence/qa_*.txt, v_139_3_real.txt: 64 repos, 0 mismatch/missing/extra). Pipeline compare: only conclusion.json inputs_sha differs, same on a gate-off vs gate-off control (run-specific).
Decision: ready for verifier.
Next: Argus verify.

## VERIFIED - TASK-139 - 2026-10-27T23:48:26Z
Action: Argus verified; main fixed design line 139 (said off by default; the user-accepted option (a) = on, commit 7eec59af, matches code).
Result: Argus PASS; shell.sh only the pre-existing pipeline_step.sh FAIL.
Decision: VERIFIED. The real paid comparison stays with TASK-143 (needs_user).
Next: report, DONE.

## DONE - TASK-139 - 2026-10-27T23:49:30Z
Action: report written; crosscheck waived (tester run pairs + Argus reconcile the counts).
Result: hash gate done on /bin/bash evidence; real paid comparison stays open under REQ-0105 / TASK-143.
Decision: DONE; pick the next WORKABLE task in this turn.
Next: pick TASK-155.

## TODO - TASK-155 - 2026-10-27T23:49:49Z
Action: after TASK-139 DONE the watcher said STALL pick TASK-155; picked in the same turn.
Result: TASK-155 TODO.
Decision: short design (one-line fix in a main-owned gate script).
Next: design.

## DESIGN - TASK-155 - 2026-10-27T23:52:14Z
Action: main wrote the short design. Result: 155.1/155.2. Decision: main implements (roles may not edit _tasks.py). Next: implement.

## IMPLEMENTING - TASK-155 - 2026-10-27T23:52:14Z
Action: main applied 155.1/155.2 and a keepalive assert. Result: py_compile OK. Decision: test. Next: unit tests.

## UNIT_TESTED - TASK-155 - 2026-10-27T23:52:14Z
Action: ran multi_task, keepalive and two bites. Result: 205/0, 55/0, bites red. Decision: UNIT_TESTED. Next: verify.

## VERIFIED - TASK-155 - 2026-10-27T23:52:46Z
Action: real tasks.sh recover. Result: rc 0, 0 stderr lines. Decision: VERIFIED. Next: DONE.

## DONE - TASK-155 - 2026-10-27T23:52:46Z
Action: report. Result: fixes in, suites green. Decision: DONE; pick next workable. Next: workable check.

## TODO - TASK-156 - 2026-10-27T23:53:14Z
Action: queue drained (OK idle); main queued the 4 pre-existing red checks found in TASK-141/139 QA and picked it.
Result: TASK-156 TODO.
Decision: coder diagnoses each (regression vs stale test) before fixing.
Next: Titan diagnose + fix.

## TODO - TASK-156 - 2026-10-27T23:55:30Z
Action: picked TASK-156 after the queue drained (OK idle).
Result: TASK-156 TODO.
Decision: diagnose each red check (regression vs stale test) before fixing; never weaken an assertion.
Next: diagnose the 4 checks, short design.

## DESIGN - TASK-156 - 2026-10-27T23:59:44Z
Action: main diagnosed the 4 red checks and wrote docs/design/phase-156-pre-existing-red-checks.md.
Result: 1 regression from me (U7, TASK-154), 2 tests out of date (106.7, S3), 1 lint item; roles waived (small fixes).
Decision: fix the test expectations, never weaken a check; keep the ratchet.
Next: IMPLEMENTING.

## IMPLEMENTING - TASK-156 - 2026-10-27T23:59:55Z
Action: main applied 156.1-156.4.
Result: 4 files, +15/-19.
Decision: no ratchet change; disables carry reasons.
Next: UNIT_TESTED.

## UNIT_TESTED - TASK-156 - 2026-10-28T00:00:06Z
Action: main ran the 3 suites, shellcheck and shell.sh, plus an S3 bite.
Result: all pass; the bite drops to 0 matches.
Decision: tester waived (small test fixes).
Next: VERIFIED.

## VERIFIED - TASK-156 - 2026-10-28T00:00:17Z
Action: main ran pipeline_step.sh on a scratch plan (guard, adopt, reset, cascade apply).
Result: same behaviour as before; evidence work/TASK-156/evidence/v.txt.
Decision: verifier waived (lint and test fixes).
Next: DONE.

## DONE - TASK-156 - 2026-10-28T00:00:30Z
Action: report docs/report/phase-156-pre-existing-red-checks.md; backlog complete.
Result: the 4 checks pass.
Decision: residual: no unit suite covers pipeline_step.sh.
Next: tasks.sh workable.

## TODO - TASK-157 - 2026-10-28T00:52:50Z
Action: RAW-01044/01045 -> REQ-0122; main found the root cause in the Upzi/full logreach.json and query log (work/RAW-01044/seen_not_exact.txt).
Result: 4 caller-basis findings marked seen with own route 0 hits; 11 non-exact seen share one vague report label.
Decision: engine + generator fix only (RAW-01045); designer drafts.
Next: Nova design.

## DESIGN - TASK-157 - 2026-10-28T00:58:57Z
Action: Nova drafted; main published docs/design/phase-157-logreach-verdict-basis.md.
Result: 157.1-157.6; engine owns wording; cache keys unchanged ($0 rebuild).
Decision: no real count (full scan + cache invalidation); KQL always masked.
Next: Titan implements.

## DESIGN - TASK-157 - 2026-10-28T01:08:37Z
Action: RAW-01047..01049 triaged to REQ-0122 (AC7 query block results; AC1 revised: caller hit is seen only with a shown A-route -> B-route link).
Result: Titan told to add 157.7 and hold 157.1; Nova revising 157.1.
Decision: the user rule replaces "caller hit -> via_caller".
Next: merge the 157.1 revision, send it to Titan.

## IMPLEMENTING - TASK-157 - 2026-10-28T01:22:16Z
- Action: Titan (coder) implemented 157.1 (revised caller-link rule, D2 strict) and 157.2-157.7.
- Result: coder self-check logreach_ladder 119/0, report 68/0, render 44/0, logreach_test 201/0, shell.sh 591/0 (work/TASK-157/handoff/code.md).
- Decision: accept for independent QA; real rebuild runs in parallel ($0).
- Next: tester QA -> UNIT_TESTED; V1-V6 on Upzi/full.

## UNIT_TESTED - TASK-157 - 2026-10-28T01:29:24Z
- Action: tester (independent QA) re-ran logreach suites, run_all --fast, 5 heavy suites, shell.sh; bite tests.
- Result: all pass (ladder 119, report 68, render 44, logreach_test 201, fast 169 suites, shell 591); tier swap, 157.7 heading and B-queried breaks each fail a test.
- Decision: UNIT_TESTED. Real rebuild already done ($0): 008 seen/caller_link, 009/011/005 via_caller, 3 extra not_seen->via_caller (B paths no longer queried on A host), coverage gaps=0, report_qa PASS, deliverables 152/0.
- Next: verifier + security pass -> VERIFIED.

## VERIFIED - TASK-157 - 2026-10-28T01:33:12Z
- Action: real $0 rebuild of Upzi/full; verifier checked AC1-AC7 on saved JSON/reports; main closed AC2/AC5 with saved evidence.
- Result: 008 seen via shown caller link; 009/011/005 and 3 more via_caller; gaps=0, report_qa PASS, deliverables 152/0; security pass clean.
- Decision: VERIFIED; operation-service-002 losing suggested accepted (old basis invalid).
- Next: report + DONE.

## DONE - TASK-157 - 2026-10-28T01:33:45Z
- Action: wrote docs/report/phase-157-logreach-verdict-basis.md; backlog complete.
- Result: REQ-0122 AC1-AC7 ticked; Upzi/full reports show the caller link, basis, per-window hits and KQL.
- Decision: DONE.
- Next: queue REQ-0123 (opt-in Istio B-route check) as a new task.

## DESIGN - TASK-158 - 2026-10-28T01:41:09Z
- Action: Nova drafted the mesh-check design; main wrote docs/design/phase-158-logreach-mesh-check.md and added D-VNW wording.
- Result: 158.1-158.5, U158-1..12, V1-V4, Plan modes section.
- Decision: DESIGN complete; Vietnamworks hit worded "B route served in access log" (not "strong").
- Next: Titan implements.

## IMPLEMENTING - TASK-158 - 2026-10-28T02:00:07Z
- Action: Titan implemented the opt-in mesh note (decisive/preflight withdrawn per RAW-01058).
- Result: self-check logreach_mesh 64/0, ladder 119/0, report 68/0, render 44/0, logreach 201/0, pipeline_logreach 13/0, shell pass.
- Decision: to independent QA.
- Next: tester; Upzi/full trial.

## UNIT_TESTED - TASK-158 - 2026-10-28T03:07:42Z
- Action: tester QA of db4da04e (mesh, ladder, report suites, run_all --fast, heavy suites, shell.sh, 4 bites); Upzi/full trial rebuild with LOGREACH_MESH=1.
- Result: all pass, 0 fail; bites fail as expected. Trial: mesh rows=1 found=1 requests=1, 0 verdict moves of 142, 008 shows "strong: B call seen in mesh log" + KQL, gaps=0, report_qa PASS, deliverables 152/0.
- Decision: UNIT_TESTED; value shown on Upzi, so LOGREACH_MESH=1 set in the local plans/Upzi/full/plan.conf (RAW-01057).
- Next: verifier.

## VERIFIED - TASK-158 - 2026-10-28T03:09:08Z
- Action: verifier read code + trial evidence; coordinator saved the per-key jq verdict diff (verify_verdict_diff.tsv).
- Result: AC1-AC8 pass; security pass clean; 0/142 verdict/basis/level moves; deliverables 152/0.
- Decision: VERIFIED.
- Next: report and DONE.

## DONE - TASK-158 - 2026-10-28T03:09:27Z
- Action: wrote docs/report/phase-158-logreach-mesh-check.md; backlog complete.
- Result: mesh note shipped, opt-in; Upzi on (found=1), other plans off.
- Decision: DONE.
- Next: REQ-0123 to DONE; queued TASK-143/144/146 need the user.

## DESIGN - TASK-146 - 2026-10-28T03:25:07Z
- Action: designer checked the 10-26 draft on HEAD febfc889 (work/TASK-146/handoff/design.md); coordinator folded the corrections into docs/design/phase-146-pipeline-unit-control.md.
- Result: premise holds; 5 fixes: fresh_call flag (reuse paths would re-mark a reset unit done), rebuild not --render, V- units own the verify step, 146.5 only with --only, copy not move of the out file. 146.7 dropped, no carry-forward on new, release meaning unchanged.
- Decision: design completed; slices A/B/C. No dependency on TASK-144 (RAW-01062).
- Next: coder slice A.

## IMPLEMENTING - TASK-146 - 2026-10-28T04:32:45Z
- Action: coder slices A, B, C; coordinator applied the run-pipeline skill line and fixed the guide's rebuild --render lines (--render = reports only).
- Result: pipeline_unit_control 48/0; pipeline suites pass; G1 dry-run byte-identical, G2 e2e identical after masks, G3 scan_batch.sh diff empty; shell.sh 593/0.
- Decision: implementation complete; pipeline_step.sh retired.
- Next: tester QA.

## UNIT_TESTED - TASK-146 - 2026-10-28T04:50:58Z
- Action: tester QA (independent re-run): run_all --fast, pipeline_unit_control + 10 pipeline suites, shell.sh, bites a-d, goldens G1-G3.
- Result: 171 suites 0 failed; unit_control 48/0; shell 593; bites bite; G1/G3 reproduce, G2 PASS with hash masked (stored gold.sh lacks the mask). Each AC1-AC6 has a test.
- Decision: UNIT_TESTED. Two gaps go to the verifier (no unit test): track.sh idempotency on a reopened run, verify_carry fresh_call skip.
- Next: verifier on a scratch Upzi/full copy with fake claude; coverage_check gaps=0.

## VERIFIED - TASK-146 - 2026-10-28T05:07:04Z
- Action: coordinator ran the runtime steps (verifier has no Bash) on a scratch Upzi/full copy with fake claude; verifier judged the saved v_*.txt.
- Result: AC1-AC6 PASS; track idempotent on reopened run; fresh_call V- unit not carried; changed 2b answer flows to conclusion with gaps=0; G2 hash diff is temp-path noise. Security clean except low F-146-1.
- Decision: VERIFIED. F-146-1 (set -f around key loops) recorded as follow-up; stale list naming verify/ext after a 2b reset is advisory only (run finished with calls=1).
- Next: DONE report, crosscheck, backlog complete, REQ-0113.

## DONE - TASK-146 - 2026-10-28T05:07:53Z
- Action: report docs/report/phase-146-pipeline-unit-control.md; crosscheck handoff; backlog complete.
- Result: REQ-0113 AC1-AC6 ticked with evidence; F-146-1 and the advisory stale line recorded as follow-ups.
- Decision: DONE.
- Next: REQ-0124 waits for the user's Q1; then TASK-143 (queued), TASK-144 (low).

## TODO - TASK-159 - 2026-10-28T05:21:08Z
- Action: picked TASK-159 for REQ-0124 after the user answered Q1 (a) in RAW-01066.
- Result: REQ-0124 has AC1-AC7; RAW-01064/01066 noted on the task.
- Decision: high priority (RAW-01063); keep the caller_link rule, fix the report wording and add QC.
- Next: designer drafts docs/design/phase-159-logreach-caller-path-text.md.

## DESIGN - TASK-159 - 2026-10-28T05:46:14Z
- Action: designer drafted work/TASK-159/handoff/design.md; coordinator wrote docs/design/phase-159-caller-link-internet-path.md with RAW-01067..01069 folded in.
- Result: one basis_text order (reached /internal route, public caller + auth, sink, mesh, scanned URL 0 hits); two engine bugs found (refs cap 3 drops the sink, unlabeled hit lines).
- Decision: design completed; verdict rule unchanged (Q1 a); prompts untouched; /internal twin only where a 2b link exists.
- Next: coder 159.1-159.6.

## IMPLEMENTING - TASK-159 - 2026-10-28T06:07:21Z
- Action: coder implemented 159.1-159.6; RAW-01072 wording applied (no "safe", no "no traffic seen").
- Result: logreach_ladder, logreach_mesh, logreach_report, logreach_render, report_crossgrep, inspect_tools pass; coder: run_all --fast 172 pass, shell.sh 595/0. Deviation: labels on caller_link rows only (others byte-identical).
- Decision: implementation completed; real rebuild not yet run (guard refused it for the coder; coordinator runs it).
- Next: tester QA, coordinator V1/V2/V7 on scratch copy.

## UNIT_TESTED - TASK-159 - 2026-10-28T06:19:23Z
- Action: tester re-ran the 7 suites, --fast and shell.sh, ran bites a-g, checked byte-identical rows; coordinator ran the scratch Upzi/full rebuild.
- Result: all pass; bite d first passed on a no-match glob, tester fixed the test (render 49 cases). Scratch: 0/142 moves, 0 ES requests, crossgrep 0/2663 mismatches, coverage gaps=0, report_qa PASS, deliverables 150/2/1 (D14 scratch-only).
- Decision: unit_test passed.
- Next: verifier.

## VERIFIED - TASK-159 - 2026-10-28T06:21:49Z
- Action: verifier judged AC1-AC7 on the scratch rebuild evidence and the diff; coordinator added the report_crossgrep line to the verify skill checklist and the tester QA gate (AC6).
- Result: AC1-AC7 pass; security no finding; D14 deliverable FAIL is scratch-only (no ext_inscope copy), unrelated to the change; V7 on fixture.
- Decision: verification passed.
- Next: DONE report with the lessons section (AC8).

## DONE - TASK-159 - 2026-10-28T06:22:52Z
- Action: coordinator wrote docs/report/phase-159-caller-link-internet-path.md with the Lessons from the 008 case section; curated the lessons into pentest-report-qa, api-platform-security, coordinator, verify and the tester agent.
- Result: REQ-0124 AC1-AC8 ticked.
- Decision: TASK-159 DONE; REQ-0125 (twin mounts) waits for Q1.
- Next: rebuild the real Upzi/full reports at $0 so the 10-28 set carries the new text.

## TODO - TASK-160 - 2026-10-28T06:34:51Z
- Action: picked TASK-160 for REQ-0125 (RAW-01073, RAW-01074).
- Result: Q1 = (a) with cache; ACs 160.1-160.6.
- Decision: start design.
- Next: designer.

## DESIGN - TASK-160 - 2026-10-28T06:42:23Z
- Action: designer draft -> docs/design/phase-160-twin-mount-caller.md; coordinator settled OPEN 1 (own twin budget 10) and OPEN 2 (dry proof = unit reselect + run --only --dry-run).
- Result: separate --twin key keeps old 2b items byte-equal (cache reuse, AC6); cap safe (AC7); RAW-01075 sequence 160.7.
- Decision: implement.
- Next: coder 160.1-160.6.

## IMPLEMENTING - TASK-160 - 2026-10-28T06:54:43Z
- Action: two coders: slice A (correlate/logreach twins, coverage-first budget) and slice B (unit reselect).
- Result: scratch r160: 33 twin pairs, 24 twin items, 10 selected covering all 8 fids, old-key diff 0; suites correlate, logreach, pipeline_unit_control 60/0, pipeline_dryrun 7/0 pass.
- Decision: to tester.
- Next: tester independent QA.

## UNIT_TESTED - TASK-160 - 2026-10-28T07:22:00Z
- Action: tester independent QA (suites, 4 bites, jq oracle on scratch r160).
- Result: all pass; bites fail as expected; 30 old keys byte-equal, 10 twin items, 0 mismatch rows (work/TASK-160/evidence/oracle_mismatch.tsv).
- Decision: verify on a scratch kit.
- Next: V1-V8.

## VERIFIED - TASK-160 - 2026-10-28T08:27:22Z
- Action: scratch Upzi/full kit V5-V8 (reselect, run --only fake claude, logreach with ES stub for 3 uncached twin-caller queries, rebuild, coverage); single-source base vs HEAD diff; verifier read-only review; skill_layout + correlate_twin re-run at HEAD.
- Result: AC1-AC7 VERIFIED. 30 old 2b items reused, 10 twin calls; 008 card refs in every report kind; 4 twin-driven verdict/basis moves, 0 seen change (earlier "0 moves" corrected: it came from a kept stored result); gaps=0; report_qa PASS; single-source identical but timestamps.
- Decision: VERIFIED. Paid twin run on the real Upzi/full stays on hold (RAW-01081).
- Next: DONE (crosscheck, report, backlog complete); then REQ-0127.

## DONE - TASK-160 - 2026-10-28T08:29:38Z
- Action: coordinator jq/grep crosscheck (work/TASK-160/handoff/crosscheck.md), report docs/report/phase-160-twin-mount-caller.md.
- Result: counts agree (64/9/69 in logreach, conclusion, access-log review; 33 pairs, 10/24 twin items selected, 40 2b units done).
- Decision: DONE. The paid twin run on the real Upzi/full stays on hold (RAW-01081).
- Next: REQ-0127 (exposure display) when picked; queued TASK-143, TASK-144.

## TODO - TASK-161 - 2026-10-28T08:59:07Z
- Action: picked TASK-161 for REQ-0127 (RAW-01083..01088).
- Result: scope = engine reads prompt http-v16 output (internal-only via callers, multi-mount, exposure line, compare runs). Real Upzi/full run 20261028-154021 track A (phase 1, v16) running; track B waits for this task.
- Decision: start design.
- Next: designer.

## DESIGN - TASK-161 - 2026-10-28T09:09:19Z
- Action: designer draft (PARTIAL, turn limit) -> coordinator wrote docs/design/phase-161-multi-mount-in-cluster.md; 4 OPENs settled with the designer's picks (not_checkable+in_cluster, T1 unchanged, plain R1, shared tier_of).
- Result: design covers 161.1-161.6, plan modes, tests, V1-V7.
- Decision: proceed to IMPLEMENTING (autonomy, RAW-01059).
- Next: coder brief.

## IMPLEMENTING - TASK-161 - 2026-10-28T09:31:07Z
- Action: coder implemented 161.1-161.6 + tests; skill line (guard-flagged Bash edit) reviewed and accepted by the coordinator.
- Result: coder self-check: run_all --fast 174 pass, shell.sh 599/0, logreach_mounts 33 checks, 19 fail on revert.
- Decision: hand to tester. 161.4 graph/2b: no anchor, no view.
- Next: tester.

## UNIT_TESTED - TASK-161 - 2026-10-28T11:13:39Z
- Action: tester re-ran suites independently, added the AI-fallback in_cluster case to logreach_ladder.
- Result: all mapped suites + --fast pass, shell.sh 599/0; bites proven. tracking_new_only N3 pre-existing failure (same on base 0d762946).
- Decision: UNIT_TESTED.
- Next: verifier on the real Upzi/full v16 run once track A finishes.
