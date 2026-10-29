#!/usr/bin/env python3
"""process_metrics.py: read-only process cost of workflow tasks (TASK-098, 98.7).

  process_metrics.py <T>... [--json] [--compare <baseline.json>] [--root DIR]

Per task: commits (wip / transitions), briefs (SubagentStart rows), PARTIAL
(partial_stop violations + handoffs whose line 1 is `PROGRESS: PARTIAL`), guard
refusals by kind, user round trips (user_notes raws; RAWs created between
picked_at and DONE) and minutes per state (phase-log headers).
Missing logs give zeros and a WARN on stderr; the exit code stays 0.
Stdlib only, writes nothing.
"""
import argparse
import calendar
import json
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True

# scope_out is an allowed, logged write (not a refusal): its own field.
REFUSAL_KINDS = ("protected", "deny_zone", "tamper")
HDR = re.compile(r"^## (\S+) - (TASK-\d+) - (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\s*$")


def warn(msg):
    sys.stderr.write("WARN: %s\n" % msg)


def iso_epoch(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


def read_jsonl(path):
    rows = []
    if not os.path.isfile(path):
        warn("missing %s" % path)
        return rows
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def git_commits(root, task):
    """Return (wip, transitions) commit counts for `Task: <task>` trailers."""
    try:
        out = subprocess.run(
            ["git", "-C", root, "log", "--grep", "^Task: %s$" % task,
             "--format=%s%x1f%B%x1e"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
            universal_newlines=True).stdout
    except (OSError, subprocess.CalledProcessError):
        warn("git log failed in %s" % root)
        return 0, 0
    wip = trans = 0
    for rec in out.split("\x1e"):
        if "\x1f" not in rec:
            continue
        subj, body = rec.split("\x1f", 1)
        if subj.strip().startswith("wip"):
            wip += 1
        elif re.search(r"^State: ", body, re.M):
            trans += 1
    return wip, trans


def phase_minutes(root, task):
    """Minutes spent per state, from phase-log headers; also DONE epoch."""
    seen = []
    for name in ("phase-log-archive.md", "phase-log.md"):
        p = os.path.join(root, ".claude", "state", name)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = HDR.match(line)
                if m and m.group(2) == task:
                    seen.append((iso_epoch(m.group(3)), m.group(1)))
    if not seen:
        warn("no phase-log entries for %s" % task)
        return {}, None
    seen.sort()
    mins = {}
    for i, (ts, state) in enumerate(seen[:-1]):
        mins[state] = mins.get(state, 0) + int(round((seen[i + 1][0] - ts) / 60.0))
    done = None
    last_ts, last_state = seen[-1]
    if last_state == "DONE":
        done = last_ts
    mins.setdefault(last_state, 0)
    return mins, done


def raws_in_window(root, start, end):
    d = os.path.join(root, "docs", "req", "raw")
    if not os.path.isdir(d):
        warn("missing %s" % d)
        return 0
    n = 0
    for name in os.listdir(d):
        if not name.startswith("RAW-"):
            continue
        with open(os.path.join(d, name), encoding="utf-8", errors="replace") as fh:
            head = fh.read(600)
        m = re.search(r"^created: (\d{4}-\d\d-\d\d \d\d:\d\d)", head, re.M)
        if not m:
            continue
        ts = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M"))  # local time
        if start <= ts <= end:
            n += 1
    return n


HANDOFF_ROLE = {"design": "designer", "code": "coder", "test": "tester", "verify": "verifier"}


def partial_handoffs(root, task, roles=None):
    d = os.path.join(root, "work", task, "handoff")
    n = 0
    if not os.path.isdir(d):
        return 0
    for name in os.listdir(d):
        if not name.endswith(".md"):
            continue
        if roles is not None and HANDOFF_ROLE.get(name[:-3], name[:-3]) not in roles:
            continue
        with open(os.path.join(d, name), encoding="utf-8", errors="replace") as fh:
            if fh.readline().strip() == "PROGRESS: PARTIAL":
                n += 1
    return n


def collect(root, task, calls, viol, roles=None):
    """roles (a set) limits calls, violations and partial handoffs to those roles
    and adds `turns` (tool-call rows); without it the output is unchanged."""
    if roles is not None:
        calls = [r for r in calls if r.get("role") in roles]
        viol = [r for r in viol if r.get("role") in roles]
    wip, trans = git_commits(root, task)
    briefs = sum(1 for r in calls
                 if r.get("task") == task and r.get("tool") == "SubagentStart")
    kinds = {}
    for r in viol:
        if r.get("task") == task:
            k = str(r.get("kind", "?"))
            kinds[k] = kinds.get(k, 0) + 1
    mins, done = phase_minutes(root, task)
    notes = 0
    picked = None
    tf = os.path.join(root, ".claude", "state", "task.%s.json" % task)
    if os.path.isfile(tf):
        try:
            with open(tf, encoding="utf-8") as fh:
                td = json.load(fh)
            notes = len(td.get("user_notes") or [])
            if td.get("picked_at"):
                picked = iso_epoch(td["picked_at"])
        except (ValueError, KeyError):
            warn("bad %s" % tf)
    else:
        warn("missing %s" % tf)
    raws = 0
    if picked is not None:
        raws = raws_in_window(root, picked, done if done else time.time())
    out = {
        "commits": wip + trans, "wip": wip, "transitions": trans,
        "briefs": briefs,
        "partial": kinds.get("partial_stop", 0) + partial_handoffs(root, task, roles),
        "refusals": sum(kinds.get(k, 0) for k in REFUSAL_KINDS),
        "scope_out": kinds.get("scope_out", 0),
        "violations_by_kind": kinds,
        "user_notes": notes, "raws_in_window": raws,
        "minutes_by_state": mins, "minutes_total": sum(mins.values()),
    }
    if roles is not None:
        out["turns"] = sum(1 for r in calls if r.get("task") == task
                           and r.get("tool") != "SubagentStart")
    return out


NUM = ("commits", "wip", "transitions", "briefs", "partial", "refusals",
       "scope_out", "user_notes", "raws_in_window", "minutes_total")


def compare(base, cur):
    """Rows: metric, baseline average over its tasks, current average, delta."""
    rows = []
    for k in NUM:
        b = [t.get(k, 0) for t in base.values()]
        c = [t.get(k, 0) for t in cur.values()]
        ba = sum(b) / float(len(b)) if b else 0.0
        ca = sum(c) / float(len(c)) if c else 0.0
        rows.append((k, ba, ca, ca - ba))
    return rows


def no_worse(base, cur):
    """Regression rule for a skill edit (74.7c). base/cur: {task: collect(..., roles)}.
    Returns (verdict, reasons): verdict is ok | worse | insufficient. Refusals and
    partial must not rise; turns may rise by max(2, 10% of the baseline average)."""
    def avg(d, k):
        v = [t.get(k, 0) for t in d.values()]
        return sum(v) / float(len(v)) if v else 0.0
    if not base or not any(t.get("turns", 0) for t in base.values()):
        return "insufficient", ["baseline has no call of the roles"]
    if not cur or not any(t.get("turns", 0) for t in cur.values()):
        return "insufficient", ["current side has no call of the roles (unknown role?)"]
    why = []
    for k in ("refusals", "partial"):
        if avg(cur, k) > avg(base, k):
            why.append("%s %.1f -> %.1f" % (k, avg(base, k), avg(cur, k)))
    bt, ct = avg(base, "turns"), avg(cur, "turns")
    if ct > bt + max(2.0, 0.1 * bt):
        why.append("turns %.1f -> %.1f" % (bt, ct))
    return ("worse" if why else "ok"), why


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tasks", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--compare")
    ap.add_argument("--roles", help="r1,r2: only these roles; adds turns and a verdict with --compare")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    a = ap.parse_args(argv)
    calls = read_jsonl(os.path.join(a.root, ".claude", "agent_setup_calls.jsonl"))
    viol = read_jsonl(os.path.join(a.root, ".claude", "agent_setup_violations.jsonl"))
    roles = set(x for x in a.roles.split(",") if x) if a.roles else None
    cur = {t: collect(a.root, t, calls, viol, roles) for t in a.tasks}
    if a.compare:
        try:
            with open(a.compare, encoding="utf-8") as fh:
                base = json.load(fh).get("tasks", {})
        except (OSError, ValueError) as e:
            raise SystemExit("FAIL: cannot read baseline %s: %s" % (a.compare, e))
        rows = compare(base, cur)
        if roles is not None:
            verdict, why = no_worse(base, cur)
            print("verdict\t%s\t%s" % (verdict, "; ".join(why)))
            return 0 if verdict == "ok" else 5
        if a.json:
            print(json.dumps({"compare": [
                {"metric": m, "baseline": b, "current": c, "delta": d}
                for m, b, c, d in rows]}, indent=2))
        else:
            print("metric\tbaseline_avg\tcurrent_avg\tdelta")
            for m, b, c, d in rows:
                print("%s\t%.1f\t%.1f\t%+.1f" % (m, b, c, d))
        return 0
    if a.json:
        print(json.dumps({"tasks": cur}, indent=2, sort_keys=True))
        return 0
    print("task\t" + "\t".join(NUM))
    for t in a.tasks:
        print(t + "\t" + "\t".join(str(cur[t][k]) for k in NUM))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
