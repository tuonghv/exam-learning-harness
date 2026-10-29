#!/usr/bin/env bash
# Python: syntax, lint, tests. Runnable standalone (e.g. from the python
# skill) or via quality-check.sh, which runs every checks/*.sh module.
set -Eeuo pipefail
CHECK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(dirname "$CHECK_DIR")"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPTS_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPTS_DIR")"
cd "$ROOT"

PASS=0; FAIL=0; WARN=0

if command -v python3 >/dev/null 2>&1; then
  run_check "Python syntax" python3 -m compileall -q -x '(^|/)tests/fixtures/' .
else
  warn "python3 not installed"
fi

if find . -name '*.py' -not -path './.git/*' -print -quit | grep -q .; then
  if command -v ruff >/dev/null 2>&1; then
    run_check "Ruff" ruff check --extend-exclude tests/fixtures .
  else
    warn "ruff not installed"
  fi
  # pytest exits 5 when it collects nothing; no tests is not a failing test.
  if ! find . \( -name 'test_*.py' -o -name '*_test.py' \) -not -path './.git/*' -not -path './tests/fixtures/*' -print -quit | grep -q .; then
    warn "no pytest tests found"
  elif command -v pytest >/dev/null 2>&1; then
    run_check "Pytest" python3 -m pytest --ignore=tests/fixtures
  else
    warn "pytest not installed"
  fi
fi

echo "SUMMARY(python): pass=$PASS fail=$FAIL warn=$WARN"
[ "$FAIL" -eq 0 ]
