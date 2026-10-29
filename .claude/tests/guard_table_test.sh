#!/usr/bin/env bash
# TASK-064 64.10 (AC12): the coordinator's guard table (skill coordinator §2b) must match what the
# guard and the agent files really do. $0, read-only on the real kit; negative cases run on scratch copies.
# Run: bash .claude/tests/guard_table_test.sh
set -Eeuo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
python3 - "$KIT" "$WORK" <<'PY'
import json, re, shutil, sys
from pathlib import Path

kit, work = Path(sys.argv[1]), Path(sys.argv[2])
ROLES = ["designer", "coder", "tester", "verifier"]


def brace(s):
    m = re.search(r"\{([^{}]*)\}", s)
    if not m:
        return [s]
    out = []
    for alt in m.group(1).split(","):
        out += brace(s[:m.start()] + alt + s[m.end():])
    return out


def table_rows(skill):
    sec = skill.split("## 2b.", 1)[1]
    sec = re.split(r"\n## ", sec, 1)[0]
    rows = []
    for ln in sec.splitlines():
        if not ln.startswith("|") or re.match(r"^\|[-| ]+\|$", ln):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] != "Roles cannot":
            rows.append(cells)
    return rows


def probes(rows):
    out = []
    for cells in rows:
        write = cells[0].startswith("Write")
        # column 3 also names the commands that cover a rule (rebuild/report writers)
        extra = [s for s in re.findall(r"`([^`]+)`", cells[2]) if ".sh" in s] if len(cells) > 2 else []
        for span, is_extra in [(s, False) for s in re.findall(r"`([^`]+)`", cells[0])] + [(s, True) for s in extra]:
            for s in brace(span):
                s = s.replace("*", "x")
                if write and not is_extra:
                    if re.match(r"^(agents|hooks|scripts|skills)/", s):
                        s = ".claude/" + s
                    elif s.startswith("phase"):
                        s = "docs/prompts/" + s
                    out.append("echo x > " + s.rstrip("/") + "/f")
                elif " " in s:
                    head, _, last = s.rpartition(" ")
                    out += [head + " " + a for a in last.split("/") if a and a != "..."]
                else:
                    out.append(s)
    return out


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", text)


def check(kdir):
    """Return a list of failure strings for the kit at kdir (a .claude dir)."""
    fails = []
    cfg = json.loads((kdir / "agent_setup.json").read_text())["protect"]
    skill = (kdir / "skills/coordinator/SKILL.md").read_text()
    rows = table_rows(skill)
    col1 = "\n".join(r[0] for r in rows)
    for r in rows:  # `.claude/{settings*,agent_setup}.json` names agent_setup.json only once expanded
        for span in re.findall(r"`([^`]+)`", r[0]):
            col1 += "\n" + "\n".join(brace(span))
    pr = probes(rows)
    for rx in cfg["bash_deny"]:
        c = re.compile(rx)
        if not any(c.search(p) for p in pr):
            fails.append("bash_deny matches no probe from section 2b: " + rx[:70])
    for g in cfg["write_globs"]:
        segs = [s for s in g.split("/") if s.strip("*")]
        frag = max(segs[-1].split("*"), key=len) if segs else ""
        if frag and frag not in col1:
            fails.append("write_glob %s: '%s' not in any section 2b column 1" % (g, frag))
    m = re.search(r"designer\s+(\d+),\s+coder\s+(\d+),\s+tester\s+(\d+),\s+verifier\s+(\d+)", skill)
    turns = dict(zip(ROLES, m.groups())) if m else {}
    if not m:
        fails.append("coordinator skill: no 'designer N, coder N, tester N, verifier N' maxTurns line")
    for role in ROLES:
        f = kdir / "agents" / (role + ".md")
        if not f.exists():
            fails.append("agent file missing: " + role)
            continue
        fm, body = frontmatter(f.read_text())
        tools = [t.strip() for t in (re.search(r"^tools:\s*(.*)$", fm, re.M) or [None, ""])[1].split(",")]
        for tool in ("Bash", "Edit"):
            if tool not in tools and not any(
                    tool in r[0] and re.search(r"\b" + role + r"\b", r[1]) for r in rows):
                fails.append("%s lacks %s in tools: but section 2b has no row naming both" % (role, tool))
        mt = re.search(r"^maxTurns:\s*(\d+)\s*$", fm, re.M)
        if not mt:
            fails.append("%s: maxTurns missing in frontmatter" % role)
        elif turns and mt.group(1) != turns[role]:
            fails.append("%s: maxTurns %s != coordinator section 2 %s" % (role, mt.group(1), turns[role]))
        if "Turn budget" not in body:
            fails.append("%s: body lacks the 'Turn budget' rule" % role)
        if "PROGRESS: IN_PROGRESS" not in body or "PROGRESS: COMPLETE" not in body:
            fails.append("%s: body lacks the PROGRESS line rule" % role)
    return fails


passed = failed = 0


def report(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print("PASS: " + name)
    else:
        failed += 1
        print("FAIL: " + name)
        for d in detail:
            print("    " + d)


real = check(kit)
report("real kit: guard table matches protect and agent files", not real, real)


def fixture(name):
    d = work / name
    shutil.copytree(kit, d, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    return d


def negative(name, mutate, expect):
    d = fixture(name)
    mutate(d)
    got = check(d)
    hit = [g for g in got if expect in g]
    report("negative: " + name + " is caught", bool(hit), ["expected a failure containing '%s', got %r" % (expect, got)])


def edit(path, fn):
    p = Path(path)
    p.write_text(fn(p.read_text()))


def add_json(key, val):
    def m(d):
        p = d / "agent_setup.json"
        j = json.loads(p.read_text())
        j["protect"][key].append(val)
        p.write_text(json.dumps(j))
    return m


negative("new bash_deny regex with no table row", add_json("bash_deny", r"zzneverzz\.sh"), "zzneverzz")
negative("new write_glob with no table row", add_json("write_globs", "zzfake/*"), "zzfake")
negative("coder loses Bash but table names no coder row",
         lambda d: edit(d / "agents/coder.md", lambda t: t.replace("Edit, Write, Bash,", "Edit, Write,", 1)),
         "coder lacks Bash")
negative("maxTurns differs from coordinator number",
         lambda d: edit(d / "agents/coder.md", lambda t: t.replace("maxTurns: 60", "maxTurns: 61")),
         "coder: maxTurns 61")
negative("maxTurns removed",
         lambda d: edit(d / "agents/verifier.md", lambda t: re.sub(r"maxTurns: \d+\n", "", t)),
         "verifier: maxTurns missing")
negative("Turn budget rule removed",
         lambda d: edit(d / "agents/designer.md", lambda t: t.replace("Turn budget", "Budget")),
         "designer: body lacks the 'Turn budget'")
negative("PROGRESS rule removed",
         lambda d: edit(d / "agents/tester.md", lambda t: t.replace("PROGRESS: COMPLETE", "done")),
         "tester: body lacks the PROGRESS")
print("SUMMARY(guard_table): pass=%d fail=%d" % (passed, failed))
sys.exit(1 if failed else 0)
PY
