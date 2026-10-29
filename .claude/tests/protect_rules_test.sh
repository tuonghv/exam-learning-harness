#!/usr/bin/env bash
# TASK-069 (REQ-0026) 69.1-69.5, 69.7: protected-list blocks.
#  A. role read guard covers every source-tree copy (component roots) and nothing else ($0, fake trees)
#  B. settings.json: ask before paid runs / irreversible git, deny keys, no dead Write() rules, and the
#     rest of the permissions unchanged; a small emulator of the documented matching rules runs the
#     must-ask and must-not-ask command lists (it proves intent; the live probe proves Claude Code's own matcher)
#  C. role Bash write routes: cd into protected dirs, node/ruby -e, awk -i inplace, rsync (69.8)
# Run: bash .claude/tests/protect_rules_test.sh   (KIT=<dir holding .claude/> tests another copy, e.g. git archive HEAD)
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KIT="${KIT:-$HERE}"
W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT
export TMPDIR="$W/tmp"
mkdir -p "$TMPDIR"

PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); printf '%s\n' "$2" | sed 's/^/    /'; }

# --- fake layout: $W/online/{kit, <src>, <src>_copy, <src>.bak, security-findings} --------------------
SRC="pentest_source_code"
ON="$W/online"
mkdir -p "$ON/kit" "$ON/$SRC/a" "$ON/${SRC}_copy/a" "$ON/${SRC}.bak/a" "$ON/${SRC}2/a" "$ON/${SRC}-old/a" "$ON/security-findings"
for d in "$SRC" "${SRC}_copy" "${SRC}.bak" "${SRC}2" "${SRC}-old"; do echo x > "$ON/$d/a/f"; done
echo x > "$ON/security-findings/x"
cp -r "$KIT/.claude" "$ON/kit/.claude"
find "$ON/kit/.claude" -name __pycache__ -prune -exec rm -rf {} +
rm -rf "$ON/kit/.claude/state" "$ON/kit/.claude/tests"
echo repo > "$ON/kit/file.txt"
ln -s "../${SRC}_copy" "$ON/kit/lnk"
python3 - "$ON/kit/.claude/agent_setup.json" "$ON" <<'PY'
import sys
p, on = sys.argv[1:3]
s = open(p).read()
old = "/home/tuonghv/Documents/git/online-system"
assert old in s, "read_globs prefix not found"
open(p, "w").write(s.replace(old, on))
PY

# hook <agent_type|-> <tool> <tool_input-json>: sets RC (the guard's exit code)
hook() {
  local role="$1" tool="$2" ti="$3" json
  json="$(python3 - "$role" "$tool" "$ti" "$ON/kit" <<'PY'
import json, sys
role, tool, ti, cwd = sys.argv[1:5]
o = {"tool_name": tool, "tool_input": json.loads(ti), "session_id": "s1",
     "hook_event_name": "PreToolUse", "cwd": cwd}
if role != "-":
    o["agent_type"] = role
print(json.dumps(o))
PY
)"
  RC=0
  (cd "$ON/kit" && python3 .claude/hooks/agent_setup.py hook --config .claude/agent_setup.json \
      <<<"$json" >/dev/null 2>"$W/err") || RC=$?
  ERR="$(cat "$W/err")"
}
refuse() { # refuse <name> <role> <tool> <json>
  hook "$2" "$3" "$4"
  if [ "$RC" = 2 ]; then ok "$1"; else bad "$1" "rc=$RC (want 2) $ERR"; fi
}
allow() {
  hook "$2" "$3" "$4"
  if [ "$RC" = 0 ]; then ok "$1"; else bad "$1" "rc=$RC (want 0) $ERR"; fi
}
jstr() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }

# =========================================================== A. role read guard (69.1)
refuse "A1 Read a sibling copy"        designer Read "{\"file_path\":\"$ON/${SRC}_copy/a/f\"}"
refuse "A2 Read a .bak copy"           designer Read "{\"file_path\":\"$ON/${SRC}.bak/a/f\"}"
refuse "A3 Read the original tree"     designer Read "{\"file_path\":\"$ON/$SRC/a/f\"}"
refuse "A4 Grep a copy (relative)"     designer Grep "{\"pattern\":\"x\",\"path\":\"../${SRC}_copy\"}"
refuse "A5 Grep the parent dir"        designer Grep "{\"pattern\":\"x\",\"path\":\"$ON\"}"
refuse "A6 Grep via symlink"           designer Grep '{"pattern":"x","path":"lnk"}'
refuse "A7 Glob from the parent"       designer Glob "{\"pattern\":\"**/f\",\"path\":\"$ON\"}"
refuse "A8 Glob absolute pattern"      designer Glob "{\"pattern\":\"$ON/${SRC}_copy/**\"}"
refuse "A9 Bash ls ../pent*"           coder    Bash '{"command":"ls ../pent*"}'
refuse "A10 Bash grep -r x .."         coder    Bash '{"command":"grep -r x .."}'
refuse "A11 Bash find parent abs"      coder    Bash "{\"command\":\"find $ON -name a\"}"
refuse "A19 Read a numbered copy"       designer Read "{\"file_path\":\"$ON/${SRC}2/a/f\"}"
refuse "A20 Read a dashed copy"         designer Read "{\"file_path\":\"$ON/${SRC}-old/a/f\"}"
refuse "A21 Bash cat a copy (relative)" coder    Bash "{\"command\":\"cat ../${SRC}2/a/f\"}"
refuse "A22 Bash grep a .bak copy"      coder    Bash "{\"command\":\"grep -r x $ON/${SRC}.bak\"}"
allow  "A12 Read a repo file"          designer Read '{"file_path":"file.txt"}'
allow  "A13 Grep no path"              designer Grep '{"pattern":"x"}'
allow  "A14 Grep path ."               designer Grep '{"pattern":"x","path":"."}'
allow  "A15 Read security-findings"    designer Read "{\"file_path\":\"$ON/security-findings/x\"}"
allow  "A16 Bash ls ../security-findings" coder Bash '{"command":"ls ../security-findings"}'
allow  "A17 Grep in security-findings" designer Grep "{\"pattern\":\"x\",\"path\":\"$ON/security-findings\"}"
allow  "A18 main session reads a copy (settings covers it)" - Read "{\"file_path\":\"$ON/${SRC}_copy/a/f\"}"

# =========================================================== C. role Bash write routes (69.8)
cmdj() { printf '{"command":%s}' "$(jstr "$1")"; }
refuse "C1 node -e writes settings"     coder Bash "$(cmdj "node -e \"require('fs').writeFileSync('.claude/settings.json','x')\"")"
refuse "C2 ruby -e writes agent_setup"  coder Bash "$(cmdj "ruby -e 'File.write(\"x\",1)' .claude/agent_setup.json")"
refuse "C3 awk -i inplace CLAUDE.md"    coder Bash "$(cmdj "awk -i inplace '{print}' CLAUDE.md")"
refuse "C4 rsync onto settings"         coder Bash "$(cmdj "rsync x.json .claude/settings.json")"
refuse "C5 cd into .claude/hooks"       coder Bash "$(cmdj "cd .claude/hooks && echo x > a.py")"
refuse "C6 pushd .claude/state"         coder Bash "$(cmdj "ls; pushd .claude/state")"
refuse "C7 cd ./.claude/scripts/"       coder Bash "$(cmdj "cd ./.claude/scripts/ && ls")"
allow  "C8 python3 req.py list"         coder Bash "$(cmdj "python3 .claude/req/req.py list")"
allow  "C9 python3 -c print"            coder Bash "$(cmdj "python3 -c 'print(1)'")"
allow  "C10 scratch patch"              coder Bash "$(cmdj "cd \$SCRATCH && patch -p1 < p.patch")"
allow  "C11 awk reads settings"         coder Bash "$(cmdj "awk '{print}' .claude/settings.json")"
allow  "C12 cd .claude/tests"           coder Bash "$(cmdj "cd .claude/tests && ls")"
allow  "C13 cd .claude (read use, replay)" coder Bash "$(cmdj "cd .claude; ls hooks")"
allow  "C14 node -e no protected path"  coder Bash "$(cmdj "node -e 'console.log(1)'")"
allow  "C15 scratch-kit cd"             coder Bash "$(cmdj "cd \$S/.claude/hooks && ls")"
allow  "C16 main session cd .claude/hooks" -   Bash "$(cmdj "cd .claude/hooks")"

# =========================================================== D. role Bash names a key file (69.12, F69-4)
refuse "D1 cat x.key"                  coder Bash "$(cmdj "cat x.key")"
refuse "D2 head -n 3 /a/b.pem"         coder Bash "$(cmdj "head -n 3 /a/b.pem")"
refuse "D3 grep k \"f.key\""           coder Bash "$(cmdj "grep k \"f.key\"")"
refuse "D4 cp a.pem /tmp"              coder Bash "$(cmdj "cp a.pem /tmp")"
allow  "D5 jq .key f.json"             coder Bash "$(cmdj "jq .key f.json")"
allow  "D6 python d.keys()"            coder Bash "$(cmdj "python3 -c 'd.keys()'")"
allow  "D7 echo keyfile"               coder Bash "$(cmdj "echo keyfile")"
allow  "D8 grep -n pem notes.md"       coder Bash "$(cmdj "grep -n pem notes.md")"
allow  "D9 main session cat x.key (settings handle it)" - Bash "$(cmdj "cat x.key")"

# =========================================================== B. settings.json (69.2-69.5, 69.7)
SJ="$KIT/.claude/settings.json"
python3 - "$SJ" > "$W/settings.out" 2>&1 <<'PY' && RCB=0 || RCB=$?
import json, re, sys

perm = json.load(open(sys.argv[1]))["permissions"]
ask, deny, allow = perm.get("ask", []), perm.get("deny", []), perm.get("allow", [])
res = []


def check(name, cond, detail=""):
    res.append(("PASS" if cond else "FAIL", name, detail))


paid = ["Bash(claude -p *)", "Bash(claude --print *)", "Bash(claude * -p *)", "Bash(claude * --print *)"]
for s in ("scan_batch.sh", "auto_scan.sh"):
    paid += ["Bash(./%s *)" % s, "Bash(%s *)" % s, "Bash(bash %s *)" % s, "Bash(bash ./%s *)" % s]
for v in ("run", "new", "verify"):
    paid += ["Bash(./pipeline.sh %s *)" % v, "Bash(bash pipeline.sh %s *)" % v,
             "Bash(bash ./pipeline.sh %s *)" % v]
gitask = ["Bash(git push *)", "Bash(git reset --hard *)", "Bash(git reset * --hard *)",
          "Bash(git clean -*f*)", "Bash(git clean --force *)", "Bash(git branch -D *)",
          "Bash(git branch * -D *)", "Bash(git *--force*)", "Bash(git -C * push *)",
          "Bash(git -C * reset --hard *)", "Bash(git -C * clean -*f*)", "Bash(git -C * branch -D *)"]
keys = ["Read(//**/*.pem)", "Read(//**/*.key)", "Read(~/.claude/.credentials*)"]
for grp, want, where, wname in (("69.2 paid", paid, ask, "ask"), ("69.3 git", gitask, ask, "ask"),
                                ("69.4 keys", keys, deny, "deny")):
    miss = [w for w in want if w not in where]
    check("B %s rules present in %s" % (grp, wname), not miss, "missing: %s" % miss)
check("B 69.7 no Write( rule left", not [a for a in ask + deny + allow if a.startswith("Write(")],
      str([a for a in ask if a.startswith("Write(")]))
edits = ["Edit(.claude/%s)" % g for g in ("hooks/**", "settings*.json", "agent_setup.json", "agents/**",
                                          "skills/**", "scripts/**", "req/**")]
check("B 69.7 the 7 Edit twins stay", all(e in ask for e in edits))
# 69.5: everything else is as before (the added rules are the only new ones)
rest_ask = [a for a in ask if a not in paid + gitask]
check("B 69.5 ask minus added = old ask minus Write",
      sorted(rest_ask) == sorted(edits + ["Read(//home/tuonghv/Documents/git/online-system/pentest_source_code*/**)"]),
      str(rest_ask))
check("B 69.5 deny minus added = .env rules", sorted(d for d in deny if d not in keys) == ["Read(.env)", "Read(.env.*)"])
# RAW-00107/00168: the user widened allow with Bash(...) entries; the tool base stays and nothing else is added
base_allow = ["Read", "Glob", "Grep", "Edit", "Write", "Bash", "Agent", "Monitor", "TaskStop"]
check("B 69.5 allow keeps the base and adds only Bash(...) rules",
      allow[:len(base_allow)] == base_allow and all(a.startswith("Bash(") for a in allow[len(base_allow):]), str(allow[len(base_allow):]))


# --- emulator of the documented matcher: split compounds, strip wrappers and VAR=, glob with *,
#     `x *` also matches bare x
def rx(rule):
    body = rule[len("Bash("):-1]
    def glob(x):
        return re.compile("^(%s)$" % ".*".join(re.escape(p) for p in x.split("*")))
    return glob(body), (glob(body[:-2]) if body.endswith(" *") else None)


RULES = [rx(a) for a in paid + gitask]


def subcmds(c):
    for part in re.split(r"&&|\|\||;|\||&|\n", c):
        t = part.strip()
        while True:
            m = re.match(r"^(\w+=\S*|nohup|time|command|builtin|stdbuf(\s+-\S+)*|nice(\s+-n\s*\d+)?|timeout\s+\S+)\s+", t)
            if not m:
                break
            t = t[m.end():]
        if t.startswith("cd "):
            continue
        yield t


def asks(c):
    for t in subcmds(c):
        # a redirect target is not part of the rule match
        t = re.split(r"\s+[12]?>>?\s*\S+", t)[0].strip()
        for r, bare in RULES:
            if r.match(t) or (bare is not None and bare.match(t)):
                return True
    return False


MUST = ["git push", "git push origin main", "git -C /tmp/s push origin", "git -C . push",
        "cd /tmp/s && git reset --hard", "git reset --hard HEAD~1", "git reset HEAD~1 --hard",
        "git clean -fd", "git clean --force -d", "git branch -D x", "git branch x -D", "git push --force",
        "claude -p hi", "claude --print hi", "claude --model x -p hi",
        "cd kit && ./scan_batch.sh", "./scan_batch.sh --plan a/b", "bash scan_batch.sh x", "bash ./auto_scan.sh",
        "PLAN=a/b ./pipeline.sh run", "PLAN=a/b ./pipeline.sh run --run latest", "./pipeline.sh new x",
        "./pipeline.sh verify", "nohup ./auto_scan.sh > log", "AUTO_DRIVER=pipeline ./auto_scan.sh",
        "timeout 60 ./scan_batch.sh", "true && ./pipeline.sh run x", "bash pipeline.sh run"]
NOT = ["tests/run_all.sh auto_scan", "tests/run_all.sh scan_batch", "./pipeline.sh rebuild", "./pipeline.sh status",
       "git status", "git diff scan_batch.sh", "git log --oneline -5", "git add -A", "git commit -F /tmp/m",
       "commit-check.sh /tmp/m > /tmp/o && git commit -F /tmp/m", ".claude/scripts/backlog.sh pick --force TASK-1",
       "./summarize_report.sh", "grep -c x scan_batch.sh", "sed -n 1,5p scan_batch.sh", "shellcheck scan_batch.sh",
       "shellcheck auto_scan.sh pipeline.sh", "git clean -n", "git reset HEAD file.txt", "git branch -d x",
       "python3 .claude/req/req.py list", "cat auto_scan.sh", "tests/run_all.sh pipeline", "./pipeline.sh rebuild --run latest",
       "./summarize_technical.sh", "tests/run_all.sh scan_batch auto_scan"]
for c in MUST:
    check("B emu asks: %s" % c, asks(c))
for c in NOT:
    check("B emu silent: %s" % c, not asks(c))
for r in res:
    print("%s: %s" % r[:2])
    if r[0] == "FAIL" and r[2]:
        print("    " + r[2])
PY
while IFS= read -r line; do
  case "$line" in
    PASS:*) PASS=$((PASS + 1)); echo "$line" ;;
    FAIL:*) FAIL=$((FAIL + 1)); echo "$line" ;;
    *) echo "$line" ;;
  esac
done < "$W/settings.out"
if [ "$RCB" != 0 ]; then FAIL=$((FAIL + 1)); echo "FAIL: B settings checker crashed (rc=$RCB)"; fi

echo "SUMMARY(protect_rules): pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
