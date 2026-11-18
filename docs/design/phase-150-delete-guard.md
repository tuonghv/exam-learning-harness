# Phase 150 – Delete guard, safe work cleanup, auto backup (TASK-150, REQ-0156)

Source: REQ-0156 (RAW-00376/00377: a QA agent deleted the repo while cleaning `./work`; RAW-00378: it was a bash
`rm`; RAW-00379: user approved the new block).

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
- 150.3 Targets: `$VAR`, `${VAR}`, `$PWD`, `$HOME`, `~` expanded from the tracked assignments (unknown var ->
  unresolved); a glob is checked by its directory before the first glob char; path = realpath(cwd + target).
  Allowed roots: `<repo>/work/` (strictly inside, `work` itself refused), `/tmp/` (strictly inside; the session
  scratchpad lives there).
  - Recursive delete (`rm -r/-R/--recursive`, `rmdir`, `find ... -delete|-exec rm`, `git clean`, inline python
    `shutil.rmtree(...)`): every target must be inside an allowed root; unresolved var, no target, or `xargs` input
    -> deny. `git clean` with `-x`/`-X` always denied.
  - Plain `rm` (files): deny targets under `plans/ reports/ input/ results/ .git/ .claude/state/`, the repo root
    itself or above, and unresolved vars; other tracked files stay allowed (git restores them).
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
