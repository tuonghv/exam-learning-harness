#!/usr/bin/env bash
# TASK-098 98.5 (P18-P20): apply-patches.sh --check / --apply on fixture kits in mktemp (no real state).
#   P18 good bundle: CHECK PASS and the fixture tree hash is unchanged.
#   P19 bad anchor: CHECK FAIL / APPLY FAIL and nothing is applied.
#   P20 --apply twice is idempotent; a failing patch or suite restores the backup.
# Run: bash .claude/tests/patch_bundle_test.sh
set -Eeuo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AP="$KIT/scripts/apply-patches.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

# expect <name> <want-rc> <want-substring|""> <cmd...>
expect() {
  local name="$1" want_rc="$2" want_out="$3" out rc=0; shift 3
  out="$("$@" 2>&1)" || rc=$?
  if [ "$rc" -ne "$want_rc" ]; then
    bad "$name (rc=$rc, want $want_rc)"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 12; return
  fi
  if [ -n "$want_out" ] && ! printf '%s' "$out" | grep -qF -- "$want_out"; then
    bad "$name (output lacks '$want_out')"; printf '%s\n' "$out" | sed 's/^/    /' | head -n 12; return
  fi
  ok "$name"
}

# same <name> <a> <b>: pass when the two values are equal
same() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1"; fi; }
tree_hash() { (cd "$1" && find . -type f -print0 | sort -z | xargs -0 cksum | cksum); }

# fixture <dir> <anchor> <suite-exit>: a tiny kit; patch 01 replaces <anchor> by PATCHED in .claude/scripts/foo.sh.
fixture() {
  local d="$1" anchor="$2" suite_rc="$3"
  rm -rf "$d"; mkdir -p "$d/.claude/scripts" "$d/.claude/state" "$d/tests" "$d/work/T1/patches"
  printf '#!/usr/bin/env bash\necho OLDLINE\n' > "$d/.claude/scripts/foo.sh"
  echo '{"keep":"state"}' > "$d/.claude/state/task.json"
  # the copy's suite runner: passes when foo.sh holds PATCHED (or is unpatched and suite_rc=0)
  cat > "$d/tests/run_all.sh" <<EOS
#!/usr/bin/env bash
echo "SUMMARY(run_all): suite \$1"
[ ! -d .claude/state ] || { echo "state leaked into the copy"; exit 3; }
exit $suite_rc
EOS
  cat > "$d/work/T1/patches/01-foo.py" <<EOP
import sys
p = sys.argv[1] + "/foo.sh"
s = open(p).read()
if "# MARK-01" in s:
    sys.exit(0)
if s.count("$anchor") != 1:
    sys.exit("anchor count != 1")
open(p, "w").write(s.replace("$anchor", "echo PATCHED  # MARK-01"))
EOP
  printf '# bundle\n01-foo.py\t.claude/scripts\nsuites: alpha beta\n' > "$d/work/T1/patches/bundle.txt"
}

G="$WORK/good"
fixture "$G" "echo OLDLINE" 0
H0="$(tree_hash "$G")"
expect "P18a --check good bundle passes" 0 "CHECK PASS" bash "$AP" T1 --check --root "$G"
same "P18b repo hash unchanged after --check" "$H0" "$(tree_hash "$G")"

W="$WORK/wk"
fixture "$W" "echo OLDLINE" 0
mkdir -p "$W/work/T2/patches/backup" "$W/work/T1/evidence"; echo x > "$W/work/T2/n.txt"; echo y > "$W/work/T1/evidence/e.txt"
echo p > "$W/work/T2/patches/other.py"; echo b > "$W/work/T2/patches/backup/b.txt"
cat > "$W/tests/run_all.sh" <<'EOS'
#!/usr/bin/env bash
[ -f work/T1/patches/01-foo.py ] || { echo "patches missing in copy"; exit 3; }
[ -f work/T2/patches/other.py ] || { echo "other task patches missing"; exit 5; }
[ -z "$(find work -path '*/backup/*' | head -n 1)" ] || { echo "backup copied"; exit 6; }
extra="$(find work -type f ! -path 'work/*/patches/*' | head -n 3)"
[ -z "$extra" ] || { echo "extra work files: $extra"; exit 4; }
echo "SUMMARY(run_all): wk ok"
EOS
expect "P18c --check copy holds every work/*/patches (no backup/) and no other work/" 0 "CHECK PASS" bash "$AP" T1 --check --root "$W"

B="$WORK/bad"
fixture "$B" "echo NOSUCHLINE" 0
HB="$(tree_hash "$B")"
expect "P19a bad anchor: --check FAILs" 1 "CHECK FAIL" bash "$AP" T1 --check --root "$B"
expect "P19b bad anchor: --apply FAILs" 1 "APPLY FAIL" bash "$AP" T1 --apply --root "$B"
same "P19c bad bundle: nothing applied, no backup left" "$HB" "$(tree_hash "$B")"

S="$WORK/suite"
fixture "$S" "echo OLDLINE" 1
HS="$(tree_hash "$S")"
expect "P19d failing suite: --apply FAILs" 1 "APPLY FAIL" bash "$AP" T1 --apply --root "$S"
same "P19e failing suite: nothing applied" "$HS" "$(tree_hash "$S")"

expect "P20a --apply good bundle" 0 "APPLY PASS" bash "$AP" T1 --apply --root "$G"
if grep -qF "echo PATCHED" "$G/.claude/scripts/foo.sh" && [ -f "$G/work/T1/patches/backup/.claude/scripts/foo.sh" ]; then
  ok "P20b target patched and backup saved"; else bad "P20b target not patched or no backup"; fi
T1="$(cksum < "$G/.claude/scripts/foo.sh")"
expect "P20c --apply twice passes" 0 "APPLY PASS" bash "$AP" T1 --apply --root "$G"
same "P20d one MARK after two applies" 1 "$(grep -c MARK-01 "$G/.claude/scripts/foo.sh")"
same "P20e target unchanged by the second apply" "$T1" "$(cksum < "$G/.claude/scripts/foo.sh")"

# A patch that breaks bash -n restores the backup.
X="$WORK/syntax"
fixture "$X" "echo OLDLINE" 0
sed -i.bak 's/echo PATCHED  # MARK-01/if then  # MARK-01/' "$X/work/T1/patches/01-foo.py"; rm -f "$X/work/T1/patches/01-foo.py.bak"
BEFORE="$(cksum < "$X/.claude/scripts/foo.sh")"
expect "P20f syntax-breaking patch: --apply FAILs" 1 "APPLY FAIL" bash "$AP" T1 --apply --root "$X"
same "P20g backup restored" "$BEFORE" "$(cksum < "$X/.claude/scripts/foo.sh")"

echo "SUMMARY(patch_bundle): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
