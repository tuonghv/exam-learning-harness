---
name: bash
description: Bash standards and pitfalls for this repo - the whole toolkit (scan_batch.sh, auto_scan.sh, *_common.sh, report scripts), its tests/*_test.sh harness, and the .claude hooks/scripts. Use when writing, changing, testing or reviewing any *.sh file here.
---

# Bash

Use:
set -Eeuo pipefail

Prefer:
- functions
- quoted variables
- explicit arguments
- meaningful exit codes
- cleanup traps
- shellcheck-compatible code

Avoid:
- unquoted variables
- eval unless strictly justified
- parsing ls
- silent failures
- unnecessary subshells

## This repo

- **bash 3.2 (macOS):** no `mapfile`/`readarray`, no associative arrays, no
  `${var,,}`; initialise every array (`FOO=()`) because `set -u` is on.
- **Portable tools:** BSD + GNU `date`/`sed`/`stat` differ — reuse the helpers
  in `scheduler_common.sh` instead of calling them with GNU-only flags.
- **Embedded Python/jq:** pass values as argv (`python3 - "$f" <<'PY'`,
  `jq --arg`), never interpolate a path or value into the program text; quote
  the heredoc delimiter so the shell expands nothing inside it.
- **State files** (`manifest.json`, `.claude/state/*.json`): write via
  `tmp && mv`, and only from the owner named in docs/guide/toolkit-reference.md (invariant #4).
- **Sourced files** (`config.sh`, `*_common.sh`, `scan_excludes.sh`): keep them
  free of top-level side effects so a test can source them and call one
  function.
- **Scripted edits:** when patching a file from a script, assert each anchor
  matches exactly once before replacing (a silent zero-match edit is a bug).
  If the patch text itself contains a heredoc, use a delimiter that cannot
  occur inside it (`<<'PATCH_EOF'`, not `<<'PY'`): an early terminator makes
  the shell execute the rest of the text as commands. Prefer the Edit tool
  for multi-line changes to scripts that embed heredocs.

## Pitfalls hit in this repo (phases 10–18)

- **`pkill -f <pattern>` kills your own shell** when the pattern appears in
  your command line (exit 144, seen twice). Kill by the pid you recorded
  (`BG+=("$!")`), or with `pgrep` and a filter that excludes `$$`.
- **`while pgrep -f <pat>` never ends** when the loop's own shell command line holds `<pat>`
  (TASK-044: two wait loops slept 8 h). Wait on the job itself: `run_in_background` and its
  completion notice, or `wait <pid>` / `until [ -e <done-file> ]`, and give every wait a deadline.
- **Timezones:** `TZ=""` means UTC to both Python and `date`, not "local". Leave
  `TZ` unset when no zone is given. Validate a zone name against a regex and
  `/usr/share/zoneinfo/$z` before you use it (`_zone_ok`). Compute wall-clock epochs
  in one helper (`clock_epoch`), with both BSD `date -j -f` and GNU `date -d`.
- **jq on model or CLI output:** a field may be a string, an object or null.
  Use `if type=="string" then . else tojson end`; string concatenation
  either errors or prints `null` (phase 16).
- **grep patterns that contain `'`** (for example "You've"): double-quote the ERE and keep
  it anchored to phrases. An exit-0 answer is a security report, so its words are never
  control signals (only match when claude failed).
- **`grep -q` under `pipefail`** can SIGPIPE the writer and flip the result.
  Capture the output in a variable first, then use `printf '%s' "$out" | grep -q`.
- **`wait` with no args** also waits for unrelated background jobs (a `sleep`
  that stands in for a pid, for example). Wait on the pids you collected.
- **New exit codes are an interface.** A distinct meaning (11 = busy) needs its
  own `case` branch in every caller (`auto_scan.sh`), plus the header comment,
  docs/guide/toolkit-reference.md and the runbook.

- **jq traps (phases 27-28):** `$as` is a reserved word (use `$AS`); a filter parameter is
  `def f(g)`, not `$g`; a stream inside `"x" + (...)` must be collected first
  (`[...] | join("")`); `A | . as $x | B` binds over the whole rest, so bracket it.

- **jq traps (phase 32):** `first(empty) as $x` binds nothing, so the rest of the program
  silently yields nothing. Use `(first(...) // null) as $x`. jq without `-n` and with no
  input file waits on stdin, which hangs a test helper. Use `jq -n` for pure constructions.
  `cond && mv` after jq trips SC2015. Put the `mv` on its own line.

## Tests (tests/*_test.sh harness)

- One suite per behaviour area, `expect <name> <rc> <substr> <cmd…>` style
  (template: `.claude/tests/workflow_gates_test.sh`), fixtures in `mktemp -d`
  with a `trap … EXIT` cleanup, never the real `manifest.json`/`results/`/
  `.claude/state`. End with `SUMMARY(<suite>): pass=N fail=M` and exit non-zero
  on any failure; `tests/run_all.sh` relies on both.
- Under `set -e`, every fixture helper must succeed or the suite dies
  silently mid-way (a bare `git commit` with nothing staged did this: use
  `--allow-empty`). Only the command under test may fail, inside `expect`.
- Some suites sleep on purpose (blocking_loop, lock_guard): iterate with
  `tests/run_all.sh <name>` (use `run_in_background` for the full run), and
  run the whole set once before UNIT_TESTED.
- Prove each new case bites: run it against `git archive HEAD` of the old
  scripts and record how many fail (`unit-test` skill).

## Claude Code hooks (.claude/hooks/*.sh)

- Input is JSON on stdin (`tool_input.file_path`, `stop_hook_active`); parse
  it with `python3 -c`/`jq`, tolerate empty or bad input.
- Exit 2 = block and feed stderr back to Claude; exit 0 = allow (stdout goes
  into context only for SessionStart/UserPromptSubmit). Any other code is a
  non-blocking hook error Claude never acts on, so never let `set -e` produce one.
- A blocking Stop hook must honour `stop_hook_active` or it can loop.
- Keep hooks fast (they run on every edit/turn): per-file checks only, never
  `tests/run_all.sh`. Resolve the repo with `$CLAUDE_PROJECT_DIR`.
- Every hook change gets a case in `.claude/tests/workflow_gates_test.sh`.

## Static checks

The post-edit hook runs `bash -n` + `shellcheck -x` on each edited file.
Before UNIT_TESTED run `.claude/scripts/checks/shell.sh` (bash -n + shellcheck
on every *.sh file). The repo is shellcheck-clean (phase 4): `fail=0` is required, not a
diff against a baseline. Fix the finding; if it is a false positive, silence
it with a line-level `# shellcheck disable=SCxxxx  # <reason>`. Add a code to
`.shellcheckrc` only when it is idiomatic for the whole codebase (today:
SC2016 for single-quoted jq/awk programs).
