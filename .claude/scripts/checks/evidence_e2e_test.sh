#!/usr/bin/env bash
# TASK-057 (57.3/57.5/57.7, RAW-00174): evidence_required end to end through advance.sh in throwaway git repos.
# Reuses the fixture/helpers of .claude/scripts/checks/advance_test.sh (everything before its "2 gates" section).
# Run: bash .claude/scripts/checks/evidence_e2e_test.sh
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${ADV_TEST_SRC:-$HERE/advance_test.sh}"
KITDIR="${KIT_UNDER_TEST:-$HERE/../..}"
PRE="$(mktemp)"
trap 'rm -f "$PRE"' EXIT
sed -n '1,/^# -* 2 gates at TODO/p' "$SRC" | sed '$d' \
  | sed "s|^KIT=.*|KIT=\"$(cd "$KITDIR" && pwd)\"|" > "$PRE"
# shellcheck disable=SC1090
. "$PRE"

EVT="docs/report/evidence/TASK-9"
flag() {
  python3 - "$1" <<'PY'
import json, sys
p = sys.argv[1] + "/.claude/state/task.TASK-9.json"
t = json.load(open(p)); t["evidence_required"] = True; json.dump(t, open(p, "w"), indent=2)
PY
  sh_ bash .claude/scripts/tasks.sh sync >/dev/null
  git -C "$1" add -A -- .claude/state; git -C "$1" commit -qm flag --no-verify
}
F="$WORK/f"; fixture "$F"; D="$F"; flag "$F"
to_state UNIT_TESTED
echo "see https://example.invalid/x" > "$F/work/TASK-9/ev.txt"
gatecase "7.1 flagged VERIFIED, evidence refused by scan (url) -> evidence" VERIFIED none evidence "url"
check "7.1b nothing published after refusal" test ! -e "$F/$EVT"
echo "evidence" > "$F/work/TASK-9/ev.txt"
prep VERIFIED; mkspec VERIFIED
expect "7.2 flagged VERIFIED publishes and passes" 0 "PASS: TASK-9 -> VERIFIED committed" adv TASK-9 VERIFIED --spec work/TASK-9/advance-VERIFIED.json
check "7.2b published file is tracked" tracked "$EVT/ev.txt"
check "7.2c verification.published recorded" grep -q "$EVT/ev.txt" "$F/.claude/state/task.TASK-9.json"
G="$WORK/g"; clone "$F" "$G"
sh_ python3 -c "
import json
p='.claude/state/task.TASK-9.json'; t=json.load(open(p)); t['verification']['published']=[]; json.dump(t,open(p,'w'))"
expect "7.3 flagged workflow-check fails when published is empty" 1 "verification.published" sh_ bash .claude/scripts/workflow-check.sh --task TASK-9
D="$F"
echo "report doc, no evidence cited" > "$F/docs/report/phase-9-gates.md"; mkspec DONE
rc7=0; out="$(adv TASK-9 DONE --spec work/TASK-9/advance-DONE.json 2>&1)" || rc7=$?
if [ "$rc7" -ne 0 ] && printf '%s' "$out" | grep -qF "names no $EVT"; then ok "7.4 flagged DONE fails when the report cites no evidence file"; else bad "7.4 (rc=$rc7)"; printf '%s\n' "$out" | head -n 8; fi
echo "report cites $EVT/ev.txt" > "$F/docs/report/phase-9-gates.md"; mkspec DONE
expect "7.5 flagged DONE passes with citation + INDEX row" 0 "PASS: TASK-9 -> DONE committed" adv TASK-9 DONE --spec work/TASK-9/advance-DONE.json
check "7.5b INDEX.md has the TASK-9 row" grep -q '^| TASK-9 ' "$F/docs/report/INDEX.md"
check "7.5c INDEX.md tracked" tracked docs/report/INDEX.md
H="$WORK/h"; clone "$F" "$H"; sed -i '/^| TASK-9 /d' "$H/docs/report/INDEX.md"
expect "7.6 flagged DONE without an INDEX row fails workflow-check" 1 "no row for TASK-9" sh_ bash .claude/scripts/workflow-check.sh --task TASK-9
U="$WORK/u"; fixture "$U"; D="$U"; to_state VERIFIED
out="$(sh_ bash .claude/scripts/workflow-check.sh --task TASK-9 2>&1)" || true
if printf '%s' "$out" | grep -qF "WARN: no published evidence" && ! printf '%s' "$out" | grep -q '^FAIL'; then ok "7.7 unflagged VERIFIED: WARN only, no publish"; else bad "7.7 unflagged"; printf '%s\n' "$out" | head -n 6; fi
check "7.7b unflagged publishes nothing" test ! -e "$U/$EVT"

echo "SUMMARY(evidence-e2e): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
