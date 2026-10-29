---
name: verify
description: Verify implemented functionality against acceptance criteria using real runtime or integration behavior.
---

# Verification

Unit tests prove isolated behavior. Verification proves the real execution path.

Before verification:
- unit tests must pass
- identify acceptance criteria

Verify real commands, APIs, inputs, configuration and expected outputs as applicable.

## What VERIFIED means in this repo

Run each row of the design doc's `Verification` table
(`docs/design/phase-<N>-<slug>.md`) exactly as written:

- **Content tasks (EPIC-002):** the crosscheck "Exam content oracle" run is Tier 1 and is the evidence; Tiers 2-3 are N/A (no scratch kit, no `claude` call).
- **Workflow/kit changes:** run the gates on the real repo state, and replay
  real history in a clone (`git clone -q . <tmp>`; `git show <sha>:<path>`)
  to show a historic problem is now caught.
- **Both plan modes:** run the design's `Plan modes` rows for each mode it names. That is a
  single-source scratch plan (`scan_batch.sh`, then the reports and `check_deliverables.sh` with no flag),
  and a pipeline scratch run (`--run`). A mode marked "not affected" still gets one cheap check that its
  output is unchanged, for example `cmp` of a report or the gate's summary line, before and after.
- Never point a scan at this toolkit itself, and never spend real tokens or
  mutate the real manifest to verify.

## Save cost: pick the cheapest check that proves the item

Verification must prove behaviour, but it should not cost more than the change. Choose
a tier **per acceptance item** and record the tier in `verification.evidence`.

| Tier | When | What counts as evidence | Cost |
|---|---|---|---|
| 0 static | docs, comments, test-only or rename changes; no runtime path | `checks/shell.sh` + the unit suite already run at UNIT_TESTED; `security.status=not_applicable` if no surface | none |
| 1 snippet | a small bug or one function (a regex, a jq filter, a guard, a message) | a small real snippet: source the file and call the function with a fixture, or run one script once on a scratch dir, with the exact output pasted | seconds, no tokens |
| 2 scratch kit | a change on the scan path, scheduler, manifest writes, report output or a cross-script flow | **one** scratch kit plus fake `claude` that runs every Tier-2 row of the phase in a single script | minutes, no tokens |
| 3 real `claude` | only when the fake cannot stand in: prompt text, CLI flags or wording, auth or usage-limit detection against the live CLI | one small throwaway repo, once, covering all pending Tier-3 items together, after the user approves the spend | tokens |

Rules:
1. **Batch, never one-by-one.** Write one scratch script (in the scratchpad) that runs
   all of a phase's Verification rows. Build kits and fixtures once and reuse them.
   Small bugs belong in one task, so they share one pass. When several phases are
   waiting, verify them together on one kit.
2. **No real run for a small item.** Tier 1 is enough for a one-function fix. Don't
   drive `scan_batch.sh`/`auto_scan.sh` end to end to prove a regex.
3. **Reuse evidence, don't repeat it.** A script-level unit test that already runs the
   real script with fake `claude` counts for that row (cite it). A premise reproduced
   at DESIGN is the "before" half of HEAD-vs-new, so don't rebuild it. Run the full
   `tests/run_all.sh` once per phase (in the background), not after every edit; use a
   filter while iterating.
4. **Real tokens are a paid call.** Tier 3 needs the user's yes (`token-efficiency`).
   Never use the real 80-repo tree. Check the real `manifest.json` read-only
   (md5 before and after).
5. **Escalate only on doubt.** Go up one tier only when the cheaper check could not
   see the failure (for example a flow across two scripts). Write down why.

## Pipeline changes: resume one step on a copy (tier 2 and tier 3)

Copy the toolkit (`git ls-files -co --exclude-standard`, without `plans/ reports/ tmp/`) and one
finished run into a scratch kit, with the plan's `manifest.json` and `plan.conf`, and add a
`runs/latest` symlink. Then, to re-run only the steps you changed:
1. Set `run.json` `status` to `"running"` (a `complete` run makes `pipeline.sh run` start
   a **new run from phase 0**; TASK-032 had to stop two unintended starts).
2. Remove those steps and everything after them from `.pipeline.steps_done`, delete
   `.pipeline.step`, and set their units to `{phase, key, status:"pending"}`.
3. Pin the spend: `PIPELINE_2B_MAX=<the run's selected count>` and `--max-units <same>`.
   On resume correlate re-selects up to the current cap (default 30, which is twice the pilot's 6).
4. After the first `== phase…` line in the log, confirm the run id and the pending count, then leave it running.
Only the completion tail changed (`finish_run`, phase 48)? Do step 1 only and keep every step in
`steps_done`: `./pipeline.sh run` skips them all and runs just the tail, $0, with a `claude` stub that
refuses any prompt (count its calls: 0). Take D10 before and after (TASK-048).
Report-only changes need no model: run `graph_build.sh evidence|overlay` and the report scripts with
`--run <run_dir>` on the copy, and edit the 2b answers in the copy to reach each verdict path.
Check the real `plans/<sys>/<plan>/manifest.json` md5 before and after.

**Any change to overlay/conclude/report scripts must prove no finding was lost** (user rule,
2026-09-26; phases 40–42). On the real run, read-only: `python3 coverage_check.py <run_dir>
--conclusion` and `PLAN=<sys>/<plan> ./check_deliverables.sh --run latest` must show D10
`gaps=0` with the same counts as before the change (Upzi_g02/main 20260925-142931:
`findings=12 shown=12 hidden=0 xr=1 answers_upheld=3`; 20260927-112049, the latest:
`findings=15 shown=15 hidden=0 xr=8 answers_upheld=11`). A changed count is a finding to explain,
not to accept. Then one negative on a copy (drop a finding) to show the check still bites.
**Never `rebuild` the real run to verify** (it rewrites `overlay.json` and the reports). Instead,
$0 in a few minutes: copy the kit (`*.sh *.md *.py docs/prompts`) and `plans/<sys>/<plan>` into the
scratchpad, `export PLAN_DIR=<copy>`, put a `claude` stub that exits 99 first on `PATH`, run
`./pipeline.sh rebuild --run latest` in the kit copy, then patch the copy's script to force the
failure path (TASK-042). Reports land in the kit copy's `reports/`.

## HEAD vs new, same inputs

Use this for Tier 2 behavioural changes where the before/after difference is the evidence.

The strongest evidence is a side-by-side run:

1. Build two scratch kits: `git archive HEAD | tar -x -C <old>` and a copy of the
   working tree in `<new>`. Give both the same fake-`claude` modes (write one
   `mode.<repo>` file per repo) and the same fresh manifest.
2. Drive the real entry point that the bug reaches: usually
   `./auto_scan.sh tick`, not only `scan_batch.sh`, because the scheduler turns
   one bad classification into many charged attempts (in phase 18, one tick charged
   5 attempts across 3 repos).
3. Show a table of HEAD vs new: status, `attempts`, `blocking_streak`, abort class,
   `reset_epoch` shown in the zone that matters, scheduler `state`, `next_run`.
4. Run with the machine set to an unusual environment (`TZ=UTC` when the message names
   `Asia/Ho_Chi_Minh`) so local-time assumptions show up.
5. Re-check the real manifest read-only for already-affected repos, and say so
   even when the count is 0.

Long suites (`blocking_loop_test.sh` runs many batches) can exceed the 600 s tool
timeout, so run the full set with `run_in_background` and read the output file.
Don't run it twice.

Evidence:
- action/command
- input
- expected result
- actual result
- pass/fail

Paste the real command output in the chat response, not just its summary in
`task.json` — don't paraphrase or reconstruct output from memory
(`token-efficiency`).

Do not claim VERIFIED from code inspection or unit tests alone.

Record evidence under `.claude/state/task.json` `verification.evidence`,
set `verification.status = passed`, then run
`.claude/scripts/workflow-check.sh` - it rejects VERIFIED without both.

## Before calling the verifier role: save the evidence

The `verifier` has no Bash. It judges only files in `work/<TASK>/evidence/`, and it marks
any claim without a file as UNVERIFIED. Save each check you ran with
`.claude/scripts/save-evidence.sh <name> -- <cmd...>`. The script writes a header (task,
command, HEAD, time, rc), then the output, and it returns the command's rc. Use `bash -c '...'`
for pipes, and end it with the command under test, because the rc comes from the last command. `# head:`
does not pin files git ignores (`work/`, scratch kits), so name them in the request. Save one file per claim, and name each file in the verifier request:

- [ ] the unit suites the change touches: `unit-<suite> -- tests/run_all.sh <suite>`
- [ ] static checks: `static-shell -- .claude/scripts/checks/shell.sh`
- [ ] the real $0 run for each acceptance item (tier 2/3 above): `run-<item> -- ...`
- [ ] for a behaviour change, both sides with the same inputs: `before-<x>` (HEAD) and `after-<x>`
- [ ] an overlay/conclude/report change: coverage `gaps=0` on the real run's counts (`coverage -- python3 coverage_check.py <run_dir> --conclusion`)
- [ ] a report/logreach change: reports agree with logreach/conclusion (`crossgrep -- python3 tools/inspect/report_crossgrep.py <run_dir> <reports_run_dir>`, 0 mismatch rows)

Never save a paid run through the helper just to make evidence. Reuse the run's saved output
instead: copy it into `evidence/` and note its source path.

## On failure — fix, do not paper over

A real check that fails is evidence, not a dead end:

1. Set `verification.status = failed` and record the failing command + actual
   output in `verification.evidence` (never discard it).
2. Move `state` back to `IMPLEMENTING` (the fix is code, not a re-run) and
   append a phase-log entry: Action (what failed) → Result (the output) →
   Decision (the fix) → Next. Commit that revert before writing fix code
   (`commit` skill), so history shows the unit tests passed while behavior was
   wrong — that gap is the lesson.
3. Fix, re-run unit tests to UNIT_TESTED, then re-verify. Each fix-and-rerun is
   one attempt; after repeated failures, stop and reconsider the design or the
   acceptance criteria rather than retrying blindly — a test that passes while
   verification keeps failing is checking the wrong contract.

Run `.claude/scripts/workflow-check.sh` after each status change; it keeps the
state and evidence honest.
- A new report gate is verified on the real run that caused its incident, not only on fixtures: TASK-124 D16 printed nothing on the pre-122 g01 run whose layout no fixture had (evidence work/TASK-124/evidence/V1a_g01_head.txt).
