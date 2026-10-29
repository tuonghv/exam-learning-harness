#!/usr/bin/env python3
"""Configured check (docs/req/config.json `checks`): a REQ may reach STATE only when every
linked workflow TASK has reached it too. The workflow (.claude/state) owns the gates and the
evidence; the REQ status follows it and never runs ahead.

Usage: task_gate.py REQ-0001 UNIT_TESTED     exit 0 = pass, 1 = fail (reason on stdout)
A TASK's state: task.<TASK>.json `state` when that file exists (REQ-0060), else task.json `state` when it is the active task, DONE when backlog.json says
`done`, else TODO (queued, not started)."""
import json, re, sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in .claude/ (commit-check rejects bytecode)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import req  # noqa: E402


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def task_state(tid, task, backlog):
    if re.fullmatch(r"TASK-[0-9]+", str(tid)):  # per-task state file (REQ-0060)
        own = load(req.ROOT / ".claude" / "state" / f"task.{tid}.json", None)
        if isinstance(own, dict) and own.get("task_id") == tid:
            return own.get("state", "TODO")
    if task.get("task_id") == tid:
        return task.get("state", "TODO")
    for item in backlog:
        if item.get("task_id") == tid:
            return "DONE" if item.get("status") == "done" else "TODO"
    return None


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in req.ORDER:
        print(f"usage: task_gate.py REQ-id {{{'|'.join(req.ORDER)}}}")
        return 2
    rid, want = sys.argv[1], sys.argv[2]
    meta, _ = req.parse(req.path_of(rid))
    rid = meta.get("id", rid)
    tasks = req.as_list(meta.get("tasks"))
    if not tasks:
        print(f"{rid}: no TASK linked - link the workflow task first: {req.TOOL} task {rid} TASK-0NN")
        return 1
    state_dir = req.ROOT / ".claude" / "state"
    task = load(state_dir / "task.json", {})
    backlog = load(state_dir / "backlog.json", [])
    behind = []
    for tid in tasks:
        st = task_state(tid, task, backlog)
        if st is None:
            behind.append(f"{tid} not found in task.json/backlog.json")
        elif st not in req.ORDER or req.ORDER.index(st) < req.ORDER.index(want):
            behind.append(f"{tid} is {st}")
    if behind:
        print(f"{rid} cannot be {want} before its task(s): " + "; ".join(behind)
              + ". Advance the TASK through the workflow skill first.")
        return 1
    print(f"linked task(s) {', '.join(tasks)} at or past {want}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
