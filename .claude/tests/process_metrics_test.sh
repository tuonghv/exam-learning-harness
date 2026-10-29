#!/usr/bin/env bash
# TASK-074 74.7c: process_metrics.py --roles, no_worse verdict and rc 5 (REQ-0033 AC8), $0.
# Fixtures live in mktemp dirs; no real .claude/state or logs are read.
# Run: bash .claude/tests/process_metrics_test.sh   (KIT_DIR=<.claude copy> tests another copy, the bite check)
set -Eeuo pipefail
KIT="${KIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PMX="$KIT/scripts/process_metrics.py"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

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

# mk <dir> <coder-calls> <coder-refusals> <coder-handoff-first-line>
# TASK-800 always also has 20 tester calls, 5 tester refusals and one COMPLETE test.md.
mk() {
  local d="$1" cc="$2" cv="$3" hl="$4" i
  mkdir -p "$d/.claude/state" "$d/work/TASK-800/handoff"
  git -C "$d" init -q
  printf '{"picked_at":"2026-10-01T10:00:00Z"}\n' > "$d/.claude/state/task.TASK-800.json"
  printf '%s\n' "$hl" > "$d/work/TASK-800/handoff/code.md"
  printf 'PROGRESS: COMPLETE\n' > "$d/work/TASK-800/handoff/test.md"
  : > "$d/.claude/agent_setup_calls.jsonl"; : > "$d/.claude/agent_setup_violations.jsonl"
  echo '{"ts":1,"task":"TASK-800","tool":"SubagentStart","role":"coder"}' >> "$d/.claude/agent_setup_calls.jsonl"
  i=0; while [ "$i" -lt "$cc" ]; do
    echo '{"ts":2,"task":"TASK-800","tool":"Read","role":"coder"}' >> "$d/.claude/agent_setup_calls.jsonl"; i=$((i + 1)); done
  i=0; while [ "$i" -lt 20 ]; do
    echo '{"ts":3,"task":"TASK-800","tool":"Bash","role":"tester"}' >> "$d/.claude/agent_setup_calls.jsonl"; i=$((i + 1)); done
  i=0; while [ "$i" -lt "$cv" ]; do
    echo '{"ts":4,"task":"TASK-800","kind":"protected","role":"coder"}' >> "$d/.claude/agent_setup_violations.jsonl"; i=$((i + 1)); done
  i=0; while [ "$i" -lt 5 ]; do
    echo '{"ts":5,"task":"TASK-800","kind":"protected","role":"tester"}' >> "$d/.claude/agent_setup_violations.jsonl"; i=$((i + 1)); done
}
P() { python3 -B "$PMX" TASK-800 "$@"; }

mk "$WORK/base" 10 1 "PROGRESS: PARTIAL"
js() { P --root "$1" --roles "$2" --json 2>/dev/null; }
chk() { printf '%s' "$1" | jq -e "$2" >/dev/null 2>&1; }

# --roles output
OUT="$(js "$WORK/base" coder)"
if chk "$OUT" '.tasks["TASK-800"] | .turns==10 and .refusals==1 and .partial==1 and .briefs==1'; then
  ok "R1 --roles coder: turns, refusals, partial count only the coder"; else bad "R1 --roles coder"; printf '%s\n' "$OUT" | head -n 20; fi
OUT="$(js "$WORK/base" tester)"
if chk "$OUT" '.tasks["TASK-800"] | .turns==20 and .refusals==5 and .partial==0'; then
  ok "R2 --roles tester: its own calls, refusals, no partial"; else bad "R2 --roles tester"; printf '%s\n' "$OUT" | head -n 20; fi
OUT="$(js "$WORK/base" coder,tester)"
if chk "$OUT" '.tasks["TASK-800"] | .turns==30 and .refusals==6 and .partial==1'; then
  ok "R3 --roles a,b adds both roles"; else bad "R3 --roles coder,tester"; printf '%s\n' "$OUT" | head -n 20; fi

# without --roles: unchanged (no turns key, all roles counted, same TSV header)
OUT="$(P --root "$WORK/base" --json 2>/dev/null)"
if chk "$OUT" '.tasks["TASK-800"] | (has("turns")|not) and .refusals==6 and .partial==1'; then
  ok "R4 no --roles: no turns key, every role counted"; else bad "R4 no --roles json"; printf '%s\n' "$OUT" | head -n 20; fi
expect "R5 no --roles: TSV header unchanged" 0 "task	commits	wip	transitions	briefs	partial	refusals	scope_out	user_notes	raws_in_window	minutes_total" P --root "$WORK/base"
base_tsv="$(P --root "$WORK/base" 2>/dev/null | head -n 1)"
expect "R5b no turns column in the TSV" 1 "" grep -q turns <<<"$base_tsv"

# verdicts
js "$WORK/base" coder > "$WORK/base.json"
mk "$WORK/same" 10 1 "PROGRESS: PARTIAL"
expect "V1 same numbers: verdict ok, rc 0" 0 "verdict	ok" P --root "$WORK/same" --roles coder --compare "$WORK/base.json"
mk "$WORK/fewer" 6 0 "PROGRESS: COMPLETE"
expect "V2 better numbers: verdict ok" 0 "verdict	ok" P --root "$WORK/fewer" --roles coder --compare "$WORK/base.json"
mk "$WORK/ref" 10 2 "PROGRESS: PARTIAL"
expect "V3 more refusals: worse, rc 5" 5 "verdict	worse	refusals 1.0 -> 2.0" P --root "$WORK/ref" --roles coder --compare "$WORK/base.json"
# the tester's refusals do not count when only the coder is compared
mk "$WORK/part" 10 1 "PROGRESS: PARTIAL"
printf 'PROGRESS: PARTIAL\n' > "$WORK/part/work/TASK-800/handoff/test.md"
expect "V4 other role's PARTIAL is ignored" 0 "verdict	ok" P --root "$WORK/part" --roles coder --compare "$WORK/base.json"
mk "$WORK/part2" 10 1 "PROGRESS: PARTIAL"
printf 'PROGRESS: PARTIAL\n' > "$WORK/part2/work/TASK-800/handoff/code.md"
mk "$WORK/more" 10 1 "PROGRESS: PARTIAL"
mk "$WORK/b0" 10 1 "PROGRESS: COMPLETE"; js "$WORK/b0" coder > "$WORK/b0.json"
expect "V5 a new PARTIAL: worse, rc 5" 5 "partial 0.0 -> 1.0" P --root "$WORK/more" --roles coder --compare "$WORK/b0.json"
mk "$WORK/t12" 12 1 "PROGRESS: PARTIAL"   # 12 turns vs 10: inside max(2, 10%)
expect "V6 turns +2 inside the tolerance: ok" 0 "verdict	ok" P --root "$WORK/t12" --roles coder --compare "$WORK/base.json"
mk "$WORK/t13" 13 1 "PROGRESS: PARTIAL"   # 13 turns: past the tolerance
expect "V7 turns +3: worse, rc 5" 5 "turns 10.0 -> 13.0" P --root "$WORK/t13" --roles coder --compare "$WORK/base.json"
js "$WORK/base" nobody > "$WORK/nobody.json"
expect "V8 baseline without calls: insufficient, rc 5" 5 "verdict	insufficient" P --root "$WORK/same" --roles nobody --compare "$WORK/nobody.json"
# F-74-1: an unknown role on the current side (a typo) is insufficient too, never a pass
expect "V8b unknown role on the current side: insufficient, rc 5 (F-74-1)" 5 "verdict	insufficient" P --root "$WORK/same" --roles nobody --compare "$WORK/base.json"
expect "V9 unreadable baseline still fails rc 1" 1 "cannot read baseline" P --root "$WORK/same" --roles coder --compare "$WORK/none.json"
# --compare without --roles keeps the old table and rc 0 even when numbers rose
P --root "$WORK/base" --json > "$WORK/all.json" 2>/dev/null
expect "V10 compare without --roles: old table, rc 0" 0 "metric	baseline_avg" P --root "$WORK/ref" --compare "$WORK/all.json"

echo "SUMMARY(process_metrics): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
