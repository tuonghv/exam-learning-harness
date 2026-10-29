# Phase 1 — Harness exam fit

Task: TASK-001 · REQ-0005 · Status: draft r5 (Nova, designer, 2026-10-29; r2 Q6/AC8-AC11, r3 AC12, r4 AC7 50 % + AC13,
r5 RAW-00023: bash, context-compaction, task-priority already removed in d87aed7)

## Goal
Roles briefed for EPIC-002 exam-content work get exam rules (one override block), check content with an independent
exam-content oracle, and see no scan text and no pointer to a removed skill or role. CLAUDE.md is exam-only (<= 4 KB),
orphans are deleted, kept skills shrink by >= 50 % and role bodies to <= 75 lines each, with role management and
monitoring intact. Done when AC1-AC13 of REQ-0005 hold (greps and `git diff` below).

## Constraints
- Q1: override block + small skill edits. Q6 (A+B+C) supersedes Q4 for CLAUDE.md, role bodies, skills, commands, docs/guide;
  Q4 still holds for `agent_setup.json` dead entries (D: not done).
- RAW-00023 (user): a skill that is not relevant is removed, not fixed. Further removals are listed as candidates for the
  user (2.11); this design removes nothing beyond what the coordinator already removed.
- AC11 (user): no edit or deletion of `.claude/agent_setup.json`, `.claude/hooks/agent_setup.py`,
  `.claude/tests/agent_setup_hook_test.sh`, not even pointer fixes; dangling pointers inside them are tolerated.
- AC12 (user): keep skills `coordinator`, `role-monitor`, `inspector` and scripts `team-status.sh`, `watch-role.sh`,
  `brief.sh`; compress wording, never cut a role-management or monitoring rule. `task-priority` was on the AC12 list
  but was removed in d87aed7 (RAW-00023); the coordinator should reword AC12 to match (see handoff).
- AC13 (user): role bodies designer/coder/tester/verifier/inspector <= 75 lines each; keep frontmatter, identity line,
  agent-setup markers, STATUS/PROGRESS/SKILLS handoff lines, scope/refusal rules.
- `.claude/settings.json` is the coordinator's. `.claude/hooks/*` stay unchanged.
- CLAUDE.md keeps `<!-- req-kit -->` and `<!-- agent-setup:start|custom|end -->` (`agent_setup.py:252`). Agent bodies keep
  `<!-- agent-setup:project:start|end -->` (`agent_setup.py:127,281`; rewritten only by an explicit `init --profile`).
- Kept skill names stay (frontmatter preloads `coding`, `unit-test`, `design`, `verify`, `crosscheck`, `inspector`,
  `token-efficiency`; `brief.sh:95` adds `python` by name). Every kept SKILL.md keeps `name` + `description`.

## Known incidents
None (this harness has no `docs/notes/incidents.md`).

## Plan modes
| Mode | Impact | Verified by |
|---|---|---|
| single-source (`scan_batch.sh`, no flag) | n/a: script absent from this harness | — |
| pipeline (`pipeline.sh`, `--run`) | n/a: same; this task edits docs/skills/role bodies and deletes orphans only | — |

## Implementation steps (5 coder steps, in order, each closed by its check)
| Step | Items | Check (must hold before the next step) |
|---|---|---|
| A | 2.7 CLAUDE.md rewrite — DONE (coordinator) | `wc -c CLAUDE.md` <= 4096; AC9 pattern on CLAUDE.md = 0; `grep -c 'agent-setup:\|req-kit' CLAUDE.md` = 4 |
| B | 2.2 override doc, 2.3 oracle, 2.4 Tier-1 note, 2.6 pointers (incl. the removed-skill one-liners), 2.8 workflow-roles.md, delete `agents/lead.md` | 2.2, 2.3, 2.4 rows; V-B0 (pointers to removed skills) -> empty |
| C | 2.5 compression (16 skills) + `skill_layout.allow` ratchet | 2.5a (<= 1033), 2.5b (16/16 frontmatter), V-12 |
| D | 2.10 role bodies (absorbs 2.1 rows 1-4) | V-13; V-B1 (AC9) = 0 over everything |
| E | 2.9 deletions | `test ! -e` per path; dangling `git grep` per row -> empty; V-11 |

## Design

### 2.1 Audit fix list (AC1; each row checked by reading the line on 2026-10-29)
| # | file:line | finding | impact | fix |
|---|---|---|---|---|
| 1 | agents/{coder:125, designer:109, tester:136, verifier:39,113} | "append each security issue … findings.jsonl" | MISLEADS | step D (2.10) |
| 2 | agents/{coder:98-103, designer:81-86, tester:109-114, verifier:86-91} | skill examples name removed skills | MISLEADS | step D: Skills section rewritten |
| 3 | agents/designer:72-73, tester:99 | load `security` / `api-platform-security` / `ext-scan` | MISLEADS | step D |
| 4 | agents/{coder:91, designer:74, tester:89, verifier:80, inspector:141} | `L:` lessons line, "Only the skill-curator edits" | MISLEADS | step D: delete (lessons.py deleted in E) |
| 5 | agents/lead.md | role removed by Q2 | MISLEADS | step B: delete file |
| 6 | commands/design-phase:7-8 | `api-platform-security`, `security` | MISLEADS | step B: drop both clauses |
| 7 | commands/next, verify-phase | removed-skill pointers | MISLEADS | done by the coordinator (d87aed7) |
| 8 | agents/{coder:102, designer:85, tester:113, verifier:90} | state-moving list names removed `context-compaction` (+ `run-security-review`) | MISLEADS | step B: drop both names from the list (one line each) |
| 9 | skills/coordinator:106 | same list (`context-compaction`, `run-security-review`) | MISLEADS | step B: drop both names |
| 10 | skills/coordinator:105-117,132,137-138,156,159-171,215,227,297,314,332,362 | removed skills, skill-curator, lessons, §2d leads, scan/REPOS_ROOT/paid-run rows | MISLEADS | pointers in B; the rest in C |
| 11 | skills/token-efficiency:19-21,219 | `api-platform-security`, `pentest-report-qa` (and the `bash` language line) | MISLEADS | step C (line 34 `security` = task.json field: keep) |
| 12 | skills/workflow/references/tasks.md:14 | skill-curator/lessons step | MISLEADS | step B: delete sentence |
| 13 | skills/workflow/references/resume-and-failure.md:15 | `tasks.sh lead` | MISLEADS | step B: delete the lead clause |
| 14 | skills/inspector:76 + step "0. Check tools/inspect/INDEX.md" (agent :55) | `run-security-review/references/…`; INDEX.md is an empty index (2 lines) | MISLEADS | step B: delete :76; step D: drop step 0 (no scripts listed) |
| 15 | skills/role-monitor:12-17 + scripts/watch-role.sh:3 | Monitor recipe while the Monitor tool is disabled (RAW-00160) | MISLEADS | role-monitor: keep the :12 "disabled" note and the watch-role.sh arm, Monitor parameter line -> 1 line (C); watch-role.sh left as is (AC12) |
| 16 | scripts/checks/skill_layout.allow:3-6,11 | rows for removed skills (api-platform-security, bash, ext-scan, inbox-triage) | COSMETIC | step B: delete; step C: ratchet the remaining rows |
| 17 | scripts/brief.sh:41 | default checks = missing `tests/run_all.sh --changed` | MISLEADS | left as is (AC12); coordinator passes `--checks` (:17) |
| 18 | scripts/brief.sh:85,96,99 | `context-compaction`/`run-security-review` in the state-moving list; `add_skill bash` (skill removed) | COSMETIC | left as is (AC12); `add_skill` warns "bash (no such skill)" in coder/tester briefs (:89), harmless |
| 19 | scripts/commit-check.sh:114 | staged `docs/prompts/*.md` fails without `Prompt-change:` | BLOCKS if exam prompts go there | left as is; override rule 7 |
| 20 | scripts/lessons.py (+ 2 tests, ledger) | serves only the removed skill-curator flow | COSMETIC | step E: delete |
| 21 | scripts/team-status.sh | named in the brief; no removed pointer found | — | left as is (AC12) |
| 22 | scripts/workflow-check.sh:317 | comment names `context-compaction` | COSMETIC | left as is (comment) |
| 23 | .claude/tests/agent_setup_hook_test.sh:363-375 | skill-curator guard cases | COSMETIC | left as is (user, AC11) |
| 24 | .claude/hooks/agent_setup.py (lead code :521-1527, `lessons` cmd :1985) | dead lead/lessons code | COSMETIC | left as is (user, AC11) |
| 25 | agent_setup.json:44-55,88-90,96-141 | lead/skill-curator configs, scan `bash_deny`; write_globs miss `examples/` `evals/` `tools/examples/` | COSMETIC (`enforce: []`) | left as is (user, AC11; Q4/D) |
| 26 | settings.json | dead `ask` rules | COSMETIC | removed by the coordinator |
| 27 | CLAUDE.md | scan toolkit text, removed-skill pointers | MISLEADS | step A (done) |
| 28 | docs/guide/workflow-roles.md:32-41,48,76-79,93-124 | leads, REPOS_ROOT, scan guard text, scan rules 2 and 9 | MISLEADS | step B (2.8) |
| 29 | .gitignore:24-29,35-38,46 | inbox-triage / tools/triage / ext-scan rules | COSMETIC | step E: delete 24-29, 35-38; keep 31-33; :46 left as is |
| 30 | docs/templates/sample-state/** | history copies name deleted files | COSMETIC | left as is (history) |

### 2.2 `docs/guide/exam-brief-override.md` (AC2; new file, ~25 lines)
One fenced block that the coordinator pastes as the first lines of every EPIC-002 brief, then 3 lines explaining why:
1. Domain: exam/learning content (Maths, Physics, English, Literature); `examples/FORMAT.md` is the I/O standard (Q3).
2. Ignore any leftover scan, frozen-prompt or security-severity text in role bodies and skills.
3. Do not run `.claude/scripts/*`, `tests/*`, `req.py`, a scratch kit, `claude -p` or network tools.
4. Run only `tools/examples/*` with `python3 -I`; everything outside the brief's write list is read-only.
5. Write only the files the brief names, plus your handoff.
6. Content defects (wrong key, unit or quote) go in the handoff under `## Defects`.
7. Never put exam prompts under `docs/prompts/` (commit-check.sh:114 freezes that path).
8. Verify with skill `crosscheck` §Exam content oracle (Tier 1).
(No literal `findings.jsonl` / `REPOS_ROOT` in this file: AC9 greps docs/guide.)

### 2.3 crosscheck "Exam content oracle" (AC3a; `.claude/skills/crosscheck/SKILL.md`)
New `## Exam content oracle` section (~20 lines) after `## Output` (:42). Each check runs without the generator's code:
- Maths/Physics: recompute every key from the item text (stdlib `python3 -I -c`, `fractions`/`decimal`); compare the value,
  the unit (SI, as stated) and the rounding (stated places or sig figs).
- English: re-apply the named grammar/vocabulary rule to each option; exactly one option may pass.
- Literature: every quote is a verbatim substring of the passage (`grep -F`), and its attribution matches.
- Leakage: no eval key string appears in eval inputs or few-shot files (`grep -F -f keys inputs`); empty = PASS.
- Output: the existing TSV mismatch format (:42-48), one row per item; any row = FAIL.
Drop the scan recipes at :29-41 (SARIF/gosec/bandit) and the scan report cross-check at :49+ (REQ-0058).

### 2.4 verify Tier-1 note (AC3b; `.claude/skills/verify/SKILL.md`, tier table :41-46)
Add one line under the tier table: "Content tasks (EPIC-002): the crosscheck exam oracle run is Tier 1 and is the evidence;
Tiers 2-3 are N/A (no scratch kit, no `claude` call)." Drop :21 (scratch `REPOS_ROOT`).

### 2.5 Compression (AC7 = 50 %; baseline 2,066 -> <= 1,033; Grep count after d87aed7 = 1,854 over 16 skills; step C)
Remove all scan, pipeline, report-QA, REPOS_ROOT, paid-run, lead and lessons/curator text, dated TASK-0xx lessons,
RAW-id citations in prose, and repeated rules (each rule lives in one skill; the others point to it).
* = AC12 skill: wording only.
| skill | now | max | what stays |
|---|---|---|---|
| coordinator * | 363 | 150 | identity/roster; §1 owns; §2 assign + brief (brief.sh) + cover what roles cannot; keep-busy; §4 talk + message budget; §5 unstick; §6 alert user (one-click hints); §7 report. Out: §2d leads, guard table (-> 3-line summary), lessons/curator, paid-go, scan rows, request-ordering text (task-priority removed: 3 lines on batching kept here) |
| token-efficiency | 264 | 40 | scope, read-smallest table (6 rows), reuse recorded results, output/end-of-turn rules. Out: the whole "Going faster" log, per-role scan notes, :19-21 |
| design | 228 | 70 | steps 1-6, reuse order, path convention, doc structure (section names only). Out: premise/CLI mining, failure economics, analyze/propose/recommend, plan-modes text |
| verify | 176 | 60 | what VERIFIED means, tier table (Tier 1 = oracle for content), save evidence before the verifier, on failure. Out: pipeline resume, HEAD-vs-new recipe |
| workflow | 137 | 90 | states, task.json fields table, skill-per-state table, transitions/momentum. Out: lessons, scan notes |
| commit | 106 | 60 | when, gate, trailers per state, never pipe the gate. Out: prompt-freeze prose |
| crosscheck | 56 | 60 | principles, output TSV, the 2.3 oracle |
| role-monitor * | 75 | 60 | arm (watch-role.sh; Monitor in 1 line), events table, team-status block, root-cause checklist, token rules |
| inspector * | 76 | 55 | goal focus, ANSWER first, handoff size; out :76 and the empty-index step |
| req-intake | 74 | 50 | RAW triage, REQ create, questions |
| req-track | 55 | 40 | status/ac/next commands |
| req-design | 52 | 35 | one REQ at a time, link to the design section |
| report | 46 | 30 | report from task.json + evidence |
| unit-test | 56 | 35 | case design, bite test; out fake-claude text |
| python | 61 | 35 | 3.8 stdlib, `-I`, no removeprefix/match |
| coding | 29 | 25 | as is, tightened |
Sum of max = 905 (-56.2 % vs 2,066; margin 128). If an AC12 skill needs more, it may use the margin. No merges: the names
are load-bearing (frontmatter preloads, `brief.sh:95`, CLAUDE.md table), and the budget meets 50 % without merges.
`skill_layout.allow`: ratchet the rows to the new counts (delete a row once its skill is under the limit).

### 2.6 Pointer cleanup (AC6; step B)
2.1 rows 5, 6, 8, 9, 12, 13, 14 (:76) and 16, plus the pointer lines of rows 10-11 (the rest of 10-11 is in C).
V-B0 must be empty after B.

### 2.7 CLAUDE.md rewrite (AC8; step A, done by the coordinator)
Kept: purpose (exam harness, untrusted, FORMAT.md, `python3 -I`), commands, workflow + rules 1-10, kept-skill table,
the exam Never-break list, req-kit and agent-setup blocks with their markers, identity. Dropped: all scan toolkit text.

### 2.8 workflow-roles.md strip (AC9; step B)
Delete 32-41 (§2 leads) and the clause on `REPOS_ROOT` at 48. Reword 76-79 to "reads outside the harness, paid commands".
Replace 93-124 (§7 rules 2 and 9) with one line pointing to `exam-brief-override.md`. §1 and §3-§5 role-management text stay (AC12).

### 2.9 Delete list (AC10; step E; the dangling grep excludes `work/`, `.claude/state/`, `docs/templates/` = history)
| Path | Live references (grep 2026-10-29) | Action |
|---|---|---|
| `tools/triage/` | `.gitignore:36-38` only | delete dir + .gitignore 24-29, 35-38 (keep 31-33) |
| `docs/review/2026-09-23-scan-reliability-review.md` | none | delete (and `docs/review/` if empty) |
| `docs/report/phase-2-prompt-exclusions.md` | none | delete |
| `docs/design/phase-1-init-status.md` | none live; clashes with this phase-1 basename | delete |
| `.claude/tests/lessons_test.sh` | none (tests lessons.py) | delete |
| `.claude/scripts/lessons.py` | coordinator:115-116, workflow:106, tasks.md:14 (gone after B); `lessons_revert_confine_test.sh` | delete |
| `.claude/tests/lessons_revert_confine_test.sh` | none | delete |
| `.claude/lessons/ledger.jsonl` | lessons.py:77 only | delete dir |
| `.claude/scripts/scratch-kit.sh` | tamper_test:183, protect_rules_test:109, scratch_kit_test, coordinator:207,310 | KEEP |
| `.claude/scripts/checks/secrets.sh` | commit-check.sh:14, quality-check.sh:4 | KEEP |
Not touched: `agent_setup.py`'s `lessons` subcommand (AC11); `team-status.sh`, `watch-role.sh`, `brief.sh` (AC12).

### 2.10 Role bodies <= 75 lines (AC13; step D; owner `.claude/agents/<role>.md`)
Target shape for designer/coder/tester/verifier (~70 lines, blanks included):
| Section | Lines | Keep | Goes |
|---|---|---|---|
| frontmatter | as is (8) | name, description, tools, skills, maxTurns, model, byte-identical | — |
| Identity + Team roster | 5 | display name line, signing rule, roster, "ids stay the address" | — |
| Inputs | 3 | read only the named inputs; no re-exploration | kit.md/plan.md mention |
| Context budget | 6 | read cap per call, output cap, file cap, no vendor/lockfiles, turn budget + `PROGRESS:` at half, service error = retry once then PARTIAL `BLOCKED: service` | RAW ids, the Monitor line, long rate-limit prose (verifier keeps 1 "no Bash" line) |
| Role rules | 4-8 | role-specific scope + refusal rules (coder "Do" 45-52 -> 5; tester QA gate 92-103 -> 5; verifier 38-44 -> 5; designer 38-43 -> 4) | scan wording, the cache-key note |
| project block (markers kept) | <= 8 | harness untrusted; main owns state/ledger/design/report docs and commits; never `git commit/push/reset/checkout`; Python stdlib; follow `docs/guide/exam-brief-override.md`; designer: draft for main, main writes `docs/design/` | all scan, REPOS_ROOT, pentest, frozen-prompt, paid-command, rtk, Bash-3.2 text, the `L:` lessons line |
| Skills | 4 | preload list = frontmatter; load the brief's `Load:` skills with Skill before the first edit; coordinator-only skills (workflow, commit, req-*, coordinator) are never loaded; `SKILLS:` = handoff line 2 | the examples paragraph naming removed skills |
| Team | 7 | one question + recommendation to `main`; peers only when named; 3 messages / 2 rounds; escalate both positions; PARTIAL with `QUESTION:`; no work-around of a guard | duplicate prose |
| Output | 10 | handoff path, `PROGRESS:` line 1, `SKILLS:` line 2, content list, defects under `## Defects`, "stop requested" -> PARTIAL, reply <= 8 lines `STATUS/OUTPUT/NEXT/NOTE`, no code in the reply | the findings.jsonl item, the verifier:39 clause |
Per file, today -> cut: coder 136 (-61+), designer 117 (-42+), tester 145 (-70+), verifier 122 (-47+).
inspector 141 -> 75: keep the frontmatter (1-8); header 10-19 -> 3; Primary goal 2; Responsibilities 25-37 -> 6 (11 Goal focus
kept; 9-10 merged into Boundaries); Token efficiency 39-49 -> 4; Investigation priority 51-64 -> 5 (step 0 dropped: INDEX.md is
empty); Follow-up 66-72 -> 3; Boundaries 74-85 -> 5; Output + INSPECTION HANDOFF template 87-124 -> 25 (field list kept,
examples cut); Quality rules 125-141 -> 6 (the :141 `L:` line deleted). The inspector has no agent-setup markers or
STATUS/PROGRESS lines today; it keeps its `ANSWER:` / handoff template instead.

### 2.11 Remove candidates (for the user; not removed by this design, RAW-00023)
| Candidate | Why it may not be needed | Cost if removed | Recommendation |
|---|---|---|---|
| skill `req-design` (52) | overlaps `design` + `req-track`; one REQ is designed at a time anyway | drop pointers in CLAUDE.md/workflow | remove: fold its 3 rules into `req-track` |
| skill `unit-test` (56) | exam tasks run no tests (override rule 3) | tester preload changes (agents/tester.md:5, AC13 frontmatter is fixed) | keep: `tools/examples/*.py` will need tests |
| skill `report` (46) | only used at DONE | CLAUDE.md rule 10 needs a DONE report | keep, compressed |
| skill `python` / `coding` | — | brief.sh:95 / coder preload | keep: exam tooling is Python |
| `commit` parts | prompt-freeze, scan trailers | — | cut in C (not a skill removal) |
| `tools/inspect/INDEX.md` | empty index (2 lines) | inspector step 0 dropped in D | remove in E if the user agrees |
| `.claude/scripts/scratch-kit.sh` + `scratch_kit_test.sh` | the override forbids scratch kits | `tamper_test.sh:183`, `protect_rules_test.sh:109` reference it | keep (removal touches kept guard tests) |

## Failure modes
| Failure | Response | Operator sees |
|---|---|---|
| Compression drops a rule a role still needs | revert that hunk (git) | a role asks main, or takes a wrong step |
| An AC12 management/monitoring rule is cut | V-12 fails; revert | row V-12 |
| A role body loses frontmatter, markers or handoff lines | V-13 fails | row V-13 |
| A skill's frontmatter breaks | 2.5b fails | row 2.5b |
| A kept suite greps stripped text | not run here (override); listed as a risk | next run of that suite |
| An AC11 file changes | V-11 fails | row V-11 |

## Unit tests
None: docs/skills/role bodies/deletions only, and the override forbids `tests/*`. The checks are the greps below.

## Verification (all Tier 0, static)
| Item | Command -> expected |
|---|---|
| 2.1 | REQ-0005 Design links this doc; the table has 30 rows, each with impact + fix |
| 2.2 | `test -f docs/guide/exam-brief-override.md`; grep each of the 8 rules -> 8 hits |
| 2.3 | `grep -n '^## Exam content oracle' .claude/skills/crosscheck/SKILL.md` -> 1 |
| 2.4 | `grep -n 'Tier 1' .claude/skills/verify/SKILL.md` names the oracle and "N/A" |
| V-B0 (AC6) | `git grep -nE 'api-platform-security\|ext-scan\|pentest-report-qa\|run-pipeline\|run-security-review\|inbox-triage\|skill-maintenance\|skill-curator\|context-compaction\|task-priority\|skills/bash\|agents/lead\|tasks.sh lead' .claude/skills .claude/agents .claude/commands .claude/scripts/checks/skill_layout.allow` -> empty |
| 2.5a | `cat .claude/skills/*/SKILL.md \| wc -l` -> <= 1033 (plan: 905) |
| 2.5b | each SKILL.md has `name:` and `description:` in its frontmatter -> 16/16 |
| V-B1 (AC9) | `git grep -ciE 'api-platform\|pentest\|REPOS_ROOT\|findings\.jsonl\|ext-scan\|run-pipeline' .claude/skills .claude/agents .claude/commands CLAUDE.md docs/guide` -> no output |
| V-12 (AC12) | coordinator, role-monitor and inspector keep each rule topic in 2.5 (one keyword per topic: `brief.sh`, `busy`, `3 messages`, `stuck`, `watch-role.sh`, `team-status`, `ANSWER`) -> all hit; `git diff --stat HEAD -- .claude/scripts/{team-status,watch-role,brief}.sh` -> empty |
| V-13 (AC13) | `wc -l .claude/agents/{designer,coder,tester,verifier,inspector}.md` -> each <= 75; `git diff -U0 HEAD -- <file>` changes no line in 1-8; `grep -c 'agent-setup:project'` = 2 in the 4 roles; `grep -cE 'STATUS:\|PROGRESS:\|SKILLS:'` >= 3 in the 4 roles; `grep -c 'ANSWER' inspector.md` >= 1 |
| 2.9 (E) | per path: `test ! -e <p>`; `git grep -n '<basename>' -- . ':!work' ':!.claude/state' ':!docs/templates'` -> empty |
| V-11 (AC11) | `git diff --stat HEAD -- .claude/agent_setup.json .claude/hooks .claude/tests/agent_setup_hook_test.sh` -> empty |
| AC5 | `git grep -nE 'git +push\|curl \|wget ' .claude/scripts .claude/req .claude/hooks` -> empty |

## Decisions
- No skill merges: the names are load-bearing, and 905 lines already meets 50 %.
- Removed-skill one-liners in agents/coordinator are fixed in B (pointer step); the rest of the role-body work is in D.
- brief.sh:41/85/96/99 and commit-check.sh:114 stay as they are (AC12 / override rule 7); the `bash` warning in briefs is harmless.
- lessons.py, its two tests and the ledger are deleted; scratch-kit.sh and secrets.sh stay (still used).
- `security` -> `crosscheck` wherever a removed-skill pointer had a live replacement (Q2).
- Phase number 1, per the coordinator; `phase-1-init-status.md` is deleted in E, which removes the basename clash.

## Out of scope
D: dead entries in agent_setup.json (Q4/Q6). Anything in AC11 files. Hook, guard and `tasks.sh lead` code. Removing 2.11 candidates without the user's go.
