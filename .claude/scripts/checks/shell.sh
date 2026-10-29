#!/usr/bin/env bash
# Shell: shellcheck + syntax check on every tracked *.sh file. Runnable work/ (scratch evidence and bench scripts) is excluded (user, 2026-10-06).
# standalone (e.g. from the bash skill) or via quality-check.sh.
set -Eeuo pipefail
CHECK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(dirname "$CHECK_DIR")"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPTS_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPTS_DIR")"
cd "$ROOT"

PASS=0; FAIL=0; WARN=0

if find . -name '*.sh' -not -path './.git/*' -not -path './work/*' -print -quit | grep -q .; then
  if command -v shellcheck >/dev/null 2>&1; then
    while IFS= read -r f; do
      # -x: follow `source ./config.sh` etc. (paths are relative to ROOT, the cwd)
      run_check "ShellCheck $f" shellcheck -x "$f"
    done < <(find . -name '*.sh' -not -path './.git/*' -not -path './work/*')
  else
    warn "shellcheck not installed"
  fi

  while IFS= read -r f; do
    run_check "Bash syntax $f" bash -n "$f"
  done < <(find . -name '*.sh' -not -path './.git/*' -not -path './work/*')
fi

# 96.14: every reader of task.json uses the per-task resolver or is listed with a reason
run_check "Task readers inventory" bash "$CHECK_DIR/task_readers.sh" "$ROOT"

echo "SUMMARY(shell): pass=$PASS fail=$FAIL warn=$WARN"
[ "$FAIL" -eq 0 ]
