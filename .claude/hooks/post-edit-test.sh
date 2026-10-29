#!/usr/bin/env bash
# PostToolUse on Edit|Write: fast per-file checks on the file just edited, so a
# broken script is caught at the edit, not at commit. The full suite
# (tests/run_all.sh) is slow and belongs to the UNIT_TESTED transition.
#   *.sh              bash -n + shellcheck -x (repo .shellcheckrc applies)
#   *.py              py_compile (+ ruff if installed)
#   .claude/state/*.json  must stay valid JSON
# Exit 2 feeds the failure back to Claude; anything else is a no-op.
set -uo pipefail
file="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))' 2>/dev/null)"
[ -n "$file" ] && [ -f "$file" ] || exit 0
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT" || exit 0

case "$file" in
  *.sh)
    out="$(bash -n "$file" 2>&1)" || { echo "bash -n failed for $file:" >&2; echo "$out" >&2; exit 2; }
    if command -v shellcheck >/dev/null 2>&1; then
      out="$(shellcheck -x "$file" 2>&1)" || { echo "shellcheck failed for $file:" >&2; echo "$out" | head -40 >&2; exit 2; }
    fi
    ;;
  *.py)
    out="$(python3 -m py_compile "$file" 2>&1)" || { echo "py_compile failed for $file:" >&2; echo "$out" >&2; exit 2; }
    if command -v ruff >/dev/null 2>&1; then
      out="$(ruff check -q "$file" 2>&1)" || { echo "ruff failed for $file:" >&2; echo "$out" | head -40 >&2; exit 2; }
    fi
    ;;
  */.claude/state/*.json)
    out="$(python3 -m json.tool "$file" 2>&1 >/dev/null)" || { echo "invalid JSON in $file: $out" >&2; exit 2; }
    ;;
esac
exit 0
