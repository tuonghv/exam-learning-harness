#!/usr/bin/env bash
# TASK-098 F5: Stop hook warns (not blocks) on an uncommitted task.<T>.json whose lead_at is <= 15 min old.
# Applies work/TASK-098/patches/04-stopcheck-live-lead.py to a scratch copy of the hook only while it lacks
# the marker (a no-op once main applied it). PATCH_OFF=1 skips the patch (bite run). The scratch dir has no
# repo: a stub `git` on PATH reports the dirty list. Never touches the real repo.
set -Eeuo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(dirname "$KIT")"
PATCH="$ROOT/work/TASK-098/patches/04-stopcheck-live-lead.py"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); printf '%s\n' "$2" | sed 's/^/    /'; }

KP="$WORK/kit"; mkdir -p "$KP/hooks" "$WORK/bin"
cp "$KIT/hooks/stop-check.sh" "$KP/hooks/"
if [ "${PATCH_OFF:-0}" != 1 ]; then
  if ! grep -qF "TASK-098 fresh lead_at" "$KP/hooks/stop-check.sh"; then
    python3 "$PATCH" "$KP" >/dev/null
  fi
  again="$(python3 "$PATCH" "$KP")"
  if [ "$again" = "already patched $KP/hooks/stop-check.sh" ]; then ok "patch idempotent"; else bad "patch idempotent" "$again"; fi
fi

cat > "$WORK/bin/git" <<'GIT_EOF'
#!/bin/sh
case "$*" in
  *rev-parse*) exit 0 ;;
  *status*) case "$*" in *.claude/state*) cat "$DIRTY" 2>/dev/null || true ;; esac ;;
esac
exit 0
GIT_EOF
chmod +x "$WORK/bin/git"

ago() { python3 -c 'import sys,time;print(time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(time.time()-int(sys.argv[1]))))' "$1"; }

fresh() { # fresh <dir> <lead_at|none>
  local d="$1"; rm -rf "$d"; mkdir -p "$d/.claude/hooks" "$d/.claude/state"
  cp "$KP/hooks/stop-check.sh" "$d/.claude/hooks/"
  printf '{"state":"IMPLEMENTING"}\n' > "$d/.claude/state/task.json"
  printf '{"task_id":"TASK-2","state":"IMPLEMENTING","checkpoint":{"next":"x"}}\n' > "$d/.claude/state/task.TASK-2.json"
  if [ "$2" = none ]; then
    printf '{"task_id":"TASK-1","state":"IMPLEMENTING","checkpoint":{"next":"x"}}\n' > "$d/.claude/state/task.TASK-1.json"
  else
    printf '{"task_id":"TASK-1","state":"IMPLEMENTING","lead_at":"%s","checkpoint":{"next":"x"}}\n' "$2" > "$d/.claude/state/task.TASK-1.json"
  fi
  : > "$d/dirty.txt"
}
dirty() { printf ' M .claude/state/%s\n' "$2" >> "$1/dirty.txt"; }
run() { # run <dir>  -> RC, SO
  SO="$(cd "$1" && PATH="$WORK/bin:$PATH" DIRTY="$1/dirty.txt" CLAUDE_PROJECT_DIR="$1" bash .claude/hooks/stop-check.sh <<<'{}' 2>&1)" && RC=0 || RC=$?
}

D="$WORK/r"
fresh "$D" "$(ago 60)"; dirty "$D" task.TASK-1.json; dirty "$D" task.json; run "$D"
if [ "$RC" = 0 ] && printf '%s' "$SO" | grep -qF 'TASK-1: lead_at is fresh'; then ok "F5 fresh lead_at: warn, rc 0"; else bad "F5 fresh lead_at: rc=$RC" "$SO"; fi

fresh "$D" "$(ago 3600)"; dirty "$D" task.TASK-1.json; run "$D"
if [ "$RC" = 2 ] && printf '%s' "$SO" | grep -qF 'task.TASK-1.json'; then ok "F5 stale lead_at: block"; else bad "F5 stale lead_at: rc=$RC" "$SO"; fi

fresh "$D" none; dirty "$D" task.TASK-1.json; run "$D"
if [ "$RC" = 2 ]; then ok "F5 no lead_at: block"; else bad "F5 no lead_at: rc=$RC" "$SO"; fi

fresh "$D" "$(ago 60)"; dirty "$D" task.TASK-1.json; dirty "$D" task.TASK-2.json; run "$D"
if [ "$RC" = 2 ] && printf '%s' "$SO" | grep -qF 'task.TASK-2.json'; then ok "F5 other task state file: block"; else bad "F5 other task state: rc=$RC" "$SO"; fi

fresh "$D" "$(ago 60)"; dirty "$D" backlog.json; run "$D"
if [ "$RC" = 2 ]; then ok "F5 non-task state file with fresh lead: block"; else bad "F5 backlog dirty: rc=$RC" "$SO"; fi

echo "SUMMARY(stop_check_lead): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
