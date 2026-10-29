# CLAUDE.md

This is a **toolkit**, not a scan target — never scan this folder. It drives `claude -p`
headlessly over ~80 repos under `REPOS_ROOT` (`config.sh`), one repo per call, tracks progress
in a per-plan `manifest.json` (`plans/<sys>/<plan>/`, picked with `PLAN=<sys>/<plan>`), and
aggregates that plan's `results/*.json` into Markdown + PDF reports. Bash + `jq`.

**Full reference (commands, architecture, invariants, where changes go, testing):
`docs/guide/toolkit-reference.md` — read the relevant section before changing code.**
Operating a review: `docs/guide/security-review-runbook.md` / skill `run-security-review`.
Roles, leads, inspector, guard, delegation, identity and the long rule texts: `docs/guide/workflow-roles.md`.

## Commands
- Unit tests: `tests/run_all.sh [filter]` (slow suites sleep; filter while iterating). Static: `.claude/scripts/checks/shell.sh`.
- Real verify: scratch kit + fake `claude` — reference "Testing a change", skill `verify`.
- Workflow state: `.claude/scripts/task-state.sh`, `status.sh`, `workflow-check.sh`.
- Multi-repo pipeline: `./pipeline.sh run|new|status` (`--track A|B`, `--run`), unattended via
  `AUTO_DRIVER=pipeline ./auto_scan.sh`; flow, steps and flags: `docs/guide/architecture.md`, reference "Multi-repo pipeline".
  `--track A` = deploy, recon, extpre, phase1 + PRELIMINARY report; `--track B` = the rest; no flag = all (REQ-0068). Phase1 store key = prompt + tree + model only.
- No finding lost ($0): `python3 coverage_check.py <run_dir> --conclusion`; `check_deliverables.sh --run latest` D10.
- Report QA gate ($0, last step of `summarize_report.sh`): `python3 report_qa.py <report.md> --manifest <m> (--results <dir> | --run <run_dir>)`;
  on FAIL fix the generator, never the data (skill `pentest-report-qa`).
- Stable ids ($0, auto after each complete run, `TRACK_AFTER_RUN=0` = off): `./tracking/track.sh --run latest|--baseline`; `docs/finding-identity.md`.
- Open-source tools (set B): on by default (`EXT_SCAN=1`); `./plan.sh new <sys>/<plan> <root> --tools-only` (`REVIEW_AI=0`) = 0 `claude` calls. Skill `ext-scan`.

## Workflow
TODO → DESIGN → IMPLEMENTING → UNIT_TESTED → VERIFIED → DONE, up to `max_active` (1) tasks in
`.claude/state/task.<TASK>.json` (`task.json` = view; `tasks.sh status|show|hold|resume`, REQ-0060),
queue in `backlog.json`, audit trail in `phase-log.md`; one task per commit (`Task:` trailer).
1. Do not implement non-trivial work before a short design. 2. Reuse existing code first.
3. Stay on the current TODO item. 4. Unit tests ≠ real runtime verification.
5. No VERIFIED without evidence. 6. Load language skills only for that language.
7. Run deterministic checks before claiming completion. 8. Persist state, not memory.
9. At phase completion record: Action → Result → Decision → Next.
10. Every transition ends committed (`commit-check.sh` then `git commit`); DONE also needs the
    report and `backlog.sh complete`. The Stop hook blocks a turn that leaves `.claude/state` dirty.

| Need | Skill |
|---|---|
| Start/advance/resume/block a task (`/next`, `/design-phase`, `/verify-phase`) | `workflow` |
| Design doc (`docs/design/phase-<N>-<slug>.md`) | `design` |
| Unit tests / real verification / security pass | `unit-test` / `verify` / `security` |
| Independent cross-check of counts/decisions | `crosscheck` |
| Commit a transition / report at DONE | `commit` / `report` |
| Many requests: summarise, order, batch | `task-priority` |
| Context boundary, /clear, /compact | `context-compaction` |
| Scope, reading, approvals | `token-efficiency` |
| Bash code | `bash` |
| External tools (set B) | `ext-scan` |
| New user need / REQ design / REQ progress | `req-intake` / `req-design` / `req-track` |
| Roles, leads, inspector, guard, delegation | `coordinator`, `docs/guide/workflow-roles.md` |

## Never break
- One repo per fresh `claude -p` process; never multi-repo sessions. Exception: a 2b unit mounts only its item's two repos
  (`--add-dir`, `--restricted`, empty cwd), never the whole `REPOS_ROOT`.
- Toolkit dir and `REPOS_ROOT` are separate; repo source is read only inside `scan_batch.sh`'s subshell (the exceptions —
  `tree_evidence.py`, `ext_scan.sh`, `ext_snippet.py` — and their limits: `workflow-roles.md` §7). Agents never modify a
  plan's `REPOS_ROOT` and only list names/paths there, never file contents, unless `./plan.sh kind <sys>/<plan>` prints `demo`
  (notes to `docs/notes/demo-<plan>-<date>.md`). Agents keep findings exactly as written (no add/drop/re-rate/`status`).
  Tree problems: tell the user in the reply (paths, counts); never fix the tree or write notes for the team that prepares it.
- Scope is this toolkit and its scan engine (user, 2026-09-27): never design, propose or depend on other teams' or tools' work.
- The JSON schema at the end of `security_prompt.md` is load-bearing; changing a category, severity or `stats` key touches every file listed in the reference, invariant 3.
- Each plan's `manifest.json` is its only progress tracker; only `scan_batch.sh` writes repo status
  (`auto_scan.sh` never does); only `pipeline.sh` writes `.pipeline` (never `.repos`). Repo key is `(workspace, repo_name)`.
- Never run two `scan_batch.sh` at once (`.scan.lock`). Stop on auth/rate_limit/service failures.
- Scheduler waits for Claude's *reported* reset time (`detect_reset_at()`), not a constant.
- `X-User-Id` is gateway-set and trusted — not a finding; ownership checks still are.
  Edit `security_prompt.md` and `.claude/skills/api-platform-security` together.
- Model prompts are frozen (user, 2026-09-25): `security_prompt.md`, `docs/prompts/phase0-*.md` and `phase2b-*.md` do not
  change for a new feature or a bug fix; work in the deterministic layer (overlay, correlate.py, report scripts). Only exception:
  a prompt output that cannot be mapped to findings/results, and only after a no-cost stdlib script (like `correlate.py`) failed to map it.
- Every scan finding reaches the reports unchanged: overlay/conclude/report changes keep `coverage_check` at `gaps=0` with the
  real run's counts (skill `verify`). Never edit run files or `conclusion.json` to make it pass.
- Two plan modes, one behaviour: every design states its impact on single-source (no flag) and pipeline (`--run`) plans
  (`## Plan modes`, gated from phase 47); one source per mode, one renderer.
- Bash 3.2 clean (macOS): no `mapfile`, no associative arrays, init arrays under `set -u`.
- Haiku only for simple jobs with small, simple context (user, 2026-09-27). Never for reading repos or other complex work (TASK-039 closed).
- Scan model (user, 2026-10-18): Sonnet 5.5 is kept for cost; Sonnet 5 / Opus 5.5 find more, accepted trade-off. `docs/notes/scan-model-choice-2026-10-18.md`.
- Phase 0 cost tuning is closed (2026-09-27): defaults = Sonnet + recon + compact, ~$0.70/repo. Read `docs/notes/phase0-tried-options.md` before proposing any phase 0 change; do not re-run a listed option unless its reopen condition holds.

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
its role (`.claude/agents/`: designer, coder, tester, verifier; supporting inspector; leads only when 2 tasks run). Roles are required
(a skip needs a recorded waiver), never commit, and are blocked by the context guard from workflow/ledger/design/frozen-prompt/run
files, source trees and `$REPOS_ROOT`. Delegation briefs, grants, leads, inspector and guard detail: `docs/guide/workflow-roles.md` §1-5.
- Blocking is opt-in (user, 2026-09-28): default is allow; any new or wider block, deny or ask for agents or the main session
  (`.claude/settings.json` `permissions`, `.claude/agent_setup.json` `protect`/`enforce`, `.claude/hooks/agent_setup.py`) needs the user's explicit confirmation first.
- Working style (user, RAW-00134..00137): keep free roles busy with non-conflicting work; ask user decisions as one-click hints.
- Status lines (user, RAW-00361): when the coordinator is not acting, the reply's last line says exactly one of `Wait for <what>` (background work, a role) or `Your turn: <the decision/command>`; never leave the user guessing what happens next.
<!-- agent-setup:end -->

## Main session identity
Display name **Admiral Tuonghv** (leader: coordinator); display only, changes no role, permission or process. Detail: `workflow-roles.md` §8.
