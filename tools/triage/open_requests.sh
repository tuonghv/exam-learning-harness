#!/usr/bin/env bash
# open_requests.sh - OPEN_REQUESTS for inbox-triage (phase 71): one "REQ-NNNN | toolkit | <title>"
# line per open ReqKit requirement, from ReqKit's own query (`req.py list --active`).
# Env: TRIAGE_REQ_CMD (default "python3 <repo>/.claude/req/req.py"); REQ_DIR is passed through.
set -euo pipefail
cd "$(dirname "$0")/../.."
cmd="${TRIAGE_REQ_CMD:-python3 .claude/req/req.py}"
# list line: "REQ-0028  IMPLEMENTING EPIC-001  AC 0/7  <title>" (EPIC column is "-" when none)
$cmd list --active | sed -nE 's/^(REQ-[0-9]+)[[:space:]]+[A-Z_]+[[:space:]]+(EPIC-[0-9]+|-)[[:space:]]+AC [0-9]+\/[0-9]+[[:space:]]+(.*)$/\1 | toolkit | \3/p'
