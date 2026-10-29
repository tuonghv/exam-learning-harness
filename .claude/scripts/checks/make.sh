#!/usr/bin/env bash
# Fallback for anything with a Makefile `check` target. Runnable standalone
# or via quality-check.sh.
set -Eeuo pipefail
CHECK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(dirname "$CHECK_DIR")"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPTS_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPTS_DIR")"
cd "$ROOT"

PASS=0; FAIL=0; WARN=0

if [ -f Makefile ] && grep -qE '^check:' Makefile; then
  if command -v make >/dev/null 2>&1; then
    run_check "make check" make check
  else
    warn "make not installed"
  fi
fi

echo "SUMMARY(make): pass=$PASS fail=$FAIL warn=$WARN"
[ "$FAIL" -eq 0 ]
