#!/usr/bin/env bash
# Phase 71 (REQ-0029): inbox-triage orchestrator + adapter against a scratch kit with its own ReqKit
# ledger and a fake `claude` that replays tools/triage/tests/fixtures/fake/<stem>/. No tokens; this
# repo's docs/req and .triage are never touched.
#
#   bash tools/triage/tests/triage_test.sh [toolkit-dir]     (run_all: tests/triage_test.sh)
set -Eeuo pipefail
KIT="$(cd "${1:-$(dirname "${BASH_SOURCE[0]}")/../../..}" && pwd)"
FIX="$KIT/tools/triage/tests/fixtures"
WORK="$(mktemp -d)"
trap '[ -z "${KEEP:-}" ] || cp -R "$WORK" "$KEEP"; rm -rf "$WORK"' EXIT

PASS=0; FAIL=0
check() {  # check <name> <want> <got>
  if [ "$2" = "$3" ]; then echo "PASS: $1"; PASS=$((PASS + 1))
  else echo "FAIL: $1 (want '$2', got '$3')"; FAIL=$((FAIL + 1)); fi
}
yn() { if "$@"; then echo yes; else echo no; fi; }

# scratch kit: triage tools, the kit's agent + skill, a ReqKit copy with an empty ledger, one plan
K="$WORK/kit"
mkdir -p "$K/tools" "$K/.claude/agents" "$K/.claude/skills" "$K/.claude/req" "$K/plans/Sys/main" "$WORK/bin" "$WORK/calls"
cp -R "$KIT/tools/triage" "$K/tools/"; cp "$KIT/job_hold.sh" "$K/"
cp "$KIT/.claude/agents/inbox-triage.md" "$K/.claude/agents/"
cp -R "$KIT/.claude/skills/inbox-triage" "$KIT/.claude/skills/req-intake" "$K/.claude/skills/"
mkdir -p "$K/docs/guide"; cp "$KIT/CLAUDE.md" "$K/"; cp "$KIT/docs/guide/toolkit-reference.md" "$K/docs/guide/"   # context pack sources
cp "$KIT/.claude/req/req.py" "$K/.claude/req/"
export CLAUDE_PROJECT_DIR="$K" REQ_DIR="docs/req"
REQ="python3 $K/.claude/req/req.py"
$REQ init >/dev/null
$REQ new --title "Old report colour change" --text "Change the report colour." >/dev/null
printf 'docs/req/.lock\n.triage/\n' > "$K/.gitignore"
git -C "$K" init -q && git -C "$K" add -A && git -C "$K" -c user.email=t@t -c user.name=t commit -qm base
T="$K/.triage"
raws() { find "$K/docs/req/raw" -name 'RAW-*.md' 2>/dev/null | wc -l | tr -d ' '; }

# fake claude: replays the fixture for the message named in the prompt, logs argv + cwd
cat > "$WORK/bin/claude" <<'EOF'
#!/usr/bin/env bash
n=$(( $(find "$CALLS" -mindepth 1 -maxdepth 1 | wc -l) + 1 )); d="$CALLS/$n"; mkdir -p "$d"
printf '%s\n' "$@" > "$d/argv"; pwd > "$d/cwd"
prompt="$2"; name="$(printf '%s\n' "$prompt" | sed -n 's/^INBOX_FILE: msg\///p')"; stem="${name%.*}"
printf '%s\n' "$prompt" > "$d/prompt"; cp "msg/$name" "$d/msg" 2>/dev/null || true; ls context > "$d/context" 2>/dev/null || true; cp -R context "$d/ctx" 2>/dev/null || true
case "${FAKE_MODE:-}" in
  service) echo '{"type":"result","is_error":true,"result":"rate limit reached"}'; exit 1 ;;
  stray) echo x > ./stray.txt ;;
esac
src="$FIX/fake/$stem"
[ -d "$src" ] || { jq -n '{type:"result",is_error:false,result:"no fixture"}'; exit 0; }
[ ! -d "$src/staging" ] || cp "$src"/staging/*.json .triage/staging/ 2>/dev/null || true
[ ! -d "$src/outbox" ] || cp "$src"/outbox/* .triage/outbox/ 2>/dev/null || true
jq -n --arg r "$(cat "$src/result.txt")" '{type:"result",is_error:false,result:("done\n" + $r)}'
EOF
chmod +x "$WORK/bin/claude"
export CLAUDE_BIN="$WORK/bin/claude" CALLS="$WORK/calls" FIX
orch() { bash "$K/tools/triage/orchestrate.sh" > "$WORK/orch.out" 2>&1; }
drop() { cp "$FIX/inbox/$1" "$T/inbox/$1"; }

mkdir -p "$T/inbox"
# V1 simple -> one record -> one RAW
drop simple.md; r0="$(raws)"; rc=0; orch || rc=$?
rid="$(jq -r '.reqkit_id' "$T/submitted/trg-simple-01.json" 2>/dev/null || echo none)"
check "V1 simple: rc 0, one RAW, message in done/, record in submitted/ with reqkit_id" "0|$((r0 + 1))|yes|RAW-00001" \
  "$rc|$(raws)|$(yn test -f "$T/done/simple.md")|$rid"
check "V1 RAW text: header line with triage_id and target, title, task" "yes|yes|yes" \
  "$(yn grep -q '^\[inbox-triage trg-simple-01 · config · - · target toolkit\]$' "$K/docs/req/raw/RAW-00001.md")|$(yn grep -q '^Add --json flag to status.sh$' "$K/docs/req/raw/RAW-00001.md")|$(yn grep -q '^- status.sh --json prints' "$K/docs/req/raw/RAW-00001.md")"
check "V1 RAW is NEW (untriaged: req-intake sorts it like a typed prompt)" "NEW" \
  "$(sed -n 's/^status: //p' "$K/docs/req/raw/RAW-00001.md")"
a="$WORK/calls/1/argv"
check "V1 agent call: Read,Write only, agent inbox-triage, cwd outside the kit, prompt has all 4 inputs" "yes|yes|yes|yes" \
  "$(yn grep -qx 'Read,Write' "$a")|$(awk 'p{print;exit} $0=="--agent"{p=1}' "$a" | grep -qx inbox-triage && echo yes || echo no)|$(case "$(cat "$WORK/calls/1/cwd")" in "$K"*) echo no;; *) echo yes;; esac)|$(grep -c -e '^INBOX_FILE: ' -e '^RUN_TS: ' -e '^KNOWN_TARGETS:' -e '^OPEN_REQUESTS:' "$WORK/calls/1/prompt" | sed 's/^4$/yes/')"
check "V1 prompt lists targets and open requests" "yes|yes" \
  "$(yn grep -qx 'Sys/main' "$WORK/calls/1/prompt")|$(yn grep -qx 'REQ-0001 | toolkit | Old report colour change' "$WORK/calls/1/prompt")"
check "V1 agents json: model sonnet, tools Read+Write, prompt from the agent file" "sonnet|Read,Write|yes" \
  "$(awk 'p{print;exit} $0=="--agents"{p=1}' "$a" | jq -r '."inbox-triage".model')|$(awk 'p{print;exit} $0=="--agents"{p=1}' "$a" | jq -r '."inbox-triage".tools|join(",")')|$(awk 'p{print;exit} $0=="--agents"{p=1}' "$a" | jq -r '."inbox-triage".prompt' | grep -q 'You are the inbox-triage subagent' && echo yes || echo no)"

check "71.8 context pack in the agent cwd: 5 files, skills list names req-intake" "project.md reference-toc.md req-intake.md requirements.md skills.md|yes" \
  "$(tr '\n' ' ' < "$WORK/calls/1/context" | sed 's/ $//')|$(yn grep -q 'skill `req-intake`' "$WORK/calls/1/ctx/skills.md")"

# V2 two tasks -> two records -> two RAWs
drop two-tasks.md; r0="$(raws)"; orch || true
check "V2 two tasks: two records submitted, two RAWs" "yes|yes|$((r0 + 2))" \
  "$(yn test -f "$T/submitted/trg-two-tasks-01.json")|$(yn test -f "$T/submitted/trg-two-tasks-02.json")|$(raws)"

# V3 ambiguous -> CLARIFY, question in outbox, nothing submitted
drop ambiguous.md; r0="$(raws)"; orch || true
check "V3 ambiguous: question in outbox, record held, no RAW, not in submitted/" "yes|yes|$r0|no" \
  "$(yn test -s "$T/outbox/trg-ambiguous-01.question.md")|$(yn test -f "$T/outbox/trg-ambiguous-01.json")|$(raws)|$(yn test -f "$T/submitted/trg-ambiguous-01.json")"
check "V3 log: CLARIFY" "yes" "$(yn grep -q 'ambiguous.md CLARIFY 1 trg-ambiguous-01' "$T/logs/orchestrate.log")"

# R1 reply to the held clarification -> held context appended, new RAW, held request closed
drop reply.md; r0="$(raws)"; orch || true
lc="$(find "$WORK/calls" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')"
R="$(jq -r '.reqkit_id' "$T/submitted/trg-reply-01.json" 2>/dev/null || echo none)"
check "R1 reply: message copy carries the held request, one RAW with Answers held request, held moved to answered/" "yes|$((r0 + 1))|yes|yes|no" \
  "$(yn grep -q '^--- Held request trg-ambiguous-01' "$WORK/calls/$lc/msg")|$(raws)|$(yn grep -qx 'Answers held request: trg-ambiguous-01' "$K/docs/req/raw/$R.md")|$(yn test -f "$T/outbox/answered/trg-ambiguous-01.question.md")|$(yn test -f "$T/outbox/trg-ambiguous-01.json")"
# R2 the user's case: a reply marked update with no REQ id -> invalid, and its question is not left in outbox/
drop badreply.md; r0="$(raws)"; orch || true
check "R2 bad reply: invalid (schema related_reqkit_id), question moved to invalid/, no RAW" "yes|no|yes|$r0" \
  "$( (jq -r .reason "$T/invalid/trg-badreply-01.json" 2>/dev/null || true) | grep -q 'related_reqkit_id: expected string' && echo yes || echo no)|$(yn test -f "$T/outbox/trg-badreply-01.question.md")|$(yn test -f "$T/invalid/trg-badreply-01.question.md")|$(raws)"

# V4 injected instructions -> flagged, transcribed, nothing executed
drop injection.md; r0="$(raws)"; orch || true
R="$(jq -r '.reqkit_id' "$T/submitted/trg-injection-01.json")"
check "V4 injection: one RAW with Flags: suspicious_instruction, repo tree unchanged" "$((r0 + 1))|yes|" \
  "$(raws)|$(yn grep -qx 'Flags: suspicious_instruction' "$K/docs/req/raw/$R.md")|$(git -C "$K" status --porcelain | grep -v ' docs/req/' || true)"

# V5 cancel of an open request -> intent + related_reqkit_id
drop cancel.md; orch || true
R="$(jq -r '.reqkit_id' "$T/submitted/trg-cancel-01.json")"
check "V5 cancel: RAW says Relates to: REQ-0001 (cancel); REQ-0001 untouched (ReqKit decides)" "yes|TODO" \
  "$(yn grep -qx 'Relates to: REQ-0001 (cancel)' "$K/docs/req/raw/$R.md")|$(sed -n 's/^status: //p' "$K/docs/req/items/REQ-0001.md")"

# V6 chatter -> NOOP
drop thanks.md; r0="$(raws)"; orch || true
check "V6 thanks: NOOP, no RAW, message in done/" "$r0|yes|yes" \
  "$(raws)|$(yn test -f "$T/done/thanks.md")|$(yn grep -q 'thanks.md NOOP 0 -' "$T/logs/orchestrate.log")"

# V7 re-run the same inbox file -> no duplicate RAW
drop simple.md; r0="$(raws)"; orch || true
check "V7 re-run simple: no new RAW, logged duplicate of RAW-00001, ledger has one row" "$r0|yes|1" \
  "$(raws)|$(yn grep -q 'trg-simple-01	duplicate	already RAW-00001' "$T/logs/adapter.log")|$(grep -c '^trg-simple-01	' "$T/ledger.tsv")"

# V8 malformed staging record -> invalid/, ReqKit untouched
cp "$FIX/malformed-record.json" "$T/staging/trg-malformed-01.json"; r0="$(raws)"; rc=0
python3 "$K/tools/triage/adapter.py" --triage-dir "$T" >/dev/null || rc=$?
check "V8 malformed: rc 1, in invalid/ with schema reason, no RAW, staging emptied" "1|yes|$r0|no" \
  "$rc|$(jq -r '.reason' "$T/invalid/trg-malformed-01.json" | grep -q '^schema: .*missing confidence' && echo yes || echo no)|$(raws)|$(yn test -f "$T/staging/trg-malformed-01.json")"

# extra: secret in a record -> invalid, value not logged
jq '.triage_id="trg-secret-01" | .task="Rotate it: password=Hunter2Secret99"' "$FIX/fake/simple/staging/trg-simple-01.json" > "$T/staging/trg-secret-01.json"
rc=0; python3 "$K/tools/triage/adapter.py" --triage-dir "$T" >/dev/null || rc=$?
check "secret: rc 1, reason secret_detected, value not in the log" "1|secret_detected: assignment|no" \
  "$rc|$(jq -r .reason "$T/invalid/trg-secret-01.json")|$(yn grep -q Hunter2 "$T/logs/adapter.log")"
# extra: unknown target and alias
jq '.triage_id="trg-alias-01" | .target="scanner"' "$FIX/fake/simple/staging/trg-simple-01.json" > "$T/staging/trg-alias-01.json"
jq '.triage_id="trg-target-01" | .target="nope/x"' "$FIX/fake/simple/staging/trg-simple-01.json" > "$T/staging/trg-target-01.json"
python3 "$K/tools/triage/adapter.py" --triage-dir "$T" >/dev/null || true
R="$(jq -r '.reqkit_id' "$T/submitted/trg-alias-01.json" 2>/dev/null)"
check "targets: alias scanner -> toolkit accepted; unknown target invalid" "yes|unknown_target: nope/x" \
  "$(yn grep -q 'target toolkit\]$' "$K/docs/req/raw/$R.md")|$(jq -r .reason "$T/invalid/trg-target-01.json")"

# extra: write guard -> failed/, nothing submitted
drop two-tasks.md; cp "$FIX/inbox/two-tasks.md" "$T/inbox/stray.md"; rm "$T/inbox/two-tasks.md"
r0="$(raws)"; FAKE_MODE=stray orch || true
check "write guard: stray write -> failed/, no RAW" "yes|$r0|yes" \
  "$(yn test -f "$T/failed/stray.md")|$(raws)|$(yn grep -q 'stray.md FAILED write_guard: unexpected writes: ./stray.txt' "$T/logs/orchestrate.log")"

# extra: service failure -> message back in inbox, exit 3; lock busy -> 11
drop simple.md; rc=0; FAKE_MODE=service orch || rc=$?
check "service failure: rc 3, message back in inbox/" "3|yes" "$rc|$(yn test -f "$T/inbox/simple.md")"
rm -f "$T/inbox/simple.md"
mkdir "$T/.lock"; rc=0; orch || rc=$?; rmdir "$T/.lock"
check "lock busy: rc 11" "11" "$rc"

# U10 (72.5g): a message with 2 service failures is held (no 3rd call); 2 distinct failing messages
# raise the run hold (HOLD file, no call, watcher does not drain); releases put things back
ncalls() { find "$WORK/calls" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' '; }
drop simple.md; rc=0; FAKE_MODE=service orch || rc=$?
check "U10 same message fails twice: held/, out of inbox, ledger status held, one hold line" "yes|no|held|1" \
  "$(yn test -f "$T/held/simple.md")|$(yn test -f "$T/inbox/simple.md")|$(jq -r '[.jobs[]|.status][0]' "$T/holds.json")|$(grep -c 'simple.md HELD' "$T/logs/orchestrate.log")"
check "U10 one held message alone is no run hold" "no" "$(yn test -f "$T/HOLD")"
cp "$FIX/inbox/thanks.md" "$T/inbox/h2.md"; rc=0; FAKE_MODE=service orch || rc=$?
check "U10 2nd distinct failing message: rc 3, HOLD written (streak), message stays in inbox" "3|yes|streak|yes" \
  "$rc|$(yn test -f "$T/HOLD")|$(jq -r '.why' "$T/HOLD" 2>/dev/null)|$(yn test -f "$T/inbox/h2.md")"
c0="$(ncalls)"; rc=0; orch || rc=$?
check "U10 run held: rc 3, no claude call, log says run held" "3|$c0|yes" \
  "$rc|$(ncalls)|$(yn grep -q 'run held' "$WORK/orch.out")"
TRIAGE_NO_INOTIFY=1 bash "$K/tools/triage/watch.sh" --poll 1 > "$WORK/watch3.out" 2>&1 &
wp=$!; sleep 3; kill "$wp"; wait "$wp" 2>/dev/null || true
check "U10 watcher: no drain while HOLD exists, logged once, no backoff line, no call" "$c0|1|0" \
  "$(ncalls)|$(grep -c 'run held' "$T/logs/watch.log")|$(grep -c 'retry in' "$T/logs/watch.log")"
rc=0; bash "$K/tools/triage/orchestrate.sh" --release nosuch.md > /dev/null 2>&1 || rc=$?
check "U10 --release of an unknown message: rc 2" "2" "$rc"
bash "$K/tools/triage/orchestrate.sh" --release run > /dev/null 2>&1
bash "$K/tools/triage/orchestrate.sh" --release simple.md > /dev/null 2>&1
check "U10 release: HOLD gone, simple.md back in inbox, ledger job released (pending, counts cleared)" "no|yes|pending|0" \
  "$(yn test -f "$T/HOLD")|$(yn test -f "$T/inbox/simple.md")|$(jq -r '[.jobs[]|select(.key|startswith("simple.md@"))|.status][0]' "$T/holds.json")|$(jq -r '[.jobs[]|select(.key|startswith("simple.md@"))|(.fail_counts|length)][0]' "$T/holds.json")"
rm -f "$T/inbox/simple.md" "$T/inbox/h2.md"

# extra: file names with spaces become safe triage ids; no fixture -> bad output -> failed/
cp "$FIX/inbox/thanks.md" "$T/inbox/my note.md"; orch || true
check "unsafe name renamed my-note.md; no TRIAGE line -> failed/" "yes" "$(yn test -f "$T/failed/my-note.md")"

# W1 watcher (poll mode; inotifywait may be absent): picks up a drop, single instance, clean stop
TRIAGE_NO_INOTIFY=1 bash "$K/tools/triage/watch.sh" --poll 1 > "$WORK/watch.out" 2>&1 &
wp=$!
cp "$FIX/inbox/thanks.md" "$T/inbox/w1.md"
for _ in $(seq 1 30); do [ -f "$T/failed/w1.md" ] || [ -f "$T/done/w1.md" ] && break; sleep 0.5; done
rc=0; TRIAGE_NO_INOTIFY=1 bash "$K/tools/triage/watch.sh" --poll 1 >/dev/null 2>&1 || rc=$?
check "W1 watcher: drop picked up without a manual run; second watcher refused (11)" "yes|11" \
  "$(yn test ! -f "$T/inbox/w1.md" -a \( -f "$T/failed/w1.md" -o -f "$T/done/w1.md" \))|$rc"
kill "$wp"; wait "$wp" 2>/dev/null || true
check "W1 watcher stop: pid file removed, log says started (poll)" "no|yes" \
  "$(yn test -f "$T/.watch.pid")|$(yn grep -q 'started (poll every 1s' "$T/logs/watch.log")"

# W2 watcher, inotify mode (when inotify-tools is installed): instant pickup of a drop made after start
if command -v inotifywait >/dev/null 2>&1; then
  bash "$K/tools/triage/watch.sh" > "$WORK/watch2.out" 2>&1 &
  wp=$!
  for _ in $(seq 1 20); do grep -q 'started (inotify)' "$T/logs/watch.log" 2>/dev/null && break; sleep 0.25; done
  sleep 0.5; cp "$FIX/inbox/thanks.md" "$T/inbox/w2.md"
  for _ in $(seq 1 20); do [ -f "$T/failed/w2.md" ] && break; sleep 0.25; done
  check "W2 watcher (inotify): drop after start picked up within 5 s (no fixture: failed/)" "yes|yes" \
    "$(yn grep -q 'started (inotify)' "$T/logs/watch.log")|$(yn test -f "$T/failed/w2.md")"
  kill "$wp"; wait "$wp" 2>/dev/null || true
  check "W2 watcher stop: no inotifywait left, pid file removed" "0|no" \
    "$(pgrep -f "inotifywait.*$T/inbox" | wc -l | tr -d ' ')|$(yn test -f "$T/.watch.pid")"
else
  echo "SKIP: W2 inotify mode (inotify-tools not installed)"
fi

# the kit's ReqKit code is unchanged by all of this
check "ReqKit copy unchanged (req.py)" "yes" "$(yn cmp -s "$KIT/.claude/req/req.py" "$K/.claude/req/req.py")"

echo "SUMMARY(triage): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
