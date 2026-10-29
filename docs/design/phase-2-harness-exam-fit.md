# Phase 2 — Harness exam fit

Task: TASK-001 · REQ-0005 · Status: draft (Nova, designer, 2026-10-29)

## Goal
Roles briefed for EPIC-002 exam-content work get exam rules (one override block), check content with an
independent exam-content oracle, and see no pointer to a removed skill or role. Kept skills shrink by >= 30 % so the
inherited scan text stops costing tokens. Done when AC1-AC7 of REQ-0005 hold (the greps and `git diff` below).

## Constraints
- Q1: override block + small skill edits; no role-body rewrite. Q4: dead scan entries in `settings.json`,
  `agent_setup.json` and `CLAUDE.md` stay; only dangling pointers to removed skills or roles get a minimal fix.
- AC4: `.claude/settings.json`, `agent_setup.json` and `hooks/*` stay unchanged; in `agents/*`, only pointer edits plus deleting `lead.md`.
- Every kept `SKILL.md` keeps its frontmatter `name` + `description`. Bash/Python sources: no behaviour change.

## Known incidents
None (this harness has no `docs/notes/incidents.md`).

## Plan modes
| Mode | Impact | Verified by |
|---|---|---|
| single-source (`scan_batch.sh`, no flag) | n/a: script is absent from this harness (Glob found no `scan_batch.sh` or `pipeline.sh`) | — |
| pipeline (`pipeline.sh`, `--run`) | n/a: same reason; this task edits docs and skills only | — |

## Design

### 2.1 Audit fix list (AC1; each row checked by reading the line on 2026-10-29)
| # | file:line | finding | impact | fix |
|---|---|---|---|---|
| 1 | agents/{coder:125, designer:109, tester:136, verifier:113} | "append each security issue … findings.jsonl" | MISLEADS | left as is (AC4); override 2.2 rule 6 sends defects to the handoff |
| 2 | agents/{coder:98-103, designer:81-86, tester:109-114, verifier:86-91} | skill examples name `pentest-report-qa`, `api-platform-security`, `security`, `run-security-review` | MISLEADS | pointer edit: examples become `report`, `python`, `crosscheck`; drop `run-security-review` from the state-moving list |
| 3 | agents/designer:72-73, tester:99 | load `security` / `api-platform-security` / `ext-scan` | MISLEADS | delete those clauses |
| 4 | agents/{coder:91, designer:74, tester:89, verifier:80, inspector:141} | "Only the skill-curator edits skills" | MISLEADS | change to "Only the coordinator edits …" |
| 5 | agents/lead.md | role removed by Q2 | MISLEADS | delete file |
| 6 | commands/design-phase:7-8 | `api-platform-security`, `security` | MISLEADS | drop both clauses |
| 7 | commands/next:11,13 | same | MISLEADS | drop `(+ api-platform-security …)`; replace `security` with `crosscheck` |
| 8 | commands/verify-phase:7 | loads `security` | MISLEADS | replace with `crosscheck` |
| 9 | skills/coordinator:105-117,132,159-171,227,297,332,362 | removed skills, skill-curator, §2d leads | MISLEADS | removed by the 2.5 compression |
| 10 | skills/token-efficiency:21,219 | `api-platform-security`, `pentest-report-qa` | MISLEADS | removed in 2.5 (line 34 `security` is a task.json field: keep) |
| 11 | skills/workflow:76,79 | `api-platform-security`, `security` | MISLEADS | drop the clause; replace `security` with `crosscheck` (line 42 is a task.json field: keep) |
| 12 | skills/workflow/references/tasks.md:14 | skill-curator/lessons step | MISLEADS | delete the sentence |
| 13 | skills/workflow/references/resume-and-failure.md:15 | `tasks.sh lead` | MISLEADS | delete the lead clause |
| 14 | skills/inspector:76 | `run-security-review/references/…` | MISLEADS | delete the line |
| 15 | skills/role-monitor:12-17 + scripts/watch-role.sh:3 | Monitor tool recipe (Monitor is disabled, RAW-00160) | MISLEADS | role-monitor: keep the "disabled" note, drop the Monitor recipe (2.5); watch-role.sh left as is |
| 16 | scripts/checks/skill_layout.allow:3,6,11 | rows for removed skills | COSMETIC | delete the rows; ratchet rows 4,5,7-10 to the new sizes (2.5) |
| 17 | scripts/brief.sh:41 | default checks = `tests/run_all.sh --changed` (file does not exist) | MISLEADS | left as is; the coordinator passes `--checks "python3 -I tools/examples/<x>.py …"` (flag at :17) |
| 18 | scripts/brief.sh:76 | FORBID lists the frozen scan prompts | COSMETIC | left as is |
| 19 | scripts/brief.sh:85 | `run-security-review` in the state-moving list | COSMETIC | left as is (the name never matches now, so it is harmless) |
| 20 | scripts/commit-check.sh:114 | any staged `docs/prompts/*.md` fails without a `Prompt-change:` trailer | BLOCKS if exam prompts are placed there | left as is; override rule 7 keeps exam prompts in `examples/` or `evals/`, never `docs/prompts/` |
| 21 | scripts/lessons.py:34 | `APP_SKILLS` = 4 removed skills | COSMETIC | left as is; its only workflow caller (the coordinator:115 drift step) is removed in row 9 |
| 22 | scripts/team-status.sh | named in the brief, but grep finds no removed-skill or role pointer | — | left as is (claim not confirmed) |
| 23 | .claude/tests/lessons_test.sh:493-513 | `ext-scan` is a fixture directory name in a scratch dir | COSMETIC | left as is (not a pointer) |
| 24 | .claude/tests/agent_setup_hook_test.sh:363-375 | skill-curator guard cases | COSMETIC | left as is (tests are not run, per the override) |
| 25 | settings.json:19-39 | `ask` rules (the brief said "allows") for absent `claude -p` and scan/pipeline scripts | COSMETIC | left as is (Q4) |
| 26 | agent_setup.json:44-55,88-90,123-141 | `lead`/`skill-curator` role configs, protect.roles, scan `bash_deny` | COSMETIC | left as is (Q4, AC4) |
| 27 | agent_setup.json:96-119 | `write_globs` miss `examples/`, `evals/`, `tools/examples/` | COSMETIC (`enforce: []`, opt-in) | left as is (Q4; any widening needs the user's go) |
| 28 | CLAUDE.md:10,22,24,49,68 | "skill `run-security-review` / `pentest-report-qa` / `ext-scan` / `api-platform-security`" | MISLEADS | drop only the skill-name tail; delete the :49 table row |
| 29 | CLAUDE.md:42 | `security` skill in the table | MISLEADS | replace with `crosscheck` |
| 30 | .gitignore:24,46 | inbox-triage header, ext-scan path | COSMETIC | left as is (rules under :24 still guard `settings.local.json`) |
| 31 | .claude/lessons/ledger.jsonl:2-5,15 | history rows name removed skills | COSMETIC | left as is (append-only history) |

### 2.2 `docs/guide/exam-brief-override.md` (AC2; new file, ~25 lines)
One fenced block that the coordinator pastes as the first lines of every EPIC-002 brief, followed by 3 lines explaining why:
1. Domain: exam/learning content (Maths, Physics, English, Literature); `examples/FORMAT.md` is the input/output standard (Q3).
2. Ignore all scan, REPOS_ROOT, frozen-prompt, security-severity and `findings.jsonl` text in role bodies and skills.
3. Do not run `.claude/scripts/*`, `tests/*`, `req.py`, a scratch kit, `claude -p` or network tools.
4. Run only `tools/examples/*` with `python3 -I`; everything outside the brief's write list is read-only.
5. Write only the files the brief names, plus your handoff.
6. Content defects (wrong key, unit or quote) go in the handoff under `## Defects`, never in `findings.jsonl`.
7. Never put exam prompts under `docs/prompts/` (commit-check.sh:114 freezes that path).
8. Verify with skill `crosscheck` §Exam content oracle (Tier 1).

### 2.3 crosscheck "Exam content oracle" (AC3a; owner `.claude/skills/crosscheck/SKILL.md`)
Add a new `## Exam content oracle` section (~20 lines) after `## Output` (:42). Each check runs without the generator's code:
- Maths/Physics: recompute every key from the item text (stdlib `python3 -I -c`, `fractions`/`decimal`);
  compare the value, the unit (SI, as stated) and the rounding (the item's stated places or sig figs).
- English: re-apply the named grammar/vocabulary rule to each option; exactly one option may pass.
- Literature: every quote is a verbatim substring of the passage (`grep -F`), and its attribution matches.
- Leakage: no eval key string appears in the eval inputs or few-shot files (`grep -F -f keys inputs`); empty output = PASS.
- Output: the existing TSV mismatch format (:42-48), one row per item; any row = FAIL.
In the same edit, drop the scan recipes at :29-41 (SARIF/gosec/bandit); this counts toward 2.5.

### 2.4 verify Tier-1 note (AC3b; owner `.claude/skills/verify/SKILL.md`, tier table at :41-46)
Add one line under the tier table: "Content tasks (EPIC-002): the crosscheck exam oracle run is Tier 1 and is
the evidence; Tiers 2-3 are N/A (no scratch kit, no `claude` call)."

### 2.5 Compression (AC7; baseline 2,066 lines, target <= 1,446; Grep count today = 2,122)
Remove scan, pipeline, report-QA, REPOS_ROOT, paid-run, lead and skill-curator text, and the dated TASK-0xx scan lessons;
keep the generic rules. Per-skill targets (today -> max):
| skill | now | max | cut |
|---|---|---|---|
| coordinator | 363 | 180 | §2d leads; lessons/curator 115-117; paid-go/run-review lines 227,297,332,362; scan rows in the guard table |
| token-efficiency | 264 | 90 | "Going faster" scan lessons (keep <= 10 generic lines); the api-platform line |
| design | 228 | 110 | failure economics, CLI-string mining, Analyze/propose cost tuning; Plan modes shrinks to one optional line |
| verify | 176 | 90 | pipeline resume §66-97, scan Tier-2/3 detail; adds the 2.4 line |
| workflow | 137 | 110 | row 11, scan-specific notes |
| bash | 118 | 80 | scan_batch/manifest examples |
| commit | 106 | 80 | prompt-freeze and scan trailer prose |
| context-compaction | 80 | 60 | scan-run hand-off text |
| inspector | 76 | 55 | pipeline/plan lines |
| role-monitor | 75 | 55 | Monitor recipe |
| task-priority | 70 | 55 | scan examples |
| python | 61 | 50 | scan helper names |
| unit-test | 56 | 50 | fake-claude fixture text |
| crosscheck | 56 | 80 | adds 2.3, drops the scan recipes |
| req-intake, req-track, req-design, report, coding | 74, 55, 52, 46, 29 | unchanged | — |
The max column sums to 1,401 lines (-32.2 % vs 2,066). Set the `skill_layout.allow` rows 4,5,7-10 to the new counts (or delete a row if its skill is under the limit).

### 2.6 Pointer cleanup (AC6)
Apply rows 2-16 and 28-29 of 2.1, and delete `.claude/agents/lead.md`.

## Failure modes
| Failure | Response | Operator sees |
|---|---|---|
| Compression drops a rule a role still needs | revert that hunk (git) | a role asks main, or takes a wrong step |
| An edit breaks a skill's frontmatter | the 2.5b check fails | Verification row 2.5b |
| An agent body is edited beyond pointers | the AC4 diff check fails | row 2.6b |

## Unit tests
None: the change touches docs and skills only, and the override forbids running `tests/*`. The checks are the greps below.

## Verification (all Tier 0, static)
| Item | Command -> expected |
|---|---|
| 2.1 | the REQ-0005 Design section links this doc; the table has 31 rows, each with impact + fix |
| 2.2 | `test -f docs/guide/exam-brief-override.md`; grep for each of the 8 rules -> 8 hits |
| 2.3 | `grep -n '^## Exam content oracle' .claude/skills/crosscheck/SKILL.md` -> 1 hit |
| 2.4 | `grep -n 'Tier 1' .claude/skills/verify/SKILL.md` names the exam oracle and "N/A" |
| 2.5a | `cat .claude/skills/*/SKILL.md \| wc -l` -> <= 1446 |
| 2.5b | each SKILL.md has `name:` and `description:` in its frontmatter -> 19/19 |
| 2.6a | `git grep -nE 'api-platform-security\|ext-scan\|pentest-report-qa\|run-pipeline\|run-security-review\|inbox-triage\|skill-maintenance\|skill-curator\|agents/lead\|tasks.sh lead' .claude/skills .claude/agents .claude/commands .claude/scripts/checks/skill_layout.allow` -> empty |
| 2.6b | `git diff --stat HEAD -- .claude/settings.json .claude/agent_setup.json .claude/hooks` -> empty; `git diff .claude/agents` shows only pointer lines + the lead.md deletion |
| AC5 | `git grep -nE 'git +push\|curl \|wget ' .claude/scripts .claude/req .claude/hooks` -> empty |

## Decisions
- brief.sh:41 and commit-check.sh:114 stay as they are, handled by the override and `--checks`: editing scripts is outside Q1's "small skill edits".
- The `findings.jsonl` rows in role bodies stay as they are: AC4 forbids body changes beyond pointers, and override rule 6 neutralises them.
- Replace `security` with `crosscheck` wherever a removed-skill pointer had a live replacement (Q2: the verifier preloads crosscheck).
- Phase number 2 as the brief says (`phase-1-init-status.md` already holds phase 1), not `phase-<task number>`.

## Out of scope
Hook, guard and `tasks.sh lead` code (dead while max_active = 1); settings/agent_setup cleanup (Q4); any role-body rewrite (Q1).
