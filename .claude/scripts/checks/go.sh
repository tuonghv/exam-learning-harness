#!/usr/bin/env bash
# Go: tests, format, vet. Runnable standalone (e.g. from the golang skill)
# or via quality-check.sh.
set -Eeuo pipefail
CHECK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(dirname "$CHECK_DIR")"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPTS_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPTS_DIR")"
cd "$ROOT"

PASS=0; FAIL=0; WARN=0

if [ -f go.mod ]; then
  if command -v go >/dev/null 2>&1; then
    run_check "Go tests" go test ./...
    run_check "Go vet" go vet ./...
  else
    warn "go not installed"
  fi

  if command -v gofmt >/dev/null 2>&1; then
    run_check "Go format" bash -c 'test -z "$(gofmt -l .)"'
  else
    warn "gofmt not installed"
  fi
fi

echo "SUMMARY(go): pass=$PASS fail=$FAIL warn=$WARN"
[ "$FAIL" -eq 0 ]
