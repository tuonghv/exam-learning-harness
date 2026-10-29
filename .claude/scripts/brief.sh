#!/usr/bin/env bash
# Print the standard role brief for one design item (read-only; stdout only).
# Usage: brief.sh <TASK> <item> <role> [--turns N] [--peers "<text>"] [--checks "<cmd>"]
#        [--load "a,b"] [--refresh]
# BRIEF_ROOT overrides the repo root (tests use a fixture).
set -Eeuo pipefail

die() { echo "brief.sh: $*" >&2; exit 1; }

[ "$#" -ge 3 ] || die "usage: brief.sh <TASK> <item> <role> [--turns N] [--peers TEXT] [--checks CMD] [--load a,b] [--refresh]"
T="$1"; ITEM="$2"; ROLE="$3"; shift 3
TURNS=""; PEERS=""; CHECKS=""; LOADX=""; REFRESH=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --turns)  [ "$#" -ge 2 ] || die "--turns needs a value"; TURNS="$2"; shift 2 ;;
    --peers)  [ "$#" -ge 2 ] || die "--peers needs a value"; PEERS="$2"; shift 2 ;;
    --checks) [ "$#" -ge 2 ] || die "--checks needs a value"; CHECKS="$2"; shift 2 ;;
    --load)   [ "$#" -ge 2 ] || die "--load needs a value"; LOADX="$2"; shift 2 ;;
    --refresh) REFRESH=1; shift ;;
    *) die "unknown option $1" ;;
  esac
done

ROOT="${BRIEF_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
case "$T" in TASK-[0-9]*) ;; *) die "bad task id: $T" ;; esac
case "$ITEM" in *[!0-9A-Za-z._-]*|"") die "bad item: $ITEM" ;; esac

case "$ROLE" in
  designer) DEF_TURNS=40; OUT=design ;;
  coder)    DEF_TURNS=35; OUT=code ;;
  tester)   DEF_TURNS=30; OUT="test" ;;
  verifier) DEF_TURNS=30; OUT=verify ;;
  *) die "unknown role: $ROLE (designer|coder|tester|verifier)" ;;
esac
[ "$REFRESH" -eq 0 ] || [ "$ROLE" = designer ] || die "--refresh is designer only"
[ -n "$TURNS" ] || TURNS="$DEF_TURNS"
case "$TURNS" in *[!0-9]*|"") die "--turns must be a number" ;; esac
EXPECT=$((TURNS / 5))
if [ -z "$CHECKS" ]; then
  case "$ROLE" in
    coder|tester) CHECKS="tests/run_all.sh --changed" ;;
    *) CHECKS="(none; save evidence with .claude/scripts/save-evidence.sh)" ;;
  esac
fi

TF="$ROOT/.claude/state/task.$T.json"
[ -f "$TF" ] || die "no state file for $T"
DPATH="$(jq -r '.design.path // ""' "$TF")"
[ -n "$DPATH" ] || die "$T has no design.path"
[ -f "$ROOT/$DPATH" ] || die "design file missing: $DPATH"

# Heading "### <item> ..." (item followed by space, dot-less end or punctuation).
LINE="$(grep -n -m1 -E "^###+ ${ITEM//./\\.}([^0-9A-Za-z]|$)" "$ROOT/$DPATH" | cut -d: -f1 || true)"
[ -n "$LINE" ] || die "item $ITEM not found in $DPATH"
HEAD="$(sed -n "${LINE}p" "$ROOT/$DPATH")"
GOAL="$(printf '%s' "$HEAD" | sed -E 's/^#+ +//')"
GOAL="${GOAL#"$ITEM"}"
GOAL="$(printf '%s' "$GOAL" | sed -E 's/^[ .:-]+//')"

SCOPE="$(jq -r '(.scope // []) | join(", ")' "$TF")"
GRANTS="$(jq -r --arg r "$ROLE" '(.roles.grants[$r] // []) | join(", ")' "$TF")"
HANDOFFS=""
if [ -d "$ROOT/work/$T/handoff" ]; then
  for f in "$ROOT/work/$T/handoff/"*.md; do
    [ -e "$f" ] || continue
    HANDOFFS="${HANDOFFS:+$HANDOFFS, }work/$T/handoff/$(basename "$f")"
  done
fi

FORBID="REPOS_ROOT and source trees"
AS="$ROOT/.claude/agent_setup.json"
if [ -f "$AS" ]; then
  RG="$(jq -r '(.protect.read_globs // []) | join(", ")' "$AS")"
  [ -z "$RG" ] || FORBID="$FORBID ($RG)"
fi
FORBID="$FORBID, reports/, runs/, plans/, results/, frozen prompts (security_prompt.md, docs/prompts/phase0-*, phase2b-*)"

# Load: skills to load with the Skill tool (scope types, role default, design "Skills:" line, --load).
LOADS=" "
SKILL_WARN=""
add_skill() {
  local n="$1"
  case "$n" in
    "") return 0 ;;
    workflow|commit|coordinator|context-compaction|run-security-review|req-*)
      SKILL_WARN="${SKILL_WARN:+$SKILL_WARN, }$n (state-moving)"; return 0 ;;
  esac
  case "$n" in *[!a-z0-9-]*) SKILL_WARN="${SKILL_WARN:+$SKILL_WARN, }$n (bad name)"; return 0 ;; esac
  [ -f "$ROOT/.claude/skills/$n/SKILL.md" ] || { SKILL_WARN="${SKILL_WARN:+$SKILL_WARN, }$n (no such skill)"; return 0; }
  case "$LOADS" in *" $n "*) ;; *) LOADS="$LOADS$n " ;; esac
}
while IFS= read -r sp; do
  case "$sp" in
    *.md|*.json|docs/*) ;;
    *.py) add_skill python ;;
    *.sh|tests/*|.claude/tests/*|.claude/scripts/*) add_skill bash ;;
  esac
done < <(jq -r '.scope[]?' "$TF")
[ "$ROLE" != tester ] || add_skill bash
SEC="$(awk -v s="$LINE" 'NR>s && /^###/ {exit} NR>=s && /^Skills:/ {sub(/^Skills:[[:space:]]*/, ""); print}' "$ROOT/$DPATH")"
for n in $(printf '%s' "$SEC" | tr ',' ' '); do add_skill "$n"; done
for n in $(printf '%s' "$LOADX" | tr ',' ' '); do add_skill "$n"; done
PRE=""
if [ -f "$ROOT/.claude/agents/$ROLE.md" ]; then
  PRE="$(grep -m1 '^skills:' "$ROOT/.claude/agents/$ROLE.md" | sed -E 's/^skills:[[:space:]]*//' || true)"
fi
LOAD_OUT=""
for n in $LOADS; do
  case ", $PRE," in *", $n,"*|*", $n "*) continue ;; esac
  LOAD_OUT="${LOAD_OUT:+$LOAD_OUT, }$n"
done
[ -z "$SKILL_WARN" ] || echo "brief.sh: skipped skills: $SKILL_WARN" >&2

# Patch route: scope entries under protect.write_globs and not granted to the role (main applies them).
PATCH=""
if [ -f "$AS" ]; then
  WG="$(jq -r '(.protect.write_globs // [])[]' "$AS")"
  GR="$(jq -r --arg r "$ROLE" '(.roles.grants[$r] // [])[]' "$TF")"
  while IFS= read -r sp; do
    [ -n "$sp" ] || continue
    hit=0
    while IFS= read -r g; do
      [ -n "$g" ] || continue
      # shellcheck disable=SC2254  # the glob is data, matched on purpose
      case "$sp" in $g) hit=1; break ;; esac
    done <<EOF
$WG
EOF
    [ "$hit" -eq 1 ] || continue
    gr=0
    while IFS= read -r g; do
      [ -n "$g" ] || continue
      # shellcheck disable=SC2254  # the glob is data, matched on purpose
      case "$sp" in $g) gr=1; break ;; esac
    done <<EOF
$GR
EOF
    [ "$gr" -eq 0 ] || continue
    PATCH="${PATCH:+$PATCH, }$sp"
  done < <(jq -r '.scope[]?' "$TF")
fi

printf '%s item %s: %s\n' "$T" "$ITEM" "$GOAL"
printf 'Read `tasks.sh show %s` first.\n' "$T"
printf 'Inputs: %s §%s (line %s)%s\n' "$DPATH" "$ITEM" "$LINE" "${HANDOFFS:+; earlier handoffs: $HANDOFFS}"
printf 'Scope: %s\n' "${SCOPE:-(none recorded)}"
printf 'Grants (%s): %s\n' "$ROLE" "${GRANTS:-(none)}"
[ "$REFRESH" -eq 0 ] || printf 'Mode: delta refresh (launch with model: sonnet)\n'
if [ -n "$LOAD_OUT" ]; then
  printf 'Load: %s (Skill tool; preloaded: %s)\n' "$LOAD_OUT" "${PRE:-none}"
else
  printf 'Load: (none)\n'
fi
[ -z "$PATCH" ] || printf 'Patch route: %s (protected, not granted: do not edit; give main the exact patch in the handoff)\n' "$PATCH"
printf 'Forbidden: %s\n' "$FORBID"
printf 'Rules: Edit/Write only; no Bash writes into the repo. A refusal means stop: save the handoff and reply PARTIAL.\n'
[ -z "$PEERS" ] || printf 'Peers: %s\n' "$PEERS"
printf 'Turns: %s. Expect: %s min.\n' "$TURNS" "$EXPECT"
printf 'Checks: %s\n' "$CHECKS"
printf 'Output: work/%s/handoff/%s.md. Reply ≤ 8 lines.\n' "$T" "$OUT"
