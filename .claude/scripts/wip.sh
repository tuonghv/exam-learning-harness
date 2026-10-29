#!/usr/bin/env bash
# One-call task commit (TASK-098 98.1): message + trailers + optional state move + tasks.sh commit.
#   wip.sh <T> "<subject>" [--state S] [--body B] [--tests "<cmd -> result>"] [--verified-by X]
#          [--report P] [--area A] -- <paths>
# Prints `COMMITTED <sha7> <T> <S>` or the FAIL lines; on FAIL the state move is undone.
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${TASKS_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
TASKS="$SCRIPT_DIR/tasks.sh"

usage() {
  echo 'usage: wip.sh <TASK-N> "<subject>" [--state S] [--body B] [--tests T] [--verified-by X] [--report P] [--area A] -- <paths>' >&2
  exit 2
}

[ $# -ge 2 ] || usage
T="$1"; SUBJ="$2"; shift 2
case "$T" in TASK-[0-9]*) ;; *) usage ;; esac
STATE=""; BODY=""; TESTS=""; VBY=""; REPORT=""; AREA="workflow"
while [ $# -gt 0 ]; do
  case "$1" in
    --) shift; break ;;
    --state|--body|--tests|--verified-by|--report|--area)
      [ $# -ge 2 ] || usage
      case "$1" in
        --state) STATE="$2" ;; --body) BODY="$2" ;; --tests) TESTS="$2" ;;
        --verified-by) VBY="$2" ;; --report) REPORT="$2" ;; --area) AREA="$2" ;;
      esac
      shift 2 ;;
    *) usage ;;
  esac
done

TF="$ROOT/.claude/state/task.$T.json"
[ -f "$TF" ] || { echo "FAIL: $T is not an active task"; exit 1; }
cur="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("state",""))' "$TF")"
S="${STATE:-$cur}"

WD="$ROOT/work/$T"
mkdir -p "$WD"
MSG="$WD/wip-msg.txt"; LOG="$WD/wip-log.md"
case "$SUBJ" in
  [a-z]*:\ *|[a-z]*\(*\):\ *) HEAD="$SUBJ" ;;
  *) HEAD="wip($AREA): $T $SUBJ" ;;
esac
{
  printf '%s\n\n' "$HEAD"
  [ -z "$BODY" ] || printf '%s\n\n' "$BODY"
  printf 'Task: %s\nState: %s\n' "$T" "$S"
  [ -z "$TESTS" ] || printf 'Tests: %s\n' "$TESTS"
  [ -z "$VBY" ] || printf 'Verified-by: %s\n' "$VBY"
  [ -z "$REPORT" ] || printf 'Report: %s\n' "$REPORT"
  printf 'Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\n'
} > "$MSG"

SAVED=""
if [ -n "$STATE" ]; then
  SAVED="$(mktemp)"; trap 'rm -f "$SAVED"' EXIT
  cp "$TF" "$SAVED"
  out="$("$TASKS" set "$T" --state "$STATE" 2>&1)" || { printf '%s\n' "$out" | head -n 8; exit 1; }
  {
    printf '## %s - %s - %s\n\n' "$STATE" "$T" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'Action: %s\nResult: %s\n' "$SUBJ" "${BODY:-state $cur -> $STATE}"
  } > "$LOG"
  LOGARG="$LOG"
else
  LOGARG="-"
fi

rc=0
out="$("$TASKS" commit "$T" "$MSG" --log "$LOGARG" -- "$@" 2>&1)" || rc=$?
if [ "$rc" -ne 0 ]; then
  if [ -n "$SAVED" ]; then cp "$SAVED" "$TF"; "$TASKS" sync >/dev/null 2>&1 || true; fi
  printf '%s\n' "$out" | head -n 8
  exit 1
fi
sha="$(git -C "$ROOT" rev-parse --short=7 HEAD)"
echo "COMMITTED $sha $T $S"
