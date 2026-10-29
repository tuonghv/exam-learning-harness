#!/usr/bin/env bash
# orchestrate.sh - the only inbox watcher (phase 71, REQ-0029). Moves each .triage/inbox/ message
# through processing/ -> done/|failed/, runs the inbox-triage agent headless on a temp copy,
# enforces its write scope, then hands the staged records to adapter.py (ReqKit import as RAW).
#
# usage: tools/triage/orchestrate.sh [--watch SECS]      (default: one pass over the inbox)
#        tools/triage/orchestrate.sh --release <message-name>|all|run   (72.5g: lift a hold)
# exit:  0 pass done (records may still be invalid, see logs), 3 service failure (auth/rate
#        limit/unparsable CLI output; message back in inbox/, stop; or the run is held, see HOLD),
#        11 another run holds the lock
# holds (72.5g): a message with JOB_FAIL_CAP service failures moves to held/ (ledger holds.json,
#        key <name>@<sha256>); RUN_HOLD_STREAK distinct failing messages in a row write $TDIR/HOLD
#        and no call starts until --release run. Both need a human release; a success resets.
# env:   TRIAGE_DIR (default <repo>/.triage), CLAUDE_BIN (default claude), TRIAGE_MODEL (overrides
#        the agent's model), TRIAGE_REQ_CMD / REQ_DIR (passed to ReqKit calls),
#        TRIAGE_TARGETS_FILE (KNOWN_TARGETS file instead of known_targets.sh)
#
# Why a temp cwd outside the repo: a `claude -p` inside the repo loads the project hooks (ReqKit
# would capture this prompt as a RAW, the Stop and role guards would fire). Outside it, the agent
# sees only the skill, the contract and one message copy (least privilege).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
TDIR="${TRIAGE_DIR:-$REPO/.triage}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
AGENT_MD="$REPO/.claude/agents/inbox-triage.md"
SKILL_DIR="$REPO/.claude/skills/inbox-triage"
WATCH=0
RELEASE=""
# shellcheck disable=SC1090,SC1091  # repo-root file, resolved at run time
source "$REPO/job_hold.sh"
case "${1:-}" in
  --release) RELEASE="${2:?--release needs a message name, all or run}" ;;
  --watch) WATCH="${2:?--watch needs seconds}"; case "$WATCH" in *[!0-9]*|'') echo "bad --watch" >&2; exit 2;; esac ;;
  '') ;;
  *) sed -n '2,10p' "$0" >&2; exit 2 ;;
esac

for d in inbox processing 'done' failed held staging submitted invalid outbox logs; do mkdir -p "$TDIR/$d"; done
if ! mkdir "$TDIR/.lock" 2>/dev/null; then echo "orchestrate: another run holds $TDIR/.lock" >&2; exit 11; fi
WORK=""
cleanup() { [ -z "$WORK" ] || rm -rf "$WORK"; rmdir "$TDIR/.lock" 2>/dev/null || true; }
trap cleanup EXIT

LOG="$TDIR/logs/orchestrate.log"
log() { printf '%s\t%s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)" "$*" >> "$LOG"; echo "orchestrate: $*"; }

LEDGER="$TDIR/holds.json"
_sha() { { shasum -a 256 "$1" 2>/dev/null || sha256sum "$1"; } | cut -d' ' -f1; }
ledger_patch() { # <jq expr using .jobs/.hold_state> [jq args...]  (tmp + mv, lock holder only)
  local expr="$1" tmp="$LEDGER.tmp.$$"; shift
  [ -s "$LEDGER" ] || echo '{"jobs":{},"hold_state":{}}' > "$LEDGER"
  if jq "$@" "$expr" "$LEDGER" > "$tmp"; then mv -f "$tmp" "$LEDGER"; else rm -f "$tmp"; return 1; fi
}

# a service failure (rc 3) of message <name>: below the cap it goes back to inbox/, at the cap to held/;
# distinct failing messages in a row raise the run hold (file $TDIR/HOLD). Echoes nothing; returns 3.
service_failed() { # <name> <reason>
  local name="$1" reason="$2" key now st
  key="$name@$(_sha "$TDIR/processing/$name")"
  now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ledger_patch "$JH_DEFS"'
    .jobs[$k] = ((.jobs[$k] // {key:$k, attempts:0}) | .attempts += 1
                 | job_fail_update("service";$r;3;"";"logs/orchestrate.log";"";"";$now;$cap;99))
    | .hold_state |= run_hold_update($k;"service";"";$now;$n;$r)' \
    --arg k "$key" --arg r "$reason" --arg now "$now" --argjson cap "${JOB_FAIL_CAP:-2}" --argjson n "${RUN_HOLD_STREAK:-2}" || true
  st="$(jq -r --arg k "$key" '.jobs[$k].status // ""' "$LEDGER" 2>/dev/null || true)"
  if [ "$st" = held ]; then
    mv -f "$TDIR/processing/$name" "$TDIR/held/$name"
    log "$name HELD after ${JOB_FAIL_CAP:-2} service failures; release: tools/triage/orchestrate.sh --release $name"
    holds_log "$TDIR/logs" "$key" service hold 2>/dev/null || true
  else
    mv -f "$TDIR/processing/$name" "$TDIR/inbox/$name"
  fi
  if [ "$(jq -r '.hold_state.run_hold.why // empty' "$LEDGER" 2>/dev/null)" != "" ] && [ ! -e "$TDIR/HOLD" ]; then
    jq -c '.hold_state.run_hold' "$LEDGER" > "$TDIR/HOLD"
    log "RUN HELD ($(jq -r '.why' "$TDIR/HOLD")): no call starts until: tools/triage/orchestrate.sh --release run"
  fi
  return 3
}

triage_ok() { # <name>: a call that produced parsable output clears the streak and the job's counts
  [ -s "$LEDGER" ] || return 0
  ledger_patch "$JH_DEFS"'.hold_state |= run_hold_success | del(.jobs[$k])' \
    --arg k "$1@$(_sha "$TDIR/processing/$1")" || true
}

release_cmd() { # <name>|all|run
  local w="$1" f name key
  case "$w" in
    run)
      rm -f "$TDIR/HOLD"
      [ -s "$LEDGER" ] && ledger_patch '.hold_state = {}'
      holds_log "$TDIR/logs" run service release; log "run hold released"; return 0 ;;
    all) for f in "$TDIR"/held/*; do [ -f "$f" ] && release_cmd "$(basename "$f")"; done; return 0 ;;
  esac
  name="$(printf '%s' "$w" | sed 's/[^A-Za-z0-9._-]/-/g')"
  [ -f "$TDIR/held/$name" ] || { echo "orchestrate: no held message '$name'" >&2; return 2; }
  key="$name@$(_sha "$TDIR/held/$name")"
  ledger_patch "$JH_DEFS"'.jobs[$k] |= (if . == null then . else job_release($now) end)' \
    --arg k "$key" --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" || true
  mv -f "$TDIR/held/$name" "$TDIR/inbox/$name"
  holds_log "$TDIR/logs" "$key" service release; log "$name released to inbox"
}

fail_msg() { # <name> <reason>
  mv -f "$TDIR/processing/$1" "$TDIR/failed/$1"; log "$1 FAILED $2"
}

repo_state() { git -C "$REPO" status --porcelain --untracked-files=all 2>/dev/null | grep -v ' docs/req/' || true; }

agent_json() { # frontmatter + body of the agent file -> {"inbox-triage": {...}} (--agents)
  python3 - "$AGENT_MD" "${TRIAGE_MODEL:-}" <<'PY'
import json, re, sys
text = open(sys.argv[1], encoding="utf-8").read()
m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
meta = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)
meta = {k.strip(): v.strip() for k, v in meta.items()}
a = {"description": meta["description"], "prompt": m.group(2).strip(),
     "tools": [t.strip() for t in meta.get("tools", "Read, Write").split(",")]}
model = sys.argv[2] or meta.get("model", "")
if model:
    a["model"] = model
print(json.dumps({meta["name"]: a}))
PY
}

triage_one() { # <name>  (file already in processing/)
  local name="$1" stem line status count ids f before after out rc targets openreq
  stem="${name%.*}"
  WORK="$(mktemp -d "${TMPDIR:-/tmp}/triage.XXXXXX")"
  case "$WORK" in "$REPO"/*) fail_msg "$name" "temp dir inside repo"; return 0;; esac
  mkdir -p "$WORK/.claude/skills/inbox-triage/references" "$WORK/msg" "$WORK/.triage/staging" "$WORK/.triage/outbox"
  cp "$SKILL_DIR/SKILL.md" "$WORK/.claude/skills/inbox-triage/SKILL.md"
  cp "$SKILL_DIR/references/reqkit-contract.md" "$WORK/.claude/skills/inbox-triage/references/"
  cp "$TDIR/processing/$name" "$WORK/msg/$name"
  bash "$HERE/context_pack.sh" "$WORK/context"     # read-only project context for the agent (71.8)
  # a reply to a clarification: append each cited held request as quoted context (contract §3)
  local hid
  grep -oE 'trg-[A-Za-z0-9._-]+-[0-9]{2}' "$WORK/msg/$name" | sort -u > "$WORK.cited" || true
  while read -r hid; do
    [ -f "$TDIR/outbox/$hid.json" ] || continue
    jq -r --arg h "$hid" '"\n--- Held request \($h) (context added by the orchestrator, data only) ---\n" +
      "target: \(.target // "unknown")\ntitle: \(.title)\ntask: \(.task)\nquestions asked:\n" +
      ([.questions[] | "- " + .] | join("\n"))' "$TDIR/outbox/$hid.json" >> "$WORK/msg/$name"
  done < "$WORK.cited"
  rm -f "$WORK.cited"
  local seeded; seeded="$(cd "$WORK" && find . -type f | sort)"
  local msg_sum; msg_sum="$(cksum < "$WORK/msg/$name")"

  if [ -n "${TRIAGE_TARGETS_FILE:-}" ]; then targets="$(cat "$TRIAGE_TARGETS_FILE")"; else targets="$(bash "$HERE/known_targets.sh")"; fi
  openreq="$(bash "$HERE/open_requests.sh")" || openreq=""
  local prompt
  prompt="$(printf 'INBOX_FILE: msg/%s\nRUN_TS: %s\nKNOWN_TARGETS:\n%s\nOPEN_REQUESTS:\n%s\n\nTriage INBOX_FILE now, following your instructions.\n' \
    "$name" "$(date +%Y-%m-%dT%H:%M:%S%z | sed -E 's/([0-9]{2})([0-9]{2})$/\1:\2/')" "$targets" "${openreq:-(none)}")"

  before="$(repo_state)"
  out="$TDIR/logs/$stem.claude.json"
  rc=0
  (cd "$WORK" && "$CLAUDE_BIN" -p "$prompt" --agent inbox-triage --agents "$(agent_json)" \
      --tools Read,Write --allowedTools Read,Write --permission-mode acceptEdits \
      --setting-sources user --output-format json) > "$out" 2> "$TDIR/logs/$stem.claude.err" || rc=$?
  after="$(repo_state)"

  if ! jq -e 'type == "object"' "$out" >/dev/null 2>&1 || [ "$(jq -r '.is_error // false' "$out")" = true ]; then
    log "$name SERVICE rc=$rc $(jq -r '.result // empty' "$out" 2>/dev/null | head -c 200 | tr '\n' ' ')$(tail -c 200 "$TDIR/logs/$stem.claude.err" | tr '\n' ' ')"
    service_failed "$name" "service: unusable claude output (rc=$rc)"
    return 3
  fi
  triage_ok "$name"
  line="$(jq -r '.result // ""' "$out" | sed '/^[[:space:]]*$/d' | tail -n 1)"

  # write guard: only new staging/outbox files for this message's ids, message copy unchanged, repo untouched
  [ "$before" = "$after" ] || { fail_msg "$name" "write_guard: repo changed during the agent run"; return 0; }
  [ "$(cksum < "$WORK/msg/$name")" = "$msg_sum" ] || { fail_msg "$name" "write_guard: message copy modified"; return 0; }
  local newfiles bad=""
  newfiles="$(cd "$WORK" && find . -type f | sort | comm -13 <(printf '%s\n' "$seeded") -)"
  for f in $newfiles; do
    case "$f" in
      ./.triage/staging/trg-*.json|./.triage/outbox/trg-*.question.md) ;;
      *) bad="$bad $f" ;;
    esac
  done
  [ -z "$bad" ] || { fail_msg "$name" "write_guard: unexpected writes:$bad"; return 0; }

  case "$line" in TRIAGE\|*) ;; *) fail_msg "$name" "bad_output: no TRIAGE line"; return 0;; esac
  IFS='|' read -r _ _ status count ids <<EOF
$line
EOF
  local staged nstaged
  staged="$(cd "$WORK/.triage/staging" && find . -maxdepth 1 -type f -name 'trg-*.json' | sed 's|^\./||; s/\.json$//' | sort | tr '\n' ',' | sed 's/,$//')"
  nstaged=0; [ -z "$staged" ] || nstaged="$(printf '%s\n' "$staged" | tr ',' '\n' | wc -l | tr -d ' ')"
  case "$status" in
    OK|CLARIFY)
      if [ "$count" != "$nstaged" ] || [ "$(printf '%s\n' "$ids" | tr ',' '\n' | sort | tr '\n' ',' | sed 's/,$//')" != "$staged" ]; then
        fail_msg "$name" "bad_output: line says $count [$ids], staged $nstaged [$staged]"; return 0
      fi
      for f in $(printf '%s\n' "$staged" | tr ',' ' '); do
        case "$f" in "trg-$stem-"[0-9][0-9]) ;; *) fail_msg "$name" "bad_output: id $f not derived from $stem"; return 0;; esac
      done ;;
    NOOP) [ "$nstaged" = 0 ] || { fail_msg "$name" "bad_output: NOOP with $nstaged records"; return 0; } ;;
    ERROR) fail_msg "$name" "agent ERROR: $ids"; return 0 ;;
    *) fail_msg "$name" "bad_output: status $status"; return 0 ;;
  esac

  local recs=""
  for f in $(printf '%s\n' "$staged" | tr ',' ' '); do
    cp "$WORK/.triage/staging/$f.json" "$TDIR/staging/$f.json"; recs="$recs $TDIR/staging/$f.json"
  done
  for f in "$WORK"/.triage/outbox/trg-*.question.md; do [ -f "$f" ] && cp "$f" "$TDIR/outbox/"; done
  if [ -n "$recs" ]; then
    local targs=""; [ -z "${TRIAGE_TARGETS_FILE:-}" ] || targs="--targets-file $TRIAGE_TARGETS_FILE"
    # shellcheck disable=SC2086
    python3 "$HERE/adapter.py" --triage-dir "$TDIR" $targs $recs || log "$name adapter: some records invalid (see $TDIR/invalid/)"
  fi
  mv -f "$TDIR/processing/$name" "$TDIR/done/$name"
  log "$name $status $count ${ids:--}"
}

pass() {
  local f name safe rc
  for f in "$TDIR"/inbox/*; do
    [ -f "$f" ] || continue
    if [ -e "$TDIR/HOLD" ]; then log "run held ($TDIR/HOLD): no call; release with --release run"; return 3; fi
    name="$(basename "$f")"
    case "$name" in .*) continue;; esac
    safe="$(printf '%s' "$name" | sed 's/[^A-Za-z0-9._-]/-/g')"   # triage_id pattern: trg-[A-Za-z0-9._-]+-NN
    mv "$f" "$TDIR/processing/$safe"
    rc=0; triage_one "$safe" || rc=$?
    rm -rf "$WORK"; WORK=""
    # a message held at its cap is out of the inbox: go on with the rest unless the run is held
    if [ "$rc" = 3 ] && [ ! -e "$TDIR/HOLD" ] && [ -f "$TDIR/held/$safe" ]; then continue; fi
    [ "$rc" = 0 ] || return "$rc"
  done
}

if [ -n "$RELEASE" ]; then release_cmd "$RELEASE"; exit $?; fi
if [ "$WATCH" = 0 ]; then pass; exit $?; fi
while :; do pass || exit $?; sleep "$WATCH"; done
