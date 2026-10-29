#!/usr/bin/env bash
# TASK-074 74.2: .claude/scripts/lessons.py (collect, similar, patch, mark-from, scope), $0.
# Scratch root per case (mktemp), --root points the script there; the real repo is never touched.
# apply-patches.sh is main-only for roles, so the patch contract is checked by running the patch directly.
# Run: bash .claude/tests/lessons_test.sh      (KIT_DIR=<.claude copy> tests another copy, the bite check)
set -Eeuo pipefail
KIT="${KIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LP="$KIT/scripts/lessons.py"
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
L() { python3 -B "$LP" --root "$R" "$@"; }

R="$WORK/r"
fixture() {
  rm -rf "$R"
  mkdir -p "$R/work/TASK-9/handoff" "$R/.claude/skills/alpha" "$R/.claude/agents" "$R/.claude/lessons"
  cat > "$R/work/TASK-9/handoff/coder.md" <<'EOF'
PROGRESS: COMPLETE
## Lessons
- L: kind=tip target=alpha | always quote paths in alpha scripts | evidence=work/TASK-9/x.log
- L: kind=wrong-rule target=agent:coder | coder must commit after edit | evidence=-
- L: kind=bogus target=alpha | bad kind line | evidence=-
- L: not a lesson line
## Other
- L: kind=tip target=alpha | outside section ignored | evidence=-
EOF
  printf '# Alpha\n- quote every path in alpha scripts (RAW-00123)\n- other rule about widgets\n' > "$R/.claude/skills/alpha/SKILL.md"
  printf -- '---\nname: coder\nskills: alpha\n---\nbody line\n' > "$R/.claude/agents/coder.md"
  printf '# Claude\nnever commit as a role\n' > "$R/CLAUDE.md"
  printf 'refusal log\n' > "$R/work/TASK-9/x.log"   # 74.7: the first lesson's evidence exists
}
fixture

# collect
expect "C1 collect new/bad counts" 0 "TOTAL new=2 seen=0 bad=2" L collect "$R/work/TASK-9"
# 74.7a: evidence_ok is true for an existing repo file, false for "-"
expect "E1 evidence_ok true for an existing file" 0 '"evidence_ok": true' L collect "$R/work/TASK-9"
expect "E2 evidence_ok false for '-'" 0 '"evidence_ok": false' L collect "$R/work/TASK-9"
# 74.7a evidence_ok: direct calls, one per rejected shape
EV() { python3 -B -c 'import sys; sys.path.insert(0, sys.argv[1]); import lessons; print(lessons.evidence_ok(sys.argv[2], sys.argv[3]))' "$(dirname "$LP")" "$R" "$1"; }
expect "E3 evidence_ok true for work/TASK-9/x.log:3" 0 "True" EV "work/TASK-9/x.log:3"
expect "E4 evidence_ok false for empty" 0 "False" EV ""
expect "E5 evidence_ok false for a missing file" 0 "False" EV "work/TASK-9/missing.log"
expect "E6 evidence_ok false for a parent-dir escape" 0 "False" EV "../../etc/passwd"
expect "E7 evidence_ok false for an absolute path outside the repo" 0 "False" EV "/etc/passwd"
expect "E8 evidence_ok false for a directory" 0 "False" EV "work/TASK-9"
KEY="$(L collect "$R/work/TASK-9" | head -n 1 | python3 -c 'import json,sys; print(json.loads(sys.stdin.readline())["key"])')"
expect "C2 key is sha256 hex" 0 "" test "${#KEY}" -eq 64
expect "C3 path outside work rejected" 1 "outside root" L collect /etc
# mark_from fixture: curate file
CUR="$R/work/TASK-9/handoff/curate.md"
printf '| key | verdict | file | reason |\n|---|---|---|---|\n| %s | merged | .claude/skills/alpha/SKILL.md | dup |\n' "$KEY" > "$CUR"
expect "M1 mark-from appends" 0 "marked 1" L mark-from "$CUR"
expect "M2 ledger row has where=path:line" 0 ".claude/skills/alpha/SKILL.md" cat "$R/.claude/lessons/ledger.jsonl"
expect "M3 second mark-from rc 2 (dedupe)" 2 "already in ledger" L mark-from "$CUR"
LINES="$(wc -l < "$R/.claude/lessons/ledger.jsonl" | tr -d ' ')"
expect "M4 ledger not duplicated" 0 "" test "$LINES" -eq 1
expect "C4 collect skips marked key" 0 "TOTAL new=1 seen=1 bad=2" L collect "$R/work/TASK-9"
printf '| %s | merged | x | y |\n' "$(printf 'z%.0s' $(seq 64))" > "$WORK/junk.md"
expect "M5 bad curate path rejected" 1 "outside root" L mark-from "$WORK/junk.md"
printf '| %s | bogus | a | b |\n' "$KEY" > "$R/work/TASK-9/handoff/curate2.md"
expect "M6 unknown key/verdict rejected" 1 "bad verdict" L mark-from "$R/work/TASK-9/handoff/curate2.md"

# 74.7 evidence gate + watch rows
expect "W1 skill row has status watch" 0 '"status": "watch"' cat "$R/.claude/lessons/ledger.jsonl"
expect "W2 row names skill and evidence" 0 '"skill": "alpha"' cat "$R/.claude/lessons/ledger.jsonl"
expect "W3 row keeps the evidence path" 0 '"evidence": "work/TASK-9/x.log"' cat "$R/.claude/lessons/ledger.jsonl"
expect "W4 row lists the roles loading the skill" 0 '"roles": ["coder"]' cat "$R/.claude/lessons/ledger.jsonl"
expect "W5 row has the new text" 0 '"new": "always quote paths in alpha scripts"' cat "$R/.claude/lessons/ledger.jsonl"
expect "W6 watch lists the row" 0 "TOTAL watch=1" L watch
expect "W7 watch line has skill and roles" 0 "alpha	coder" L watch
KEY2="$(L collect "$R/work/TASK-9" | head -n 1 | python3 -c 'import json,sys; print(json.loads(sys.stdin.readline())["key"])')"
printf '| %s | applied | .claude/skills/alpha/SKILL.md | new |\n' "$KEY2" > "$R/work/TASK-9/handoff/curate3.md"
expect "N1 skill edit without evidence rc 2" 2 "no-evidence" L mark-from "$R/work/TASK-9/handoff/curate3.md"
LINES="$(wc -l < "$R/.claude/lessons/ledger.jsonl" | tr -d ' ')"
expect "N2 nothing written on no-evidence" 0 "" test "$LINES" -eq 1
printf '| %s | applied | .claude/agents/coder.md | new |\n' "$KEY2" > "$R/work/TASK-9/handoff/curate4.md"
expect "N3 agent-file row without evidence is gated (F-74-V1)" 2 "no-evidence" L mark-from "$R/work/TASK-9/handoff/curate4.md"
printf '| %s | rejected | .claude/skills/alpha/SKILL.md | no-evidence |\n' "$KEY2" > "$R/work/TASK-9/handoff/curate5.md"
head -n 1 "$R/.claude/lessons/ledger.jsonl" > "$WORK/ledger1"   # keep only the header row (N3 wrote nothing)
cp "$WORK/ledger1" "$R/.claude/lessons/ledger.jsonl"
expect "N4 rejected row needs no evidence" 0 "marked 1" L mark-from "$R/work/TASK-9/handoff/curate5.md"
expect "N5 rejected row is not a watch row" 0 "TOTAL watch=1" L watch
expect "WS1 watch --set kept" 0 "set ${KEY:0:12} kept" L watch --set "$KEY" kept
expect "WS2 watch list now empty" 0 "TOTAL watch=0" L watch
expect "WS3 set on a settled key rc 2" 2 "no watch row" L watch --set "$KEY" reverted
expect "WS3b valid-format key absent from the ledger rc 2" 2 "no watch row" L watch --set "$(printf 'a%.0s' $(seq 64))" kept
expect "WS3c malformed key rc 1" 1 "usage" L watch --set nothex kept
expect "WS4 bad status rc 1" 1 "usage" L watch --set "$KEY" bogus
expect "WS5 status stored" 0 '"status": "kept"' cat "$R/.claude/lessons/ledger.jsonl"

# similar
expect "S1 duplicate ranked first with raw flag" 0 "SKILL.md:2" L similar "always quote paths in alpha scripts"
OUT="$(L similar "always quote paths in alpha scripts" | head -n 1)"
expect "S2 raw id shown" 0 "raw=RAW-00123" printf '%s' "$OUT"
mkdir -p "$R/docs/guide"
printf '%s\n' "- zebra widgets must always frobnicate carefully" > "$R/docs/guide/workflow-roles.md"
expect "S4 workflow-roles doc listed" 0 "workflow-roles.md:1" L similar "zebra widgets frobnicate carefully"
expect "S3 empty text rejected" 1 "no usable words" L similar "a b"

# patch
expect "P1 patch writes" 0 "patch work/TASK-9/patches/01-quote.py" \
  L patch --file .claude/skills/alpha/SKILL.md --anchor "- other rule about widgets" --after "- always quote paths" --out work/TASK-9/patches/01-quote.py
expect "P2 bundle line" 0 "01-quote.py	.claude/skills/alpha" cat "$R/work/TASK-9/patches/bundle.txt"
cp "$R/.claude/skills/alpha/SKILL.md" "$WORK/before.md"
expect "P3 patch applies" 0 "applied" python3 -B "$R/work/TASK-9/patches/01-quote.py" "$R/.claude/skills/alpha"
cp "$R/.claude/skills/alpha/SKILL.md" "$WORK/after1.md"
expect "P4 patch changed file" 0 "- always quote paths" cat "$R/.claude/skills/alpha/SKILL.md"
expect "P5 second apply is idempotent" 0 "already applied" python3 -B "$R/work/TASK-9/patches/01-quote.py" "$R/.claude/skills/alpha"
expect "P6 idempotent file unchanged" 0 "" cmp "$WORK/after1.md" "$R/.claude/skills/alpha/SKILL.md"
cp "$WORK/before.md" "$R/.claude/skills/alpha/SKILL.md"
printf -- '- other rule about widgets\n- other rule about widgets\n' >> "$R/.claude/skills/alpha/SKILL.md"
expect "P7 duplicate anchor fails" 1 "matched 3 times" python3 -B "$R/work/TASK-9/patches/01-quote.py" "$R/.claude/skills/alpha"
expect "P8 anchor not a line" 1 "not an exact line" \
  L patch --file .claude/skills/alpha/SKILL.md --anchor "nope" --after "x" --out work/TASK-9/patches/02-x.py
expect "P9 file outside allowed set" 3 "allowed set" \
  L patch --file CLAUDE.md --anchor "never commit as a role" --after "x" --out work/TASK-9/patches/02-x.py
expect "P10 path escape" 1 "outside root" \
  L patch --file ../../etc/passwd --anchor a --after b --out work/TASK-9/patches/02-x.py
expect "P11 bad out name" 1 "--out must be" \
  L patch --file .claude/skills/alpha/SKILL.md --anchor "# Alpha" --after "x" --out work/TASK-9/patches/evil.py

# scope (scratch git repo built here)
fixture
git -C "$R" init -q
git -C "$R" config user.email t@example.invalid
git -C "$R" config user.name test
mkdir -p "$R/docs"
seq 1 79 | sed 's/^/l/' > "$R/.claude/skills/alpha/SKILL.md"
seq 1 81 | sed 's/^/l/' > "$R/.claude/skills/big.md"
git -C "$R" add -A >/dev/null
git -C "$R" commit -q -m base
expect "G1 clean tree rc 0" 0 "" L scope
echo "l80" >> "$R/.claude/skills/alpha/SKILL.md"
expect "G2 skill grows to 80 ok" 0 "" L scope
echo "l81" >> "$R/.claude/skills/alpha/SKILL.md"
expect "G3 skill grows past 80 rc 4" 4 "GREW" L scope
git -C "$R" checkout -q -- .claude/skills/alpha/SKILL.md
sed -i.bak '1,3d' "$R/.claude/skills/big.md"; rm -f "$R/.claude/skills/big.md.bak"
expect "G4 over-80 skill that shrinks ok" 0 "" L scope
git -C "$R" checkout -q -- .claude/skills/big.md
echo "l82" >> "$R/.claude/skills/big.md"
expect "G4b 74.5 skill 81 -> 82 lines rc 4" 4 "GREW" L scope
git -C "$R" checkout -q -- .claude/skills/big.md
printf -- '---\nname: coder2\n---\nbody line\n' > "$R/.claude/agents/coder.md"
expect "G5 agent frontmatter change rc 4" 4 "FRONTMATTER" L scope
printf -- '---\nname: coder\nskills: alpha\n---\nbody line\nmore\n' > "$R/.claude/agents/coder.md"
expect "G6 agent body change ok" 0 "" L scope
echo x > "$R/docs/note.md"
expect "G7 path outside allowed set rc 3" 3 "OUTSIDE docs/note.md" L scope
expect "G8 bad rev rejected" 1 "bad rev" L scope --base=--output=x

# 74.6 seeded lessons: a duplicate, a contradiction of a RAW rule, a new tip ($0; the agent part is main's)
lowscore() { printf '%s\n' "$1" | awk 'NR==1 && $2+0 >= 0.3 { exit 1 }'; }
keyof() { L collect "$R/work/TASK-9" | python3 -c '
import json, sys
for line in sys.stdin:
    if line.startswith("{") and json.loads(line)["text"] == sys.argv[1]:
        print(json.loads(line)["key"])' "$1"; }
fixture
mkdir -p "$R/.claude/skills/token-efficiency"
printf '# TE\n- read files in slices of at most 300 lines using offset and limit\n' > "$R/.claude/skills/token-efficiency/SKILL.md"
printf '# Claude\n- roles never commit their own edits, the main session commits (RAW-00200)\n' > "$R/CLAUDE.md"
DUP="read files in slices of at most 300 lines using offset and limit"
CON="roles may commit their own edits after finishing"
NEW="pin the fixture clock before comparing stamps"
cat > "$R/work/TASK-9/handoff/coder.md" <<EOF
PROGRESS: COMPLETE
## Lessons
- L: kind=tip target=token-efficiency | $DUP | evidence=work/TASK-9/x.log
- L: kind=wrong-rule target=CLAUDE.md | $CON | evidence=work/TASK-9/x.log
- L: kind=tip target=token-efficiency | $NEW | evidence=work/TASK-9/x.log
EOF
expect "Z1 seeded: three lessons collected" 0 "TOTAL new=3 seen=0 bad=0" L collect "$R/work/TASK-9"
OUT="$(L similar "$DUP" | head -n 1)"
expect "Z2 duplicate ranks its source line first" 0 "token-efficiency/SKILL.md:2 1.000" printf '%s' "$OUT"
OUT="$(L similar "$CON" | head -n 1)"
expect "Z3 contradiction hit carries the RAW id" 0 "CLAUDE.md:2" printf '%s' "$OUT"
expect "Z4 contradiction raw=RAW-00200" 0 "raw=RAW-00200" printf '%s' "$OUT"
OUT="$(L similar "$NEW" | head -n 1)"
expect "Z5 new tip has no close match" 0 "" lowscore "$OUT"
cp "$R/.claude/skills/token-efficiency/SKILL.md" "$WORK/te.before"
expect "Z6 patch for the new tip" 0 "patch work/TASK-9/patches/01-new.py" \
  L patch --file .claude/skills/token-efficiency/SKILL.md --anchor "# TE" --after "- $NEW" --out work/TASK-9/patches/01-new.py
expect "Z7 patch applies" 0 "applied" python3 -B "$R/work/TASK-9/patches/01-new.py" "$R/.claude/skills/token-efficiency"
cp "$R/.claude/skills/token-efficiency/SKILL.md" "$WORK/te.after"
expect "Z8 only the new line was added" 0 "" test "$(wc -l < "$WORK/te.after" | tr -d ' ')" -eq "$(( $(wc -l < "$WORK/te.before" | tr -d ' ') + 1 ))"
expect "Z8b the new line is in the skill" 0 "- $NEW" cat "$WORK/te.after"
expect "Z9 second apply changes nothing" 0 "already applied" python3 -B "$R/work/TASK-9/patches/01-new.py" "$R/.claude/skills/token-efficiency"
expect "Z10 file unchanged by the second apply" 0 "" cmp "$WORK/te.after" "$R/.claude/skills/token-efficiency/SKILL.md"
printf '| %s | merged | .claude/skills/token-efficiency/SKILL.md | dup |\n| %s | rejected | CLAUDE.md | contradicts RAW-00200 |\n| %s | applied | .claude/skills/token-efficiency/SKILL.md | new |\n' \
  "$(keyof "$DUP")" "$(keyof "$CON")" "$(keyof "$NEW")" > "$R/work/TASK-9/handoff/curate.md"
expect "Z11 verdicts marked" 0 "marked 3" L mark-from "$R/work/TASK-9/handoff/curate.md"
expect "Z12 nothing left to curate" 0 "TOTAL new=0 seen=3" L collect "$R/work/TASK-9"
expect "Z13 only the two skill edits are watched" 0 "TOTAL watch=2" L watch

# 74.7 watch row fields: commit = HEAD at marking time, hunk = anchor of a replace patch
# (own task dir TASK-8, so the first-match patch lookup does not pick 01-new.py of TASK-9)
GT() { git -C "$R" "$@"; }
GT init -q; GT config user.email t@example.invalid; GT config user.name test
GT add -A >/dev/null; GT commit -q -m zbase
HEADC="$(GT rev-parse HEAD)"
HK="- hunk anchor line"
printf '%s\n' "$HK" >> "$R/.claude/skills/token-efficiency/SKILL.md"
TIP="replace tip for the hunk row"
mkdir -p "$R/work/TASK-8/handoff"
printf 'PROGRESS: COMPLETE\n## Lessons\n- L: kind=tip target=token-efficiency | %s | evidence=work/TASK-9/x.log\n' "$TIP" > "$R/work/TASK-8/handoff/coder.md"
HKEY="$(L collect "$R/work/TASK-8" | python3 -c '
import json, sys
for line in sys.stdin:
    if line.startswith("{"):
        print(json.loads(line)["key"])')"
expect "W8 hunk lesson has a key" 0 "" test -n "$HKEY"
expect "W9 replace patch" 0 "patch work/TASK-8/patches/01-h.py" \
  L patch --file .claude/skills/token-efficiency/SKILL.md --anchor "$HK" --replace "- replaced hunk line" --out work/TASK-8/patches/01-h.py
printf '| %s | applied | .claude/skills/token-efficiency/SKILL.md | new |\n' "$HKEY" > "$R/work/TASK-8/handoff/curate.md"
expect "W10 hunk row marked" 0 "marked 1" L mark-from "$R/work/TASK-8/handoff/curate.md"
ROW="$(grep "$HKEY" "$R/.claude/lessons/ledger.jsonl" | tail -n 1)"
expect "W11 row stores the replaced anchor as hunk" 0 "\"hunk\": \"$HK\"" printf '%s' "$ROW"
expect "W12 row stores HEAD as commit" 0 "\"commit\": \"$HEADC\"" printf '%s' "$ROW"
expect "W13 row stores the replacement as new" 0 "- replaced hunk line" printf '%s' "$ROW"

# F-74-2: the patch is found by its full target path, one patch per row (no first-basename match)
keys_of() { L collect "$1" | python3 -c '
import json, sys
for line in sys.stdin:
    if line.startswith("{"):
        print(json.loads(line)["key"])'; }
SK="$R/.claude/skills"; mkdir -p "$SK/other" "$R/work/TASK-7/handoff" "$R/work/TASK-6/handoff"
printf '# O\n' > "$SK/other/SKILL.md"
printf -- '- anchor one\n- anchor two\n' >> "$SK/token-efficiency/SKILL.md"
printf -- '- anchor three\n' >> "$SK/other/SKILL.md"
GT add -A >/dev/null; GT commit -q -m zbase2
# two replace patches on one file, two lessons
printf 'PROGRESS: COMPLETE\n## Lessons\n- L: kind=tip target=token-efficiency | first same-file tip | evidence=work/TASK-9/x.log\n- L: kind=tip target=token-efficiency | second same-file tip | evidence=work/TASK-9/x.log\n' > "$R/work/TASK-7/handoff/coder.md"
K7="$(keys_of "$R/work/TASK-7")"; K7A="$(printf '%s\n' "$K7" | sed -n 1p)"; K7B="$(printf '%s\n' "$K7" | sed -n 2p)"
expect "W14 two lessons collected" 0 "" test -n "$K7B"
expect "W15 first same-file patch" 0 "01-a.py" L patch --file .claude/skills/token-efficiency/SKILL.md --anchor "- anchor one" --replace "- new one" --out work/TASK-7/patches/01-a.py
expect "W16 second same-file patch" 0 "02-b.py" L patch --file .claude/skills/token-efficiency/SKILL.md --anchor "- anchor two" --replace "- new two" --out work/TASK-7/patches/02-b.py
printf '| %s | applied | .claude/skills/token-efficiency/SKILL.md | new |\n| %s | applied | .claude/skills/token-efficiency/SKILL.md | new |\n' "$K7A" "$K7B" > "$R/work/TASK-7/handoff/curate.md"
expect "W17 both rows marked" 0 "marked 2" L mark-from "$R/work/TASK-7/handoff/curate.md"
expect "W18 row 1 keeps its own hunk" 0 "\"hunk\": \"- anchor one\"" bash -c 'grep "$1" "$2" | tail -n 1' _ "$K7A" "$R/.claude/lessons/ledger.jsonl"
expect "W19 row 2 keeps its own hunk" 0 "\"hunk\": \"- anchor two\"" bash -c 'grep "$1" "$2" | tail -n 1' _ "$K7B" "$R/.claude/lessons/ledger.jsonl"
expect "W20 row 2 keeps its own new text" 0 "- new two" bash -c 'grep "$1" "$2" | tail -n 1' _ "$K7B" "$R/.claude/lessons/ledger.jsonl"
# two files with the same basename (SKILL.md) in different skills, one patch each
printf 'PROGRESS: COMPLETE\n## Lessons\n- L: kind=tip target=other | other skill tip | evidence=work/TASK-9/x.log\n- L: kind=tip target=token-efficiency | te skill tip | evidence=work/TASK-9/x.log\n' > "$R/work/TASK-6/handoff/coder.md"
K6="$(keys_of "$R/work/TASK-6")"; K6A="$(printf '%s\n' "$K6" | sed -n 1p)"; K6B="$(printf '%s\n' "$K6" | sed -n 2p)"
expect "W21 patch on the first skill" 0 "01-o.py" L patch --file .claude/skills/other/SKILL.md --anchor "- anchor three" --replace "- new three" --out work/TASK-6/patches/01-o.py
expect "W22 patch on the second skill" 0 "02-t.py" L patch --file .claude/skills/token-efficiency/SKILL.md --anchor "- anchor one" --replace "- newer one" --out work/TASK-6/patches/02-t.py
printf '| %s | applied | .claude/skills/token-efficiency/SKILL.md | new |\n| %s | applied | .claude/skills/other/SKILL.md | new |\n' "$K6B" "$K6A" > "$R/work/TASK-6/handoff/curate.md"
expect "W23 both rows marked" 0 "marked 2" L mark-from "$R/work/TASK-6/handoff/curate.md"
expect "W24 other-skill row has the other hunk" 0 "\"hunk\": \"- anchor three\"" bash -c 'grep "$1" "$2" | tail -n 1' _ "$K6A" "$R/.claude/lessons/ledger.jsonl"
expect "W25 token-efficiency row has its hunk, not the other file's" 0 "\"hunk\": \"- anchor one\"" bash -c 'grep "$1" "$2" | tail -n 1' _ "$K6B" "$R/.claude/lessons/ledger.jsonl"

# F-74-V1: the evidence gate covers every applied/merged row (agent:<role>, CLAUDE.md), not only skills
mkdir -p "$R/work/TASK-5/handoff"
printf 'PROGRESS: COMPLETE\n## Lessons\n- L: kind=wrong-rule target=agent:coder | agent line without proof | evidence=-\n- L: kind=tip target=CLAUDE.md | claude line without proof | evidence=-\n- L: kind=wrong-rule target=agent:coder | agent line with proof | evidence=work/TASK-9/x.log\n- L: kind=tip target=CLAUDE.md | claude line with proof | evidence=work/TASK-9/x.log\n' > "$R/work/TASK-5/handoff/coder.md"
K5="$(keys_of "$R/work/TASK-5")"
K5A="$(printf '%s\n' "$K5" | sed -n 1p)"; K5B="$(printf '%s\n' "$K5" | sed -n 2p)"
K5C="$(printf '%s\n' "$K5" | sed -n 3p)"; K5D="$(printf '%s\n' "$K5" | sed -n 4p)"
LN0="$(wc -l < "$R/.claude/lessons/ledger.jsonl" | tr -d ' ')"
printf '| %s | applied | .claude/agents/coder.md | new |\n' "$K5A" > "$R/work/TASK-5/handoff/c1.md"
printf '| %s | merged | CLAUDE.md | dup |\n' "$K5B" > "$R/work/TASK-5/handoff/c2.md"
printf '| %s | applied | .claude/agents/coder.md | new |\n| %s | merged | CLAUDE.md | dup |\n' "$K5C" "$K5D" > "$R/work/TASK-5/handoff/c3.md"
expect "V1a agent:<role> row without evidence: rc 2" 2 "no-evidence" L mark-from "$R/work/TASK-5/handoff/c1.md"
expect "V1b CLAUDE.md row without evidence: rc 2" 2 "no-evidence" L mark-from "$R/work/TASK-5/handoff/c2.md"
expect "V1c refused rows write nothing" 0 "" test "$(wc -l < "$R/.claude/lessons/ledger.jsonl" | tr -d ' ')" -eq "$LN0"
expect "V1d agent and CLAUDE.md rows with evidence are marked" 0 "marked 2" L mark-from "$R/work/TASK-5/handoff/c3.md"

# U2: in-place skill edit (no patch file): hunk comes from git diff BASE, or the row says revert: manual
mkdir -p "$R/.claude/skills/ugamma" "$R/work/TASK-4/handoff"
SK=".claude/skills/ugamma/SKILL.md"
printf '# U\n- l1 keep\n- l2 old two\n- l3 old three\n- l4 old four\n- l5 old five\n' > "$R/$SK"
printf 'ugamma\n' > "$R/.claude/agents/ugamma.md"
GT add -A >/dev/null; GT commit -q -m ubase
cp "$R/$SK" "$WORK/u.orig"
printf 'PROGRESS: COMPLETE\n## Lessons\n' > "$R/work/TASK-4/handoff/coder.md"
for n in 1 2 3 4; do
  printf -- '- L: kind=tip target=ugamma | u2 lesson number %s | evidence=work/TASK-9/x.log\n' "$n" >> "$R/work/TASK-4/handoff/coder.md"
done
K4="$(keys_of "$R/work/TASK-4")"
U1="$(printf '%s\n' "$K4" | sed -n 1p)"; U2="$(printf '%s\n' "$K4" | sed -n 2p)"
U3="$(printf '%s\n' "$K4" | sed -n 3p)"; U4="$(printf '%s\n' "$K4" | sed -n 4p)"
LED="$R/.claude/lessons/ledger.jsonl"
rowof() { grep "$1" "$LED" | tail -n 1; }
# edit 1: in-place replace of line 3, uncommitted
sed -i.bak 's/^- l2 old two$/- l2 NEW two/' "$R/$SK"; rm -f "$R/$SK.bak"
printf '| %s | applied | %s:3 | new |\n' "$U1" "$SK" > "$R/work/TASK-4/handoff/c1.md"
expect "U2a in-place replace marked" 0 "marked 1" L mark-from "$R/work/TASK-4/handoff/c1.md"
expect "U2b hunk = the replaced old line" 0 "\"hunk\": \"- l2 old two\"" printf '%s' "$(rowof "$U1")"
expect "U2c new = the current line" 0 "\"new\": \"- l2 NEW two\"" printf '%s' "$(rowof "$U1")"
expect "U2d revert marker is replace" 0 "\"revert\": \"replace\"" printf '%s' "$(rowof "$U1")"
# reverse patch built from the row restores the file byte for byte
L patch --file "$SK" --anchor "- l2 NEW two" --replace "- l2 old two" --out work/TASK-4/patches/01-rev.py >/dev/null
expect "U2e reverse patch applies" 0 "applied" python3 -B "$R/work/TASK-4/patches/01-rev.py" "$R/.claude/skills/ugamma"
expect "U2f file restored byte-identically" 0 "" cmp "$WORK/u.orig" "$R/$SK"
rm -rf "$R/work/TASK-4/patches"
# edit 2: committed edit of line 4 (diff vs HEAD is empty): default base cannot pair it
sed -i.bak 's/^- l3 old three$/- l3 NEW three/' "$R/$SK"; rm -f "$R/$SK.bak"
GT add -A >/dev/null; GT commit -q -m uedit
printf '| %s | applied | %s:4 | new |\n' "$U2" "$SK" > "$R/work/TASK-4/handoff/c2.md"
expect "U2g committed edit, default base: marked" 0 "marked 1" L mark-from "$R/work/TASK-4/handoff/c2.md"
expect "U2h unpairable row is flagged, not silent" 0 "\"revert\": \"manual\"" printf '%s' "$(rowof "$U2")"
expect "U2i watch listing shows revert: manual" 0 "revert: manual" L watch
LN1="$(wc -l < "$LED" | tr -d ' ')"
expect "U2j re-run with --base updates the row in place" 0 "updated 1" L mark-from "$R/work/TASK-4/handoff/c2.md" --base HEAD^
expect "U2k committed edit: hunk filled" 0 "\"hunk\": \"- l3 old three\"" printf '%s' "$(rowof "$U2")"
expect "U2l no duplicate row" 0 "" test "$(grep -c "$U2" "$LED")" -eq 1
expect "U2m ledger line count unchanged" 0 "" test "$(wc -l < "$LED" | tr -d ' ')" -eq "$LN1"
cp "$LED" "$WORK/led.before"
expect "U2n re-run with nothing new: rc 2" 2 "already in ledger" L mark-from "$R/work/TASK-4/handoff/c2.md" --base HEAD^
expect "U2o re-run changed nothing" 0 "" cmp "$WORK/led.before" "$LED"
# pure addition: hunk empty, marker says the revert is a delete
printf -- '- l6 added six\n' >> "$R/$SK"
printf '| %s | applied | %s:7 | new |\n' "$U3" "$SK" > "$R/work/TASK-4/handoff/c3.md"
expect "U2p pure addition marked" 0 "marked 1" L mark-from "$R/work/TASK-4/handoff/c3.md"
expect "U2q pure addition: revert delete" 0 "\"revert\": \"delete\"" printf '%s' "$(rowof "$U3")"
expect "U2r pure addition: new = the added line" 0 "\"new\": \"- l6 added six\"" printf '%s' "$(rowof "$U3")"
# an option-like base is never passed to git: the row is flagged manual
printf '| %s | applied | %s:7 | new |\n' "$U4" "$SK" > "$R/work/TASK-4/handoff/c4.md"
expect "U2s option-like base is flagged manual" 0 "marked 1" L mark-from "$R/work/TASK-4/handoff/c4.md" --base=--output=x
expect "U2t no file written by the base" 1 "" test -e "$R/x"
expect "U2u option-like base row is manual" 0 "\"revert\": \"manual\"" printf '%s' "$(rowof "$U4")"

# U2b: real shape - one curate file with 2 rejected rows + 1 in-place watch row with an empty hunk
mkdir -p "$R/work/TASK-5/handoff"
printf 'PROGRESS: COMPLETE\n## Lessons\n' > "$R/work/TASK-5/handoff/coder.md"
for n in 1 2 3; do
  printf -- '- L: kind=tip target=ugamma | u2b lesson number %s | evidence=work/TASK-9/x.log\n' "$n" >> "$R/work/TASK-5/handoff/coder.md"
done
K5="$(keys_of "$R/work/TASK-5")"
V1="$(printf '%s\n' "$K5" | sed -n 1p)"; V2="$(printf '%s\n' "$K5" | sed -n 2p)"; V3="$(printf '%s\n' "$K5" | sed -n 3p)"
printf '| %s | rejected | no | why1 |\n| %s | rejected | no | why2 |\n| %s | applied | %s:7 | new |\n' "$V1" "$V2" "$V3" "$SK" > "$R/work/TASK-5/handoff/c.md"
expect "U2v mixed curate file marked" 0 "marked 3" L mark-from "$R/work/TASK-5/handoff/c.md" --base=--output=x
expect "U2w watch row starts manual" 0 "\"revert\": \"manual\"" printf '%s' "$(rowof "$V3")"
rowof "$V1" > "$WORK/rej1.before"; rowof "$V2" > "$WORK/rej2.before"
LN2="$(wc -l < "$LED" | tr -d ' ')"
expect "U2x refill with --base: rc 0, updated 1" 0 "updated 1" L mark-from "$R/work/TASK-5/handoff/c.md" --base HEAD
expect "U2y watch hunk path filled (delete)" 0 "\"revert\": \"delete\"" printf '%s' "$(rowof "$V3")"
rowof "$V1" > "$WORK/rej1.after"; rowof "$V2" > "$WORK/rej2.after"
expect "U2z rejected row 1 byte-identical" 0 "" cmp "$WORK/rej1.before" "$WORK/rej1.after"
expect "U2za rejected row 2 byte-identical" 0 "" cmp "$WORK/rej2.before" "$WORK/rej2.after"
expect "U2zb no rows added" 0 "" test "$(wc -l < "$LED" | tr -d ' ')" -eq "$LN2"
expect "U2zc re-run: rc 2" 2 "already in ledger" L mark-from "$R/work/TASK-5/handoff/c.md" --base HEAD

# U2c: real shape - 2-line wrapped bullets, wrong cited lines, 3 edits in one file, 2 rejected rows
mkdir -p "$R/.claude/skills/zeta" "$R/work/TASK-8/handoff"
SKZ=".claude/skills/zeta/SKILL.md"
printf 'zeta\n' > "$R/.claude/agents/zeta.md"
printf '# Z\n- keep1\n- alpha old first\n  alpha old second\n- keep2\n- keep3\n- beta old first\n  beta old second\n- keep4\n- keep5\n- gamma old first\n  gamma old second\n- keep6\n' > "$R/$SKZ"
GT add -A >/dev/null; GT commit -q -m zbase
cp "$R/$SKZ" "$WORK/z.base"
printf '# Z\n- keep1\n- alpha rule zeta NEW first\n  NEW second alpha\n- keep2\n- keep3\n- beta rule zeta NEW first\n  NEW second beta\n- keep4\n- keep5\n- gamma rule zeta NEW first\n  NEW second gamma\n- keep6\n' > "$R/$SKZ"
cp "$R/$SKZ" "$WORK/z.edited"
printf 'PROGRESS: COMPLETE\n## Lessons\n' > "$R/work/TASK-8/handoff/coder.md"
for n in alpha beta gamma rej1 rej2 zadd; do
  case "$n" in zadd) zt="zadd one" ;; *) zt="$n rule zeta NEW first NEW second $n" ;; esac
  printf -- '- L: kind=tip target=zeta | %s | evidence=work/TASK-9/x.log\n' "$zt" >> "$R/work/TASK-8/handoff/coder.md"
done
K8="$(keys_of "$R/work/TASK-8")"
ZA="$(printf '%s\n' "$K8" | sed -n 1p)"; ZB="$(printf '%s\n' "$K8" | sed -n 2p)"; ZG="$(printf '%s\n' "$K8" | sed -n 3p)"
ZR1="$(printf '%s\n' "$K8" | sed -n 4p)"; ZR2="$(printf '%s\n' "$K8" | sed -n 5p)"; KD="$(printf '%s\n' "$K8" | sed -n 6p)"
printf '| %s | applied | %s:13 | new |\n| %s | applied | %s:20 | new |\n| %s | applied | %s:21 | new |\n| %s | rejected | no | w1 |\n| %s | rejected | no | w2 |\n' \
  "$ZA" "$SKZ" "$ZB" "$SKZ" "$ZG" "$SKZ" "$ZR1" "$ZR2" > "$R/work/TASK-8/handoff/c.md"
expect "U2c1 five rows marked" 0 "marked 5" L mark-from "$R/work/TASK-8/handoff/c.md" --base HEAD
for k in "$ZA" "$ZB" "$ZG"; do
  expect "U2c2 revert=replace" 0 "\"revert\": \"replace\"" printf '%s' "$(rowof "$k")"
done
expect "U2c3 alpha hunk is both old lines" 0 "\"hunk\": \"- alpha old first\\n  alpha old second\"" printf '%s' "$(rowof "$ZA")"
expect "U2c4 gamma new is both new lines" 0 "\"new\": \"- gamma rule zeta NEW first\\n  NEW second gamma\"" printf '%s' "$(rowof "$ZG")"
expect "U2c5 patch still refuses multi-line text" 1 "" L patch --file "$SKZ" --anchor "- alpha rule zeta NEW first
  NEW second alpha" --replace "x" --out work/TASK-8/patches/01-ml.py
rm -rf "$R/work/TASK-8/patches"
expect "U2c6 revert rejected row refused" 1 "not watch" L revert "$ZR1"
expect "U2c7 revert manual row refused" 1 "manual" L revert "$U4"
expect "U2c8 unknown key refused" 1 "matches 0" L revert 0123456789abcdef
# ambiguous: the new block occurs twice
printf -- '- alpha rule zeta NEW first\n  NEW second alpha\n' >> "$R/$SKZ"
expect "U2c9 ambiguous block refused" 1 "2 times" L revert "$ZA"
cp "$WORK/z.edited" "$R/$SKZ"
# missing: the block was edited away
sed -i.bak 's/NEW second beta/changed/' "$R/$SKZ"; rm -f "$R/$SKZ.bak"
expect "U2c10 missing block refused" 1 "0 times" L revert "$ZB"
cp "$WORK/z.edited" "$R/$SKZ"
expect "U2c11 refusals left the file alone" 0 "" cmp "$WORK/z.edited" "$R/$SKZ"
# revert each key in turn
expect "U2c12 revert alpha" 0 "reverted" L revert "$ZA"
expect "U2c13 alpha old text back" 0 "alpha old second" cat "$R/$SKZ"
expect "U2c14 revert beta" 0 "reverted" L revert "$ZB"
expect "U2c15 revert gamma" 0 "reverted" L revert "$ZG"
expect "U2c16 file byte-identical to base" 0 "" cmp "$WORK/z.base" "$R/$SKZ"
expect "U2c17 status is reverted" 0 "\"status\": \"reverted\"" printf '%s' "$(rowof "$ZA")"
expect "U2c18 double revert refused" 1 "not watch" L revert "$ZA"
expect "U2c19 file still byte-identical" 0 "" cmp "$WORK/z.base" "$R/$SKZ"
# revert of a pure addition removes the block
printf -- '- zadd one\n' >> "$R/$SKZ"
printf '| %s | applied | %s:99 | new |\n' "$KD" "$SKZ" > "$R/work/TASK-8/handoff/c2.md"
expect "U2c20 pure addition marked" 0 "marked 1" L mark-from "$R/work/TASK-8/handoff/c2.md" --base HEAD
expect "U2c21 revert delete" 0 "reverted" L revert "$KD"
expect "U2c22 addition removed byte-identically" 0 "" cmp "$WORK/z.base" "$R/$SKZ"

# U2d: real shape (TASK-074 token-efficiency): lesson texts are paraphrases of the merged text,
# cites :13/:20/:21 fall in no hunk; pairing falls back to token overlap with a margin
mkdir -p "$R/.claude/skills/eta" "$R/work/TASK-9/handoff"
SKE=".claude/skills/eta/SKILL.md"
printf 'eta\n' > "$R/.claude/agents/eta.md"
cat > "$R/$SKE" <<'EOF'
# E
- keep1
- Full suite takes > 10 min: start it with `run_in_background` at once;
  foreground `sleep` is blocked, the finish notification wakes you.
- keep2
- keep3
  `save-evidence.sh` (hash before, run, hash after, diff). An inline `bash -c` of echoed hashes was rejected by
  the verifier and cost a round trip.
- keep4
- keep5
  is not parsed by `req.py ac` and costs an extra turn at VERIFIED. Never `pkill -f` a pattern that also
  appears in the same command line: it kills its own shell (exit 144) and the evidence run is lost.
- keep6
EOF
GT add -A >/dev/null; GT commit -q -m ebase
cp "$R/$SKE" "$WORK/e.base"
cat > "$R/$SKE" <<'EOF'
# E
- keep1
- Full suite takes > 10 min: start it with `run_in_background` after the item's edits are committed
  (TASK-074: an earlier run went stale and blocked test edits 20+ min); foreground `sleep` is blocked.
- keep2
- keep3
  `save-evidence.sh` (hash before, run, hash after, diff). An inline `bash -c` was rejected by the verifier
  (TASK-059) and by the removal safety check, which dropped a whole call incl. a commit (TASK-074).
- keep4
- keep5
  is not parsed by `req.py ac` and costs an extra turn at VERIFIED. Never `pkill -f` a pattern in the same
  command line: it kills its own shell (exit 144; again TASK-074); kill by the PID from `pgrep`.
- keep6
EOF
printf 'PROGRESS: COMPLETE\n## Lessons\n' > "$R/work/TASK-9/handoff/coder.md"
printf -- '%s\n' \
 "- L: kind=tip target=eta | Start the background run_all only after the coder's edits for the item are committed; a run started earlier went stale, blocked test-file edits for 20+ min and had to be killed | evidence=work/TASK-9/x.log" \
 "- L: kind=tip target=eta | Save a multi-command check as a script file (work/<T>/evidence/*.sh) and run it through save-evidence.sh; an inline \`bash -c '...'\` was refused by the built-in removal safety check and the whole call (incl. a commit) did not run | evidence=work/TASK-9/x.log" \
 "- L: kind=tip target=eta | A pkill whose pattern is in its own command line killed the tester's shell again (TASK-061 lesson); never pkill -f a pattern you are typing, kill by the PID from pgrep | evidence=work/TASK-9/x.log" \
 "- L: kind=tip target=eta | zebra quartz unrelated words | evidence=work/TASK-9/x.log" >> "$R/work/TASK-9/handoff/coder.md"
K9="$(keys_of "$R/work/TASK-9")"
E1="$(printf '%s\n' "$K9" | sed -n 1p)"; E2="$(printf '%s\n' "$K9" | sed -n 2p)"; E3="$(printf '%s\n' "$K9" | sed -n 3p)"; E4="$(printf '%s\n' "$K9" | sed -n 4p)"
printf '| %s | applied | %s:13 | new |\n| %s | applied | %s:20 | new |\n| %s | applied | %s:21 | new |\n| %s | applied | %s:22 | new |\n' \
  "$E1" "$SKE" "$E2" "$SKE" "$E3" "$SKE" "$E4" "$SKE" > "$R/work/TASK-9/handoff/c.md"
expect "U2d1 four rows marked" 0 "marked 4" L mark-from "$R/work/TASK-9/handoff/c.md" --base HEAD
for k in "$E1" "$E2" "$E3"; do
  expect "U2d2 paired by text: replace" 0 "\"revert\": \"replace\"" printf '%s' "$(rowof "$k")"
done
expect "U2d3 run_all lesson got the suite hunk" 0 "the finish notification wakes you" printf '%s' "$(rowof "$E1")"
expect "U2d4 bash -c lesson got the verifier hunk" 0 "cost a round trip" printf '%s' "$(rowof "$E2")"
expect "U2d5 pkill lesson got the pkill hunk" 0 "evidence run is lost" printf '%s' "$(rowof "$E3")"
expect "U2d6 no overlap stays manual" 0 "\"revert\": \"manual\"" printf '%s' "$(rowof "$E4")"
expect "U2d7 revert E1" 0 "reverted" L revert "$E1"
expect "U2d8 revert E2" 0 "reverted" L revert "$E2"
expect "U2d9 revert E3" 0 "reverted" L revert "$E3"
expect "U2d10 base bytes restored" 0 "" cmp "$WORK/e.base" "$R/$SKE"
expect "U2d11 manual row cannot be reverted" 1 "manual" L revert "$E4"
# no clear winner: two hunks overlap the lesson text equally
printf -- '- alpha beta gamma delta epsilon one\n- mid\n- alpha beta gamma delta epsilon two\n' > "$R/.claude/skills/eta/TWO.md"
GT add -A >/dev/null; GT commit -q -m tbase
printf -- '- alpha beta gamma delta epsilon ONE\n- mid\n- alpha beta gamma delta epsilon TWO\n' > "$R/.claude/skills/eta/TWO.md"
GP='import importlib.util,sys
sp=importlib.util.spec_from_file_location("lessons",sys.argv[1])
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
r=m.git_pair(sys.argv[2],sys.argv[3],"HEAD",sys.argv[4],set())
print("none" if r is None else "paired")'
expect "U2d12 tie between hunks stays manual" 0 "none" python3 -B -c "$GP" "$LP" "$R" ".claude/skills/eta/TWO.md:2" "alpha beta gamma delta epsilon words"
expect "U2d13 cited line outside hunks warns" 0 "cited line 2 not in any hunk; paired by text" python3 -B -c "$GP" "$LP" "$R" ".claude/skills/eta/TWO.md:2" "alpha beta gamma delta epsilon words" 2>&1
rm -f "$R/.claude/skills/eta/TWO.md"

# ---- TASK-103 drift (design phase-103), $0 ----
D="$WORK/d"
dfix() {
  rm -rf "$D"; mkdir -p "$D/.claude/skills/ext-scan" "$D/.claude/state" "$D/work/TASK-7"
  git -C "$D" init -q; git -C "$D" config user.email t@t; git -C "$D" config user.name t
  printf 'run `real.sh --keep` then `old_gone.sh` and `--lonely`\n' > "$D/.claude/skills/ext-scan/SKILL.md"
  printf '#!/bin/sh\n# --keep\n' > "$D/real.sh"
  git -C "$D" add -A; git -C "$D" commit -q -m base
}
DL() { python3 -B "$LP" --root "$D" "$@"; }
dfix
expect "U1 drift: removed script is MISSING" 6 "MISSING" env -C "$D" python3 -B "$LP" --root "$D" drift --all --skills ext-scan
out="$(DL drift --all --skills ext-scan 2>&1 || true)"
if printf '%s' "$out" | grep -qF "old_gone.sh" && printf '%s' "$out" | grep -qF -- "--lonely" && printf '%s' "$out" | grep -qF "TOTAL missing=2 changed=0"; then ok "U1b two MISSING rows (script and flag), real.sh clean"; else bad "U1b rows"; printf '%s\n' "$out" | head; fi
printf 'run `real.sh --keep`\n' > "$D/.claude/skills/ext-scan/SKILL.md"; git -C "$D" commit -qam clean
expect "U6 clean skill rc 0" 0 "TOTAL missing=0 changed=0" env -C "$D" python3 -B "$LP" --root "$D" drift --all --skills ext-scan
printf 'run `real.sh --keep`\n' > "$D/.claude/skills/ext-scan/SKILL.md"
printf '#!/bin/sh\n# changed\n' > "$D/real.sh"; git -C "$D" commit -qam "chg" -m "Task: TASK-7"
expect "U3 flag removed by task diff is CHANGED" 6 "CHANGED" python3 -B "$LP" --root "$D" drift --base HEAD~1 --skills ext-scan
rm -rf "$D/work/TASK-7/handoff"
expect "U4 emit writes kind=stale lesson" 6 "TOTAL" python3 -B "$LP" --root "$D" drift --base HEAD~1 --skills ext-scan --emit work/TASK-7
if grep -qF "kind=stale target=ext-scan" "$D/work/TASK-7/handoff/drift.md" 2>/dev/null; then ok "U4b drift.md has stale line"; else bad "U4b drift.md"; fi
printf '[{"task_id":"A","status":"done"},{"task_id":"B","status":"done"}]' > "$D/.claude/state/backlog.json"
out="$(DL drift --task TASK-7 --sweep-every 3 --skills ext-scan 2>&1 || true)"
if printf '%s' "$out" | grep -qF "SWEEP yes done=3"; then ok "U5 sweep fires at multiple of N"; else bad "U5 sweep"; printf '%s\n' "$out" | head -4; fi

echo "SUMMARY(lessons): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
