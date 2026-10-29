---
name: run-security-review
description: Operate this toolkit end to end for a security review - plan, preflight, discover/approve repos, scan, triage findings, generate the FULL report set (technical + executive + per-repo, PDF) and prove it complete with ./check_deliverables.sh. Load when asked to run/continue a security scan or review, "init" newly configured repos, generate or check reports, or asked whether the reports are complete. Not for changing the toolkit's code (use workflow/design for that).
---

# Run a security review

Procedure and rationale: `docs/guide/security-review-runbook.md` (steps 0-7).
Whole flow, both modes (set B, gap review, latest conclusion): `docs/guide/architecture.md`.
Flag reference: `README.md`. Triage rules: the `api-platform-security` skill.
This file is the agent's version: the same steps, plus where to stop and ask.

## Source trees are off-limits (hands off)
The cleaned source under `REPOS_ROOT` is the review evidence. **Why no reading:** the
report must measure only what the scan model (`CLAUDE_MODEL`, default `sonnet`) found by
itself. An operating agent that reads the source mixes its own judgement into the
findings, and then the result no longer shows the scan model's quality. So never
add, drop or re-rate a finding from your own reading of the code. It also costs:
reading the source is the scan model's paid work, so doing it again with the operating
model spends tokens twice. Never modify it:
no `git init`, no file moves or edits, no deletes, nothing written into it.
- **Inspect only:** folder and file names, paths, counts, sizes, and `find -type f`
  to check that a folder is not empty. **Never read contents:** no Read, cat, grep or
  sed on files in that tree. Only `scan_batch.sh`'s `claude -p` subshell reads the source.
- **Triage** works from `results/*.json` (`file`, `line`, `evidence`) only. When a
  finding needs checking against the code, say so and leave it to a human reviewer
  or a targeted re-scan the user approves.
- **Anything wrong with the tree itself** (a stray file, a missing folder):
  tell the user in your reply, with paths and counts, without quoting file
  contents. Never fix it and never write notes or issues for the team that
  prepares the tree: not our job (user, 2026-09-27).
- **Scope — check the plan's kind first:** `./plan.sh kind <sys>/<plan>`. Only when it
  prints `demo` may you read that plan's source (to explain or check findings).
  `review`, an error, or no plan at all means names only. The kind is set only in the
  git-tracked `plan_kinds.conf` (`./plan.sh new ... --demo` adds the line); never edit
  that file or change a kind yourself to get read access, but ask the user. A scratch/fixture tree you built yourself is readable.
- **Demo plans:** what you find by reading the code (something the scan model missed
  or got wrong) goes in a separate note, `docs/notes/demo-<plan>-<date>.md`, and never
  into that plan's `results/` or reports.

- **Scope:** this toolkit and its engine only. Never propose or depend on another team's or
  tool's work; solve it here or drop it.

## Stop points (ask the user)
- $0 manifest/admin forms go through `./scan_admin.sh --approve|--approve-all|--unapprove|--release|--dry-run` (no prompt); real scans stay `./scan_batch.sh`, which always asks (user RAW-00283).
- Upzi (user RAW-00267): never propose, estimate or ask about paid Upzi steps (AI scan, gap review); the user asks when the engine is stable. Upzi = $0 ext-scan learning only; paid tests only on small project groups (bench).
- **Scope and approval.** `--approve`/`--approve-all` decide what gets
  reviewed. Approve when the user asked for it, otherwise list what `init` found and ask.
- **Spending money.** A scan (`scan_batch.sh`, `auto_scan.sh enable/now`) is
  paid. Run it when the user asked for a scan. A *re-scan* the user didn't ask
  for (e.g. to prove a fix) is also paid: say what it costs (~$0.25/small repo) and ask. The gap review (`ext_gapreview.sh`, `ext_gap_eval.sh --go`) is paid too: state units, items and the estimate (dry-run) and ask.
- **Destroying state.** Resetting `manifest.json` or deleting results or reports
  needs a yes. Look at the file first, and remember git history has the old manifest.
- **Paid-go checklist (before asking for any paid go: a scan, a pipeline run or new, a gap review).** (1) `./plan.sh features <sys>/<plan>`: name every `missing`/`off` feature and why. (2) `./pipeline.sh status` deploy line (`deploy: source=.. verdict=..`): `empty`/`none` = fix first. (3) logreach row `on`? If `missing`, say so in the ask. (4) What changed since the last run (preflight `changed since last run` lines); nothing changed + same failure = do not re-run. (5) `./check_deliverables.sh --run latest` of the last run: list open FAIL/WARN lines (D15 logreach, D16 deploy context) in the ask.
- **No skipped safeguard.** Never recommend skipping or waiving a safeguard (deploy context, graph hold, logreach, inventory, approval gate) unless the ask carries a root-cause line and the engine-level fix (task id or proposal). A waiver is the user's choice, never the default recommendation.
- **Header fields.** If `SYSTEM_NAME`/`PLAN_NAME`/`ASSESSMENT_*`/`POINT_OF_CONTACT` in
  `config.sh` look like they belong to a previous review, say so before you hand anything over.
  `SYSTEM_NAME` + `PLAN_NAME` also choose the folder, `reports/<sys>/<plan>/`.

## Steps
0. **Plan**: every step runs on one plan: `./plan.sh list`; a new one is
   `./plan.sh new <sys>/<plan> <repos_root> [--demo]` (`--demo` only when the user says
   it is a demo); prefix every command below with
   `PLAN=<sys>/<plan>` (state in `plans/<sys>/<plan>/`, reports in `reports/<sys>/<plan>/`).
   Root `manifest.json`/`results/` from before plans are ignored until `./plan.sh adopt`.
1. **Preflight**: `claude auth status`; the plan's `REPOS_ROOT` (`plan.conf`); every repo
   sits at `<workspace>/<repo>/` (`.git` optional: cleaned sources have none; a
   workspace folder must hold only repo folders, or its no-`.git` repos are skipped
   with a WARN, so report those, never fix the tree yourself); `jq empty manifest.json` passes (a 0-byte
   manifest breaks every script).
2. **Discover**: `./init_manifest.sh`, then show the new `init` repos (workspace, name).
3. **Approve**: only after step 1's stop point is cleared. Then `./scan_batch.sh --dry-run`.
4. **Scan**: `./scan_batch.sh [--batch N]`, run in the background (about 2 min per small
   repo). On exit 10, read the printed block: a blocking class (`auth`/`rate_limit`/`service`)
   leaves the repo `pending`, so report the reset time or fix and don't retry in a loop.
   After every batch, check that `manifest.json` still lists every repo (`jq '.repos|length'`).
5. **Triage**: `./status.sh --failures`, `./verify_findings.sh --detail`.
   Keep every finding **exactly as the scan model wrote it**: never add, drop or re-rate
   one, and never set its `status`. Work from the result JSON only, never the source tree
   (see "Source trees are off-limits"). Tell the user, in your message and not in the
   report: repos that failed, findings `verify_findings.sh` marks incomplete, findings
   that look like platform false positives (`X-User-Id` is trusted, `/internal/` is one
   level lower), and the same issue rated differently in different repos. The user
   decides; a prompt fix and re-scan happen only if they approve it.
6. **Generate BOTH reports**, always together:
   `./summarize_report.sh --per-repo` **and** `./summarize_exec.sh`
   (`--csv <path>` if a spreadsheet was asked for).
   On a re-scan the technical report adds section 13 "Changes since previous scan"; report its
   counts as they are (not re-found ≠ fixed unless the code changed). Optional for reviewers:
   `./compare_runs.sh` (single-source) / `--run latest` (pipeline) → `run_comparison_`, never hand over.
7. **Completion gate**: `./check_deliverables.sh` (plus `--csv`/`--no-pdf` to match
   what was produced). The review is done only when it exits 0. If it fails,
   run the command at the end of each FAIL line, then run the check again.

## Pipeline run (multi-repo)
Procedure, costs and the verdict table: runbook "Pipeline run". Use it only when the user asks for a
cross-service or pipeline review; the single-repo steps above stay as they are.
- Where each step gets its input (deploy, logreach, inventory, switches), the `$0` check and the fix: `references/pipeline-inputs.md`; read it before debugging an empty or missing step.
- **Stop points are only at the start.** First, the scope is approved. Then show the user
  `./pipeline.sh run --dry-run` (every path must be a repo of this plan) and the cost estimate
  (runbook table: pilot ≈ $1.85 per repo + $0.35 per 2b item, capped by `PIPELINE_2B_MAX`).
  After that, `AUTO_DRIVER=pipeline ./auto_scan.sh enable && AUTO_DRIVER=pipeline ./auto_scan.sh run`
  runs hands-off. Check with `./auto_scan.sh status` / `./pipeline.sh status`; never ask mid-run.
- **A finished run is never resumed:** `./pipeline.sh run` then starts a new, paid run from
  phase 0. To re-report a run, use `./pipeline.sh rebuild --render --run <run_dir>` ($0; plain
  `rebuild` also redoes overlay + conclude). Never start a new run that the user did not ask for.
- **No finding lost (trust chain, $0):** every report renders from `report/conclusion.json`.
  `coverage_check.py` proves scan → conclusion → reports: the `conclude` step runs it
  (`--conclusion`) and the gate runs it as D10. `GAP ...` + `ERROR: step conclude failed.` means
  a toolkit script lost or changed a finding: no report was made, the run shows as blocked under
  auto_scan. Tell the user and the toolkit maintainers; never edit `conclusion.json` or run files
  to make it pass. Quick read-only check: `python3 coverage_check.py <run_dir> --conclusion`.
  A finished run is concluded again once it is marked complete (phase 48), so D10 passes with no rebuild.
  `run <id> is complete but its conclusion was not refreshed` (exit 1): run the printed
  `rebuild --render` command; it is $0, and the run is not repeated.
- **Report set:** `reports/<sys>/<plan>/run-<id>/` holds `security_report_`, `executive_summary_`,
  `by-repo/` (+ auto `by-repo-public/` = by-repo minus 0-finding repos), `findings_` (hand these over) and `verification_appendix_` (reviewers only, never
  hand over), each with a PDF. `engine_review_` is for toolkit maintainers: when a verdict looks
  wrong, give the user its `ER-` row and stage tag. For "what changed since the last run / was a missing finding checked?",
  point to its §11 (run-over-run drift: `verified: <verdict>` or `unverified` per not-re-found High/Medium row). Never edit run files to "fix" a verdict.
  Gate: `./check_deliverables.sh --run latest`. Optional, $0: `./evaluate_run.sh`.
- **Stable ids (optional, $0):** `PLAN=<sys>/<plan> ./tracking/track.sh --run latest` records the run in
  `../security-findings` (commit is local; the user pushes) and writes copies of every report with
  `VNW-SEC-nnnn` ids to `reports/<sys>/<plan>/tracking/<run>/` (`index.md` maps engine file → copy) plus
  `tracking/delta_<run>.md|pdf` (new/fixed/reopened). Hand over the copies when the team tracks by stable
  id. Engine reports are never changed. `--baseline` refreshes all tracked runs. Doc: `docs/finding-identity.md`.
- **Read verdicts per finding, not per chain.** A refuted chain does not make its findings false.
  Only a finding judged not upheld on its own is hidden (counted, and listed in the appendix), and
  only when every check agrees, the evidence is in its own repo and its route is not
  `/public/`/`/external/`; otherwise it stays listed as **disputed**.
  Confirmed raises severity and never lowers it. R4/R5 results become `XR-nnn` issues.
  You report these; you never change them. Runs, 2b answers and the overlay are data: never
  edit them. A hide that looks wrong goes to the user, with `PIPELINE_HIDE_NOT_UPHELD=0` as a way to show it.
- **Reporting back** adds: hidden count, XR issues, severities raised, run cost
  (`./evaluate_run.sh` or `./pipeline.sh status`), and the `check_deliverables --run` line
  (its D10 `COVERAGE findings=... gaps=0` is the proof that no finding was lost).

- **Set B and gap review (add-ons).** Set B (`ext_scan.sh`, $0, Docker) runs by default (`EXT_SCAN=1`; `0` turns it off per plan).
  PL: the `extpre` step runs the tools before the approval gate (`--pre-gate`, no AI set, WARN only) and the gate shows the tool
  pre-review `runs/<id>/recon/ext_pre/ext_ab_<date>.md` next to the recon report; the `ext` step runs after conclude and writes the
  ext reference report (`ext_ab_<date>.md` + .pdf: tool summary, S1-S4 anomaly flags, "review again" recommendation only).
  SS: by hand after the scan (no `--run`). The main report stays AI-only; B-only rows are leads, not findings. Every run re-scans;
  `EXT_SKIP_UNCHANGED=1` opts in to skip a repo by hash. The AI gap review (79.7) is built but **off and out of the flow** (AC5):
  no AI call reviews a tool row; never enable it or set it in plan.conf without the user's go (paid, Sonnet, never Haiku).

## After a run: engine health review ($0, read-only)
The QA gates prove no finding was lost; they do not prove the engine behaved. Passing gates can
hide wasted spend or a stale report (g02 `--jobs 2`: all gates passed, 5 engine problems). After
every paid run or resume, check the items below using only run files, logs, reports and `git status`.
Never read a source tree, and never edit run files to make a check look right.
| Look at | How | Problem it catches |
|---|---|---|
| Unit log vs recorded status | each unit's log tail (`finished (Ns)`, `rate_limit`, rc) against `./pipeline.sh status` / `.pipeline` | unit marked failed although its log says finished (misclassified) |
| Resume | list finished units (out file + cost) before the resume and compare after; count `claude` launches per unit (`ls runs/<id>/<phase>/log/<key>.*.raw` = extra calls, phase 65) | finished units re-run, logs overwritten, and cost lost from the totals |
| Holds and limits | hold/reset lines in the auto_scan log, `.usage_hold.json`, and the pause start and end times | limit reached sooner with `--jobs N`; long waits for the reported reset |
| Timing and cost | wall time with pauses left out, summed call time, and cost per unit, per phase; compare per unit when unit counts differ (2b picks vary) | a speedup or saving that comes from different work, not the change |
| Report freshness | status, wall time and run id in `run_comparison_` / `engine_review_` against the run's final state | report written before the run was marked complete ("running", "n/a") |
| Toolkit side effects | `git status` and new files at the toolkit root after runs and tests | a test or script writes real kit state (e.g. `.usage_hold.json`) |
| Report cross-check | the `CROSSCHECK:` line and `plans/<s>/<p>/crosscheck/<scope>.json`; the tester's `RESULT:` (skill `crosscheck`) | a finding, repo or count not carried into a report; an unregistered report file |
| Finding drift | not-re-found High/Medium: has the repo changed since the last run (tree evidence / engine review §11)? | run-to-run noise reported as a fix |

**Plan each problem before touching code; nothing is fixed mid-run.**
1. State the symptom with evidence (file, line or log excerpt, count, $ impact).
2. Find the cause's layer. Fix the generator or script, never the data. Model prompts are frozen,
   so the fix goes in the deterministic layer. Scope is this toolkit only; tree problems go to the user.
3. Weigh cost (does it waste paid calls or mislead the report?) and choose a priority.
4. Give the user one numbered list, "Problems found (none fixed yet)", with a recommendation per item.
   On the user's go, queue each one through `req-intake` as REQ + backlog TASK. Write ACs that a fake
   `claude` and a scratch kit can test, and add one AC for the other plan mode.

## Reporting back to the user
- A table: repo → Critical/High/Medium/Low, plus the top Critical titles with `file:line`.
- The list of report files and who each one is for (runbook step 7).
- Anything triage found: inconsistent severities, suspected false positives,
  repos left `init`, and spend (`./status.sh` shows it).
- The `check_deliverables.sh` summary line as the proof.
