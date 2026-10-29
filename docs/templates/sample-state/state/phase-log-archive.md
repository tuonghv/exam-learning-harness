# Phase Log Archive

Entries moved verbatim from phase-log.md for finished tasks (context-compaction skill).
Read-only; workflow-check.sh still counts them.

## DESIGN - 2026-09-18T08:26:39Z

### Action
- Inspected init_manifest.sh, scan_batch.sh (args, lock, selection, exclusion wiring), status.sh, auto_scan.sh, summarize_report.sh, scan_excludes.sh, config.sh.
- Wrote docs/DESIGN-init-status.md (TASK-001) and docs/DESIGN-prompt-exclusions.md (TASK-002).

### Result
- User confirmed: status name 'init'; no migration of existing entries; keep deny rules, only make the prompt list optional.
- TASK-001 active in DESIGN (design completed); TASK-002 queued with approved design.

### Decision
- Approval flags go in scan_batch.sh (invariant #4: single status writer), not a new script.
- Prompt gets a ~60-token brief by default instead of nothing, to avoid retry churn and bogus "could not read" findings.

### Next
- On go-ahead: implement TASK-001 in three slices (see task.json next), then pick TASK-002.

## IMPLEMENTING - 2026-09-18T09:40:00Z

### Action
- Slice 1: NEW_REPO_STATUS in config.sh (validated init|pending); init_manifest.sh writes it for new entries and reports the init count + approve command.
- Slice 2: scan_batch.sh gets --approve/--approve-all/--unapprove (mutually exclusive, cannot combine with --repo/--retry-failed), running after the manifest checks and .scan.lock but before any claude/timeout prerequisite; --repo now refuses an 'init' repo even with --force; empty-batch message names the init count.
- Slice 3: status.sh progress line, auto_scan.sh 'Scan queue' line + queue-empty log/notify, and summarize_report.sh's coverage-gap section (12) all surface the init count; CLAUDE.md and README.md documented (command table, architecture block, new "Approving newly discovered repos" section).

### Result
- All 8 files listed in task.json implementation.files changed; bash -n clean on every changed script.

### Decision
- Moved the claude-CLI/prompt-template/timeout-binary checks to after the lock+approval block (approving needs none of them), per the design's ordering requirement.
- Kept manifest_patch()/slug() defined before the approval block since bash executes top-to-bottom and approval calls them directly.

### Next
- Unit/real-run verification in a scratch REPOS_ROOT (see UNIT_TESTED/VERIFIED entries).

## UNIT_TESTED - 2026-09-18T09:40:00Z

### Action
- Built a scratch REPOS_ROOT with throwaway git repos and a full copy of the toolkit; ran init_manifest.sh and scan_batch.sh directly against it (no claude mock needed — approval mode never shells out to claude).

### Result
- See task.json unit_test.result: AC1-AC3 scenarios (new repos land 'init', idempotent re-run, NEW_REPO_STATUS=pending, invalid value rejected, --dry-run no-ops, --repo/--force refusal, approve/approve-all/unapprove incl. workspace disambiguation/ambiguous/unknown-name/wrong-source-status/lock-contention) all passed.

### Decision
- No changes needed after this pass — first implementation matched the design's test strategy directly.

### Next
- Real-run verification of the reader-side changes (status.sh, auto_scan.sh, summarize_report.sh).

## VERIFIED - 2026-09-18T09:40:00Z

### Action
- Ran status.sh, auto_scan.sh status, and summarize_report.sh (with a hand-built results/*.json + manifest.json) against the same scratch state to confirm the init count surfaces in each.

### Result
- See task.json verification.evidence: all four reader-side surfaces (status.sh, auto_scan.sh status, scan_batch.sh empty-batch message, summarize_report.sh coverage gaps) show the init count as designed; AC6 docs re-read and confirmed.

### Decision
- No formal report needed yet; deferring report.status=completed until the user asks or TASK-002 is also done, to avoid a report per micro-task.

### Next
- Optional /report, then TASK-002 (docs/DESIGN-prompt-exclusions.md).

## IMPLEMENTING - 2026-09-18T10:35:00Z

### Action
- TASK-002: PROMPT_EXCLUSIONS=0 (default) added to config.sh's scan-scope block.
- New render_exclusions_brief() in scan_excludes.sh (~60-token static text, next to render_exclusions_md); added --brief to its CLI eyeball flags.
- scan_batch.sh: new --prompt-excludes flag; EXCLUSION_TEXT now picks render_exclusions_brief() or render_exclusions_md() per PROMPT_EXCLUSIONS; banner gained a 'Prompt: ...' line stating which variant is active; help comment block and its sed range updated.
- CLAUDE.md/README.md updated: command tables, a new Commands bullet, the config.sh/scan_excludes.sh/scan_batch.sh architecture blocks, the README Scan-scope section and Files section.

### Result
- All 5 files listed in task.json implementation.files changed; bash -n clean on every changed script; --help and scan_excludes.sh usage text reflect the new flags.

### Decision
- Kept the deny-rule path (scan_settings_json) completely untouched — PROMPT_EXCLUSIONS only ever selects prompt text, never enforcement, per the design's explicit risk note.
- Added scan_excludes.sh --brief for symmetry with the existing --md eyeball flag, since it's a one-line addition using the same pattern.

### Next
- Unit/real-run verification in a scratch REPOS_ROOT with a fake `claude` that captures its -p prompt (see UNIT_TESTED/VERIFIED entries).

## UNIT_TESTED - 2026-09-18T10:35:00Z

### Action
- Built a scratch REPOS_ROOT with one throwaway git repo and a full copy of the toolkit; put a fake `claude` on PATH that saves its -p prompt argument to a file and returns a minimal valid findings envelope, so the exact prompt text sent for each mode is directly observable without spending tokens or mocking scan logic.

### Result
- See task.json unit_test.result: default/--prompt-excludes/PROMPT_EXCLUSIONS=1/--no-excludes(+--prompt-excludes)/--dry-run all produced the expected banner line and prompt content; scan_excludes.sh --brief/--md/unknown-flag all behaved as designed.

### Decision
- No changes needed after this pass — implementation matched the design's test strategy directly.

### Next
- Re-confirm AC5 (security_prompt.md unchanged) and AC6 (docs) by direct inspection, then close out VERIFIED.

## VERIFIED - 2026-09-18T10:35:00Z

### Action
- Confirmed security_prompt.md has no diff from before this task (AC5); re-read the updated CLAUDE.md/README.md sections end-to-end for accuracy against the actual flag names and defaults (AC6).

### Result
- See task.json verification.evidence: AC1-AC6 all confirmed against the real scripts and the scratch run's captured prompts.

### Decision
- Deferring report.status=completed until the user asks for /report — backlog.json now has no further queued tasks after TASK-002.

### Next
- Optional /report. No more backlog items queued.

## DONE - 2026-09-18T10:50:00Z

### Action
- Wrote docs/REPORT-prompt-exclusions.md (task/requirement, design decision, implementation table, reuse, tests, AC1-AC6 verification, security considerations, limitations, final status).

### Result
- task.json report.status=completed, report.path=docs/REPORT-prompt-exclusions.md; state advanced to DONE.

### Decision
- Flagged two limitations in the report rather than glossing over them: the token-saving estimate is the design doc's, not independently re-measured, and no real-repo (non-fake-claude) A/B cost comparison was run.

### Next
- None — TASK-002 is DONE and backlog.json has no further queued tasks.

## DESIGN - TASK-003 - 2026-09-18T10:09:02Z

### Action
- Reviewed .claude/scripts (workflow-check, commit-check, backlog, status), hooks, skills against git history; reproduced gaps in a scratch copy.
- Wrote docs/DESIGN-workflow-gates.md.

### Result
- Confirmed: trailer bypass (1d185d9, 3224666), global phase-log check (scratch TASK-003 at VERIFIED → PASS), TASK-001 hand-closed at VERIFIED, security ungated, Stop hook unwired.
- User approved TASK-003 scope (fixes 1-4 + hook wiring).

### Decision
- Tag phase-log headings with task_id instead of rewriting old entries (append-only); legacy done items get explicit waivers rather than being hidden.
- 22 pre-existing shellcheck failures stay out of scope; touched files must not add new ones.

### Next
- IMPLEMENTING per task.json next.

## IMPLEMENTING - TASK-003 - 2026-09-18T10:12:06Z

### Action
- workflow-check.sh: per-task tagged phase-log audit; security gate at VERIFIED+; audit of every backlog 'done' item (waiver, or report file + tagged DONE entry); >1 active fails; malformed backlog now fails instead of being swallowed.
- commit-check.sh: fails when Task/State/Tests/Verified-by/Report appear in the message but git did not parse them as trailers.
- backlog.sh: complete stamps completed_at/report; --force needs a reason stored as waiver; junk flags print usage for pick/complete.
- .claude/settings.json wires the Stop hook; stop-check.sh passes the path as argv.
- Waivers recorded for TASK-001 (closed at VERIFIED, hand-edited) and TASK-002 (untagged legacy log); skills and log header document the new heading format.

### Result
- All planned files changed; nothing outside .claude/ and docs/ touched.

### Decision
- Old untagged entries left as-is (append-only); they simply stop counting.

### Next
- Regression test.

## UNIT_TESTED - TASK-003 - 2026-09-18T10:12:06Z

### Action
- Wrote .claude/tests/workflow_gates_test.sh (33 cases, temp git repos, fixtures per scenario); ran it against new and pre-change scripts; bash -n + shellcheck on touched files.

### Result
- New: pass=33 fail=0. Pre-change: 18 cases fail, one per new rule - the tests bite.
- Shellcheck: no new findings (baseline SC1090 only).

### Decision
- Keep the 22 pre-existing repo-wide shellcheck failures out of scope (follow-up).

### Next
- VERIFIED against the real repo state and real commit messages.

## VERIFIED - TASK-003 - 2026-09-18T10:12:48Z

### Action
- Replayed real historic commit messages through commit-check.sh; ran workflow-check.sh, status.sh and the Stop hook on the real repo and on a clone holding the real ca9e9ea state; reproduced the real TASK-001 hand-edit in a clone; ran backlog.sh complete --force without a reason.

### Result
- Every historic gap is now caught with a message naming the task (see task.json verification.evidence).

### Decision
- No code changes needed after verification.

### Next
- Report, DONE, backlog.sh complete TASK-003.

## DONE - TASK-003 - 2026-09-18T10:13:15Z

### Action
- Wrote docs/REPORT-workflow-gates.md; completed TASK-003 via backlog.sh complete (records completed_at + report).

### Result
- task.json DONE; backlog TASK-003 done with report path, audited by the new check.

### Decision
- Follow-ups (repo-wide shellcheck baseline, atomic pick, files-exist check) listed in the report, not done here.

### Next
- None queued.

## DESIGN - TASK-004 - 2026-09-18T10:20:17Z

### Action
- Classified all 90 shellcheck findings (0.7.0) by code and site; confirmed .shellcheckrc works on 0.7.0; found pytest exit 5 keeps quality-check.sh red.
- Wrote docs/design/phase-4-shellcheck-baseline.md (first doc under the phase-<N>-<slug> convention).

### Result
- 2 real latent bugs among the findings: failed cd continues (6 scripts lack -e), dead 'pa' in auto_scan status.

### Decision
- Suppress only what is idiomatic (sourced config, jq quoting, dynamic kit source); fix the rest; prove behaviour identical old-vs-new.

### Next
- IMPLEMENTING 4.1-4.6.

## IMPLEMENTING - TASK-004 - 2026-09-18T10:22:35Z

### Action
- 4.1 file-level SC2034 in config.sh, line-level for REQUIRED_SECTIONS; 4.2 .shellcheckrc SC2016; 4.3 cd||exit x6, tr classes x4, read<<< x2, grouped SC2015, dropped dead pa; 4.4 source=/dev/null x11; 4.5 python.sh no-tests=warn; 4.6 bash skill.

### Result
- All-files shellcheck clean, but checks/shell.sh (one file per call) still failed 7 files on SC1091 — a gap in the design's baseline method.

### Decision
- Amended design (4.4b): checks/shell.sh runs shellcheck -x, following constant sources, instead of suppressing SC1091. Recorded in the design doc Decisions.

### Next
- Unit tests.

## UNIT_TESTED - TASK-004 - 2026-09-18T10:22:35Z

### Action
- Added tests/shell_helpers_test.sh (sev_rank, detect_reset_at prose forms, scan_excludes --stats); ran it on new and pre-change copies; ran all gates.

### Result
- 14/14 new and old; checks/shell.sh fail=0; quality-check.sh rc=0; workflow gates 33/33.

### Decision
- Preservation tests are expected to pass on old code; the "bites" proof for this task is the shellcheck gate itself (90 -> 0).

### Next
- VERIFIED old-vs-new on a scratch tree.

## VERIFIED - TASK-004 - 2026-09-18T10:24:20Z

### Action
- Ran the design's Verification table on scratch old/new toolkit copies with identical inputs and diffed every output.

### Result
- All outputs identical old vs new except the --out path; gates green.
- Found two pre-existing bugs (present in old too): a corrupt results/*.json silently zeroes all findings in the reports; mktemp -t is BSD-only.

### Decision
- Out of TASK-004 scope (behaviour unchanged by this task); queued as TASK-006 priority high rather than fixed silently here.

### Next
- Report + DONE, then TASK-005.

## DONE - TASK-004 - 2026-09-18T10:24:43Z

### Action
- Wrote docs/report/phase-4-shellcheck-baseline.md; backlog.sh complete TASK-004.

### Result
- 90 -> 0 findings; quality-check.sh green; TASK-006 queued for the two pre-existing report bugs.

### Decision
- None further.

### Next
- Pick TASK-005 (doc path convention enforcement).

## DESIGN - TASK-005 - 2026-09-18T10:25:32Z

### Action
- Listed every reference to the legacy doc paths; wrote docs/design/phase-5-doc-path-convention.md.

### Result
- 5 legacy docs to move (TASK-001..003); references only in backlog.json, the moved docs and the design skill (phase-log excluded, append-only).

### Decision
- Phase N = task number; enforce in workflow-check.sh once design/report is completed; migrate with git mv.

### Next
- IMPLEMENTING 5.1-5.5.

## IMPLEMENTING - TASK-005 - 2026-09-18T10:27:36Z

### Action
- workflow-check.sh: design.path/report.path rules; backlog.sh pick template design.path; skills updated; git mv of 5 legacy docs to phase-1..3 with references updated in backlog.json and the moved reports.

### Result
- Real repo workflow-check PASS with TASK-005's own convention paths.

### Decision
- A scripted patch using heredoc delimiter PY collided with an inner PY and the shell ran the remainder as commands (targets under / with empty vars; nothing changed, checked). Switched to the Edit tool and added the lesson to the bash skill.

### Next
- Unit tests.

## UNIT_TESTED - TASK-005 - 2026-09-18T10:27:36Z

### Action
- Extended .claude/tests/workflow_gates_test.sh with 14 path-convention cases; ran on new and pre-change kit.

### Result
- 47/47 new; 10 rule cases fail on the pre-change kit.

### Decision
- None.

### Next
- VERIFIED.

## VERIFIED - TASK-005 - 2026-09-18T10:28:01Z

### Action
- Ran design Verification rows 5.1-5.5 on the real repo and a clone.

### Result
- All rows as expected (see task.json verification.evidence).

### Decision
- None.

### Next
- Report + DONE.

## DONE - TASK-005 - 2026-09-18T10:28:19Z

### Action
- Wrote docs/report/phase-5-doc-path-convention.md; backlog.sh complete TASK-005.

### Result
- Path convention enforced; docs/ holds only design/ and report/ phase files.

### Decision
- None.

### Next
- TASK-006 queued (corrupt result file zeroes report findings; BSD-only mktemp) — awaiting the user's go-ahead.

## DESIGN - TASK-006 - 2026-09-18T12:10:28Z

### Action
- Traced every reader of results/*.json (build_findings, summarize_report COST + per-repo loop, status.sh x3, verify_findings, summarize_exec) and the writer (scan_batch.sh:583 non-atomic redirect).
- Wrote docs/design/phase-6-unreadable-results.md.

### Result
- Five readers hide jq errors with 2>/dev/null over the whole glob; one (per-repo loop) already guards per file.

### Decision
- Skip-and-flag loudly by default, hard stop under --strict; keep today's delete-on-failed-rescan behaviour (changing it is a separate user decision).

### Next
- IMPLEMENTING 6.1-6.8.

## IMPLEMENTING - TASK-006 - 2026-09-18T12:15:34Z

### Action
- report_common.sh: load_result_files / warn_bad_results / bad_results_md; build_findings reads RESULT_FILES only, no 2>/dev/null, no jq without args.
- summarize_report.sh: warning + --strict stop, notice before Contents, section 12 "Unreadable result files", COST and per-repo loop on RESULT_FILES, section 8 guard requires an object.
- summarize_exec.sh: warning + notice under header. verify_findings.sh: names files, exit 1, --json unreadable_results. status.sh: sources report_common.sh, reads RESULT_FILES, prints a !! line.
- scan_batch.sh: extract to .tmp, validate, mv. mktemp templates in 4 places.

### Result
- shell.sh fail=0 (two intentional patterns in the new test silenced at line level with reasons).

### Decision
- Used ${a[@]+"${a[@]}"} wherever an array may be empty (bash 3.2 + set -u).

### Next
- Unit tests.

## UNIT_TESTED - TASK-006 - 2026-09-18T12:15:34Z

### Action
- Added tests/result_files_test.sh (13 cases); ran it on the new kit and on a pre-change git archive copy.

### Result
- New 13/13. Pre-change 4/13: case 2 reproduces the bug (mixed dir yields no findings).

### Decision
- None.

### Next
- VERIFIED on a scratch tree.

## VERIFIED - TASK-006 - 2026-09-18T12:19:58Z

### Action
- Ran the design's Verification table on scratch old/new kits with a fake claude (details in task.json verification.evidence).

### Result
- Every row as designed. Old kit reproduces both bugs (LOW/High 0 report; mktemp -t failure on GNU). With every file readable, new == old (+ BSD mktemp shim) except the new section-12 line.

### Decision
- Found an unrelated, pre-existing bug: under jq 1.6, manifest_patch's `tonumber?` inside `|=` deletes the repo entry after every successful scan. Out of scope; queued as TASK-007. Scratch manifests were hand-restored identically in both kits.

### Next
- DONE: report, backlog complete.

## DONE - TASK-006 - 2026-09-18T12:20:31Z

### Action
- Wrote docs/report/phase-6-unreadable-results.md; CLAUDE.md architecture map names load_result_files; backlog complete.

### Result
- All 8 acceptance items verified.

### Decision
- TASK-007 queued (jq 1.6 manifest deletion), not fixed here.

### Next
- TASK-007 on user approval.

## DESIGN - TASK-007 - 2026-09-18T13:00:48Z

### Action
- Reproduced on a real 2-repo batch (mini-review): both scans succeeded, manifest ended {"repos": []}. Root cause: jq 1.6 _modify (label/break) + tonumber? in the success patch. Wrote docs/design/phase-7-manifest-patch-jq16.md.

### Result
- Design: rebuild .repos with if/then/else (no |=) + repo-count guard; grep shows no other |=.

### Decision
- Remove |= from manifest_patch rather than only the one tonumber? (protects future patches). User approved sequencing: TASK-007 first, then the runbook task.

### Next
- IMPLEMENTING: manifest_patch rewrite + tests/manifest_patch_test.sh.

## IMPLEMENTING - TASK-007 - 2026-09-18T13:01:36Z

### Action
- manifest_patch: .repos rebuilt with if/then/else (no |=), repo-count guard via jq error().

### Result
- Call signature and call sites unchanged; bash -n and shellcheck clean.

### Decision
- None.

### Next
- UNIT_TESTED: tests/manifest_patch_test.sh on new and pre-change kits.

## UNIT_TESTED - TASK-007 - 2026-09-18T13:01:36Z

### Action
- Added tests/manifest_patch_test.sh (9 checks); ran on new kit and a git-archive HEAD copy; reran existing suites.

### Result
- New 9/9. Pre-change 4/9: 7.1a reproduces the deletion, 7.2 shows no guard. Existing suites unchanged (14/14, 13/13, shell 58/0).

### Decision
- None.

### Next
- VERIFIED: real batch evidence.

## VERIFIED - TASK-007 - 2026-09-18T13:01:58Z

### Action
- Real 2-repo batch on mini-review before and after the fix; |= grep.

### Result
- Before: manifest emptied after both successful scans. After: both entries done, attempts 0, findings_summary set; reports read all 8 findings. Only comments contain |=.

### Decision
- None.

### Next
- DONE: report + backlog complete.

## DONE - TASK-007 - 2026-09-18T13:02:19Z

### Action
- Wrote docs/report/phase-7-manifest-patch-jq16.md; backlog complete.

### Result
- 7.1-7.3 verified.

### Decision
- Next: TASK-008 security review runbook + skill (user-approved sequencing).

### Next
- Pick TASK-008.

## DESIGN - TASK-008 - 2026-09-18T13:04:18Z

### Action
- Added TASK-008 to backlog (user request 2026-09-18) and picked it; wrote docs/design/phase-8-security-review-runbook.md.

### Result
- Runbook + skill + read-only check_deliverables.sh (D1-D7) designed; README/CLAUDE.md links.

### Decision
- Deterministic script over a prose checklist (the executive summary was missed today); verify_findings.sh stays the completeness authority.

### Next
- IMPLEMENTING check_deliverables.sh + tests.

## IMPLEMENTING - TASK-008 - 2026-09-18T13:07:53Z

### Action
- check_deliverables.sh (D1-D7), runbook docs/guide/security-review-runbook.md, skill run-security-review, README/CLAUDE.md links.

### Result
- shellcheck clean; real tree 11/11 PASS on today's set.

### Decision
- Per-repo names from result basename (matches summarize_report.sh); manifest results_file used by basename only (absolute paths from another host still resolve).

### Next
- UNIT_TESTED.

## UNIT_TESTED - TASK-008 - 2026-09-18T13:07:53Z

### Action
- tests/check_deliverables_test.sh (16 checks) + all existing suites.

### Result
- 16/16; other suites unchanged; shell.sh 62/0.

### Decision
- None.

### Next
- VERIFIED on the real tree.

## VERIFIED - TASK-008 - 2026-09-18T13:08:26Z

### Action
- Real tree: gate pass, remove exec-summary PDF, gate fail, restore, gate pass; runbook commands smoke-run; link greps.

### Result
- Every Verification row as designed (details in task.json).

### Decision
- None.

### Next
- DONE: report + backlog complete.

## DONE - TASK-008 - 2026-09-18T13:08:48Z

### Action
- Wrote docs/report/phase-8-security-review-runbook.md; backlog complete.

### Result
- 8.1-8.4 verified.

### Decision
- None.

### Next
- Nothing queued. User-owned: config.sh (REPOS_ROOT, shebang fix) and manifest.json remain uncommitted local state.

## DESIGN - TASK-010 - 2026-09-23T04:49:19Z

### Action
- Reliability review of the claude -p scan path -> docs/review/2026-09-23-scan-reliability-review.md (8 findings, 5 deferred as rare).
- Designed three phases by priority: phase-10 false-success guards (P1), phase-11 scan isolation (P2), phase-12 no silent skips (P3); TASK-010..012 queued, TASK-010 picked.

### Result
- Offline fixture runs confirmed F1 (model text "401" -> auth class), F2 (truncated JSON -> json_repair exit 2 accepted), F3 (normalizer failure ignored).

### Decision
- Keep json_repair but require .stats (follows findings in the schema); --restricted over --setting-sources ""; defer orphan/lock, blocking-cap, limit formats (rare).

### Next
- User approval of phase-10 design, then IMPLEMENTING 10.1.

## IMPLEMENTING - TASK-010 - 2026-09-23T04:54:48Z

### Action
- User approved phase 10 ("approve phase 10 ... normal load > fail > repair json"); added design item 10.6.

### Result
- json_repair 0.30.0 checked on fence, leading/trailing prose, unescaped quote, truncation: all dict; draft+correction -> list; no-JSON -> "".

### Decision
- Remove awk salvage; json_repair required (scan_batch preflight); exit 1 retired, 5 = library missing.

### Next
- Code load_json.sh + scan_batch.sh, tests.

## VERIFIED - TASK-010 - 2026-09-23T05:00:23Z

### Action
- load_json.sh: strict jq parse -> python json_repair (awk salvage removed; exit 5 = library missing).
- scan_batch.sh: classify_failure blocking patterns only on exit!=0 or is_error; new finalize_result() (gate, stats rule for repaired answers, normalizer failure = rejection, never touches the old result); python3+json_repair preflight; timeout -k 60.
- tests/scan_result_test.sh (new, 39), tests/load_json_test.sh rewritten (31); CLAUDE.md/README updated.

### Result
- All test suites pass; shellcheck fail=0. Scratch toolkit + fake claude: rows 10.1-10.6 as designed (see task.json verification.evidence).

### Decision
- Added defensive tostring in norm_sev and a stats-type guard in the normalizer (a non-object stats no longer crashes it).

### Next
- Phase 10 report, DONE; phase 11 awaits approval.

## UNIT_TESTED - TASK-010 - 2026-09-23T05:00:29Z

### Action
- Ran every tests/*.sh and .claude/scripts/checks/shell.sh (entry recorded after the VERIFIED entry above — same session, omitted by mistake).

### Result
- scan-result 39/39, load-json 31/31, check-deliverables 16/16, manifest-patch 9/9, result-files 13/13, shell-helpers 14/14; shellcheck pass=67 fail=0.

### Decision
- None.

### Next
- Covered by the VERIFIED entry.

## DONE - TASK-010 - 2026-09-23T05:31:17Z

### Action
- Wrote docs/report/phase-10-false-success-guards.md; backlog TASK-010 done.

### Result
- 10.1-10.6 verified (commit 4145564).

### Decision
- None.

### Next
- User approved phase 11: TASK-011 IMPLEMENTING.

## DESIGN - TASK-011 - 2026-09-23T05:31:55Z

### Action
- Design drafted 2026-09-23 with the review; user approved ("approve phase 11"). Added --safe-mode (found in claude 2.1.280 --help) and verification row 11.7.

### Result
- docs/design/phase-11-scan-isolation.md approved.

### Decision
- --safe-mode covers CLAUDE.md/hooks/plugins while keeping auth; must prove --settings deny rules survive.

### Next
- IMPLEMENTING 11.1-11.3.

## IMPLEMENTING - TASK-011 - 2026-09-23T05:33:17Z

### Action
- Started 11.1-11.3 in scan_batch.sh: isolation flags on the launch, claude --help preflight, env -u of the parent session's variables.

### Result
- In progress.

### Decision
- Isolation flags in one array (CLAUDE_ISOLATION_ARGS); existing --allowedTools/--settings kept.

### Next
- Unit tests with an argv/env-capturing fake claude; then canary run.

## UNIT_TESTED - TASK-011 - 2026-09-23T05:36:04Z

### Action
- scan_batch.sh: CLAUDE_ISOLATION_ARGS on the launch, env -u of CLAUDE_PARENT_ENV_UNSET, claude --help preflight, Isolation banner line. New tests/scan_isolation_test.sh (fake claude records argv/env/cwd). CLAUDE.md, README updated.

### Result
- scan-isolation 39/39; every other suite passes; shell.sh pass=70 fail=0.

### Decision
- Flag detection matches the flag as a whole word in --help output (portable ERE, no \b).

### Next
- Canary verification with real claude (design rows 11.1-11.7).

## VERIFIED - TASK-011 - 2026-09-23T05:42:44Z

### Action
- Canary repo (CLAUDE.md injection, repo hooks + MCP + permissions.allow Bash, JWT key, node_modules/leak.js) scanned twice via a scratch kit with real claude; regression re-scan of n1/demo-mini plus a control scan without isolation flags. Spend ~$0.55.

### Result
- 11.1-11.7 pass (evidence in task.json). First canary used a DB password, which http-v6 puts out of scope; replaced with a JWT signing key.

### Decision
- No prompt change for 11.4: --safe-mode keeps CLAUDE.md out of context; the model treats it as evidence.

### Next
- Report, DONE.

## DONE - TASK-011 - 2026-09-23T05:43:15Z

### Action
- Wrote docs/report/phase-11-scan-isolation.md; backlog TASK-011 done.

### Result
- 11.1-11.7 verified (commits 5c53096, 6702e1b).

### Decision
- None.

### Next
- Phase 12 awaits user approval.

## DESIGN - TASK-012 - 2026-09-23T05:47:07Z

### Action
- Design drafted 2026-09-23 with the review; user approved ("approve phase 12"). json_stage values updated for phase 10 (stage 1 retired).

### Result
- docs/design/phase-12-no-silent-skips.md approved.

### Decision
- Retry failed repos only after the pending queue drains; bounded by MAX_ATTEMPTS.

### Next
- IMPLEMENTING 12.1-12.4.

## IMPLEMENTING - TASK-012 - 2026-09-23T05:47:07Z

### Action
- Started 12.1-12.4 in scan_batch.sh, auto_scan.sh, status.sh.

### Result
- In progress.

### Decision
- None yet.

### Next
- Unit tests with fixture manifests and a fake claude.

## UNIT_TESTED - TASK-012 - 2026-09-23T07:01:02Z

### Action
- Implemented 12.1 (--retry-failed respects MAX_ATTEMPTS unless --force, reports both counts), 12.2 (auto_scan counts only scannable repos), 12.3 (auto_scan runs --retry-failed batches once pending drains), 12.4 (last_exit_code/session_id/num_turns/json_stage in manifest; status.sh shows them). New tests/no_silent_skips_test.sh. CLAUDE.md/README updated.

### Result
- no-silent-skips 22/22; all 8 test suites pass; shell.sh pass=72 fail=0.

### Decision
- Test captures command output before grep -q (pipefail + early grep exit SIGPIPEs the writer).

### Next
- VERIFIED: scratch kit + fake claude, incl. auto_scan.sh tick/run.

## VERIFIED - TASK-012 - 2026-09-23T07:04:53Z

### Action
- Scratch kit + fake claude (no tokens): --retry-failed CLI; auto_scan.sh tick (over-cap only); auto_scan.sh run with fail-first and always-fail fakes; status.sh.

### Result
- 12.1-12.4 all pass: over-cap repos stay failed and are named; tick finishes with no scan; run retries failed repos until done or exactly MAX_ATTEMPTS calls; manifest carries exit code, session id, turns, json_stage.

### Decision
- No code change needed after verification.

### Next
- DONE: phase 12 report.

## DONE - TASK-012 - 2026-09-23T07:05:20Z

### Action
- Wrote docs/report/phase-12-no-silent-skips.md.

### Result
- Phase 12 complete; 12.1-12.4 verified.

### Decision
- None.

### Next
- Next backlog item.

## DESIGN - TASK-013 - 2026-09-23T07:12:18Z

### Action
- User chose review item D4 for phase 13; wrote docs/design/phase-13-empty-result-guard.md.

### Result
- Design 13.1-13.4: reject a first empty answer from a short scan, accept a second one flagged empty_suspect, list it in status.sh and report section 12.

### Decision
- Signal = 0 findings + num_turns < EMPTY_MIN_TURNS (default 3); flag lives in manifest only (invariant 3).

### Next
- Await user approval, then IMPLEMENTING.

## IMPLEMENTING - TASK-013 - 2026-09-23T07:13:19Z

### Action
- Design approved by user ("approve phase 13"). Starting 13.1-13.3.

### Result
- In progress.

### Decision
- None yet.

### Next
- Unit tests in tests/empty_result_test.sh.

## UNIT_TESTED - TASK-013 - 2026-09-23T07:21:10Z

### Action
- finalize_result gate rule (13.1), allow_empty from last_error + empty_suspect manifest field (13.2), status.sh line + report section 12 table (13.3), EMPTY_MIN_TURNS=3 in config.sh. New tests/empty_result_test.sh; CLAUDE.md/README updated.

### Result
- empty-result 17/17; all 9 suites pass; shell.sh pass=74 fail=0.

### Decision
- Missing/non-numeric num_turns turns the guard off (old envelopes behave as before).

### Next
- VERIFIED on a scratch kit, then the 13.4 real-claude canary.

## VERIFIED - TASK-013 - 2026-09-23T07:23:36Z

### Action
- Scratch kit + fake claude for 13.1-13.3 (scan_batch.sh --repo, auto_scan.sh run, status.sh, summarize_report.sh); real-claude canary on n1/demo-mini for 13.4.

### Result
- All pass. Empty short answer rejected once, accepted and flagged on the second call (2 calls total). Genuine scan took 9 turns, far above EMPTY_MIN_TURNS=3.

### Decision
- Keep default EMPTY_MIN_TURNS=3.

### Next
- DONE: phase 13 report.

## DONE - TASK-013 - 2026-09-23T07:24:43Z

### Action
- Wrote docs/report/phase-13-empty-result-guard.md.

### Result
- Phase 13 is complete. 13.1-13.4 are verified; the canary cost $0.12.

### Decision
- Keep EMPTY_MIN_TURNS=3. Re-tune it only if real scans often finish in 3-4 turns.

### Next
- None. The next phase needs user approval.

## DESIGN - TASK-014 - 2026-09-23T07:36:03Z

### Action
- User chose review item D2 for phase 14; wrote docs/design/phase-14-blocking-loop-guard.md.

### Result
- Design 14.1-14.4: per-repo blocking_streak + deferral in selection, charge an attempt at BLOCKING_MAX_STREAK for rate_limit/service, status.sh line.

### Decision
- Deferral + consecutive streak (no cross-repo evidence); auth never charged; abort class unchanged so auto_scan still waits.

### Next
- Await user approval, then IMPLEMENTING.

## IMPLEMENTING - TASK-014 - 2026-09-23T07:54:53Z

### Action
- User approved the design ("approve phase 14"). record_failure: blocking_streak bump, charge at BLOCKING_MAX_STREAK for rate_limit/service; streak reset on done/repo failure; selection sort_by adds blocking_streak; status.sh deferred line; config BLOCKING_MAX_STREAK=3; docs.

### Result
- Code complete, bash -n clean.

### Decision
- Streak read with tonumber? // 0 so an odd value never breaks selection.

### Next
- UNIT_TESTED.

## UNIT_TESTED - TASK-014 - 2026-09-23T07:54:53Z

### Action
- New tests/blocking_loop_test.sh (fake claude); full suite; shellcheck.

### Result
- blocking-loop 16/16; all 10 suites pass; shell.sh pass=76 fail=0 (fixed one SC2034 in the new test).

### Decision
- Proceed to real-run verification on a scratch kit.

### Next
- VERIFIED.

## VERIFIED - TASK-014 - 2026-09-23T07:55:05Z

### Action
- Scratch kit with a fake claude (500 for r1 only / always auth), scan_batch.sh, auto_scan.sh run, status.sh, summarize_report.sh.

### Result
- 14.1-14.4 all pass: r1 deferred behind r2; a deterministic-500 repo ends over the cap after exactly 9 calls and the auto loop finishes; auth x4 costs 0 attempts.

### Decision
- Keep BLOCKING_MAX_STREAK=3.

### Next
- DONE: phase 14 report.

## DONE - TASK-014 - 2026-09-23T07:55:25Z

### Action
- Wrote docs/report/phase-14-blocking-loop-guard.md.

### Result
- Phase 14 complete; 14.1-14.4 verified, no tokens spent.

### Decision
- Keep BLOCKING_MAX_STREAK=3. Noted the pre-existing " null" suffix in classify_failure reasons as a cosmetic follow-up.

### Next
- None. The next phase needs user approval.

## DESIGN - TASK-015 - 2026-09-23T08:01:40Z

### Action
- User chose review item D1 for phase 15; wrote docs/design/phase-15-orphan-scan-guard.md.

### Result
- Design 15.1-15.4: shared lock_take with atomic takeover and pid+start identity, per-scan job records under the lock, orphan groups stopped before relaunch, auto_scan lock on the same helper.

### Decision
- Kill orphans rather than adopt their result; exec timeout for a process group; identify by ps lstart.

### Next
- Await user approval, then IMPLEMENTING.

## IMPLEMENTING - TASK-015 - 2026-09-23T08:23:36Z

### Action
- User approved phase 15 and asked to weigh value vs effort. Checked each D1 part: bash runs the cleanup trap on HUP/TERM (tested) and a reboot kills children, so orphans need kill -9/OOM (rare, dropped); a stale lock with a reused pid after reboot/power loss is real (kept).
- Added proc_start/proc_is/lock_owner/lock_take to scheduler_common.sh; scan_batch.sh acquire_lock, auto_scan.sh acquire_auto_lock and daemon_pid use them. Design doc trimmed accordingly; CLAUDE.md + runbook updated.

### Result
- Reproduced on HEAD code: with a reused pid in .auto_scan.lock, tick exits 0 scanning nothing and auto_scan.sh stop kills the unrelated process. New code: tick runs, stop spares it.

### Decision
- Scope = lock only (15.1, 15.2); orphan kill out of scope.

### Next
- Full test suites + shellcheck, then UNIT_TESTED.

## UNIT_TESTED - TASK-015 - 2026-09-23T08:31:28Z

### Action
- New tests/lock_guard_test.sh (12 checks); ran all 11 suites and shell.sh.

### Result
- lock-guard 12/12 (10 repeated runs, race test stable); all 11 suites pass (228 checks); shell.sh pass=78 fail=0.

### Decision
- None.

### Next
- Scratch verification, then VERIFIED.

## VERIFIED - TASK-015 - 2026-09-23T08:31:28Z

### Action
- Scratch kit with fake claude: reused-pid .scan.lock, two concurrent scan_batch.sh over a stale lock, reused-pid .auto_scan.lock (tick + stop); same auto_scan case replayed on HEAD code.

### Result
- All rows pass. HEAD code reproduced the bug: tick scanned nothing (exit 0) and stop killed the unrelated process.

### Decision
- None.

### Next
- Report, DONE.

## DONE - TASK-015 - 2026-09-23T08:32:08Z

### Action
- Wrote docs/report/phase-15-orphan-scan-guard.md.

### Result
- Phase 15 delivered: pid+start lock identity and atomic takeover for both locks; orphan kill dropped by value/effort decision.

### Decision
- Reopen orphan handling only if seen in logs/.

### Next
- Next review item on user request.

## DESIGN - TASK-016 - 2026-09-23T08:34:42Z

### Action
- User approved phase 16 (recommended item). Checked premise on jq 1.6: null .error -> " null" suffix; object .error -> join fails and the envelope is dropped.

### Result
- Wrote docs/design/phase-16-failure-reason-text.md: one-line change in classify_failure.

### Decision
- tojson for non-string fields.

### Next
- IMPLEMENTING.

## IMPLEMENTING - TASK-016 - 2026-09-23T08:35:31Z

### Action
- classify_failure envelope text: removed (.error?|tostring), non-strings rendered with tojson. Added 16.1a/16.1b checks and an overload fake mode to tests/blocking_loop_test.sh.

### Result
- shell.sh pass=78 fail=0. Scratch comparison: object .error was exec/failed/attempts 1 on HEAD, now service/pending/attempts 0; plain 500 reason no longer ends in " null".

### Decision
- None.

### Next
- UNIT_TESTED once all suites pass.

## UNIT_TESTED - TASK-016 - 2026-09-23T08:40:56Z

### Action
- Ran all 11 suites and shell.sh.

### Result
- blocking-loop 19/19; all suites pass; shell.sh pass=78 fail=0.

### Decision
- None.

### Next
- VERIFIED.

## VERIFIED - TASK-016 - 2026-09-23T08:40:56Z

### Action
- Scratch kit: HEAD vs new scan_batch.sh on object-.error and plain 500 fake envelopes.

### Result
- Object .error: exec/attempts 1 -> service/attempts 0. Plain 500: ' null' gone.

### Decision
- None.

### Next
- Report, DONE.

## DONE - TASK-016 - 2026-09-23T08:40:56Z

### Action
- Wrote docs/report/phase-16-failure-reason-text.md.

### Result
- Phase 16 delivered.

### Decision
- None.

### Next
- Next item on user request.

## DESIGN - TASK-017 - 2026-09-23T08:43:12Z

### Action
- User approved phase 17. Only D3/D5 left; checked D5: busy lock -> exit 1 -> auto_scan setup error, notify, park AUTO_BLOCKED_RETRY_SECS=3600. Happens on every manual re-scan during auto.

### Result
- Wrote docs/design/phase-17-busy-lock-exit.md.

### Decision
- D5 busy part only; exit code 11; transcript cleanup out of scope.

### Next
- IMPLEMENTING.

## IMPLEMENTING - TASK-017 - 2026-09-23T08:55:19Z

### Action
- scan_batch.sh acquire_lock exits 11 on busy; auto_scan.sh supervise() case 11 = busy (idle, history busy, schedule_next +AUTO_TICK_SECS). Docs: CLAUDE.md, README, runbook.

### Result
- shell.sh pass=78 fail=0.

### Decision
- As designed.

### Next
- UNIT_TESTED.

## UNIT_TESTED - TASK-017 - 2026-09-23T08:55:19Z

### Action
- Added 17.1a/17.2a to tests/lock_guard_test.sh; ran all suites.

### Result
- lock-guard 16/16; all 11 suites pass.

### Decision
- Proceed to verification.

### Next
- VERIFIED on a scratch kit, HEAD vs new.

## VERIFIED - TASK-017 - 2026-09-23T08:57:05Z

### Action
- Scratch kit, fake claude sleeping 15 s: a manual scan_batch.sh --repo r1 plus auto_scan.sh tick during it, on HEAD 4e75c3e and on the new code.

### Result
- HEAD: blocked, setup, consecutive_failures 1, next run +3600 s.
- New: idle, busy, 0 failures, next run +301 s; r2 scanned on the following tick.

### Decision
- 17.1 and 17.2 verified.

### Next
- DONE report.

## DONE - TASK-017 - 2026-09-23T08:57:05Z

### Action
- Wrote docs/report/phase-17-busy-lock-exit.md.

### Result
- Phase 17 complete.

### Decision
- D5's transcript and log cleanup left out (low value).

### Next
- Only D3 is left from the review.

## DESIGN - TASK-018 - 2026-09-23T09:15:32Z

### Action
- User approved phase 18 (D3) and pasted a live message. Extracted the CLI 2.1.280 limit strings from its binary and replayed them through HEAD code.

### Result
- Session, Opus and Sonnet limit messages are classified exec: the repo is failed, attempts++, and there is no reset time. The weekly limit is rate_limit but has no reset time. Wrote docs/design/phase-18-limit-message-format.md.

### Decision
- Fix classification, reset parsing and the zone; drop D3's 429-in-CLI part.

### Next
- IMPLEMENTING.

## IMPLEMENTING - TASK-018 - 2026-09-23T09:28:15Z

### Action
- classify_failure rate_limit pattern += session limit | hit your ... limit. scheduler_common.sh: _zone_ok, clock_epoch, next_clock_epoch [zone], _reset_phrase_epoch, detect_reset_at pattern 5a. Docs: CLAUDE.md, README.

### Result
- shell.sh pass=78 fail=0.

### Decision
- As designed.

### Next
- UNIT_TESTED.

## UNIT_TESTED - TASK-018 - 2026-09-23T09:28:15Z

### Action
- New checks in shell_helpers_test.sh (zone on a UTC host, NY zone, date form, unknown zone, "resets 3 times") and blocking_loop_test.sh (fake mode session).

### Result
- All 11 suites pass.

### Decision
- Proceed.

### Next
- VERIFIED.

## VERIFIED - TASK-018 - 2026-09-23T09:28:15Z

### Action
- Scratch kit, HEAD 4da34e0 vs new, CLI limit texts, host TZ=UTC; then an auto_scan tick with 3 repos.

### Result
- HEAD: exec, failed/1 per repo; the tick charged 5 attempts and ended blocked.
- New: rate_limit, pending/0, reset at the zone's wall-clock time; the tick waits until 10:52 HCM.

### Decision
- 18.1 and 18.2 verified.

### Next
- DONE report.

## DONE - TASK-018 - 2026-09-23T09:28:40Z

### Action
- Wrote docs/report/phase-18-limit-message-format.md. Read-only check of the real manifest: 0 repos with this last_error.

### Result
- Phase 18 complete.

### Decision
- The 429-in-CLI part was dropped.

### Next
- No review items left.

## DESIGN - TASK-019 - 2026-09-23T11:23:46Z
- Action: queued and picked TASK-019; reproduced on a HEAD scratch kit (two SYSTEM_NAMEs, same day, summarize_report --per-repo --no-pdf); wrote docs/design/phase-19-per-plan-reports.md.
- Result: premise confirmed twice: PlanB overwrote reports/security_report_<d>.md (System Name PlanA -> PlanB), and PlanB's report held 23 demo-mini mentions from PlanA's leftover result file. Real tree: manifest has 2 repos, results/ has 4 files.
- Decision: 19.1 REPORTS_DIR=reports/<slug(SYSTEM_NAME)>; 19.2 unsafe slug rejected by report writers only (scans never blocked); 19.3 check_deliverables follows REPORTS_DIR; 19.4 load_result_files keeps only manifest-referenced result files, NOTE for the rest. Per-plan manifest/results out of scope.
- Next: IMPLEMENTING 19.1 (config.sh, own hunk only) then 19.2, 19.4, tests.

## DESIGN - TASK-019 - 2026-09-23T11:58:06Z
- Action: revised docs/design/phase-19-per-plan-reports.md after user review ("./reports/<SYSTEM_NAME>/<PLAN_NAME>/ ... backend, frontend, operation"); queued TASK-020.
- Result: path is now reports/<sys>/<plan>/ with a new PLAN_NAME key (default main, each level slugged separately, unsafe slug rejected); added 19.5 Plan row in the report header; acceptance criteria 19.1-19.5.
- Decision: user "yes" approved old reports left in place and 19.4 kept; per-plan manifest/results/logs/scheduler queued as TASK-020.
- Next: IMPLEMENTING 19.1.

## DESIGN - TASK-019 - 2026-09-23T11:59:29Z
- Action: recorded user answer "(a) can configure" in Decisions 5 of the phase 19 design.
- Result: PLAN_NAME defaults to main and is set per plan in config.sh; no open design questions left.
- Decision: design final; stop at DESIGN (design-only role).
- Next: IMPLEMENTING 19.1.

## DESIGN - TASK-019 - 2026-09-23T12:01:48Z
- Action: user asked for reports/<system>/<plan>/prompt-eval and .../by-repo; checked who writes each.
- Result: by-repo already follows REPORTS_DIR (19.1). No script in this repo writes reports/prompt-eval (51 files, from the external security_prompt_qa tool); added 19.6: config.sh publishes PROMPT_EVAL_DIR=$REPORTS_DIR/prompt-eval.
- Decision: changing the external writer is out of scope; asked the user whether to do it.
- Next: IMPLEMENTING 19.1.

## DESIGN - TASK-019 - 2026-09-23T12:02:29Z
- Action: user confirmed security_report_* and executive_summary_* go in reports/<system>/<plan>/; added the target layout tree to the phase 19 design Goal.
- Result: no behaviour change; already 19.1.
- Decision: design unchanged apart from the layout block.
- Next: IMPLEMENTING 19.1.

## DESIGN - TASK-019 - 2026-09-23T12:04:32Z
- Action: user confirmed the layout reports/<system_name>/<plan_name>/{prompt-eval,by-repo,executive_summary_*,security_report_*}.
- Result: matches 19.1 and 19.6; fixed a stale by-repo path in the design; task title now names <SYSTEM_NAME>/<PLAN_NAME>. File names keep the date-only form.
- Decision: design unchanged; only open item is whether to change the external security_prompt_qa writer.
- Next: IMPLEMENTING 19.1.

## DESIGN - TASK-019 - 2026-09-23T12:06:07Z
- Action: user chose (a): change security_prompt_qa to write to PROMPT_EVAL_DIR.
- Result: queued TASK-021 (depends on TASK-019; needs the tool's location from the user); design Decisions 7 and Out of scope updated.
- Decision: no open design questions for TASK-019.
- Next: IMPLEMENTING 19.1.

## DESIGN - TASK-019 - 2026-09-23T12:27:44Z
- Action: user: "prompt-eval just let it be, it's not your scope, QA team do it".
- Result: dropped 19.6 (PROMPT_EVAL_DIR) from the design and acceptance criteria; closed TASK-021 with a waiver. Acceptance criteria are 19.1-19.5.
- Decision: prompt-eval/ is QA-team owned; this toolkit neither writes nor configures it.
- Next: IMPLEMENTING 19.1.

## IMPLEMENTING - TASK-019 - 2026-09-23T12:43:54Z
- Action: config.sh gets PLAN_NAME=main and REPORTS_DIR=reports/<slug SYSTEM_NAME>/<slug PLAN_NAME>; report_common.sh gets require_reports_dir, manifest-scoped load_result_files (FOREIGN_RESULT_FILES + NOTE) and a Plan row; summarize_report/summarize_exec/check_deliverables call require_reports_dir; check_deliverables warns on foreign results; scan_batch/init_manifest no longer mkdir REPORTS_DIR; in-report cross-refs say "same folder"; docs updated. New tests/plan_reports_test.sh; result_files_test pins MANIFEST (it used to read the kit's real manifest) and adds 19.4 cases; check_deliverables_test uses a fixed Sys/backend plan, 8.2f now corrupts a manifest-named file, adds 19.2/19.3/19.4.
- Result: tests/run_all.sh 13 suites all passed; checks/shell.sh pass=88 fail=0.
- Decision: config.sh committed from a HEAD-based copy so the operator's REPOS_ROOT/SYSTEM_NAME stay uncommitted.
- Next: UNIT_TESTED.

## UNIT_TESTED - TASK-019 - 2026-09-23T12:44:05Z
- Action: ran tests/run_all.sh and checks/shell.sh on 8139bf8; ran the three changed suites against a git-archive copy of the pre-change scripts.
- Result: 13 suites all passed (plan-reports 39, result_files 20, check-deliverables 22); shell pass=88 fail=0. Pre-change code fails 39 / 4 / 9 of those cases.
- Decision: UNIT_TESTED; real verification still to do (verify role).
- Next: /verify-phase on a scratch kit.

## VERIFIED - TASK-019 - 2026-09-23T12:45:46Z
- Action: old (8139bf8^) vs new (HEAD) scratch kits, two plans Sys/backend + Sys/frontend from real result copies, full report set with PDF; check_deliverables; SYSTEM_NAME/PLAN_NAME=..; scan_batch --dry-run; real tree read-only; secrets.sh.
- Result: old overwrote backend and put 23 demo-mini mentions in the frontend report; new keeps reports/Sys/{backend,frontend}/ separate, 0 cross-plan findings, Plan rows present, check_deliverables PASS (FAIL on a removed PDF), '..' rejected rc=1 while dry-run scan rc=0. Real tree: the 2 unsorted__* leftovers are now excluded; manifest untouched.
- Decision: VERIFIED; security completed.
- Next: DONE report.

## DONE - TASK-019 - 2026-09-23T12:46:14Z
- Action: wrote docs/report/phase-19-per-plan-reports.md; backlog.sh complete TASK-019.
- Result: reports go to reports/<SYSTEM_NAME>/<PLAN_NAME>/, only this plan's results, Plan row; unit + old-vs-new verification recorded.
- Decision: DONE. Limitation: manifest/results still shared between plans (TASK-020 queued).
- Next: none; TASK-020 queued for the user to pick.

## DESIGN - TASK-020 - 2026-09-23T23:13:46Z
- Action: picked TASK-020; reproduced on a HEAD scratch kit: init for plan backend (be tree) then frontend (fe tree) -> one manifest ["n1/api","n2/web"]; wrote docs/design/phase-20-per-plan-scan-state.md.
- Result: 6 items: plans/<sys>/<plan>/ state dir, PLAN= selection + plan.conf, require_plan guard, repos_root guard, plan.sh new/list/adopt, per-plan scheduler with plist env.
- Decision: user told us to proceed without asking; separate manifest per plan; scan/auto locks stay global (one account); legacy root state moved only by plan.sh adopt.
- Next: IMPLEMENTING.

## IMPLEMENTING - TASK-020 - 2026-09-23T23:26:27Z
- Action: config.sh "Plans" block (PLAN= / SYSTEM_NAME / PLAN_NAME env, PLAN_DIR=plans/<sys>/<plan> with MANIFEST/RESULTS_DIR/AUTO_LOG_DIR/SCHED_STATE/ABORT_FILE, plan.conf sourced last and re-asserted, require_plan + plan_names_ok); require_plan after source in 8 entry scripts (replaces phase 19 require_reports_dir); init_manifest repos_root record/guard and plan-named hints; new plan.sh new/list/adopt; auto_scan plist carries SYSTEM_NAME/PLAN_NAME (+PLAN_DIR), XML-escaped, status names the plan; .gitignore plans/; docs + CLAUDE.md. Tests: new tests/plans_test.sh (71 cases); 7 kit suites export PLAN_DIR=<kit>; phase-19 tests follow the new error text.
- Result: plans_test 71/0; shell.sh pass=92 fail=0; secrets PASS; full run_all in progress.
- Decision: scan/auto locks and launchd label stay global (one account, one automated plan).
- Next: UNIT_TESTED.

## UNIT_TESTED - TASK-020 - 2026-09-23T23:34:34Z
- Action: tests/run_all.sh, checks/shell.sh, checks/secrets.sh on the 4686b64 tree; tests/plans_test.sh against the pre-change scripts.
- Result: 14 suites all passed (plans 71/0); shell pass=92 fail=0; secrets PASS. Pre-change: 14 failures then abort (no plan.sh).
- Decision: UNIT_TESTED.
- Next: VERIFIED.

## VERIFIED - TASK-020 - 2026-09-23T23:34:52Z
- Action: scratch kit with fake claude: two plans end to end (new, init, approve, scan, reports, check_deliverables), PLAN=Sys/.., other REPOS_ROOT, auto_scan tick/status, adopt of a pre-change kit's real root state; real tree read-only.
- Result: disjoint plans/Sys/{backend,frontend}; reports hold only their plan (6/0, 0/6); deliverables PASS; guards rc 1 with no change; scheduler files under the plan; adopt moved and re-pointed state, status shows it; real manifest untouched.
- Decision: VERIFIED; security completed.
- Next: DONE report.

## DONE - TASK-020 - 2026-09-23T23:35:18Z
- Action: wrote docs/report/phase-20-per-plan-scan-state.md; backlog.sh complete TASK-020.
- Result: each plan keeps its own state in plans/<sys>/<plan>/, picked with PLAN=; unit (14 suites) and scratch-kit verification recorded.
- Decision: DONE. Real root manifest stays until the operator runs plan.sh adopt.
- Next: none; backlog empty.
