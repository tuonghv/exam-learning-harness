#!/usr/bin/env bash
# Zero-dependency heuristic tripwire for obviously hardcoded secrets
# (private keys, cloud access keys, inline password/api-key assignments).
# Not a substitute for a real scanner (gitleaks/trufflehog) - just a free,
# always-available check for the security skill. Runnable standalone or
# via quality-check.sh.
set -Eeuo pipefail
CHECK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(dirname "$CHECK_DIR")"
# shellcheck source=/dev/null  # resolved at run time; _lib.sh is checked on its own
source "$SCRIPTS_DIR/_lib.sh"
ROOT="$(resolve_project_root "$SCRIPTS_DIR")"
cd "$ROOT"

PASS=0; FAIL=0; WARN=0

pattern='-----BEGIN [A-Z ]*PRIVATE KEY-----'
pattern+='|AKIA[0-9A-Z]{16}'
pattern+='|(api|secret)[_-]?key[[:space:]]*[:=][[:space:]]*"[A-Za-z0-9/+_=-]{16,}"'
pattern+='|password[[:space:]]*[:=][[:space:]]*"[^"]{6,}"'

# Tracked files only: untracked results/ and reports/ hold findings copied from
# scanned repos, and echoing those secrets into a session is the leak itself.
hits="$(git grep -InE -e "$pattern" 2>/dev/null || true)"

if [ -n "$hits" ]; then
  echo "$hits" | head -20
  warn "possible hardcoded secret(s) above (showing up to 20) - verify before proceeding"
else
  run_check "Secret scan" true
fi

echo "SUMMARY(secrets): pass=$PASS fail=$FAIL warn=$WARN"
[ "$FAIL" -eq 0 ]
