#!/usr/bin/env bash
# Safe cleanup of agent scratch (TASK-150, REQ-0156): deletes only strictly below <repo>/work/.
# Usage: bash .claude/scripts/clean-work.sh TASK-NNN | work/<path> [...]   (--dry-run lists only)
set -eu
root="$(cd "$(dirname "$0")/../.." && pwd -P)"
work="$root/work"
dry=0
if [ "${1:-}" = "--dry-run" ]; then dry=1; shift; fi
if [ $# -eq 0 ]; then
  echo "usage: clean-work.sh [--dry-run] TASK-NNN|work/<path> ..." >&2
  exit 2
fi
rc=0
for arg in "$@"; do
  case "$arg" in
    TASK-[0-9]*) rel="work/$arg" ;;
    *) rel="$arg" ;;
  esac
  case "$rel" in /*) p="$rel" ;; *) p="$root/$rel" ;; esac
  parent="$(dirname "$p")"; base="$(basename "$p")"
  if [ ! -d "$parent" ] || [ "$base" = "." ] || [ "$base" = ".." ] || [ -z "$base" ]; then
    echo "REFUSED: $arg (no such parent or bad name)" >&2; rc=1; continue
  fi
  real="$(cd "$parent" && pwd -P)/$base"
  case "$real" in
    "$work"/?*) ;;
    *) echo "REFUSED: $arg resolves to $real, not below $work/" >&2; rc=1; continue ;;
  esac
  if [ ! -e "$real" ] && [ ! -L "$real" ]; then
    echo "SKIP: $arg (not there)"; continue
  fi
  if [ "$dry" = 1 ]; then echo "WOULD DELETE: $real"; continue; fi
  rm -rf -- "$real"
  echo "DELETED: $real"
done
exit $rc
