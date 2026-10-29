#!/usr/bin/env bash
# Node: run lint/test/typecheck package.json scripts when they exist.
# Runnable standalone or via quality-check.sh.
set -Eeuo pipefail
CHECK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(dirname "$CHECK_DIR")"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPTS_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPTS_DIR")"
cd "$ROOT"

PASS=0; FAIL=0; WARN=0

if [ -f package.json ]; then
  if command -v npm >/dev/null 2>&1 && command -v node >/dev/null 2>&1; then
    has_npm_script() {
      node -e "process.exit((require('./package.json').scripts||{})['$1']?0:1)" 2>/dev/null
    }
    has_npm_script lint && run_check "npm lint" npm run lint
    has_npm_script test && run_check "npm test" npm test
    has_npm_script typecheck && run_check "npm typecheck" npm run typecheck
  else
    warn "node/npm not installed"
  fi
fi

echo "SUMMARY(node): pass=$PASS fail=$FAIL warn=$WARN"
[ "$FAIL" -eq 0 ]
