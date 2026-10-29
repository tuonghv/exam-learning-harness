# Phase 2 — Harness exam fit

Task: TASK-001 · REQ-0005 · Status: draft r3 (Nova, designer, 2026-10-29; r2 adds Q6 A+B+C = AC8-AC10 and AC11; r3 adds AC12)

## Goal
Roles briefed for EPIC-002 exam-content work get exam rules (one override block), check content with an
independent exam-content oracle, and see no scan text and no pointer to a removed skill or role. CLAUDE.md is rewritten
to the exam purpose (<= 4 KB), orphan files are deleted, and kept skills shrink by >= 30 %, with role management and
monitoring intact. Done when AC1-AC12 of REQ-0005 hold (the greps and `git diff` below).

## Constraints
- Q1: override block + small skill edits. Q6 (A+B+C) supersedes Q4 for CLAUDE.md, role bodies, skills, commands and
  docs/guide; Q4 still holds for the `agent_setup.json` dead entries (D: not done).
- AC11 (user): no edit or deletion of `.claude/agent_setup.json`, `.claude/hooks/agent_setup.py` or
  `.claude/tests/agent_setup_hook_test.sh`, not even pointer fixes. Dangling pointers inside them are tolerated.
- AC12 (user): keep skills `coordinator`, `role-monitor`, `inspector`, `task-priority` and scripts `team-status.sh`,
  `watch-role.sh`, `brief.sh`. Compress their wording, but never cut a role-management or monitoring rule
  (briefing, delegation, handoff/PROGRESS checks, stuck-role steps, watcher events, team-status block, message budget).
- `.claude/settings.json` is the coordinator's (its dead `ask` rules are already removed; not planned here). `.claude/hooks/*`
  stays unchanged. Agents: text strips only (2.8) + deleting `lead.md`.
- CLAUDE.md keeps its markers `<!-- req-kit -->` (:81) and `<!-- agent-setup:start|custom|end -->` (:88-101), which
  `agent_setup.py:252` uses to find its block. Agent bodies keep `<!-- agent-setup:project:start|end -->` (`agent_setup.py:127,281`;
  only rewritten by an explicit `init --profile`, so manual edits are safe).
- Every kept `SKILL.md` keeps its frontmatter `name` + `description`. Bash/Python sources: no behaviour change.

## Known incidents
None (this harness has no `docs/notes/incidents.md`).

## Plan modes
| Mode | Impact | Verified by |
|---|---|---|
| single-source (`scan_batch.sh`, no flag) | n/a: script is absent from this harness (Glob found no `scan_batch.sh` or `pipeline.sh`) | — |
| pipeline (`pipeline.sh`, `--run`) | n/a: same reason; this task edits docs and skills and deletes orphans only | — |

## Implementation steps (3 coder steps, each closed by its grep check)
| Step | Items | Check (must hold before the next step) |
|---|---|---|
| A | 2.7 CLAUDE.md rewrite | `wc -c CLAUDE.md` <= 4096; `grep -ciE 'api-platform\|pentest\|REPOS_ROOT\|findings\.jsonl\|ext-scan\|run-pipeline\|scan_batch\|pipeline\.sh\|report_qa' CLAUDE.md` = 0; `grep -c 'agent-setup:\|req-kit' CLAUDE.md` = 4 |
| B | 2.2-2.6, 2.8 (override doc, oracle, Tier-1 note, compression, pointers, strip list) | V-B1 (AC9) = 0; 2.5a/2.5b; 2.6a; V-12 |
| C | 2.9 deletions | each 2.9 row's dangling grep is empty; `test ! -e` for each path |

## Design

### 2.1 Audit fix list (AC1; each row checked by reading the line on 2026-10-29)
| # | file:line | finding | impact | fix |
|---|---|---|---|---|
| 1 | agents/{coder:125, designer:109, tester:136, verifier:39,113} | "append each security issue … findings.jsonl" | MISLEADS | strip (2.8) |
| 2 | agents/{coder:98-103, designer:81-86, tester:109-114, verifier:86-91} | skill examples name `pentest-report-qa`, `api-platform-security`, `security`, `run-security-review` | MISLEADS | examples become `report`, `python`, `crosscheck`; drop `run-security-review` |
| 3 | agents/designer:72-73, tester:99 | load `security` / `api-platform-security` / `ext-scan` | MISLEADS | replaced with the project block / deleted (2.8) |
| 4 | agents/{coder:91, designer:74, tester:89, verifier:80, inspector:141} | `L:` lessons line, "Only the skill-curator edits" | MISLEADS | delete the line (lessons.py deleted in 2.9) |
| 5 | agents/lead.md | role removed by Q2 | MISLEADS | delete file |
| 6 | commands/design-phase:7-8 | `api-platform-security`, `security` | MISLEADS | drop both clauses |
| 7 | commands/next:11,13 | same | MISLEADS | drop `(+ api-platform-security …)`; replace `security` with `crosscheck` |
| 8 | commands/verify-phase:2,7,12 | "security pass", loads `security`, `security.*` | MISLEADS | :2 "real verification (exam oracle)"; :7 `crosscheck`; :12 keep (`security` is a task.json field) |
| 9 | skills/coordinator:105-117,132,137-138,156,159-171,215,227,297,314,332,362 | removed skills, skill-curator, lessons, §2d leads, scan/REPOS_ROOT/paid-run rows | MISLEADS | removed by 2.5/2.8; :207,310 (`scratch-kit.sh` as a helper) keep |
| 10 | skills/token-efficiency:21,219 | `api-platform-security`, `pentest-report-qa` | MISLEADS | removed in 2.5 (line 34 `security` is a task.json field: keep) |
| 11 | skills/workflow:76,79,106 | `api-platform-security`, `security`, `lessons.py collect` | MISLEADS | drop the clauses; `security` -> `crosscheck` (line 42 is a task.json field: keep) |
| 12 | skills/workflow/references/tasks.md:14 | skill-curator/lessons step | MISLEADS | delete the sentence |
| 13 | skills/workflow/references/resume-and-failure.md:15 | `tasks.sh lead` | MISLEADS | delete the lead clause |
| 14 | skills/inspector:76 | `run-security-review/references/…` | MISLEADS | delete the line |
| 15 | skills/role-monitor:12-17 + scripts/watch-role.sh:3 | Monitor recipe while the Monitor tool is disabled (RAW-00160) | MISLEADS | left as is (AC12: monitoring rules kept; :12 already says what to do when Monitor is absent) |
| 16 | scripts/checks/skill_layout.allow:3,6,11 | rows for removed skills | COSMETIC | delete the rows; ratchet rows 4,5,7-10 to the new sizes |
| 17 | scripts/brief.sh:41 | default checks = missing `tests/run_all.sh --changed` | MISLEADS | left as is (AC12 keeps brief.sh); coordinator passes `--checks` (flag at :17) |
| 18 | scripts/brief.sh:76,85 | frozen scan prompts in FORBID; `run-security-review` in the state-moving list | COSMETIC | left as is (AC12) |
| 19 | scripts/commit-check.sh:114 | staged `docs/prompts/*.md` fails without `Prompt-change:` | BLOCKS if exam prompts go there | left as is; override rule 7 |
| 20 | scripts/lessons.py (+ its tests and ledger) | serves only the removed skill-curator flow | COSMETIC | delete (2.9) |
| 21 | scripts/team-status.sh | named in the brief; grep finds no removed pointer | — | left as is (claim not confirmed; AC12) |
| 22 | .claude/tests/agent_setup_hook_test.sh:363-375 | skill-curator guard cases | COSMETIC | left as is (user, AC11) |
| 23 | .claude/hooks/agent_setup.py (lead code :521-1527, `lessons` cmd :1985) | dead lead/lessons code | COSMETIC | left as is (user, AC11) |
| 24 | agent_setup.json:44-55,88-90,96-141 | lead/skill-curator configs, protect.roles, scan `bash_deny`; write_globs miss `examples/` `evals/` `tools/examples/` | COSMETIC (`enforce: []`) | left as is (user, AC11; Q4/D) |
| 25 | settings.json:19-39 | `ask` rules for absent `claude -p` and scan/pipeline scripts | COSMETIC | already removed by the coordinator; not planned here |
| 26 | CLAUDE.md (whole) | scan toolkit text, removed-skill pointers (:10,22,24,42,49,68) | MISLEADS | rewrite (2.7) |
| 27 | docs/guide/workflow-roles.md:32-41,48,76-79,93-124 | leads, REPOS_ROOT, scan guard text, scan rules 2 and 9 | MISLEADS | strip (2.8) |
| 28 | .gitignore:24-29,35-38,46 | inbox-triage / tools/triage / ext-scan rules | COSMETIC | delete 24-29 and 35-38 with tools/triage (2.9); keep :31-33 (`settings.local.json`); :46 left as is |
| 29 | docs/templates/sample-state/** | historical state copies name deleted files | COSMETIC | left as is (history, not live references) |

### 2.2 `docs/guide/exam-brief-override.md` (AC2; new file, ~25 lines)
One fenced block that the coordinator pastes as the first lines of every EPIC-002 brief, followed by 3 lines explaining why:
1. Domain: exam/learning content (Maths, Physics, English, Literature); `examples/FORMAT.md` is the input/output standard (Q3).
2. Ignore any leftover scan, frozen-prompt or security-severity text in role bodies and skills.
3. Do not run `.claude/scripts/*`, `tests/*`, `req.py`, a scratch kit, `claude -p` or network tools.
4. Run only `tools/examples/*` with `python3 -I`; everything outside the brief's write list is read-only.
5. Write only the files the brief names, plus your handoff.
6. Content defects (wrong key, unit or quote) go in the handoff under `## Defects`.
7. Never put exam prompts under `docs/prompts/` (commit-check.sh:114 freezes that path).
8. Verify with skill `crosscheck` §Exam content oracle (Tier 1).
(No literal `findings.jsonl` / `REPOS_ROOT` in this file: AC9 greps docs/guide.)

### 2.3 crosscheck "Exam content oracle" (AC3a; owner `.claude/skills/crosscheck/SKILL.md`)
Add a new `## Exam content oracle` section (~20 lines) after `## Output` (:42). Each check runs without the generator's code:
- Maths/Physics: recompute every key from the item text (stdlib `python3 -I -c`, `fractions`/`decimal`); compare the value,
  the unit (SI, as stated) and the rounding (the item's stated places or sig figs).
- English: re-apply the named grammar/vocabulary rule to each option; exactly one option may pass.
- Literature: every quote is a verbatim substring of the passage (`grep -F`), and its attribution matches.
- Leakage: no eval key string appears in the eval inputs or few-shot files (`grep -F -f keys inputs`); empty output = PASS.
- Output: the existing TSV mismatch format (:42-48), one row per item; any row = FAIL.
In the same edit, drop the scan recipes at :29-41 (SARIF/gosec/bandit) and the scan report cross-check at :49+ (REQ-0058).

### 2.4 verify Tier-1 note (AC3b; owner `.claude/skills/verify/SKILL.md`, tier table at :41-46)
Add one line under the tier table: "Content tasks (EPIC-002): the crosscheck exam oracle run is Tier 1 and is the evidence;
Tiers 2-3 are N/A (no scratch kit, no `claude` call)." Also drop :21 (scratch `REPOS_ROOT` line).

### 2.5 Compression (AC7 + AC12; baseline 2,066 lines, target <= 1,446; Grep count today = 2,122)
Remove scan, pipeline, report-QA, REPOS_ROOT, paid-run, lead, lessons/skill-curator text and the dated TASK-0xx scan lessons;
keep the generic rules. AC12 skills (marked *) lose only that text plus wordiness: every role-management or monitoring rule stays.
| skill | now | max | cut |
|---|---|---|---|
| coordinator * | 363 | 220 | §2d leads 159-171; lessons/curator 115-117; guard-table rows 132,137,138; 156,215,227,297,314,332,362; keep §2-§5 rules (brief, delegate, cover, keep busy, talk, unstick) |
| token-efficiency | 264 | 75 | "Going faster" scan lessons (keep <= 8 generic lines); :21, :219 |
| design | 228 | 95 | failure economics, CLI-string mining, Analyze/propose cost tuning, scan "Plan modes" (one optional line) |
| verify | 176 | 80 | :21, pipeline resume §66-97, scan Tier-2/3 detail; adds the 2.4 line |
| workflow | 137 | 110 | :76,79,106 and scan-specific notes |
| bash | 118 | 75 | scan_batch/manifest examples |
| commit | 106 | 80 | prompt-freeze and scan trailer prose |
| context-compaction | 80 | 60 | scan-run hand-off text |
| inspector * | 76 | 65 | :76, pipeline/plan lines only |
| role-monitor * | 75 | 70 | wording only (Arm, Events, Team-status block, Root-cause checklist, Token rules all kept) |
| task-priority * | 70 | 65 | scan examples only |
| python | 61 | 50 | scan helper names |
| unit-test | 56 | 50 | fake-claude fixture text |
| crosscheck | 56 | 80 | adds 2.3, drops scan recipes and the scan report cross-check |
| req-intake, req-track, req-design, report, coding | 74, 55, 52, 46, 29 | unchanged | — |
The max column sums to 1,431 lines (-30.7 % vs 2,066; margin 15 lines). If AC12 forces a * skill above its max, take the
difference from token-efficiency or design, never from a * skill. Set the `skill_layout.allow` rows to the new counts
(delete a row if under the limit).

### 2.6 Pointer cleanup (AC6)
Apply rows 2, 5-14 and 16 of 2.1 (rows 1, 3, 4 are covered by 2.8).

### 2.7 CLAUDE.md rewrite (AC8, step A; today 104 lines, ~9 KB -> <= 4 KB)
| Section (new) | Kept / new content | Dropped |
|---|---|---|
| `# CLAUDE.md` + purpose (3 lines) | exam/learning harness (EPIC-002), cloned and untrusted; `examples/FORMAT.md` standard; `tools/examples/*` via `python3 -I` | "toolkit, not a scan target", claude -p over ~80 repos, manifest/results/PDF |
| `## Commands` (3 lines) | `task-state.sh`, `status.sh`, `workflow-check.sh`, `team-status.sh`; `req.py gaps` | run_all, scratch kit, pipeline, coverage_check, report_qa, tracking, ext tools |
| `## Workflow` | states line, max_active, task files, rules 1-10 (as today, :28-38) | — |
| skill table | rows for kept skills incl. `coordinator`, `role-monitor`, `inspector`, `task-priority`; "real verification / content oracle" = `verify` / `crosscheck` | ext-scan row, `security`, report-QA |
| `## Never break` (exam) | blocking opt-in (user 2026-09-28); status lines (RAW-00361); working style (RAW-00134..137: keep free roles busy, one-click hints); Bash 3.2 / Python stdlib; content defects in handoff; eval keys never in eval inputs or few-shot files; exam prompts not under `docs/prompts/`; Haiku only for simple jobs | one repo per process, REPOS_ROOT, JSON schema, manifest, scan.lock, scheduler, X-User-Id, frozen prompts, findings reach reports, plan modes, scan model, phase 0 tuning |
| `<!-- req-kit -->` `## Requirement ledger` | as today (:81-86) | — |
| `<!-- agent-setup:* -->` roles block | as today minus "leads only when 2 tasks run" and "source trees and `$REPOS_ROOT`"; keeps the pointer to `docs/guide/workflow-roles.md` | lead text |
| `## Main session identity` | as today (1 line) | — |

### 2.8 Strip list (AC9, step B)
| File | Lines | Action |
|---|---|---|
| agents/coder.md | 53-92 (project block) | replace the content between the markers with an 8-line exam block: harness untrusted; main owns state/ledger/design/report docs and commits; Bash 3.2, Python stdlib; tests only when the brief names them; pointer to `docs/guide/exam-brief-override.md` |
| agents/designer.md | 44-75 | same exam block, plus "write a draft for main, which writes `docs/design/`" |
| agents/tester.md | 51-90; :99 | same exam block; drop the `ext-scan`/`api-platform-security` sentence in the QA gate |
| agents/verifier.md | 45-81; :39 | same exam block; :39 "and findings.jsonl" -> "" |
| agents/{coder,designer,tester,verifier}.md | Skills section (row 2) | example skills -> `report`, `python`, `crosscheck`; drop `run-security-review` |
| agents/{coder:125-126, designer:109-110, tester:136-137, verifier:113-114} | Output item 2 | -> "Record each content defect or bug in the handoff under `## Defects`." |
| agents/inspector.md | 141 | delete |
| commands/* | rows 6-8 | as 2.1 |
| skills/* | 2.1 rows 9-14 + 2.5 | as listed |
| docs/guide/workflow-roles.md (129 lines) | 32-41 (§2 leads); 48 clause "It never reads `REPOS_ROOT` …"; 76-79 scan/REPOS_ROOT/pipeline items -> "reads outside the harness, paid commands"; 93-124 (§7 rules 2 and 9) | delete / reword; §7 becomes one line pointing to `exam-brief-override.md`; §1, §3-§5 role-management text stays (AC12) |
The Team, Context budget, Output and handoff sections of every role body stay (AC12): they carry the briefing and monitoring contract.

### 2.9 Delete list (AC10, step C; dangling grep excludes `work/`, `.claude/state/`, `docs/templates/` = history)
| Path | Live references found (grep 2026-10-29) | Action |
|---|---|---|
| `tools/triage/` | `.gitignore:36-38` only | delete dir + .gitignore 24-29, 35-38 (keep 31-33) |
| `docs/review/2026-09-23-scan-reliability-review.md` | none | delete (and `docs/review/` if empty) |
| `docs/report/phase-2-prompt-exclusions.md` | none (also clashes with this phase-2 basename) | delete |
| `docs/design/phase-1-init-status.md` | none live (this doc's r1 Decision line is reworded) | delete |
| `.claude/tests/lessons_test.sh` | none (tests lessons.py) | delete |
| `.claude/scripts/lessons.py` | coordinator:115-116, workflow:106, tasks.md:14 (removed in step B); `lessons_revert_confine_test.sh` | delete |
| `.claude/tests/lessons_revert_confine_test.sh` | none (tests lessons.py) | delete |
| `.claude/lessons/ledger.jsonl` | lessons.py:77 only | delete dir |
| `.claude/scripts/scratch-kit.sh` | coordinator:207,310; tester.md:70; scratch_kit_test, protect_rules_test:109, tamper_test:183 | KEEP (used by kept tests; generic) |
| `.claude/scripts/checks/secrets.sh` | commit-check.sh:14, quality-check.sh:4 | KEEP (in use) |
Not touched (user, AC11): `agent_setup.py`'s own `lessons` subcommand (:1985) is a separate command, not lessons.py.
Not touched (AC12): `team-status.sh`, `watch-role.sh`, `brief.sh`.

## Failure modes
| Failure | Response | Operator sees |
|---|---|---|
| Compression or strip drops a rule a role still needs | revert that hunk (git) | a role asks main, or takes a wrong step |
| A monitoring/management rule is cut from an AC12 skill | V-12 heading check fails; revert | row V-12 |
| An edit breaks a skill's frontmatter | 2.5b fails | Verification row 2.5b |
| A kept test greps agent/skill text that was stripped | not run here (override); listed as a risk | next run of that suite |
| CLAUDE.md markers lost | `agent_setup.py init` would append a second block | step A marker check |
| An AC11 file changes | V-11 diff check fails | row V-11 |

## Unit tests
None: docs/skills/deletions only, and the override forbids running `tests/*`. The checks are the greps below.

## Verification (all Tier 0, static)
| Item | Command -> expected |
|---|---|
| 2.1 | REQ-0005 Design links this doc; table has 29 rows, each with impact + fix |
| 2.2 | `test -f docs/guide/exam-brief-override.md`; grep each of the 8 rules -> 8 hits |
| 2.3 | `grep -n '^## Exam content oracle' .claude/skills/crosscheck/SKILL.md` -> 1 hit |
| 2.4 | `grep -n 'Tier 1' .claude/skills/verify/SKILL.md` names the exam oracle and "N/A" |
| 2.5a | `cat .claude/skills/*/SKILL.md \| wc -l` -> <= 1446 |
| 2.5b | each SKILL.md has `name:` and `description:` in its frontmatter -> 19/19 |
| 2.6a | `git grep -nE 'api-platform-security\|ext-scan\|pentest-report-qa\|run-pipeline\|run-security-review\|inbox-triage\|skill-maintenance\|skill-curator\|agents/lead\|tasks.sh lead' .claude/skills .claude/agents .claude/commands .claude/scripts/checks/skill_layout.allow` -> empty |
| 2.7 (A) | step A check above |
| V-B1 (AC9) | `git grep -ciE 'api-platform\|pentest\|REPOS_ROOT\|findings\.jsonl\|ext-scan\|run-pipeline' .claude/skills .claude/agents .claude/commands CLAUDE.md docs/guide` -> no output |
| 2.9 (C) | for each deleted path: `test ! -e <p>` and `git grep -n '<basename>' -- . ':!work' ':!.claude/state' ':!docs/templates'` -> empty |
| V-11 (AC11) | `git diff --stat HEAD -- .claude/agent_setup.json .claude/hooks .claude/tests/agent_setup_hook_test.sh` -> empty |
| V-12 (AC12) | the four * skills keep every `^## ` heading they had at HEAD except coordinator `## 2d. Task leads` (diff of `grep '^## '` before/after); `git diff --stat HEAD -- .claude/scripts/team-status.sh .claude/scripts/watch-role.sh .claude/scripts/brief.sh` -> empty |
| AC5 | `git grep -nE 'git +push\|curl \|wget ' .claude/scripts .claude/req .claude/hooks` -> empty |

## Decisions
- brief.sh:41 and commit-check.sh:114 stay as they are, handled by the override and `--checks` (AC12 keeps brief.sh).
- Role-body project blocks are replaced, not edited line by line: almost all AC9 hits sit inside them (one edit per file).
- lessons.py, its two tests and the ledger are deleted: their only workflow caller is the skill-curator flow (removed by Q2).
- scratch-kit.sh and secrets.sh are kept: kept tests and commit-check/quality-check still use them.
- role-monitor's Monitor recipe is kept (AC12); its own :12 note already covers the disabled tool.
- Replace `security` with `crosscheck` wherever a removed-skill pointer had a live replacement (Q2).
- Phase number 2 as the brief says; the legacy phase-1/phase-2 docs are deleted in 2.9.

## Out of scope
D: dead entries in agent_setup.json (Q4/Q6); settings.json (done by the coordinator). Anything in AC11 files (user).
Hook, guard and `tasks.sh lead` code.
