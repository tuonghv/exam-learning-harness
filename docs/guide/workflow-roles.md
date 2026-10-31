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
