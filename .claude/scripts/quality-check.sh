#!/usr/bin/env bash
# Deterministic lint/format/test runner. Runs every module under checks/
# (each self-detects whether it applies: go.mod, package.json, *.py, *.sh,
# Makefile, or - for secrets.sh - always) and reports overall pass/fail.
# Distinct from workflow-check.sh, which validates task.json/phase-log
# state instead of code.
#
# A single language's skill (bash/python/golang) should run its own
# checks/<lang>.sh directly instead of this - smaller, targeted output.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

fail=0
for module in "$SCRIPT_DIR"/checks/*.sh; do
  "$module" || fail=1
done

exit "$fail"
