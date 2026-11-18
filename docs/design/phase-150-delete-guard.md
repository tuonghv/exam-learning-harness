# Phase 150 – Delete guard, safe work cleanup, auto backup (TASK-150, REQ-0156)

Source: REQ-0156 (RAW-00376/00377: a QA agent deleted the repo while cleaning `./work`; RAW-00378: it was a bash
`rm`; RAW-00379: user approved the new block; RAW-00380: protect rm in general, deletes inside the repo and temp
folders stay normal, the unrecoverable loss is what must not happen).

## Plan modes
No change to single-source or pipeline plans; agent tooling and git hook only.

## Design
- 150.1 `.claude/hooks/delete_guard.py` (stdlib), PreToolUse matcher `Bash`, registered in `.claude/settings.json`
  next to agent_setup.py, so it covers the main session and every role. Deny = hook JSON
  `permissionDecision: deny` + reason naming the safe way. Never raises: a guard bug allows (logged on stderr) except
  for an unparseable command that contains a delete word, which is denied.
- 150.2 Parse: split the command on unquoted `; & | && || newline`, keep heredoc bodies with their command,
  `shlex.split` each simple command; follow `cd`/`pushd` and `NAME=value` assignments of the same command; skip
  `sudo env command nohup time nice timeout xargs` prefixes; recurse into `bash|sh -c '...'`.
- 150.3 Targets (RAW-00380: deleting inside the repo or a temp folder is normal; an unrecoverable loss is the
  incident): `$VAR`, `${VAR}`, `$PWD`, `$HOME`, `~` expanded from the tracked assignments; a glob is checked by its
  directory and its first pattern component; path = realpath(cwd + target).
  - Allowed: strictly inside the repo (git restores tracked files; work/ is scratch) or strictly inside /tmp
    (scratchpad); prefixed globs there (`/tmp/exam_*`, `build*`) too.
  - Denied: the repo root, a parent, home, /; a bare glob over the repo root or /tmp (`./*`, `/tmp/*`); a glob that
    can match a protected dir (`p*`); anything under plans/ reports/ input/ results/ .git/ (git-ignored or git
    data, not restorable); recursive deletes outside the repo and /tmp; recursive deletes with an unresolved
    variable / `$(...)` / loop variable, xargs input or no target; `git clean -x/-X`, `git clean -f` without a path;
    inline python `shutil.rmtree` on a computed path. `find -delete|-exec rm` is recursive on its roots.
  - Plain `rm`/`rmdir`/`unlink` with an unresolved variable stays allowed (one file).
- 150.4 `.claude/scripts/clean-work.sh <TASK-NNN|work/path>`: bash 3.2, resolves with `pwd -P`, refuses anything not
  strictly below `<repo>/work/`, then `rm -rf --`. Roles (coder, tester, verifier, inspector, designer) get one line
  pointing to it; CLAUDE.md "Never break" gets the rule.
- 150.5 Recovery: `post_commit_check.py --stale-backup` (exit 0 when the newest file under `plans/` or `input/` is newer
  than the newest `~/exam-harness-backup/exam-inputs-*.tar.gz`); the post-commit hook then runs `exam backup` in the
  background (log `<git-dir>/autobackup.log`, `AUTO_BACKUP=0` off). Auto-push of non-main branches: TASK-149.

## Verification
Unit tests feed the hook JSON with the incident shapes (`rm -rf "$W"/*` with W unset, `cd work/X && rm -rf ../..`,
`rm -rf ./*`, `rm -rf .`, `find . -delete`, `git clean -fdx`, `python3 -c "shutil.rmtree(p)"`, `bash -c 'rm -rf ~'`)
-> deny; `rm -rf work/TASK-1/x`, `S=/tmp/..; rm -rf $S/a`, heredoc text with `rm -rf /` -> allow. Real: the hook is
live in this session; a denied and an allowed real call are recorded.
