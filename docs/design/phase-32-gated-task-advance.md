# Phase 32: gated task advance (TASK-032; REQ-0037)
# TASK-032 design draft: `advance.sh`, one gated TASK transition (REQ-0037), by Nova
Suggested doc: `docs/design/phase-32-gated-task-advance.md` · Items 32.1-32.8 = acceptance (maps AC1-AC7).

## Goal
One command does one TASK step: it sets the fields, writes the phase-log entry, re-syncs the view, steps the linked
REQs, runs workflow-check, makes the commit through commit-check, and prints `PASS` or the FIRST failing gate.
Done when the coordinator stops hand-writing Python for transitions and the tests below pass on a temp repo.

## Premise / reuse (no new engine)
| Piece | Reused as is | Where |
|---|---|---|
| field merge (+ view sync) | `tasks.sh set T --merge work/T/f.json` (MERGE_KEYS, dicts merged one level) | `_tasks.py:1037-1072` |
| one-step state move (+ sync) | `tasks.sh set T --state S` (one step forward or a rollback) | `_tasks.py:966-987` |
| state gates | `workflow-check.sh --task T` (authority, prints FAIL lines) | `workflow-check.sh:68-160,323-330` |
| REQ moves | `req.py status R S --evidence --next`, `req.py ac R all --evidence` | `req.py:477-566` |
| backlog close | `backlog.sh complete T` | `_tasks.py:756-803` |
| commit + undo | `tasks.sh commit T msg --log - -- paths` (lock, commit-check, undo on failure) | `_tasks.py:1149-1246` |
| lock for the log append | `import _tasks; _tasks.locked(task=T)` | `_tasks.py` |
New: `.claude/scripts/advance.sh` (Bash 3.2 wrapper, `exec python3 "$SCRIPT_DIR/_advance.py" "$@"`, same style as
`tasks.sh:36`) and `.claude/scripts/_advance.py` (stdlib, about 250 lines; it orchestrates subprocess calls and adds only
the AC7 checks). New skill `.claude/skills/advance/SKILL.md`.

## 32.1 Gap list from this session (AC1), each closed by a step below
G1 stale `task.json` view → every write goes through `tasks.sh set` (it calls sync); step 6 re-checks the view.
G2 a phase-log entry is needed for EVERY state passed → one step per call, and the entry is appended before workflow-check.
G3 roles waiver/handoff and crosscheck → spec `set.roles`; workflow-check reports what is missing.
G4 `security.{status,result}` needed from VERIFIED on → spec schema for VERIFIED requires it.
G5 report.path must be `docs/report/<design basename>` → filled in from design.path when the spec leaves it out.
G6 backlog complete needs backlog.json staged → DONE runs `backlog.sh complete` and adds backlog.json to the paths (D1).
G7 the REQ must step through every state with `--evidence` and a filled Design section → step 5 / catch-up (32.4).
G8 commit trailers State/Tests/Verified-by/Report (`commit-check.sh:147-150`) → built from the task fields.

## 32.2 CLI (owner: `_advance.py main`)
```
advance.sh <TASK> <STATE> --spec work/<TASK>/advance-<STATE>.json [--dry-run]
advance.sh req-catchup <REQ> [--ac-evidence "<text naming an existing file>"] [--dry-run]
```
Exit 0 `PASS: <TASK> -> <STATE> committed <sha>` | 1 `FAIL [<gate>]: <first message>` + `fix: <hint>` | 2 usage.
The spec must sit under `work/<TASK>/` (same rule as `set --merge`, `_tasks.py:1048-1052`).

## 32.3 Spec JSON (one per state)
```
{"set":   {<MERGE_KEYS only: design|implementation|unit_test|security|verification|report|roles|acceptance_criteria>},
 "next":  "<concrete next step>"            # required; "" only at DONE
 "log":   {"action":"..","result":"..","decision":"..","next":".."},   # all four non-empty
 "commit":{"subject":"docs(design): ..","body":"..(optional)","paths":["..."]},
 "req":   {"evidence":"..(optional, otherwise taken from the task fields)","ac":"all|AC1,AC3","ac_evidence":"..","next":".."},
 "quality": {"kind":"crosscheck|rendered|real-run|n/a","evidence":["work/T/..."],"reason":".."}}  # DONE only
```
Schema per state (only presence and type; the values are judged by workflow-check):
DESIGN design{status,path,summary}+acceptance_criteria · IMPLEMENTING implementation{status,summary,files} ·
UNIT_TESTED unit_test{status,command,result} · VERIFIED verification{status,command,result,evidence[]}+security{status,result} ·
DONE report{status} (path derived, G5) + quality. `quality` is stored as `verification.quality` (verification is already
a merge key, so MERGE_KEYS stays unchanged).

## 32.4 Gate order, `advance` (first failure stops the run, then step R restores)
0 usage/spec parse → `spec`. 1 task active, STATE is one step from the current state, or equal to it (idempotent) → `state`.
2 schema (32.3) → `spec`. 3 AC7 product checks (32.5) → `quality`.
4 snapshot the bytes of task.T.json, task.json, phase-log.md, backlog.json, linked REQ files, docs/req/{STATE.json,INDEX.md}.
5 write `work/T/advance/<STATE>.set.json` → `tasks.sh set --merge` → `set --state` → append
  `## <STATE> - <T> - <ISO8601Z>` + Action/Result/Decision/Next under `_tasks.locked`; skipped when that heading already exists.
6 `workflow-check.sh --task T` → `workflow` (first FAIL line).
7 linked REQs (frontmatter `tasks:` lists T, same regex as `_tasks.py:1137`): if `req.ac` is set, `req.py ac` runs first;
  then `req.py status R <STATE>` only when R is one step behind (equal = skip; further behind = FAIL telling you to run
  req-catchup). Evidence: spec, otherwise UNIT_TESTED `unit_test.command: result`, VERIFIED `verification.command: result`.
  At DESIGN, a pre-check that R's `## Design` is non-empty → `req` (otherwise the next step's IMPLEMENTING fails late).
8 DONE: `backlog.sh complete T` → `backlog`.
9 build the message file `work/T/advance/<STATE>.msg` (subject, body, then ONE trailer block: Task, State, then Tests |
  Verified-by | Report); paths = spec paths + design.path (DESIGN) + report.path (DONE) + REQ files + backlog.json (DONE);
  `tasks.sh commit T msg --log - -- paths` → `commit` (last 8 lines of its output are printed, unchanged).
R on any FAIL after step 4: write the snapshot bytes back (the commit undo has already unstaged). Nothing is left half-moved.
Idempotence: if task already at STATE, log heading present, REQs at STATE, nothing dirty in the paths and HEAD has
`Task: T`+`State: STATE` → `PASS (already at STATE, <sha>)`. Already at STATE but uncommitted → resume at step 6.
Dry-run: steps 0-3 for real, then 5-7 on the live files with restore ALWAYS run, printing the field diff, log heading,
REQ commands, the commit paths and the gate verdict; no git calls, never commits. (Live-then-restore because workflow-check
reads ROOT; a temp copy would miss work/ handoffs and docs.)

## 32.5 Product-quality gates (AC7, owner `_advance.py quality()`)
- VERIFIED and DONE: every `verification.evidence` path exists, is a regular file under ROOT and is non-empty → `quality`.
- DONE: `quality` is required. Unless kind is `n/a`, `evidence` must be ≥1 existing non-empty file. `n/a` needs a `reason`
  and is refused when `crosscheck_required` is true or `report`/content scope is touched (design.path or scope matches
  `examples/**`, `docs/report/**` content tables) → `FAIL [quality]: content task needs crosscheck|rendered|real-run evidence`.
- crosscheck kind: workflow-check already blocks `RESULT: MISS` (`workflow-check.sh:149-163`); advance adds nothing there.
- advance never writes `verification.status=passed` on its own: the value comes only from the spec, together with evidence.

## 32.6 `req-catchup <REQ>` (AC3)
Pre: every linked TASK is DONE (task file state, or the backlog item is `done` without a waiver) → otherwise `FAIL [req]`.
Steps cur→DONE one at a time with `req.py status` (no --force): IMPLEMENTING needs Design (FAIL names it);
UNIT_TESTED evidence = the linked task's unit_test, VERIFIED needs every AC ticked: unticked ones get
`req.py ac R all --evidence` only with `--ac-evidence`, whose text must name an existing file (report or evidence path);
otherwise FAIL listing them. Same snapshot/restore. No commit (the task may not be active anymore): it prints
`stage: <paths>` for the main session's commit.

## 32.7 Skill `advance` (≤ 40 lines, AC5) outline
When (every TASK step, and a REQ lagging behind a DONE task) · spec template per state (one short block) · gate names and
what to fix for each · dry-run first when unsure · AC7: evidence files and `quality` are never left out; `n/a` only with a
reason on a non-content task · what it does not do (no --force, no paid runs, no edits to settings/hooks).
Replace `workflow/SKILL.md:11-20` (the manual recipe) and `:50-52` (REQ stepping) with a one-line link to `advance`; keep
the fields table (`:27-34`) as the spec reference. The coordinator skill gets one link line. No duplicated text.

## 32.8 Not changed (AC6)
`.claude/settings.json`, `.claude/hooks/*`, `.claude/agent_setup.json`, `agent_setup.py`: no new block/deny/ask. The
script lives in `.claude/scripts/` (already grantable). workflow-check.sh, commit-check.sh and req.py gates stay as
they are. The one small `_tasks.py` change is under D1/D2.

## Failure modes
| Failure | Response | Operator sees |
|---|---|---|
| gate fails mid-way | restore the snapshot | `FAIL [workflow]: <line>` + `fix:` |
| commit-check refuses | tasks.sh undo + restore | `FAIL [commit]:` + the tail |
| crash between steps 5 and 9 | re-run resumes (idempotence) | `resume at workflow` |
| REQ more than one step behind | stop before any write | `FAIL [req]: run advance.sh req-catchup R` |
| restore writes outside req.py's lock | accepted: only main writes state | (risk R2) |

## Unit tests `.claude/scripts/checks/advance_test.sh` (not .claude/tests: roles may only be granted .claude/scripts/*) (temp git repo copy, same fixture as `workflow_gates_test.sh:8-31`)
1 happy path TODO→…→DONE with fixture specs: each step PASS, one commit per step with the right trailers, phase-log has
5 headings, view == task file, REQ at DONE, backlog item done. 2 one test per gate: bad spec, two-step jump, missing
schema field, missing evidence file, DONE without quality, `n/a` on a crosscheck task, workflow FAIL (e.g. no security),
REQ Design empty, commit-check refusal; each asserts exit 1, `FAIL [<gate>]`, and that the file bytes match the snapshot.
3 re-running a committed step → `PASS (already…)`, no new commit; a re-run after a commit failure resumes. 4 dry-run:
prints the plan, `git status` and all file bytes unchanged. 5 req-catchup: TODO REQ with a DONE task → DONE; refuses
without --ac-evidence; refuses when a task is not DONE. 6 `bash -n` + grep: no mapfile/declare -A. Real state is never touched.

## Verification (low tier)
| Item | Command → expected |
|---|---|
| 32.2-32.6 | `bash .claude/scripts/checks/advance_test.sh` → `PASS` summary, 0 FAIL |
| 32.8 | `git diff --stat HEAD~N -- .claude/settings.json .claude/hooks .claude/agent_setup.json` → empty |
| real use | main advances TASK-032 itself with advance.sh at IMPLEMENTING onward → PASS lines in phase-log/commits |

## Decisions
- One step per call (not multi-step) — this avoids G2 by construction; rejected: `--to DONE` jumps (one commit per transition rule).
- Live apply + restore rather than a temp-copy dry-run — workflow-check needs the real work/ and docs; rejected: re-implementing the gates.
- advance commits through `tasks.sh commit` (already has undo); rejected: printing a commit recipe (that was the toil).
- REQ Design section: pre-checked only, never written by advance (main owns docs/req bodies; req.py has no writer).

## Defects
- D1 (medium) `_tasks.py:1182-1187` cmd_commit `own` leaves out `.claude/state/backlog.json` (only `_EXTRA_OWN`, `:1571`, for autohold)
  → a DONE commit that names backlog.json fails "path(s) outside". Fix: accept backlog.json when the task's state is DONE.
- D2 (medium) `_tasks.py:1124-1138` `_req_lists` accepts REQ items and INDEX.md but not `docs/req/STATE.json`, which
  `req.py status` rewrites (`req.py:521-529`) → a REQ step left STATE.json dirty or refused. Fix: treat it like INDEX.md.
- D3 (low) `workflow/SKILL.md:15` tells you to hand-append the log while `tasks.sh commit --log` also appends → two
  recipes. Fixed by 32.7.
