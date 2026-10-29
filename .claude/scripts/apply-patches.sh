#!/usr/bin/env bash
# apply-patches.sh <TASK> --check | --apply [--root DIR]   (TASK-098 98.5)
# Apply a task's bundle of guard/workflow patches in one call, checked first on a copy.
#
# Bundle: work/<TASK>/patches/bundle.txt (blank lines and '#' lines ignored)
#   <NN-name.py><TAB><target-dir relative to the kit root>     one line per patch, applied in file order
#   suites: <name> [<name> ...]                                 suites to run on the copy (tests/run_all.sh <name>)
# Patch contract (TASK-096): `python3 <patch> <target-dir>`, writes a MARK, requires its anchor to match
# exactly once (else exits non-zero), and is idempotent (a second run changes nothing).
#
# --check: copy the kit (no .git, plans/, results/, reports/, .claude/state; of work/ only the */patches dirs, minus backup/) to a mktemp dir, apply every
#          patch there in bundle order, run the suites there (ROOT = the copy), print `CHECK PASS|FAIL`.
#          Writes nothing in the repo; exit 0 on PASS, 1 on FAIL.
# --apply: run --check first (stop on FAIL, nothing applied); back up each target file the patches change to
#          work/<TASK>/patches/backup/; apply in the repo; `bash -n` / `py_compile` every changed .sh/.py;
#          print `git diff --stat`; restore the backup on any failure. Prints `APPLY PASS|FAIL`.
# --root DIR: kit root (default: the repo this script lives in); used by the tests.
# Bash 3.2 clean.
set -Eeuo pipefail

die() { echo "apply-patches: $*" >&2; exit 2; }

[ $# -ge 2 ] || die "usage: apply-patches.sh <TASK> --check|--apply [--root DIR]"
TASK="$1"; MODE="$2"; shift 2
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --root) [ $# -ge 2 ] || die "--root needs a dir"; ROOT="$(cd "$2" && pwd)"; shift 2 ;;
    *) die "unknown argument: $1" ;;
  esac
done
case "$MODE" in --check|--apply) ;; *) die "mode must be --check or --apply" ;; esac
case "$TASK" in *[!A-Za-z0-9_-]*|"") die "bad task id: $TASK" ;; esac

PDIR="$ROOT/work/$TASK/patches"
BUNDLE="$PDIR/bundle.txt"
[ -f "$BUNDLE" ] || die "no bundle: $BUNDLE"

# Parse the bundle into PATCHES (name<TAB>dir lines) and SUITES (names).
PATCHES=(); SUITES=()
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|'#'*) continue ;; esac
  case "$line" in
    suites:*) for s in ${line#suites:}; do SUITES+=("$s"); done ;;
    *"	"*)
      name="${line%%	*}"; tdir="${line#*	}"
      case "$name$tdir" in *..*|/*) die "bad bundle line (no .. or absolute paths): $line" ;; esac
      [ -f "$PDIR/$name" ] || die "patch missing: $PDIR/$name"
      PATCHES+=("$name	$tdir") ;;
    *) die "bad bundle line (want <patch><TAB><dir> or suites:): $line" ;;
  esac
done < "$BUNDLE"
[ "${#PATCHES[@]}" -gt 0 ] || die "bundle lists no patch"

TMPS=""
cleanup() { [ -z "$TMPS" ] || rm -rf "$TMPS"; }
trap cleanup EXIT

# run_patches <kit-root>: apply every patch against <kit-root>; first failure stops.
run_patches() {
  local base="$1" p name tdir
  for p in "${PATCHES[@]}"; do
    name="${p%%	*}"; tdir="${p#*	}"
    [ -d "$base/$tdir" ] || { echo "FAIL patch $name: target dir $tdir missing"; return 1; }
    if ! python3 "$PDIR/$name" "$base/$tdir" >&2; then
      echo "FAIL patch $name (anchor drifted or patch error), target $tdir"; return 1
    fi
    echo "applied $name -> $tdir"
  done
}

# run_suites <kit-root>: each suite via the copy's own tests/run_all.sh.
run_suites() {
  local base="$1" s out rc
  for s in ${SUITES[@]+"${SUITES[@]}"}; do
    rc=0; out="$(cd "$base" && bash tests/run_all.sh "$s" 2>&1)" || rc=$?
    printf '%s\n' "$out" | tail -n 5
    if [ "$rc" -ne 0 ]; then echo "FAIL suite $s (rc=$rc)"; return 1; fi
  done
}

do_check() {
  local copy
  TMPS="$(mktemp -d)"; copy="$TMPS/kit"; mkdir -p "$copy"
  (cd "$ROOT" && tar -cf - --exclude=./.git --exclude=./work --exclude=./plans --exclude=./results \
      --exclude=./reports --exclude=./.claude/state --exclude=__pycache__ .) | (cd "$copy" && tar -xf -)
  # suites read patch files of this and older tasks (process_speed P15, lead_test); nothing else of work/
  local pd t
  for pd in "$ROOT"/work/*/patches; do
    [ -d "$pd" ] || continue
    t="$(basename "$(dirname "$pd")")"
    mkdir -p "$copy/work/$t"; cp -R "$pd" "$copy/work/$t/patches"; rm -rf "$copy/work/$t/patches/backup"
  done
  if run_patches "$copy" && run_suites "$copy"; then echo "CHECK PASS"; return 0; fi
  echo "CHECK FAIL"; return 1
}

# changed files the patches may touch = every file in the target dirs; back up by listing before/after is costly,
# so back up each target dir's .sh/.py/.json/.md files that the patches change, found on the check copy.
do_apply() {
  local copy bk f rel changed=0 bad=0
  do_check || { echo "APPLY FAIL (check failed, nothing applied)"; return 1; }
  copy="$TMPS/kit"
  bk="$PDIR/backup"; rm -rf "$bk"; mkdir -p "$bk"
  # files that differ between the repo and the patched copy (excluded dirs aside)
  CHANGED_LIST="$TMPS/changed.txt"; : > "$CHANGED_LIST"
  for p in "${PATCHES[@]}"; do
    tdir="${p#*	}"
    (cd "$copy" && find "$tdir" -type f ! -path '*/__pycache__/*' ! -path './.claude/state/*' ! -path '.claude/state/*' -print) |
    while IFS= read -r f; do
      if [ ! -f "$ROOT/$f" ] || ! cmp -s "$copy/$f" "$ROOT/$f"; then echo "$f"; fi
    done >> "$CHANGED_LIST"
  done
  sort -u "$CHANGED_LIST" -o "$CHANGED_LIST"
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    if [ -f "$ROOT/$rel" ]; then mkdir -p "$bk/$(dirname "$rel")"; cp -p "$ROOT/$rel" "$bk/$rel"; echo "$rel" >> "$bk/.existing"
    else echo "$rel" >> "$bk/.created"; fi
    changed=$((changed + 1))
  done < "$CHANGED_LIST"
  if ! run_patches "$ROOT"; then bad=1; fi
  if [ "$bad" -eq 0 ]; then
    while IFS= read -r rel; do
      [ -n "$rel" ] || continue
      case "$rel" in
        *.sh) bash -n "$ROOT/$rel" || { echo "FAIL bash -n $rel"; bad=1; } ;;
        *.py) python3 -m py_compile "$ROOT/$rel" || { echo "FAIL py_compile $rel"; bad=1; } ;;
      esac
    done < "$CHANGED_LIST"
    find "$ROOT" -name __pycache__ -path "*/.claude/*" -newer "$BUNDLE" -prune -exec rm -rf {} + 2>/dev/null || true
  fi
  if [ "$bad" -ne 0 ]; then
    restore "$bk"; echo "APPLY FAIL (backup restored from $bk)"; return 1
  fi
  echo "changed files: $changed"
  if [ -d "$ROOT/.git" ]; then (cd "$ROOT" && git diff --stat | tail -n 40) || true; fi
  echo "APPLY PASS"
}

restore() {
  local bk="$1" rel
  if [ -f "$bk/.existing" ]; then
    while IFS= read -r rel; do cp -p "$bk/$rel" "$ROOT/$rel"; done < "$bk/.existing"
  fi
  if [ -f "$bk/.created" ]; then
    while IFS= read -r rel; do rm -f "$ROOT/$rel"; done < "$bk/.created"
  fi
}

case "$MODE" in
  --check) do_check ;;
  --apply) do_apply ;;
esac
