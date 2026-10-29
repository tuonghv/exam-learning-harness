#!/usr/bin/env bash
# Run one check and save its output as verifier evidence:
#   .claude/scripts/save-evidence.sh <name> -- <cmd> [args...]
# writes work/<TASK>/evidence/<name>.txt = header (task, cmd, cwd, HEAD, time, rc) + the
# combined stdout/stderr, prints a one-line summary and the last 10 output lines, and exits
# with the command's rc. TASK defaults to .claude/state/task.json task_id. Pipes need
# `bash -c '...'`. The verifier role has no Bash: it judges only what is saved here.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPT_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPT_DIR")"

usage() { echo "usage: save-evidence.sh <name> -- <cmd> [args...]" >&2; exit 2; }
if [ "$#" -lt 3 ] || [ "$2" != "--" ]; then usage; fi
name="$1"; shift 2
[[ "$name" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "bad evidence name: $name" >&2; exit 2; }

tid="${TASK:-${CTXGUARD_TASK:-}}"
if [ -z "$tid" ] && [ "$(TASKS_ROOT="$ROOT" python3 "$SCRIPT_DIR/_tasks.py" mode)" = multi ]; then
  # REQ-0060: the view's focus is not a safe default when several tasks are active.
  act="$(TASKS_ROOT="$ROOT" python3 "$SCRIPT_DIR/_tasks.py" active)"
  if [ "$(printf '%s\n' "$act" | grep -c .)" -eq 1 ]; then tid="$act"
  else echo "several active tasks: set TASK=<id> (or CTXGUARD_TASK)" >&2; exit 2; fi
fi
if [ -z "$tid" ]; then
  tid="$(jq -r '.task_id // empty' "$ROOT/.claude/state/task.json" 2>/dev/null || true)"
fi
[[ "$tid" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "no task id: set TASK=<id> or pick a task" >&2; exit 2; }

dir="$ROOT/work/$tid/evidence"
out="$dir/$name.txt"
mkdir -p "$dir"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

rc=0
"$@" >"$tmp" 2>&1 || rc=$?

head_sha="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo none)"
if [ -n "$(git -C "$ROOT" status --porcelain 2>/dev/null)" ]; then head_sha="$head_sha+dirty"; fi
{
  echo "# evidence: $name"
  echo "# task: $tid"
  printf '# cmd:'; printf ' %q' "$@"; echo
  echo "# cwd: $PWD"
  echo "# head: $head_sha"
  echo "# when: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# rc: $rc"
  echo "---"
  cat "$tmp"
} >"$out"

echo "saved ${out#"$ROOT"/} rc=$rc lines=$(wc -l <"$tmp" | tr -d ' ')"
tail -n 10 "$tmp"
exit "$rc"
