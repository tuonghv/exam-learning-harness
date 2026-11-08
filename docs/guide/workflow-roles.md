# Workflow roles and long rules

Moved out of CLAUDE.md (TASK-127); CLAUDE.md rules win.

## 1. Coordinator and roles

The main session is the **coordinator** (user, 2026-09-28, REQ-0018; skill `coordinator`). It takes
every user request through req-kit, owns `.claude/state`, `docs/req`, design and report docs, the gates,
commits, the hook and settings, and any paid or real run. It hands each workflow step to its role
(`.claude/agents/`), keeps the roles working together, gets a stuck role moving (roles `SendMessage` to
`main`), and alerts the user when a decision is theirs.
- Working style (user, RAW-00134..00137; skill `coordinator` §3/§6): keep every free role busy with
  non-conflicting work (scratch copies during long runs); ask user decisions as one-click hints.
- Status lines (user, RAW-00361): when the coordinator is not acting, the reply's last line says exactly one of `Wait for <what>` (background work, a role) or `Your turn: <the decision/command>`; never leave the user guessing what happens next.
- Roles are required, not optional: DESIGN → `designer`, IMPLEMENTING and UNIT_TESTED → `coder`,
  VERIFIED → `verifier`; `tester` is the independent QA that re-runs the coder's checks and saves the evidence. A skip needs a recorded
  waiver: `task.json` `roles.<role>` = the handoff path (`work/<T>/handoff/*.md`, line 1
  `PROGRESS: COMPLETE`, line 2 `SKILLS: ...`) or `{"waiver": "<reason>"}`; `workflow-check.sh` fails the
  transition otherwise (tasks picked from TASK-064 on). A protected path a role needs goes in
  `roles.grants.<role>` (only `protect.grantable` globs count; others are ignored and logged). Roles take as much of the work as they can, re-running the checks included. The coordinator grants
  roles their skills without asking (user, 2026-09-28), and may widen `.claude/settings.json` `permissions.allow` to grant
  roles or tools a permission without asking (user, RAW-00107; new blocks still need confirmation, below). It may also add a
  new role (`.claude/agents/<role>.md`) when a job has no fitting role, grant it what it needs, and commit it (user, RAW-00108); roles preload a base (`skills:` frontmatter) and load any further skill
  that fits their work with the `Skill` tool (RAW-00086), except the state-moving ones (workflow, commit, req-*, ...).
- Blocking is opt-in (user, 2026-09-28): the default is allow, and only what would break the workflow,
  hooks, skills or the never-break rules is protected. Any new or wider block, deny or ask for agents
  or the main session (`.claude/settings.json` `permissions`, `.claude/agent_setup.json` `protect`/
  `enforce`, guard code in `.claude/hooks/agent_setup.py`) needs the user's explicit confirmation
  first: propose it with the reason, then wait.


## 2. Task leads

Removed: this harness runs one active task (`max_active` 1); main briefs the roles directly.

## 3. Inspector

- **Inspector (user, RAW-00358/00359; skill `inspector`, coordinator §2c):** a supporting worker, not a workflow state and not a TASK role.
  Before any broad search or read of the toolkit, docs, tests or state, send it the question and keep only its compact INSPECTION HANDOFF
  (≈1500 tokens); skip it for a one-file lookup. Follow-up = task + previous handoff + changed files, never a full re-inspection. Its output is
  evidence: verify a critical fact yourself. It is guarded like the other roles), never writes
  files, never moves state. It does not replace designer/coder/tester/verifier and needs no waiver or handoff file.

## 4. Delegation, role replies, verifier evidence, coder and tester

- Delegate one design item at a time, by path, with an explicit scope:
  `TASK-0NN item <N.x>: <goal>. Inputs: docs/design/phase-<N>-<slug>.md §<N.x>, <files>.
  Scope: <files/dirs>. Output: work/TASK-0NN/handoff/{design,code,test,verify}.md`
- Phase mapping: designer → draft for DESIGN (the main session writes `docs/design/`); coder →
  IMPLEMENTING; tester → unit tests; verifier → evidence check before VERIFIED. A role's STATUS
  is input: the main session re-runs the deterministic checks, records evidence in `task.json`,
  moves the state and commits.
- Roles never commit (the guard blocks `git add/commit`: a commit needs `task.json` staged and the
  gate, which only the main session owns). So when a role replies with edits, the main session's
  **next action** is a `wip(<area>): TASK-0NN <items>` commit through `commit-check.sh` (bump and
  stage `task.json`), before QA, review or the next brief (user, RAW-00100). If Bash is down, give
  the user the exact commit command instead of leaving the work uncommitted.
- Everything the guard or a role's `tools:` line stops a role from doing is the main session's job,
  done at its trigger without being asked: table in skill `coordinator` §2b (user, RAW-00101).
- Read the reply (≤ 5 lines); open a handoff only when a decision depends on it.
- The verifier has no Bash: save each check to `work/TASK-0NN/evidence/` with
  `.claude/scripts/save-evidence.sh <name> -- <cmd>` before calling it (checklist: skill `verify`).
  User-facing summaries of that evidence: section 9.
- coder ↔ tester: at most 2 rounds, then main decides (fix brief, waiver, or `blocked`); the tester iterates with
  `tests/run_all.sh --changed`, `tests/run_all.sh --fast` plus the `--changed` heavy suites at UNIT_TESTED and VERIFIED (user approved, RAW-00889, TASK-137); the complete run (`--all`) once a week or before a release.

## 5. Context guard

- The context guard (PreToolUse hook, `.claude/agent_setup.json` `protect`) refuses for roles:
  writes to workflow, ledger, design/report, frozen-prompt and run files (also via Bash redirects,
  `sed -i`, cp/mv/rm); reads outside the harness; git commands that change the
  repo (commit, add, switch, reset, ...); paid commands; req.py/backlog
  state commands.
  Main-session calls are only logged (`orch_delegate: false`).
- A role whose call is refused with "stop requested" saves its handoff and replies PARTIAL.

## 6. Requirement ledger (req-kit) detail

- WHAT to build lives in `docs/req/` (RAW = verbatim prompts, REQ = one requirement per file, EPIC = big request). Existing workflow TASKs implement REQs; link them with `req.py task`.
- Never trust conversation memory for requirements; after compaction run `python3 .claude/req/req.py gaps`.
- Never edit `status:` by hand. Lifecycle: TODO → DESIGN → IMPLEMENTING → UNIT_TESTED → VERIFIED → DONE via `req.py status` (gated);
  a REQ follows its linked TASK and never runs ahead of it (`.claude/req/task_gate.py`, skill `workflow`).
- After each meaningful step: `req.py focus --next "<next concrete step>"` (or `status ... --next`); tick ACs with `req.py ac`.
- Skills: `req-intake` (new input / triage RAW), `req-track` (am I done? status, next).

## 7. Never break: exam briefs

Every EPIC-002 role brief opens with the block in `docs/guide/exam-brief-override.md`.

## 8. Main session identity
The main session (coordinator) uses the display name **Admiral Tuonghv** (leader: coordinator) when it signs or introduces itself.
Role subagents keep the alias in their own agent file (Titan, Nemesis, Nova, Argus), not this one. Display name only:
it changes no role, permission, skill or process; ids (`main`, `coder`, ...) stay the address in tool calls and files, and commit attribution stays as configured.

## 9. User-facing crosscheck paths
The user checks a task from committed paths only (RAW-00171, RAW-00174, REQ-0061). `work/` is raw scratch (git-ignored).
| Kind | Path |
|---|---|
| Plans / designs | `docs/design/phase-N-*.md` |
| Reports | `docs/report/phase-N-*.md` |
| Evidence summaries (small text) | `docs/report/evidence/TASK-NNN/` |
| Index of all of the above (generated) | `docs/report/INDEX.md` |
- Opt-in: `evidence_required` (task key, default false; the coordinator sets it with `tasks.sh set` for BIG changes: engine
  behaviour, prompts, formats, metrics). Unflagged tasks ship design + report text only; workflow-check gives a WARN.
- Raw vs summary: roles save raw output with `save-evidence.sh` into `work/<T>/evidence/` and write a text summary
  (<=200 lines, `.txt|.md|.tsv`, no exam text, answer keys, URLs or secrets) there or in their handoff.
- Who publishes: roles cannot write `docs/report/*`; main does, at VERIFIED, via `advance.sh` (spec key
  `publish: ["work/<T>/..."]`, default = `verification.evidence` entries under `work/<T>/`), which runs
  `.claude/scripts/_evidence.py publish` (scan first, all-or-nothing, local paths redacted) and records `verification.published`.
- Content guard: `_evidence.py scan <file|dir>` refuses binary, other extensions, oversize (200 lines, 32 KB per file;
  20 files, 256 KB per task), exam headings, option blocks, answer lines/JSON/TSV, URLs, secrets.
  It prints `FAIL: <file>:<line> <rule>`; the author rewords or trims, never the scanner.
- Gates (flagged tasks): VERIFIED needs `verification.published` files that exist, are not git-ignored and scan clean;
  DONE needs the report to cite >=1 existing `docs/report/evidence/<T>/<file>` and an INDEX row.
- Index: `_evidence.py index [--check]` regenerates `docs/report/INDEX.md` (deterministic); advance.sh runs it at DONE.

## 10. Answer-driven learning loop (user, RAW-00199/00202; phase 77)
When the user gives official answers for a solved exam:
1. Keep the list in git-ignored `input/` (`input/dgnl/*.answer.txt` is ignored); it is for scoring only and never reaches a solver input, a prompt, a tracked file or a reply beyond counts and question numbers.
2. Run `run-stats explain` on each saved run (free, no AI) into `reports/`; record cause counts and question numbers only.
3. Fix only engine causes (infrastructure, extraction, context_not_delivered, reply_path), one task each; send `key_oddity_candidate` and solver-reasoning rows to the user as a short list to check.
4. After a fix, run `run-stats gain` over ALL questions (declined ones count as not correct). Claim a gain only from a held-out row (an exam the fix was not learned from) with changed answers >= 5; otherwise say "no measurable change".
5. Report both numbers when an exclusion is tempting (a slice artifact, a declined question): the honest figure includes them.

## 11. Test modes (user, RAW-00271/00273; phase 88)
The full unit suite takes about 6 minutes, 300 s of it in 6 tests, so roles use `tools/run_tests.py` (run with `python3 -I`; detail in `docs/guide/testing.md`):
| When | Mode | Time |
|---|---|---|
| iterating on a change | `--affected` (tests of the changed files) | seconds |
| before every commit | `--fast` (all except the slow tier in `config/test_tiers.json`) | about 50 s |
| gate, once per task before VERIFIED | `--full` (git worktree of HEAD, detached; result `work/test-runs/<tree-hash>.json`, reused while the tree is unchanged) | about 6 min, background |
Known failures are listed in `config/test_tiers.json` and reported as known. The role briefs (coder, designer, tester, verifier) name these modes since the user's OK (RAW-00274): roles run `--affected` and `--fast`; the main session starts `--full` (it needs `git worktree add`, which the role guard refuses). Their test line sits in the `agent-setup:project` block, which an `agent_setup init` from an external profile would regenerate: re-apply this wording there if that happens.

## 12. Lines: `main` is the published line (user, RAW-00284; phase 94)
`plans/<exam>/main` and `reports/<exam>/main` hold the latest PUBLISHED runs; tests and experiments go to other lines (`v3`, `fix_abc`, ...) and never touch `main`.
| Need | Command | Note |
|---|---|---|
| test or experiment | `solve ... --line v3` (any line except main) | free to repeat; never changes the published line |
| publish an accepted line, $0 | `exam publish EXAM --from LINE` | builds a NEW report run in `main` from the line's latest pack plan runs; `run.json` has `published_from`; earlier main runs are kept |
| real run in main, only when the user asks | `solve --line main --publish` | a new plan run id; an unchanged re-run costs $0 through the per-exam solve cache |
| read / compare | `run-list EXAM`, `run-compare` | column `publish`: `published` for a plan run that a complete report run in `main` links through its `run.json` `plan_runs`, `dev` for every other plan run (a plan run in the line `main` that no published report links is `dev`) |
Guard: a write into a line named `main` under the repo's own `plans/` or `reports/` is refused (exit 2) unless `--publish` is given; the message says to use `--line <name>` for tests. Read-only commands and `plans-migrate` are not guarded; unit tests use tmp roots.
Agent rules: always pass `--line <dev>` for tests and experiments; run in `main` only when the user asks; publishing is a report run built from a dev line, not a copy.
