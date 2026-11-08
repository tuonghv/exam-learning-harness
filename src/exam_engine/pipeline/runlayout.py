"""Run-based layout (TASK-087, REQ-0095): the one place that knows where plan runs and report runs live.

New: plans/<exam>/runs/<YYYYMMDD-HHMMSS>[-N]/ (UTC) and reports/<exam>/run-<id>/ with run.json.
Old layouts (plans/<exam>/<run>/, reports/<exam>/<run>/<report-id>/, out-X dirs) stay readable and are
never moved. The solve cache stays plans/<exam>/cache. Pure stdlib; no model call; the only clock is
new_run_id / the created_utc stamp (both take `now`). planrun and report_kinds are imported lazily
(they import this module back).
"""
import hashlib
import json
import os
import re
import time

RUNS = "runs"
CACHE = "cache"
REPORT_PREFIX = "run-"
RUN_JSON = "run.json"
NEW_ID = re.compile(r"^\d{8}-\d{6}(-\d+)?$")
_OLD_ID = re.compile(r"^(\d{8})T(\d{6})Z(-\d+)?$")


def _safe(value, what):
    from exam_engine.pipeline import planrun
    return planrun.safe_id(value, what)


def new_run_id(now=None):
    """UTC stamp YYYYMMDD-HHMMSS; the -N suffix is added only by the claim loops."""
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime(now))


def _claim_dir(base, stamp, prefix=""):
    """makedirs(exist_ok=False) loop: two writers never share a dir; -2, -3 .. on collision."""
    os.makedirs(base, exist_ok=True)
    n = 1
    while True:
        rid = stamp if n == 1 else "%s-%d" % (stamp, n)
        out = os.path.join(base, prefix + rid)
        try:
            os.makedirs(out)
            return out
        except FileExistsError:
            n += 1


def id_time(run_id):
    """Sort string of an id: 'YYYYMMDDHHMMSS' for the new and the old (YYYYMMDDTHHMMSSZ) format, else ''."""
    m = NEW_ID.match(run_id or "")
    if m:
        return run_id[:8] + run_id[9:15]
    m = _OLD_ID.match(run_id or "")
    return m.group(1) + m.group(2) if m else ""


def _suffix(run_id):
    return int(run_id[16:]) if NEW_ID.match(run_id or "") and len(run_id) > 16 else 1


def _jload(path):
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
        return obj if isinstance(obj, dict) else None
    except (OSError, ValueError):
        return None


def cache_dir(root, exam_id):
    return os.path.join(root, _safe(exam_id, "exam id"), CACHE)


def plan_run_dir(root, exam_id, run_id):
    """root/exam/runs/id if it exists, else the legacy root/exam/id if it exists, else the new path."""
    base = os.path.join(root, _safe(exam_id, "exam id"))
    rid = _safe(run_id, "plan run id")
    new, old = os.path.join(base, RUNS, rid), os.path.join(base, rid)
    if os.path.isdir(new):
        return new
    if rid not in (RUNS, CACHE) and os.path.isdir(old):
        return old
    return new


def new_plan_run(root, exam_id, now=None):
    """Claimed plans/<exam>/runs/<UTC stamp>[-N]."""
    return _claim_dir(os.path.join(root, _safe(exam_id, "exam id"), RUNS), new_run_id(now))


def exam_of_plan_dir(plan_dir):
    """Exam id of a plan dir path: the parent name, or the grandparent when the parent is `runs` (defect D1)."""
    parent = os.path.dirname(os.path.abspath(plan_dir.rstrip("/")))
    if os.path.basename(parent) == RUNS:
        parent = os.path.dirname(parent)
    return os.path.basename(parent)


def _plan_key(run_id, plan):
    plan = plan or {}
    return (str(plan.get("started_utc") or plan.get("imported_utc") or id_time(run_id)), run_id)


def list_plan_runs(root, exam_id):
    """[{id, dir, layout 'runs'|'legacy', plan dict|None}] sorted by (started/imported/id time, id), never mtime."""
    base = os.path.join(root, _safe(exam_id, "exam id"))
    out = []
    try:
        names = sorted(os.listdir(os.path.join(base, RUNS)))
    except OSError:
        names = []
    for n in names:
        d = os.path.join(base, RUNS, n)
        if os.path.isdir(d) and not os.path.islink(d):
            out.append({"id": n, "dir": d, "layout": "runs", "plan": _jload(os.path.join(d, "plan.json"))})
    try:
        names = sorted(os.listdir(base))
    except OSError:
        names = []
    for n in names:
        d = os.path.join(base, n)
        if n in (RUNS, CACHE) or os.path.islink(d) or not os.path.isdir(d):
            continue
        if os.path.isfile(os.path.join(d, "plan.json")) or os.path.isfile(os.path.join(d, "result.json")):
            out.append({"id": n, "dir": d, "layout": "legacy", "plan": _jload(os.path.join(d, "plan.json"))})
    out.sort(key=lambda r: _plan_key(r["id"], r["plan"]))
    return out


def new_report_run(root, exam_id, run_id=None):
    """reports/<exam>/run-<id>. A given id (with or without 'run-') reuses the dir (overwrite); none = fresh id."""
    base = os.path.join(root, _safe(exam_id, "exam id"))
    if run_id:
        rid = run_id[len(REPORT_PREFIX):] if run_id.startswith(REPORT_PREFIX) else run_id
        d = os.path.join(base, REPORT_PREFIX + _safe(rid, "report run id"))
        os.makedirs(d, exist_ok=True)
        return d
    return _claim_dir(base, new_run_id(), REPORT_PREFIX)


def report_run_id(report_dir):
    """Id of a report run dir (basename without 'run-')."""
    b = os.path.basename(os.path.abspath(report_dir.rstrip("/")))
    return b[len(REPORT_PREFIX):] if b.startswith(REPORT_PREFIX) else b


def legacy_plan_link(d):
    """plan_run_id from a result-data json below a legacy report folder (depth <= 2), else None."""
    from exam_engine.pipeline import report_kinds as rk
    for dp, dns, fns in os.walk(d):
        dns.sort()
        if os.path.relpath(dp, d).count(os.sep) >= 2:
            dns[:] = []
        for fn in sorted(fns):
            p = rk.parse(fn)
            if p and p["kind"] == "result-data" and p["ext"] == "json":
                meta = _jload(os.path.join(dp, fn))
                if meta and meta.get("plan_run_id"):
                    return meta["plan_run_id"]
    return None


def scan_report_runs(exam_dir):
    """[{id, dir, layout 'run'|'incomplete'|'legacy', manifest, warn}] of one reports/<exam> folder."""
    out = []
    try:
        names = sorted(os.listdir(exam_dir))
    except OSError:
        return out
    for n in names:
        d = os.path.join(exam_dir, n)
        if os.path.islink(d) or not os.path.isdir(d):
            continue
        rid = n[len(REPORT_PREFIX):] if n.startswith(REPORT_PREFIX) else None
        if rid is not None and NEW_ID.match(rid):
            has = os.path.isfile(os.path.join(d, RUN_JSON))
            man = _jload(os.path.join(d, RUN_JSON)) if has else None
            out.append({"id": rid, "dir": d, "layout": "run" if man else "incomplete", "manifest": man,
                        "warn": has and man is None})
        else:
            out.append({"id": n, "dir": d, "layout": "legacy", "manifest": None, "warn": False})
    out.sort(key=lambda r: (id_time(r["id"]) if r["layout"] != "legacy" else "", r["id"]))
    return out


def list_report_runs(root, exam_id):
    return scan_report_runs(os.path.join(root, _safe(exam_id, "exam id")))


def new_run_dirs(folder):
    """Names of the complete new report runs (run-<NEW_ID> holding a readable run.json) directly in folder."""
    return [os.path.basename(r["dir"]) for r in scan_report_runs(folder) if r["layout"] == "run"]


def _sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def write_report_manifest(report_dir, plan_dirs, view, engine_git, cmd, repo_root=None, now=None):
    """Write report_dir/run.json (tmp + rename, sorted keys) after a successful build; returns the dict.
    Plan dirs are only read: the plan -> report link lives here and is derived by list_report_runs."""
    from exam_engine.pipeline import report_kinds as rk
    report_dir = os.path.abspath(report_dir.rstrip("/"))
    repo_root = os.path.abspath(repo_root or os.getcwd())
    plans = []
    for pd in plan_dirs:
        pd = os.path.abspath(pd.rstrip("/"))
        meta = _jload(os.path.join(pd, "plan.json")) or {}
        rel = os.path.relpath(pd, repo_root)
        plans.append({"exam_id": meta.get("exam_id") or exam_of_plan_dir(pd),
                      "plan_run_id": meta.get("plan_run_id") or os.path.basename(pd),
                      "dir": pd if rel.startswith("..") else rel.replace(os.sep, "/"),
                      "result_sha256": _sha_file(os.path.join(pd, "result.json"))})
    rid = report_run_id(report_dir)
    exam_folder = os.path.dirname(report_dir)
    prev = None
    if NEW_ID.match(rid):
        earlier = [r["id"] for r in scan_report_runs(exam_folder)
                   if r["layout"] == "run" and (id_time(r["id"]), _suffix(r["id"])) < (id_time(rid), _suffix(rid))]
        prev = earlier[-1] if earlier else None
    man = {"schema": 1, "report_run_id": rid,
           "exam_id": plans[0]["exam_id"] if plans else os.path.basename(exam_folder),
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "cmd": cmd, "view": view,
           "plan_runs": plans, "prev_report_run": prev,
           "registry_sha256": _sha_file(rk.REGISTRY), "engine_git": engine_git}
    path = os.path.join(report_dir, RUN_JSON)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    return man


def finish_report_run(report_dir, plan_dirs, view, engine_git, cmd, repo_root=None):
    """run.json, then INDEX.md of the run folder and, for a run folder in the new layout, of its exam folder."""
    from exam_engine.pipeline import report_kinds as rk
    man = write_report_manifest(report_dir, plan_dirs, view, engine_git, cmd, repo_root=repo_root)
    rk.write_index(report_dir)
    if NEW_ID.match(man["report_run_id"]) and os.path.basename(os.path.abspath(report_dir)).startswith(REPORT_PREFIX):
        rk.write_index(os.path.dirname(os.path.abspath(report_dir)))
    return man


def plan_ref(man_plan, root):
    """Plan run dir named by one run.json plan_runs entry, resolved under root (both layouts)."""
    try:
        return plan_run_dir(root, man_plan["exam_id"], man_plan["plan_run_id"])
    except (KeyError, ValueError):
        return None


def runs_table(folder):
    """Markdown lines of the report-runs table of an exam reports folder (new runs + legacy dirs), or []."""
    runs = scan_report_runs(folder)
    if not any(r["layout"] == "run" for r in runs):
        return []
    rows = ["## Report runs", "", "| Report run | Layout | Plan runs | View | Cmd | Created |",
            "| --- | --- | --- | --- | --- | --- |"]
    for r in runs:
        m = r["manifest"] or {}
        plans = ", ".join("%s/%s" % (p.get("exam_id"), p.get("plan_run_id")) for p in m.get("plan_runs", [])
                          if isinstance(p, dict)) or "-"
        if r["layout"] == "legacy":
            plans = legacy_plan_link(r["dir"]) or "-"
        rows.append("| %s | %s | %s | %s | %s | %s |" % (
            os.path.basename(r["dir"]), r["layout"], plans, m.get("view", "-"), m.get("cmd", "-"),
            m.get("created_utc", "-")))
    return rows + [""]
