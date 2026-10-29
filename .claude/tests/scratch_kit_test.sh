#!/usr/bin/env bash
# TASK-069 69.11: scratch-kit.sh gives a git-initialised scratch copy and never touches the real repo.
# Cases: rev copy = clean repo at one commit; --worktree keeps a local edit; --check ok/FAIL; --apply changes
# the copy; --dir inside the repo refused; source-tree-named dir refused; real `status --porcelain` unchanged.
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SK="$HERE/.claude/scripts/scratch-kit.sh"
W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT
export TMPDIR="$W"
pass=0; fail=0
tree="pentest_""source_code"

ok()  { pass=$((pass + 1)); echo "PASS $1"; }
bad() { fail=$((fail + 1)); echo "FAIL $1: $2"; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "got [$2] want [$3]"; fi; }
has() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1" "[$2] lacks [$3]" ;; esac; }

# dirty the real tree a bit (untracked file is enough) so 'unchanged' is a real comparison
before="$(git -C "$HERE" status --porcelain)"
same() { check "$1: real status unchanged" "$(git -C "$HERE" status --porcelain)" "$before"; }

# fixture patch (plain diff -u style with a/ b/ prefixes)
printf 'hello\n' > "$W/a.txt"
mkdir -p "$W/pa" "$W/pb"
printf 'hello\n' > "$W/pa/README.tmp"
printf 'hello\nworld\n' > "$W/pb/README.tmp"
patch_good="$W/good.patch"
{ echo "diff --git a/scratch_probe.txt b/scratch_probe.txt"; echo "new file mode 100644"
  echo "--- /dev/null"; echo "+++ b/scratch_probe.txt"; echo "@@ -0,0 +1 @@"; echo "+probe"; } > "$patch_good"
patch_bad="$W/bad.patch"
{ echo "diff --git a/no_such_file.txt b/no_such_file.txt"; echo "--- a/no_such_file.txt"
  echo "+++ b/no_such_file.txt"; echo "@@ -1 +1 @@"; echo "-x"; echo "+y"; } > "$patch_bad"

# 1 rev copy
out="$(bash "$SK")"; rc=$?
d1="$(printf '%s\n' "$out" | tail -n 1)"
check "rev: rc 0" "$rc" "0"
check "rev: one commit" "$(git -C "$d1" rev-list --count HEAD)" "1"
check "rev: clean" "$(git -C "$d1" status --porcelain)" ""
if [ -f "$d1/CLAUDE.md" ]; then ok "rev: has CLAUDE.md"; else bad "rev: has CLAUDE.md" missing; fi
check "rev: fixed identity" "$(git -C "$d1" log -1 --format=%an)" "scratch"
same rev

# 2 worktree includes a local edit (edit a copy path? no: use an existing tracked file, restore after)
f="$HERE/CLAUDE.md"
cp -p "$f" "$W/claude.bak"
printf '\nSCRATCH-KIT-LOCAL-EDIT\n' >> "$f"
out="$(bash "$SK" --worktree --dir "$W/wt")" || true
cp -p "$W/claude.bak" "$f"
if grep -q 'SCRATCH-KIT-LOCAL-EDIT' "$W/wt/CLAUDE.md"; then ok "worktree: local edit present"; else bad "worktree: local edit present" missing; fi
check "worktree: clean after commit" "$(git -C "$W/wt" status --porcelain)" ""
check "worktree: last line is D" "$(printf '%s\n' "$out" | tail -n 1)" "$W/wt"
same worktree

# 3 --check ok and FAIL
set +e
out="$(bash "$SK" --check "$patch_good" --dir "$W/c1")"; rc=$?
set -e
check "check ok: rc 0" "$rc" "0"
has "check ok: line" "$out" "ok $patch_good"
if [ ! -e "$W/c1/scratch_probe.txt" ]; then ok "check: copy unchanged"; else bad "check: copy unchanged" "file exists"; fi
set +e
out="$(bash "$SK" --check "$patch_good" "$patch_bad" --dir "$W/c2")"; rc=$?
set -e
check "check FAIL: rc 1" "$rc" "1"
has "check FAIL: line" "$out" "FAIL $patch_bad"
has "check FAIL: ok line too" "$out" "ok $patch_good"
check "check FAIL: last line is D" "$(printf '%s\n' "$out" | tail -n 1)" "$W/c2"
same check

# 4 --apply changes the copy
set +e
out="$(bash "$SK" --apply "$patch_good" --dir "$W/ap")"; rc=$?
set -e
check "apply: rc 0" "$rc" "0"
check "apply: file created" "$(cat "$W/ap/scratch_probe.txt")" "probe"
check "apply: shows as change" "$(git -C "$W/ap" status --porcelain)" "?? scratch_probe.txt"
same apply

# 5 refusals
for target in "$HERE/scratch-inside" "$HERE/.claude/scratch-inside"; do
  set +e; out="$(bash "$SK" --dir "$target" 2>&1)"; rc=$?; set -e
  check "inside repo refused: rc" "$rc" "2"
  has "inside repo refused: reason" "$out" "refused"
  if [ ! -e "$target" ]; then ok "inside repo: nothing created"; else bad "inside repo: nothing created" "$target exists"; fi
done
set +e; out="$(bash "$SK" --dir "$W/x/$tree/copy" 2>&1)"; rc=$?; set -e
check "tree name refused: rc" "$rc" "2"
has "tree name refused: reason" "$out" "source-tree"
set +e; out="$(bash "$SK" --dir "$W/x/${tree}_clean" 2>&1)"; rc=$?; set -e
check "tree-name prefix refused: rc" "$rc" "2"
if [ ! -e "$W/x" ]; then ok "tree name: nothing created"; else bad "tree name: nothing created" "$W/x exists"; fi
mkdir -p "$W/full"; : > "$W/full/f"
set +e; out="$(bash "$SK" --dir "$W/full" 2>&1)"; rc=$?; set -e
check "non-empty D refused: rc" "$rc" "2"
same refusals

# 6 fake kit (own git repo, a copy of the script): F69-5 symlink kept, F69-6 config.sh value with a variable
FK="$W/fk"
mkdir -p "$FK/.claude/scripts" "$W/outside"
cp "$SK" "$FK/.claude/scripts/scratch-kit.sh"
echo secret > "$W/outside/secret.txt"
ln -s "$W/outside/secret.txt" "$FK/link.txt"
echo plain > "$FK/plain.txt"
printf 'REPOS_ROOT="${FK_BASE}/rr"\n' > "$FK/config.sh"
git -C "$FK" init -q
git -C "$FK" add -A
git -C "$FK" -c user.name=t -c user.email=t@l commit -q -m fk
FKS="$FK/.claude/scripts/scratch-kit.sh"
out="$(bash "$FKS" --worktree --dir "$W/fkcopy" | tail -n 1)"
if [ -L "$W/fkcopy/link.txt" ]; then ok "worktree: tracked symlink stays a link"; else bad "worktree: tracked symlink stays a link" "not a symlink"; fi
check "worktree: plain file copied" "$(cat "$W/fkcopy/plain.txt")" "plain"
export FK_BASE="$W"
mkdir -p "$W/rr"
set +e; out="$(bash "$FKS" --dir "$W/rr/sub" 2>&1)"; rc=$?; set -e
check "REPOS_ROOT with a variable: refused rc" "$rc" "2"
has "REPOS_ROOT with a variable: reason" "$out" "inside REPOS_ROOT"
unset FK_BASE
# 106.2: preview marker (origin = the source toolkit), absent with --no-preview
check "marker: .preview_origin line 1 = origin" "$(head -n 1 "$W/fkcopy/.preview_origin")" "$FK"
out="$(bash "$FKS" --worktree --no-preview --dir "$W/fknp" | tail -n 1)"
check "marker: --no-preview writes none" "$([ -e "$W/fknp/.preview_origin" ] && echo yes || echo no)" "no"

echo "SUMMARY(scratch_kit): pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
