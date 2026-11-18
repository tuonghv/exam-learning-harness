# Phase 150 – Delete guard, safe work cleanup, auto backup (TASK-150, REQ-0156)

**Verdict: done.** A bash `rm` can no longer wipe the repo or the data git cannot restore, for the main session or any
role; scratch cleanup has one safe script; a loss is recoverable from origin and a fresh local backup.

## Results
- Incident (RAW-00376..00378): a QA agent meant to clean `./work`; a bash `rm` deleted the repo, not recoverable.
- `.claude/hooks/delete_guard.py` (PreToolUse `Bash`, `.claude/settings.json`), live in this session:
  - allowed (RAW-00380): deletes strictly inside the repo (git restores tracked files, work/ is scratch) or /tmp;
  - denied: repo root, a parent, home, /; `./*`, `/tmp/*`; globs that can match a protected dir; plans/ reports/
    input/ results/ .git/; recursive deletes outside the repo and /tmp or with an empty/unknown `$VAR`, `$(...)`,
    loop variable, xargs input or no target; `git clean -x/-X` or without a path; inline python `rmtree` on a
    computed path. Follows `cd`, `VAR=` of the same command, `bash -c`, `sudo`/`xargs`; heredoc text is not a command.
- `.claude/scripts/clean-work.sh TASK-NNN|work/<path>` (`--dry-run`): only strictly below `work/`, symlink-safe.
  Roles (coder, designer, tester, verifier, inspector) and CLAUDE.md point to it.
- Recovery: post-commit runs `exam backup` in the background when plans/ or input/ changed after the newest backup
  (`AUTO_BACKUP=0` off); commits on `feature` are auto-pushed (TASK-149). Fresh verified backup taken today.
- Tests: 46 deny + 30 allow command cases, hook JSON, clean-work escapes; stale-backup; `--fast` KNOWN 1 NEW 0.
  Live: `rm` under reports/ denied with the reason, `rm` under work/ ran (`work/TASK-150/evidence/`).

## Limits
- A delete hidden inside a script file (`bash x.sh` that runs `rm -rf`) is not seen; the guard reads the Bash
  command only. Scripts in the repo are reviewed code; clean-work.sh is the sanctioned one.
- `main` is not auto-pushed: work on `feature` (or push main yourself) so origin always has the history.

## Spend
$0.
