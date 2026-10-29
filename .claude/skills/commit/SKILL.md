---
name: commit
description: How and when to commit in this workflow, and the deterministic gate to run first. Use whenever you finish a phase transition (DESIGN, IMPLEMENTING, UNIT_TESTED, VERIFIED, DONE), are about to write a commit message, or need history to stay the audit trail alongside task.json. Git is the trace; task.json is current state.
---

# Commit

`task.json` holds current state; git holds history. One commit per phase transition, made right after
`workflow-check.sh` passes and the `phase-log.md` entry is written.

| After reaching | Commit contains |
|---|---|
| `DESIGN` | design doc + `task.json` + phase-log |
| `IMPLEMENTING`→`UNIT_TESTED` | code, tests, `task.json`, phase-log |
| `VERIFIED` | `task.json` (verification evidence) + phase-log |
| `DONE` | report + `task.json` + phase-log + `backlog.json` (after `backlog.sh complete`) |
| rollback to `IMPLEMENTING` | `task.json` + phase-log, before any fix (`State: IMPLEMENTING`) |
| `blocked` set/cleared | `task.json` + phase-log, `State:` = the unchanged state |

Bookkeeping (skill/script/template edits, backlog grooming) commits without `Task:`/`State:`/`Tests:`
trailers; put the test result in the body. Stage the `docs/req` files a transition changed in the same commit.

## Gate: write the message to a file, check, then commit

```bash
f="$(mktemp)"
cat > "$f" <<'EOF'
feat(exam): add chapter 3 quiz set

Why, 1-2 lines.

Task: TASK-002
State: UNIT_TESTED
Tests: python3 -I tools/examples/check.py (12 passed)
Co-Authored-By: <attribution, if any>
EOF
.claude/scripts/commit-check.sh "$f" && git commit -q -F "$f"
```

- Keep the `&&`. Never pipe the gate into `tail`/`head` and never chain with `;`: the commit would land after a
  FAIL. To save its output: `commit-check.sh "$f" > out && git commit ...`.
- Run it after `git add`, so it sees the real staged set. On a `Task:` commit it fails if anything under
  `.claude/state`, `docs/design` or `docs/report` is changed but unstaged.
- If `git commit` fails after the gate passed, fix and commit again in the same turn; confirm
  `git status --porcelain -- .claude/state` is empty. The Stop hook blocks a turn that ends with it dirty.

## Message format

`<type>(<scope>): imperative summary under ~60 chars`, then 1-2 lines of why. Types: `feat` `fix` `test`
`refactor` `docs` `chore`. Trailers form one contiguous block after a blank line, attribution last: git parses
only the last paragraph, so a blank line before `Co-Authored-By:` hides `Task:`/`State:` from the gate.

- `Task:` the `task_id` (one task per commit). `State:` the state after this commit.
- `Tests:` command + result, required at `UNIT_TESTED`. `Verified-by:` real-run command + result, required at
  `VERIFIED`. `Report:` report path, required at `DONE`.

The gate (`commit-check.sh`) runs `workflow-check.sh`, blocks secret files, requires `task.json` staged with a
`state` matching `State:`, and checks the evidence trailer. It checks form, not truth: that the tests ran is on you.
Find a task's history: `git log --grep="Task: TASK-002"`.
