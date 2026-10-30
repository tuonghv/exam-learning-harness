#!/usr/bin/env bash
# One gated TASK step (REQ-0037, phase 32): set fields from a spec, phase-log entry, view sync, REQ steps,
# workflow-check, commit through the gate. Prints PASS or the first failing gate. Logic lives in _advance.py.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") <TASK-N> <STATE> --spec work/<TASK-N>/advance-<STATE>.json [--dry-run]
  $(basename "$0") req-catchup <REQ-N> [--ac-evidence "<text naming an existing file>"] [--dry-run]
Exit 0 = PASS, 1 = first failing gate (FAIL [gate] + fix:), 2 = usage. Skill: advance.
EOF
  exit 2
}

[ $# -ge 1 ] || usage
case "$1" in
  -h|--help) usage ;;
esac
exec python3 "$SCRIPT_DIR/_advance.py" "$@"
