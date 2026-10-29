---
name: token-efficiency
description: Working-approach rules to save tokens and keep scope minimal in this repo - what to read, when to reuse prior results instead of redoing work, how verbose to be, and never guessing APIs/flags/versions. Load at the start of any session, or whenever a task starts to feel bigger than it needs to be.
---

# Token efficiency

Priority: user request → existing skill/rules → existing results
(`task.json`, `phase-log.md`, `backlog.json`, git log) → minimum files needed
→ ask for more scope → expensive operations (spawning agents, paid/remote
calls, `docker pull`).

## Scope and access

- Scope is the repo root. Don't read outside it (home dir, sibling repos,
  `~/.claude`) unless the user names that path in the current request.
- Never read `.env*`, `node_modules/`, or `.git/objects` contents directly.
- Work only on the active task in `task.json`; load only the language/domain
  skill(s) the current change actually touches (CLAUDE.md rule 6) -
  `python` only when Python code changes,
  `api-platform-security` only for prompt/triage work.

## Reading and reuse

- Locate first (`grep -rn`, `ls`, `bash .claude/scripts/task-state.sh`), then
  read only the needed section/offset of a file - don't read a whole file to
  find one function.
- Read a file once per session; re-read only if it changed since, the read
  was partial, or you're about to cite it as evidence.
- Before redoing work, check what's already recorded: `git log
  --grep="Task: <id>"`, the active task's `phase-log.md` entries (grep
  `TASK-NNN`, never read the whole log or `phase-log-archive.md`), and the relevant
  sub-status in `task.json` (`design`/`implementation`/`unit_test`/
  `verification`/`security`/`report`). A check already passed and recorded
  there does not need to be re-run "to be sure" - see `workflow`'s momentum
  section for when a passed phase should just be built on, not re-verified.
- A skill loaded earlier in the session stays loaded; don't re-invoke it
  unless its content changed on disk.

## Reading files and command output (every role; user, RAW-00132/00133)

Pick the smallest read that answers the question. A matching line is cheaper than a window, and
a window is cheaper than a whole file.

| You need | Use | Not |
|---|---|---|
| Whether X is there, where, how often | `grep -n X f` / `grep -c X f` / `grep -l X dir -r` (Grep tool: `head_limit`, `output_mode: count` or `files_with_matches`) | `cat`, a `head`/`tail` window |
| The lines around a match | `grep -n -A3 -B1 X f` | `sed -n 1,200p` |
| A test or run result | `... 2>&1 \| grep -E "SUMMARY\|FAIL\|ERROR"` | the full log, a blind `tail` |
| A known part of a file | Read with `offset`/`limit` after a `grep -n` for the line, or `sed -n A,Bp` | the whole file |
| The start or end of a file (header, last log lines) | `head -n N` / `tail -n N`, N as small as works (5 to 20) | a bare `head`/`tail` (10 lines by default, often not the ones you need) |
| A whole file | `cat`/Read, only when it is short (`wc -l` first if unsure) and you need all of it | reading it to find one line |
| A long run kept as evidence | `.claude/scripts/save-evidence.sh <name> -- <cmd>`, then grep the saved file | printing it into the context |

- Never `tail` a gate or status command to get its verdict (see the lessons below): grep the verdict line.
- Filter at the source: `jq -r '.field'`, `git log --oneline -5`, `git diff --stat`, `ls | head -n 20`.
- One batched command beats three single reads; quote only the lines you use.
- Reports and tool results (user, RAW-00221): there are many report and findings files, so never read one whole.
  Count first (`wc -l`, `jq length`, `grep -c`), then `grep`/`jq select` the rows you need, or `head -n N`/`tail -n N`
  with a small N. Summarize tool rows with `jq -r ... | sort | uniq -c | sort -rn | head -n 20`, never print them all.

Per role:
- **designer**: `grep -n` for each function or rule the design cites, then read only that part (Read `offset`/`limit`). Cite `file:line`, do not paste bodies.
- **coder**: before an edit, `grep -n` the exact anchor. After it, run the one suite and grep its SUMMARY; the full `run_all` goes in the background and you read only its summary.
- **tester**: save each run with `save-evidence.sh`, then `grep -E "SUMMARY|FAIL"` the saved file. For a bite, grep only the failing case names.
- **verifier** (no Bash): Grep with `head_limit` and `output_mode: count` or `files_with_matches` first. Read evidence files with `offset`/`limit` around the grep hit; never read a whole log.

## Output

- Mirror phase-log discipline in the chat response too: Action → Result →
  Decision → Next, deltas only - don't restate what's already in
  `task.json`, `phase-log.md`, or earlier in the conversation.
- When citing a command's output as evidence (`verify`/`unit-test`/`report`
  skills), paste the real output; don't paraphrase or reconstruct it from
  memory.
- Never guess API names, CLI flags, package versions, or config keys - read
  the code/config/docs (or run `--help`) first. The same "verify before
  trusting" applies to runtime behavior generally: confirm effects by
  running the real thing instead of reasoning about it on paper.

## Talking to the user (user rule, 2026-09-25)

- While working: one short line per step at most. No tables, no summaries,
  no recaps of what a tool already showed.
- A table or summary only when a phase (state transition) finishes, and keep
  it short.
- Code comments: short, only the why; no restating the code.

## Approvals and end of turn

- One short summary, not per-file chatter.
- Batch every pending decision into one numbered list, each item marked
  "pick ONE" or "approve any/all", with a recommended option called out -
  don't ask single questions one at a time when more than one is already
  known. These are the same cases `workflow`'s "Momentum" section says are
  worth stopping for (user-only information, a real design tradeoff, an
  irreversible action) - not every phase boundary.
- End every turn with one last line: `Decisions: None` (optionally why,
  e.g. `Decisions: None -- waiting on npm run validate`) or the numbered
  list - so the next message is always either "keep going" or a specific,
  answerable set of choices, never a vague "let me know if you want me to
  continue."
- Recommend, don't survey (user, 2026-09-27): every open decision comes with the option you
  judge best and why, based on the repo's rules and the latest run data. The user then answers
  "accept all" or names the exceptions; one round, no follow-up questions.
- After "accept all, start X": record the answers, create/pick the task, design, and keep going
  through the phases in the same turn (paid steps still need their own go).
- Approval covers every item in the list, including its stated cost/scope
  (e.g. "pull a fresh Docker image", "spend on a paid API call"); once
  given, do them all in dependency order without asking again per item.

## Going faster (lessons log — keep improving)

Proven in this repo; each line is a habit, not a suggestion. **After every
task (at its DONE), append one line here for anything that saved or wasted a
turn**, dated, and delete a line that proved wrong. Keep the list short.

- Cost rule (user, 2026-09-25): develop and test against a fake `claude` on
  PATH (pattern: tests/scan_isolation_test.sh, tests/pipeline_layout_test.sh).
  Real `claude -p` only when a fake cannot answer the question, and batched:
  once per phase, after all its unit tests pass, not per item.
- Unsure how the claude CLI behaves? Test it, don't reason about it: a
  haiku `claude -p` call in a scratchpad dir costs < $0.01 (2026-09-25:
  prompt on stdin + isolation flags, and `--restricted` + `--add-dir`
  confinement, each settled with one call).
- Open plan items: `bash .claude/scripts/checklist.sh`, not a re-read of the
  design doc. Tick rows in the commit that finishes them.
- Design docs cite `file:line` in "Code facts": read only those ranges
  (`sed -n a,bp`), never whole scripts.
- Several doc edits: one python patch with anchor-count asserts, one call.
- A transition = one Bash call: jq on task.json, append phase-log,
  workflow-check, `git add`, commit-check, commit. commit-check needs
  task.json staged even for a docs-only commit in an active task.
- Python here is 3.8: no `str.removeprefix`, no `match`.
- Tests that `sed`-extract functions from a script break when the function
  moves; grep `tests/` for the function name before moving it.
- Full suite takes > 10 min: start it with `run_in_background` after the item's edits are committed
  (TASK-074: an earlier run went stale and blocked test edits 20+ min); foreground `sleep` is blocked.
- Iterate with one suite (`tests/run_all.sh <name>`); the full suite runs in
  the background once before UNIT_TESTED.
- Never edit a test file while it runs in the background: bash reads scripts
  lazily, so the run dies with bogus syntax errors. Snapshot it or wait.
- Scratch kits: `config.sh` assigns plain values (`JOB_DELAY_SECS=60`) that
  override your env; `sed` the kit's config.sh instead. A 60 s pause per unit
  made one suite take 2.5 min instead of 20 s.
- Fakes that sleep use `exec sleep N`: an orphaned child keeps the test's
  output pipe open until it exits.
- Tier-3 checks run on haiku in a scratch kit (a phase-0 card cost $0.035). Haiku
  may break a strict schema: that proves the gate works, not the plumbing.
  Prove the plumbing with 0 `permission_denials` and prompt-specific wording in the answer.
- Never pipe `commit-check.sh` into `tail`/`head` before `&&`: the pipe's status
  is tail's, so a failed gate still commits (TASK-025). Run it bare.
- Before quoting a cross-run comparison ("same commit, 0 persisting"), check the
  join key is non-empty in both runs: `head_sha` was "" everywhere (no .git), so
  a claim built on it had to be retracted from the design (TASK-031, 2026-09-25).
- Commit trailers per state (commit skill, lines 76-78): UNIT_TESTED `Tests:`, VERIFIED
  `Verified-by:`, DONE `Report:`. Write them in the message file up front. TASK-032 hit
  commit-check once for each missing trailer (3 wasted calls).
- Report scripts are shared by single-phase and run mode. Before changing one, save a golden
  of today's standalone output (`git archive` kit, `--no-pdf`) and diff it afterwards
  (TASK-032: byte-identical proof in one call).
- Resuming a finished pipeline run in a kit: set `run.json` status `running`, drop the steps
  from `steps_done`, and pin `PIPELINE_2B_MAX` + `--max-units` to the pilot's count. Otherwise
  `pipeline.sh run` starts a new run from phase 0 (TASK-032: stopped twice, ~$0.1 lost; recipe in `verify`).
- PDFs from a relative path: Chrome prints its own error page into the PDF and exits 0. Look at a
  page image of every new PDF deliverable, not only its size (TASK-033, 2026-09-25).
- Before designing a join, dump one real run's file shapes (`jq -c keys`) in one call: TASK-034
  found `overlay.json` is an array and `calls_outside_plan` a map up front, so the collector ran
  first time on the real run (2026-09-25).
- Multi-step Bash calls: chain gates with `&&`. `set -e` on its own line did not stop the
  chain here, so commit-check's FAIL was ignored and 2 commits landed (TASK-035, 2026-09-26).
- Renderer changes: diff old vs new output over every Markdown file in the scratch kits and
  `docs/` first. That caught a stash-marker clash with hard breaks before any test ran (TASK-035).
- Appending to backlog.json: use Python json.dumps (ASCII escapes), not jq, which rewrites every \u escape and bloats the diff; queue the item in the DESIGN commit via `pick --force` after a DONE task (TASK-036).
- A change to any run report (engine review, appendix, overlay): at VERIFIED run `check_deliverables.sh --run latest` on the real plan and regenerate the set if it FAILs; a scratch render of one report is not the deliverable (TASK-036).
- commit-check.sh takes a message FILE (`printf … > $f; commit-check.sh "$f" && git commit -F "$f"`); never pipe it to `tail`, which hides its exit 2 and lets a commit skip the gate (TASK-037).
- Refactoring a report path: build a golden byte-diff harness and baseline it on HEAD before editing; G1 stayed empty at every step, so no report needed re-verifying. Before editing a doc under `docs/prompts/`, check commit-check: the gate treats every file there as a frozen prompt (TASK-038).
- After a big change, finish and check it before proposing anything new (user, 2026-09-26: no Haiku/A-B offers; quality engine = Sonnet/Opus). Close with: what can break, how to detect it, and a scan → conclusion → report coverage join (fingerprint, then display ids per report) proving no finding was lost by our scripts (TASK-040).
- When the user sends ideas mid-task, fold in only what fits the current item (TASK-041: reverse id check in D10, same script, 2 tests) and rerun just the affected suites after a full run; a restore in a test that feeds an mtime-based check needs `cp -p` (TASK-041).
- To verify a pipeline step on real data without touching the real plan: copy the kit and the plan into the scratchpad, set `PLAN_DIR`, put a failing `claude` stub first on PATH, and `rebuild`; patch the kit copy of a script to force the failure path. Run the slow full suite in the background and draft the report while it runs (TASK-042).
- Read the token split before tuning a prompt: the run envelope (output, cache write, cache read) showed D's extra cost was all input, from an appended addendum that said "follow <procedure> in full"; rules at the top of the prompt cut 27 % (TASK-043).
- A repeat in the same plan reuses cards by input hash ($0, measures nothing): measure noise in a sibling plan. Queue the next paid arm in the same background job, gated on rc 0, so a limit reset costs no extra turn (TASK-044).
- Before adopting a cheaper knob (lower `--effort`), gate it on card_ab quality rule g, not only cost: medium cut 30 % but recon cover fell to 72.8 %. One paid arm was enough to decide (TASK-045).
- Do not propose Haiku for complex work such as reading a repo or building cards: it failed quality, and Haiku plus Sonnet on the same repo doubles the spend. Check the free cost profile (`p0_cost.py`) first: a helper call that costs more than the part it trims is not worth it (TASK-039 close).
- Before a paid phase 0 try, check `docs/notes/phase0-tried-options.md`; add the row after. Fewer whole-file reads is not a saving if the model reads more around the windows: measure total result chars and turns (TASK-046).
- Never wait on a background job with `until ! pgrep -f '<pattern>'`: the waiter's own command line matches the pattern, so it never exits and burns turns. Run the suite itself with `run_in_background` and act on its notification. A finished run can be re-checked at $0 on a scratch copy of the plan with a fake `claude` that refuses prompts (TASK-048).
- Req-kit (2026-09-27): every prompt of 25+ chars becomes a RAW and the Stop hook blocks until it is triaged. Triage it at the start of the turn in one command: an instruction for the current work ("commit it", "update skills") is `req.py raw ignore RAW-x --reason "instruction for the current step"`; only a new user need becomes a REQ. Move a REQ only after its TASK (task_gate.py refuses otherwise), so REQ bookkeeping never costs a second verification.
- 2026-09-27 (TASK-049): run the paid step in the background (`run_in_background`) and do the security review of the diff while it runs; the whole paid verify plus checks fit in one turn with no polling.
- 2026-09-27 (TASK-052): run a security pass on model-text rendering *before* the real verify run; the late `esc` fix cost a second rebuild and three suite reruns. And background run_all finishes with a notification — never add a pgrep waiter (see above; I did it again).
- 2026-09-27 (TASK-053): while unit tests run in the background, do the $0 real rebuild and draft the report in parallel; wait on the Bash `run_in_background` notification only (a Monitor/until loop that `pgrep -f`s the script name matches itself). Put `implementation.files` and `verification.evidence` in task.json at the transition, or commit-check fails once each. Keep an untracked report out of docs/report until DONE, because the gate rejects unstaged workflow files.
- 2026-09-27 (req-kit): one call per REQ move: `req.py status REQ-x <STATE> --evidence ... --next "..."`; tick ACs with `req.py ac REQ-x AC1,AC2 --evidence ...` (no sed on line numbers). The workflow skill table lists the task.json fields each transition needs; set them with the state, not after commit-check fails.
- 2026-09-27 (TASK-054): a jq compile error inside a report section was silent (rc 0, deliverables PASS); grep the rendered report for the new heading on every rebuild, and make render helpers fail loudly.
- 2026-09-27 (TASK-050): the REQ Design section is its own gate: fill it (link the design doc) in the DESIGN commit, or `req.py status ... IMPLEMENTING` fails after the task commit already landed. A run_all over ~10 min outlives the foreground Bash timeout; start it with `run_in_background` from the first call.
- 2026-09-27 (TASK-051): the verifier role has no Bash; save the real-run evidence (rebuild log with rc, coverage, deliverables, the conclusion slices) to work/<id>/evidence before calling it. Tester + verifier roles found 2 real defects (a raw model-text cell, a repo-blind match) for a few cents of context, so run them before VERIFIED on report changes.
- 2026-09-28 (TASK-055): never pipe `commit-check.sh` into `tail` in a `&& git commit` chain: the pipe hides its failure and the commit lands without trailers; run it bare and test `$?`. Check the engine's own report CSV ids against an add-on's mapping on the real run, not only its in-process coverage: the first run with a shown XR row exposed a gap no fixture had. Before rewriting an add-on's git registry, check `git branch -vv`: the user had pushed it.
- 2026-09-28 (TASK-056): replaying the whole plan history into a scratch registry ($0, `--baseline --registry <scratch>`,
  back up and restore `reports/<sys>/<plan>/tracking/`) found a duplicate-id bug a single real run could not show.
  Never key identity on a model-chosen field (e.g. `owner_repo`); only on deterministic engine ids.
- 2026-09-28 (TASK-057): when a count check looks wrong (19 ids "without stable id", 18 vs 20 rows), exclude
  the parts your own tool added (appendix) and table headers before suspecting the code; one grep saved a debug loop.
- 2026-09-28 (TASK-058): try a new annotator on every real run into the scratchpad first (`--out-root $SP`, $0)
  with an independent checker (bare / marked / wrong-by-line-evidence); it found the two-run comparison ids and a
  mislabelled date before anything was written to reports/.
- 2026-09-28 (TASK-059): save read-only proofs as a script under `work/<TASK>/evidence/` run through
  `save-evidence.sh` (hash before, run, hash after, diff). An inline `bash -c` was rejected by the verifier
  (TASK-059) and by the removal safety check, which dropped a whole call incl. a commit (TASK-074).
- 2026-09-28 (TASK-060): commit-check takes a message *file* and wants one trailer block (`Task:`, `State:`,
  plus `Tests:` for UNIT_TESTED or `Verified-by:` for VERIFIED, attribution last). Never `commit-check | tail && git commit`:
  the pipe hides its rc and a failing gate still commits. Save the diff-stat and exit-code proof for the other
  plan mode together with the unit evidence, so the verifier does not come back PARTIAL for missing AC4 evidence.
- 2026-09-28 (TASK-061): write new AC lines as `- [ ] ACn: ...` (colon right after the id); `AC7 (RAW-…):`
  is not parsed by `req.py ac` and costs an extra turn at VERIFIED. Never `pkill -f` a pattern in the same
  command line: it kills its own shell (exit 144; again TASK-074); kill by the PID from `pgrep`.
- 2026-09-28 (TASK-062): roles were stopped by the user 3 times because nothing showed that they loaded skills.
  Fix: a `skills:` frontmatter line in `.claude/agents/<role>.md` (preloaded; the `/agents` wizard is gone, so edit
  the file and restart the session to reload it) and a `SKILLS:` line as line 2 of every handoff, which the
  coordinator checks. A stopped agent cannot be resumed: start a new one that keeps the partial `git diff`.
- 2026-09-28 (RAW-00086): a role without the `Skill` tool in its `tools:` line cannot load a skill mid-step,
  even when it picks the right one (probes: tester wanted `python`, verifier `pentest-report-qa` + `report`).
  Every role now lists `Skill`; agent files are read at session start, so re-probe only after a restart.
- 2026-09-28 (TASK-062): kits pin `JOB_DELAY_SECS=0` for speed, which hid a launch-during-stagger bug that only the
  verifier's code read found; give every concurrency suite one case with a non-zero stagger. Commit a role's
  finished edits as a `wip` commit at once: an accidental stop (Esc) then loses nothing, and the next role builds on a hash.
- 2026-09-28 (TASK-063, RAW-00100/101): roles cannot commit or move state, so a finished role reply is a commit
  due now, not after QA: the coder's work sat uncommitted through a classifier outage and the user committed it as
  "up". The list of what roles cannot do, and who covers it, is skill `coordinator` §2b.
- 2026-09-28 (TASK-063): `work/` is gitignored: never `git add work/...` in a transition commit (it fails after the state files are already written); evidence and handoffs are cited by path only. Draft the report while the verifier runs and leave named placeholders for its verdict: DONE then needs one replace and one commit.
- 2026-09-29 (TASK-064): chain the gate as `commit-check.sh $m > out && git commit` (no pipe into `tail`, no `;`): both let `git commit` run after a gate FAIL (three amends here). Trailers per state: UNIT_TESTED needs `Tests:`, VERIFIED `Verified-by:`, both with `Task:` + `State:` in one block. A verifier FAIL costs one rollback commit + one fix round (~40 min here); a hook change with a "scope" AC needs a test where another party dirties the tree.
- 2026-09-29 (TASK-066): a scratch kit for a pipeline rebuild needs **all** the plan's runs (carried findings chain through older runs: 2 runs gave carried=2, real is 6) and, for tracking, a registry cloned at the commit before the run (an empty one reports carried findings as gaps). Diff the kit's engine reports against the real ones of the same date: only timestamps may differ. Start the full `run_all` right after the coder's reply: it takes ~30 min and gates UNIT_TESTED.
- 2026-09-29 (TASK-065): when the root cause is unproved, make the first item a bite test on a `git archive HEAD` kit
  and gate the rest of the design on its result. It turned a "maybe" fix into proven scope in one coder round, and it
  showed that the reported case (a plain rc-10 resume) already worked.
- 2026-09-29 (TASK-067): pipe `req.py status` output through `grep -E "REQ-00NN:|ERROR"`, never `tail -1`: the
  tail hid a refused REQ move (DESIGN → UNIT_TESTED skip), so REQ and TASK drifted apart for one transition.
- 2026-09-29 (TASK-068): work done straight on a REQ (no TASK) cannot leave TODO: `task_gate.py` refuses a REQ with no
  linked task. Open the TASK first, even for small skill or doc work; a close-out later costs a full task cycle.
- 2026-09-29 (TASK-071): `commit-check.sh msg | tail -1 && git commit` commits even when the gate fails (tail exits 0). Redirect
  the gate to a file and chain on its own exit code. Also save real-run output under work/ at once: job tmp dirs are cleaned.
- 2026-09-30 (TASK-070): a helper built in one item and called from another (recheck_rows.py) passed its own tests while
  nothing called it; the tester's $0 run of the entry point alone found it. Brief the QA to run each entry point end to end
  before VERIFIED. Before a paid V-row, dry-run it: V5 needed a second scan no plan had (+$0.09, one extra user question).
- 2026-09-30 (TASK-072): tests that pin a literal list (protect_rules allow list) break on every approved widening and cost a
  full-suite rerun; assert the invariant (base kept, only `Bash(...)` added). Run the full suite once per item range, not per fix.
- 2026-09-30 (TASK-073): a V-row that needs `pipeline.sh run` cannot be run by a role (guard); write it as a test suite in
  the design (pipeline_rerun_e2e) instead of a manual kit run, which cost two extra round trips and a user question.
- 2026-10-01 (TASK-076): a failing container tool is usually an image fact (entrypoint, uid, file modes): `docker image inspect` + one stderr grep found semgrep 127, codeql 12 min and bearer rc=1 in one turn each.
- 2026-10-06 (TASK-081): after a real migration, run the $0 roll-up on the real data before UNIT_TESTED: it found unstamped run records and a misfiled product in one turn. Check a user-run write by its result (git log, file counts), never by "done"; save the user command output to a toolkit path (`tee work/<T>/x.log`). Never pipe `commit-check.sh` into `tail` in an `&&` chain: it hides the failure.
- 2026-10-07 TASK-082: three QA rounds went into a portable-key design the user then cut to a plain sha256 of the model's inputs; ask "what is the smallest version the user would accept" before a design with normalisation layers. A fake claude for real checks must answer `--help` with every flag scan_common.sh probes (copy tests/ai_reuse_pipeline_test.sh:47), else two wasted runs.
- 2026-10-07 TASK-083: "off = unchanged" and "AI report unchanged" proofs are cheapest as a `git archive <base>` kit vs HEAD and a `cp -a` copy of a real AI run with the tool on vs off, then `cmp`: both took one turn and $0, no fake claude needed. Run the evidence re-save in the background while the next proof is built. A `$S` unset in a redirect leaves stray files in the repo root (`.x`); check `git status` before saving evidence (it marks heads +dirty).
- 2026-10-07 TASK-085: parallel roles (Titan builds, Nemesis QA, Argus verifies) with real $0 checks in `git archive` scratch kits saved many turns; a background waiter using `pgrep -f <pattern>` matched its own command line and looped forever, so wait on a pid or file instead. Test flakes came from the test (history file, timing column), not the code: normalise the nondeterministic columns before calling a bug.
- 2026-10-07 TASK-086: before VERIFIED, re-run every suite that greps the changed script (`grep -l <script> tests/*_test.sh`), not only the set listed in the last evidence: it caught 5 stale QA cases and 3 suites broken a task earlier. A `git bisect run` in a `git clone` under $S found the breaking commit (753302e) in one background turn at $0; prefer it over guessing from logs.
- 2026-10-08 TASK-088: a suite that passes earlier and fails later at the same commit is a clock clue: print the classifier inputs at the failing hour before blaming the machine. A bare status-code regex (`401`) matched digits inside an epoch; pin such tests to fixed epochs. Run the whole repo serially once per task (127 suites, ~30 min in the background) so stale suites do not pile up between tasks.
- 2026-10-08 TASK-087: decide a paid A/B from the $0 bound first: a compare script plus a merged-hit delta per repo showed the effect (2 repos, ~30 hits) before any spend, so the $3-5 run was skipped. When a small QLScan run skips every repo, check the tree layout (`<ws>/<repo>`) before the tool; symlinks into a scratch root fixed it in one turn. Check whether the transition is already committed (`git log -1`, `git status`) before redoing it after compaction.
- 2026-10-08 TASK-077: when a default flips (PREFLIGHT 0 -> 1), grep every suite that reaches the gated entry points for the opt-out before the proof run; the host passes the new gate and hides the gaps (10 suites failed only in the clean container). Never run two containers at once during a full proof: load made a timing suite flake.
- 2026-10-08 TASK-089: judge a new http-out pattern by card-evidence precision (O6) before accepting it: QLScan sinks see only ssrf, so the py rows looked like +11 confirmed but were 8 % precise and would have re-carded 30 repos; one $0 join script decided it.
- 2026-10-08 TASK-091: lift a scratch script into tools/inspect the second time it is written; check the real-data numbers against the scratch numbers from the earlier task (7/15, 30/66) so the lift is proven with no new reading; a bite test must actually change what the guarded code prints (the first bite-2 edit missed its anchor and passed silently).
- 2026-10-08 (TASK-090): an external stash + rebase mid-task cost turns to merge; at resume check `git stash list` and diff each stash against HEAD (0 missing lines) before dropping it.
- 2026-10-08 TASK-094: check `protect.write_globs` vs the brief scope before launching the coder; grant the grantable globs up front and keep non-grantable paths (hooks, skills) for main — two coder rounds were lost to guard refusals.
- 2026-10-09 TASK-095: a scratch kit from `git archive HEAD` misses uncommitted fixes and a plan copy whose manifest moved to a new run gives empty results; commit wip before a scratch rebuild and pin the manifest run id, or the evidence tests old code.
- 2026-10-09 TASK-096: a state-format migration breaks every test fixture that copies the real `.claude`; re-run all suites right after migrating (and build fixtures without `.claude/state`), not only before.
- 2026-10-09 TASK-097: never pipe commit-check into `tail` in an `&&` chain (rc hidden, a failing commit went in); gate on its rc from a file. Trial a new agent role end to end before VERIFIED: the real lead runs found 6 bugs (F-97-1..6) that 162 unit cases missed.
- 2026-10-09 TASK-100: run every new auto-commit path live once before VERIFIED: fixtures never ran commit-check past IMPLEMENTING, so the missing `Tests:` trailer on the autohold commit showed only in the live trial (one rollback round).
- 2026-10-13 TASK-106: give the verifier the real-data run log and each AC proof as a saved file before the first verify brief; the first pass came back PARTIAL with 6 ACs NOT PROVEN that 4 cheap saved commands closed. A kit for a $0 real-data run must not hold an open run (pipeline.sh resumes it).
- 2026-10-13 (TASK-107): an "old vs new" golden must pin the base commit (`git show <sha>:f`), not HEAD: once the change is committed a HEAD compare silently skips (F-107-2). Prove "byte-identical on real data" by rendering the same inputs with both versions, not by comparing two runs (the run-to-run diff was 10 lines, the same-input diff 0).
