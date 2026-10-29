#!/usr/bin/env bash
# known_targets.sh - KNOWN_TARGETS for inbox-triage (phase 71): "toolkit" plus one "<sys>/<plan>"
# per review plan directory. Names only; never reads a plan's files or REPOS_ROOT.
set -euo pipefail
cd "$(dirname "$0")/../.."
echo toolkit
for d in plans/*/*/; do
  [ -d "$d" ] || continue
  d="${d%/}"; echo "${d#plans/}"
done
