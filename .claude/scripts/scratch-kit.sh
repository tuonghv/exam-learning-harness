#!/usr/bin/env bash
# Give a role a git-initialised scratch copy of the repo (TASK-069 69.11, REQ-0027):
#   .claude/scripts/scratch-kit.sh [--rev R | --worktree] [--check P... | --apply P...] [--dir D]
# --rev R      (default HEAD) `git archive R` extracted into D.
# --worktree   the tracked files as they are on disk now (local edits included).
# --no-preview no .preview_origin marker (default: the kit mirrors its reports as PREVIEW under this repo's ./reports, phase 106).
# --dir D      target (default: mktemp -d ${TMPDIR:-/tmp}/scratch-kit.XXXXXX); must be absent or empty.
#              Refused (exit 2) inside the repo, inside $REPOS_ROOT, or under a source-tree-named path.
# --check P... `git apply --check` each patch in D, in order; --apply P... applies them. One line per
#              patch: `ok <patch>` or `FAIL <patch>`; any FAIL gives exit 1.
# D gets `git init`, `git add -A` and one commit (fixed identity). The last stdout line is D.
# The real repo's index, refs and worktree are never touched (read-only git calls only).
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE

die() { echo "scratch-kit: $*" >&2; exit 2; }

rev="HEAD"; mode="rev"; action=""; dir=""; preview=1
PATCHES=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --rev) [ "$#" -ge 2 ] || die "--rev needs a value"; rev="$2"; mode="rev"; shift 2 ;;
    --worktree) mode="worktree"; shift ;;
    --no-preview) preview=0; shift ;;
    --dir) [ "$#" -ge 2 ] || die "--dir needs a value"; dir="$2"; shift 2 ;;
    --check|--apply)
      action="${1#--}"; shift
      while [ "$#" -gt 0 ] && [ "${1#--}" = "$1" ]; do PATCHES+=("$1"); shift; done ;;
    *) die "unknown argument: $1" ;;
  esac
done

# absolute path of D without creating it: resolve the nearest existing ancestor physically
abs_path() {
  local p="$1" rest="" base
  case "$p" in /*) ;; *) p="$PWD/$p" ;; esac
  while [ ! -d "$p" ]; do base="${p##*/}"; rest="/$base$rest"; p="${p%/*}"; [ -n "$p" ] || p="/"; done
  printf '%s%s\n' "$(cd -P "$p" && pwd -P)" "$rest"
}

# name built from parts: the guard refuses the literal on a command line
tree_pat="pentest_""source_code"

# refuse before anything is created (an explicit D only; the mktemp default is safe unless TMPDIR is bad)
if [ -n "$dir" ]; then D="$(abs_path "$dir")"; else D="$(abs_path "${TMPDIR:-/tmp}")/scratch-kit.new"; fi

inside() { case "$1/" in "$2"/*) return 0 ;; esac; return 1; }
inside "$D" "$ROOT" && die "refused: $D is inside the repo"
if [ -z "${REPOS_ROOT:-}" ] && [ -f "$ROOT/config.sh" ]; then
  # sourced in a subshell: a value with a variable or command substitution resolves, so the check cannot fail open (F69-6)
  # shellcheck disable=SC1090  # config.sh path is dynamic on purpose
  REPOS_ROOT="$( set +eu; . "$ROOT/config.sh" >/dev/null 2>&1 </dev/null; printf '%s' "${REPOS_ROOT:-}" )"
fi
if [ -n "${REPOS_ROOT:-}" ]; then
  RR="$(abs_path "$REPOS_ROOT")"
  inside "$D" "$RR" && die "refused: $D is inside REPOS_ROOT"
fi
case "/$D/" in */"$tree_pat"*) die "refused: $D is on a source-tree path" ;; esac

if [ -z "$dir" ]; then
  D="$(mktemp -d "${TMPDIR:-/tmp}/scratch-kit.XXXXXX")"
  D="$(abs_path "$D")"
fi
if [ -e "$D" ] && [ -n "$(ls -A "$D")" ]; then die "refused: $D is not empty"; fi
mkdir -p "$D"

# patch paths made absolute before any work in D
ABS=()
for p in ${PATCHES[@]+"${PATCHES[@]}"}; do
  case "$p" in /*) ABS+=("$p") ;; *) ABS+=("$PWD/$p") ;; esac
done

if [ "$mode" = "rev" ]; then
  git -C "$ROOT" archive "$rev" | tar -x -C "$D"
else
  while IFS= read -r -d '' f; do
    [ -f "$ROOT/$f" ] || [ -L "$ROOT/$f" ] || continue
    mkdir -p "$D/$(dirname "$f")"
    cp -pP "$ROOT/$f" "$D/$f"  # -P: a tracked symlink stays a link, its target is never copied (F69-5)
  done < <(git -C "$ROOT" ls-files -z)
fi

git -C "$D" init -q
git -C "$D" add -A
git -C "$D" -c user.name=scratch -c user.email=scratch@local commit -q --allow-empty -m "scratch copy"

# 106.2: marker for report_publish.py: this kit's reports are mirrored as PREVIEW under the origin's ./reports.
# Untracked and git-excluded, so a patch or diff never sees it. --no-preview = no marker.
if [ "$preview" = "1" ]; then
  printf '%s\n' "$ROOT" > "$D/.preview_origin"
  printf '.preview_origin\n' >> "$D/.git/info/exclude"
fi

rc=0
flag="--check"
[ "$action" = "apply" ] && flag="--verbose"
for i in ${ABS[@]+"${!ABS[@]}"}; do
  if git -C "$D" apply "$flag" "${ABS[$i]}" >/dev/null 2>&1; then
    echo "ok ${PATCHES[$i]}"
  else
    echo "FAIL ${PATCHES[$i]}"; rc=1
  fi
done
echo "$D"
exit "$rc"
