#!/usr/bin/env bash
# Task-state reader inventory (REQ-0060 AC9, phase 96.14, RAW-00486/00489). $0, read-only.
# FAILs on any script or hook under .claude/{scripts,hooks,req} that reads task.json, task_from or .task_id
# and is neither the resolver (_tasks.py, tasks.sh) nor listed in checks/task_readers.allow
# ("<path> | <one-line reason>"). Also follows the hook -> script chain: every file a settings.json hook
# runs, and every .sh/.py those files name, is scanned, so a reader reached only through a hook is found too.
# Usage: task_readers.sh [ROOT]   (ROOT defaults to the project root; tests pass a fixture repo)
set -Eeuo pipefail
CHECK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${1:-$(cd "$CHECK_DIR/../../.." && pwd)}"
ALLOW="$ROOT/.claude/scripts/checks/task_readers.allow"

python3 - "$ROOT" "$ALLOW" <<'PY'
import json, os, re, sys

root, allow_p = sys.argv[1], sys.argv[2]
READ = re.compile(r"task\.json|task_from|\.task_id")
SELF = {".claude/scripts/_tasks.py", ".claude/scripts/tasks.sh",
        ".claude/scripts/checks/task_readers.sh", ".claude/scripts/checks/task_readers.allow"}
DIRS = (".claude/scripts", ".claude/hooks", ".claude/req")


def rd(p):
    try:
        with open(os.path.join(root, p), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


allow = {}
for ln in rd(".claude/scripts/checks/task_readers.allow").splitlines():
    if ln.strip() and not ln.lstrip().startswith("#") and "|" in ln:
        k, v = ln.split("|", 1)
        if v.strip():
            allow[k.strip()] = v.strip()

files = []
for d in DIRS:
    for dp, dn, fn in os.walk(os.path.join(root, d)):
        dn[:] = [x for x in dn if x != "__pycache__"]
        for f in fn:
            if f.endswith((".sh", ".py")):
                files.append(os.path.relpath(os.path.join(dp, f), root))
files = sorted(set(files) - SELF)

# hook -> script chain
chain = {}
try:
    st = json.loads(rd(".claude/settings.json") or "{}")
except ValueError:
    st = {}
queue = []
for ev, groups in (st.get("hooks") or {}).items():
    for g in groups:
        for h in g.get("hooks", []):
            for m in re.findall(r"\.claude/[A-Za-z0-9_./-]+\.(?:sh|py)", h.get("command", "")):
                queue.append((m, "hook " + ev))
by_base = {}
for f in files:
    by_base.setdefault(os.path.basename(f), f)
while queue:
    f, via = queue.pop(0)
    if f in chain or not os.path.isfile(os.path.join(root, f)):
        continue
    chain[f] = via
    for m in re.findall(r"[A-Za-z0-9_./$\"{}-]*?([A-Za-z0-9_-]+\.(?:sh|py))\b", rd(f)):
        g = by_base.get(m)
        if g and g not in chain:
            queue.append((g, via + " -> " + os.path.basename(f)))
scan = sorted(set(files) | set(f for f in chain if f not in SELF))

fails, listed, used = [], 0, set()
for f in scan:
    hits = [i + 1 for i, ln in enumerate(rd(f).splitlines())
            if READ.search(ln) and not ln.lstrip().startswith("#")]
    if not hits:
        continue
    if f in allow:
        listed += 1
        used.add(f)
    else:
        fails.append("%s reads task state (line %d) without the per-task resolver and is not in "
                     "task_readers.allow%s" % (f, hits[0], (" [" + chain[f] + "]") if f in chain else ""))
for k in sorted(set(allow) - used):
    fails.append("task_readers.allow lists %s but it has no task.json reader (remove the row)" % k)
for m in fails:
    print("FAIL: " + m)
print("SUMMARY(task_readers): scanned=%d chain=%d allowed=%d fail=%d" % (len(scan), len(chain), listed, len(fails)))
sys.exit(1 if fails else 0)
PY
