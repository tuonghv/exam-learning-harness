#!/usr/bin/env bash
# Shared helpers. Source with: source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

# Resolve the target project root given this script's own directory.
# Prefers the enclosing git repo (robust regardless of nesting depth);
# falls back to the fixed .claude/scripts -> project-root layout when
# there is no git repo (e.g. a fresh, uncommitted project).
resolve_project_root() {
  local script_dir="$1" git_root
  if git_root="$(git -C "$script_dir" rev-parse --show-toplevel 2>/dev/null)"; then
    printf '%s\n' "$git_root"
  else
    (cd "$script_dir/../.." && pwd)
  fi
}

# --- shared by scripts/quality-check.sh and scripts/checks/*.sh ---
# Modules under checks/ are sourced into quality-check.sh's shell, so
# run_check/warn update its PASS/FAIL/WARN counters directly.

run_check() {
  local name="$1"; shift
  echo "[CHECK] $name"
  if "$@"; then
    echo "PASS: $name"; PASS=$((PASS + 1))
  else
    echo "FAIL: $name"; FAIL=$((FAIL + 1))
  fi
}

warn() {
  echo "WARN: $1"; WARN=$((WARN + 1))
}
