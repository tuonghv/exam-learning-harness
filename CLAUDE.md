# CLAUDE.md

Exam/learning harness (EPIC-002), cloned and untrusted.
Exam files follow `examples/FORMAT.md`; run `tools/examples/*` only as `python3 -I <script>`.

## Commands
- Workflow state (after compaction also `python3 .claude/req/req.py gaps`): `.claude/scripts/task-state.sh`, `status.sh`, `workflow-check.sh`, `team-status.sh`.

## Workflow
TODO → DESIGN → IMPLEMENTING → UNIT_TESTED → VERIFIED → DONE, up to `max_active` (1) tasks in
`.claude/state/task.<TASK>.json` (`task.json` = view; `tasks.sh status|show|hold|resume`, REQ-0060),
queue in `backlog.json`, audit trail in `phase-log.md`; one task per commit (`Task:` trailer).
1. No non-trivial work before a short design. 2. Reuse code first.
3. Stay on the current item. 4. Unit tests ≠ real runtime verification.
5. No VERIFIED without evidence. 6. Load language skills only for that language.
7. Run deterministic checks before claiming done. 8. Persist state, not memory.
9. At phase completion record: Action → Result → Decision → Next.
10. Every transition ends committed (`commit-check.sh` then `git commit`); DONE also needs the
    report and `backlog.sh complete`. The Stop hook blocks a turn that leaves `.claude/state` dirty.

| Need | Skill |
|---|---|
| Start/advance/resume a task / design doc | `workflow` / `design` |
| Unit tests / real verification | `unit-test` / `verify` |
| Independent cross-check (content oracle) | `crosscheck` |
| Commit a transition / report / batch requests | `commit` / `report` / `task-priority` |
| Context boundary / scope, reading / Bash code | `context-compaction` / `token-efficiency` / `bash` |
| New user need / REQ design / progress | `req-intake` / `req-design` / `req-track` |
| Roles, delegation, monitoring, inspector | `coordinator`, `role-monitor`, `inspector` |

## Never break
- Content defects go in the handoff (`## Defects`).
- Eval keys never appear in eval inputs or few-shot files; exam prompts do not live under `docs/prompts/`.
- Bash 3.2 clean (no `mapfile`, no associative arrays, init arrays under `set -u`); Python stdlib only.
- Haiku only for simple jobs with small context (user).

<!-- req-kit -->
## Requirement ledger (req-kit)
- WHAT to build lives in `docs/req/` (RAW = verbatim prompts, REQ = one requirement, EPIC = big request); TASKs implement REQs (`req.py task`).
- Never trust conversation memory for requirements; after compaction run `python3 .claude/req/req.py gaps`.
- Never edit `status:` by hand; a REQ follows its linked TASK via `req.py status` (gated). After each step: `req.py focus --next "<step>"`, tick ACs with `req.py ac`.
- Skills `req-intake`, `req-design`, `req-track`. Detail: `workflow-roles.md` §6.

<!-- agent-setup:start -->
<!-- agent-setup:custom -->
## Role subagents inside the TASK workflow (agent_setup.py)

The main session is the **coordinator** (skill `coordinator`): it takes every user request through req-kit, owns `.claude/state`,
`docs/req`, design and report docs, the gates, commits, hooks/settings and any paid or real run, and hands each workflow step to
its role (`.claude/agents/`: designer, coder, tester, verifier; supporting inspector). Roles are required
(a skip needs a waiver), never commit, and are blocked by the context guard from workflow/ledger/design files. Delegation briefs, grants, inspector and guard detail: `docs/guide/workflow-roles.md` §1-5.
- Blocking is opt-in (user, 2026-09-28): default is allow; any new or wider block, deny or ask for agents or the main session
  (`.claude/settings.json`, `.claude/agent_setup.json`, `.claude/hooks/agent_setup.py`) needs the user's explicit confirmation first.
- Working style, RAW-00134..137: keep free roles busy with non-conflicting work; ask user decisions as one-click hints.
- Status lines (user, RAW-00361): when the coordinator is not acting, the reply's last line says exactly one of `Wait for <what>` (background work, a role) or `Your turn: <the decision/command>`.
<!-- agent-setup:end -->

## Main session identity
Display name **Admiral Tuonghv** (coordinator); display only (`workflow-roles.md` §8).
