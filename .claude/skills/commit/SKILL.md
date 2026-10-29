---
name: commit
description: How and when to commit in this workflow, and the deterministic gate to run first. Use whenever you finish a phase transition (DESIGN, IMPLEMENTING, UNIT_TESTED, VERIFIED, DONE), are about to write a commit message, or need history to stay the audit trail alongside task.json. Git is the trace; task.json is current state.
---

# Commit

`task.json` holds current state; git holds history. Commit at each phase
transition so a later session can reconstruct what happened from
`git log`, not from conversation memory (CLAUDE.md rules 8–10).

## When to commit

One commit per phase transition, made right after `workflow-check.sh` passes
for the new state and the `phase-log.md` entry is written:

| After reaching | Commit contains |
|---|---|
| `DESIGN` | the design doc + `task.json` (design.status=completed) + phase-log |
| `IMPLEMENTING`→`UNIT_TESTED` | code, tests, `task.json`, phase-log |
| `VERIFIED` | `task.json` (verification evidence) + phase-log |
| `DONE` | the report + `task.json` (report.path) + phase-log + `backlog.json` (after `backlog.sh complete`) |
| rollback to `IMPLEMENTING` (verify failed) | `task.json` + phase-log, before any fix code (`State: IMPLEMENTING`) |
| `blocked` set/cleared | `task.json` + phase-log, `State:` = the unchanged state |

Bookkeeping (skill/script/template edits, backlog grooming) commits without
`Task:`/`State:` trailers — and without `Tests:` (the gate warns on it with no
`Task:`); put the test result in the body instead.

Architecture stays current (user, RAW-00299): a commit that changes the engine flow (a step, script owner,
default, cost, artifact path, or a chosen standard / decision such as REQ-0037's) updates
`docs/guide/architecture.md` in the same commit: the flow diagram, step table, "Where artifacts live", and the
"Chosen standard" section with the options compared, the verdict and the evidence path. Without that edit,
say in the commit body why the flow did not change.

Requirement ledger (`docs/req/`): stage the REQ/EPIC/RAW files a transition
changed in that same commit, plus `INDEX.md`. RAW captures of prompts that were
only instructions (`raw ignore`) ride along in the next commit of any kind.

## Gate every commit — write the message to a file, check, then commit

```bash
f="$(mktemp)"
cat > "$f" <<'EOF'
feat(api): add customer filter endpoint

Implements the nested-JSON lookup from the design.

Task: TASK-002
State: UNIT_TESTED
Tests: node --test test/unit (12 passed)
Co-Authored-By: <attribution, if any>
EOF
.claude/scripts/commit-check.sh "$f" && git commit -q -F "$f"
```

Keep the `&&`: when saving its output, write `commit-check.sh "$f" > out && git commit ...`, never
`> out; ... git commit` (TASK-069: a `;` chain committed a transition after FAIL).

Never commit a phase transition without `commit-check.sh` passing first. Run it
after `git add`, so it sees the real staged set. On a `Task:` commit it fails if
anything under `.claude/state`, `docs/design` or `docs/report` is changed but
unstaged — `workflow-check.sh` judged the working tree, so the commit must hold
exactly that tree.

If `git commit` itself fails after the gate passed, the transition is not
recorded: fix the cause and commit again in the same turn. Confirm with
`git status --porcelain -- .claude/state` (empty) before reporting the phase
as done. The Stop hook blocks a turn that ends with it dirty.

## Message format

```
<type>(<scope>): imperative summary under ~60 chars

why, 1–2 lines; git already shows what

Task: TASK-002
State: UNIT_TESTED
Tests: <command> (<result>)
```

Types: `feat` `fix` `test` `refactor` `docs` `chore`. Trailers form one block
after a blank line (no blank line inside it, attribution last). git only
parses the **last** paragraph as trailers: a blank line before
`Co-Authored-By:` hides `Task:`/`State:` from every check, so
`commit-check.sh` fails a message whose workflow keys were not parsed.

- `Task:` the task.json `task_id`; `State:` the state **after** this commit.
  With several active tasks (REQ-0060) `Task:` picks the task: the gate checks
  `task.<TASK>.json` (stage it, bump its `updated_at`) and fails when another
  task's `task.<U>.json` is staged — one task per commit.
- `Tests:` command + result — required at `UNIT_TESTED`; put it and `Verified-by:` in the one contiguous trailer block of the first message (TASK-125).
- `Verified-by:` real-run command + observed result — required at `VERIFIED`.
- `Report:` report path — required at `DONE`.

## What the gate enforces (the `commit-check.sh` header owns the detail)

`.claude/scripts/commit-check.sh <msgfile>` runs `workflow-check.sh` (the state
being committed must be valid), blocks forbidden/secret files in the staged
diff, requires `task.json` staged with a `state` that **matches** the `State:`
trailer (the cross-session status-drift guard), and checks the evidence trailer
for the state. It checks form and consistency, not truth: that the listed tests
really ran is on you.

Find what happened to a task: `git log --grep="Task: TASK-002"`.
