#!/usr/bin/env bash
# QA adversarial cases for advance.sh (TASK-032): reuses the fixture of advance_test.sh (everything before
# its "2 gates at TODO" marker). Temp repo only. Run: bash .claude/scripts/checks/advance_adv_test.sh
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KITDIR="$(cd "$HERE/../.." && pwd)"
SL="$(mktemp)"
sed -n '1,/^# -* 2 gates at TODO/p' "$HERE/advance_test.sh" | sed "s#^KIT=.*#KIT=\"$KITDIR\"#" > "$SL"
# shellcheck disable=SC1090,SC2016,SC2034
source "$SL"; rm -f "$SL"
S=work/TASK-9/advance-DESIGN.json
setjson() { # setjson <dir> <STATE> <python-statement on s>
  python3 - "$1" "$2" "$3" <<'PY'
import json, sys
p = "%s/work/TASK-9/advance-%s.json" % (sys.argv[1], sys.argv[2])
s = json.load(open(p)); exec(sys.argv[3]); json.dump(s, open(p, "w"))
PY
}
A="$WORK/a"; fixture "$A"; D="$A"

mkspec DESIGN; setjson "$A" DESIGN 's["bogus"]=1'
b="$(fp "$A")"; expect "A1 unknown spec key refused" 1 "unknown spec key" adv TASK-9 DESIGN --spec $S
check "A1b bytes unchanged" test "$b" = "$(fp "$A")"
mkspec DESIGN; setjson "$A" DESIGN 's["set"]["state"]="DONE"'
b="$(fp "$A")"; expect "A2 set.state (non-whitelisted) refused" 1 "FAIL" adv TASK-9 DESIGN --spec $S
check "A2b bytes unchanged" test "$b" = "$(fp "$A")"
mkspec DESIGN; cp "$A/work/TASK-9/advance-DESIGN.json" "$WORK/outside.json"
ln -sf "$WORK/outside.json" "$A/work/TASK-9/link.json"
expect "A3 spec symlink to outside refused" 1 "FAIL [spec]" adv TASK-9 DESIGN --spec work/TASK-9/link.json
expect "A3b spec ../ escape refused" 1 "FAIL [spec]" adv TASK-9 DESIGN --spec work/TASK-9/../../.claude/state/backlog.json

to_state UNIT_TESTED >/dev/null
echo secret > "$WORK/out.txt"; ln -sf "$WORK/out.txt" "$A/work/TASK-9/sym.txt"; mkdir -p "$A/work/TASK-9/adir"
: > "$A/work/TASK-9/empty.txt"
for ev in "../../../out.txt" "$WORK/out.txt" "work/TASK-9/sym.txt" "work/TASK-9/empty.txt" "work/TASK-9/adir" "work/TASK-9/nope"; do
  mkspec VERIFIED; setjson "$A" VERIFIED "s['set']['verification']['evidence']=['$ev']"
  b="$(fp "$A")"; expect "A4 evidence '$ev' refused" 1 "FAIL [quality]" adv TASK-9 VERIFIED --spec work/TASK-9/advance-VERIFIED.json
  check "A4b bytes unchanged" test "$b" = "$(fp "$A")"
done

# injection characters in subject, log text and paths
echo x > "$A/work/TASK-9/-weird \$(touch PWNED)\`id\`.txt"
mkspec VERIFIED
setjson "$A" VERIFIED 's["commit"]["subject"]="chore(x): verified $(touch PWNED) `touch PWNED2` ; rm -rf /nonexistent"; s["log"]["action"]="line1\n- injected: $(touch PWNED3)\n## FAKE - TASK-9 - x"; s["commit"]["paths"]=["work/TASK-9/-weird $(touch PWNED)`id`.txt","-rf"]'
out="$(adv TASK-9 VERIFIED --spec work/TASK-9/advance-VERIFIED.json 2>&1)" || true
printf '%s\n' "$out" | head -n 4
check "A5 no injected file created" test -z "$(find "$A" -name 'PWNED*' -not -name '-weird*' -not -path '*/.git/*' | head -n 1)"
check "A5b no PWNED in git status" bash -c "! git -C '$A' status --porcelain | grep -v weird | grep -q PWNED"
check "A5c phase-log has no forged heading" test "$(grep -c '^## FAKE' "$A/.claude/state/phase-log.md")" = 0

# injection, success path: hostile text and a hostile file name must be committed literally
H="$WORK/h"; fixture "$H"; D="$H"; to_state UNIT_TESTED >/dev/null
echo x > "$H/work/TASK-9/-weird \$(touch PWNED)\`id\`.txt"; : > "$H/work/TASK-9/empty.txt"
mkspec VERIFIED
setjson "$H" VERIFIED 's["commit"]["subject"]="chore(x): verified $(touch PWNED) `touch PWNED2` ; x"; s["log"]["action"]="line1\n## FAKE - TASK-9 - x\n$(touch PWNED3)"; s["commit"]["paths"]=["work/TASK-9/-weird $(touch PWNED)`id`.txt"]'
expect "A5d hostile text/path commit succeeds" 0 "PASS" adv TASK-9 VERIFIED --spec work/TASK-9/advance-VERIFIED.json
check "A5e nothing executed" test -z "$(find "$H" -name 'PWNED*' -not -name '*weird*' -not -path '*/.git/*' | head -n 1)"
check "A5f no forged phase-log heading" test "$(grep -c '^## FAKE' "$H/.claude/state/phase-log.md")" = 0
check "A5g subject committed literally" bash -c "git -C '$H' log -1 --format=%s | grep -qF 'touch PWNED2'"

# concurrency
B="$WORK/b"; fixture "$B"; D="$B"; mkspec DESIGN
( adv TASK-9 DESIGN --spec $S > "$WORK/c1.out" 2>&1 & adv TASK-9 DESIGN --spec $S > "$WORK/c2.out" 2>&1; wait ) || true
check "A6 concurrent: exactly one new commit" test "$(commits)" = 2
check "A6b concurrent: one DESIGN heading" test "$(grep -c '^## DESIGN - TASK-9' "$B/.claude/state/phase-log.md")" = 1
check "A6c concurrent: no traceback" bash -c "! grep -q Traceback '$WORK/c1.out' '$WORK/c2.out'"
echo "--- c1:"; head -n 3 "$WORK/c1.out"; echo "--- c2:"; head -n 3 "$WORK/c2.out"

# crash: kill -9 while commit-check hangs, then restore the gate and re-run
F="$WORK/f"; fixture "$F"; D="$F"; mkspec DESIGN
cp "$F/.claude/scripts/commit-check.sh" "$WORK/cc.bak"
printf '#!/usr/bin/env bash\nsleep 30\n' > "$F/.claude/scripts/commit-check.sh"
git -C "$F" commit -qam slowcheck --no-verify
snap="$(fp "$F")"
( cd "$F" && CLAUDE_PROJECT_DIR="$F" timeout -s KILL 5 bash .claude/scripts/advance.sh TASK-9 DESIGN --spec $S >/dev/null 2>&1 ) || true
pkill -KILL -f "$F/.claude/scripts" 2>/dev/null || true
if [ "$snap" = "$(fp "$F")" ]; then echo "INFO after kill -9 state == snapshot"; else echo "INFO after kill -9 state DIFFERS from snapshot (expected: no handler can run)"; fi
cp "$WORK/cc.bak" "$F/.claude/scripts/commit-check.sh"
git -C "$F" commit -qam restorecheck --no-verify 2>/dev/null || true
expect "A7 re-run after kill -9 passes (resumes)" 0 "PASS" adv TASK-9 DESIGN --spec $S
check "A7b exactly one DESIGN heading after resume" test "$(grep -c '^## DESIGN - TASK-9' "$F/.claude/state/phase-log.md")" = 1

# crash by a failing commit-check: bytes must equal the snapshot
G="$WORK/g"; fixture "$G"; D="$G"; mkspec DESIGN
printf '#!/usr/bin/env bash\necho "FAIL: forced"; exit 1\n' > "$G/.claude/scripts/commit-check.sh"
git -C "$G" commit -qam failcheck --no-verify
snap="$(fp "$G")"
expect "A8 failing commit-check -> FAIL [commit]" 1 "FAIL [commit]" adv TASK-9 DESIGN --spec $S
check "A8b bytes equal snapshot" test "$snap" = "$(fp "$G")"

echo "SUMMARY(advance_adv): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
