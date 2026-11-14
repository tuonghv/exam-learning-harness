"""Line-based layout (TASK-090, REQ-0098; run-based TASK-087, REQ-0095): the one place that knows where plan runs and
report runs live.

New: plans/<exam>/<line>/runs/<YYYYMMDD-HHMMSS>[-<subject>][-N]/ (UTC, line default `main`) and
reports/<exam>/<line>/run-<id>/ with run.json. Readable for ever: plans/<exam>/runs/<id> (REQ-0095),
plans/<exam>/<run>/ (legacy) and, after `exam plans-migrate`, the old paths through plans/MIGRATION.json
(migrated()). The solve cache stays plans/<exam>/cache for every line. Pure stdlib; no model call; the only clock is
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
RUN_JSON = "run.json"  # legacy in-folder name (migration + guards only; TASK-102)
REPORT_RUNS = "report-runs"  # per line: run-<id>.json files, one per report run
LINE_DEFAULT = "main"
MIGRATION_JSON = "MIGRATION.json"
NEW_ID = re.compile(r"^\d{8}-\d{6}(-\d+)?$")  # report run ids
PLAN_ID = re.compile(r"^(\d{8}-\d{6})(?:-([a-z][a-z0-9._-]*?))?(?:-([1-9]\d*))?$")  # plan run ids: stamp[-subject][-N]
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
    m = PLAN_ID.match(run_id or "")
    if m:
        return run_id[:8] + run_id[9:15]
    m = _OLD_ID.match(run_id or "")
    return m.group(1) + m.group(2) if m else ""


def _suffix(run_id):
    m = PLAN_ID.match(run_id or "")
    return int(m.group(3)) if m and m.group(3) else 1


def subject_tag(text):
    """Lowercase subject tag of a run id from a file stem or folder name, or None (must start with a letter)."""
    t = re.sub(r"[^a-z0-9._-]", "-", str(text or "").lower())
    t = re.sub(r"-{2,}", "-", t).strip("-._")
    t = re.sub(r"-([1-9]\d*)$", r"\1", t)  # -N suffix has no leading zero: a tag never ends in -<N>
    return t if re.match(r"^[a-z][a-z0-9._-]*$", t) else None


def safe_line(line):
    """Line name used as a path component: a safe id that is not a reserved folder name."""
    line = _safe(line, "line")
    if line in (RUNS, CACHE, REPORT_RUNS):
        raise ValueError("invalid line %r (reserved name)" % line)
    return line


# Plans/reports trees of this repo (real paths): a write to their main line needs --publish. Tests patch it.
PROTECTED_ROOTS = tuple(os.path.realpath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), d))
    for d in ("plans", "reports"))
PUBLISHED = "published"
DEV = "dev"


class PublishRequired(ValueError):
    """A write into the published line (main) without --publish."""


def is_published_line(line):
    """main (and the layout without a line, '-' / None) is the published line; any other line is dev."""
    return line in (LINE_DEFAULT, None, "-")


def require_publish(line, publish, what, root, exam=None):
    """Raise PublishRequired when `what` would write into the published line of a protected root without publish.
    line None: derived from root (a --out path: <protected>/<exam>/<line>/...). Roots outside PROTECTED_ROOTS pass."""
    rp = os.path.realpath(root)
    for prot in PROTECTED_ROOTS:
        if rp == prot or rp.startswith(prot + os.sep):
            break
    else:
        return
    parts = [x for x in os.path.relpath(rp, prot).split(os.sep) if x != "."]
    if line is None:
        line = parts[1] if len(parts) >= 2 else None
    if publish or not is_published_line(line):
        return
    exam = exam or (parts[0] if parts else None)
    raise PublishRequired("%s: line 'main'%s is the published line; tests/experiments use --line <name> (e.g. --line v3); "
                          "pass --publish only when the user asked for a main run."
                          % (what, " of %s" % exam if exam else ""))


def _jload(path):
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
        return obj if isinstance(obj, dict) else None
    except (OSError, ValueError):
        return None


def cache_dir(root, exam_id):
    return os.path.join(root, _safe(exam_id, "exam id"), CACHE)


def line_dirs(base):
    """Names of the line folders below an exam folder: real dirs that hold a runs/ dir (sorted)."""
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    return [n for n in names if n not in (RUNS, CACHE, REPORT_RUNS) and not os.path.islink(os.path.join(base, n))
            and os.path.isdir(os.path.join(base, n, RUNS))]


def _manifest(root):
    """root/MIGRATION.json when its state is `applied`, else None."""
    man = _jload(os.path.join(root, MIGRATION_JSON))
    return man if man and man.get("state") == "applied" else None


def _rel_to_root(root, path):
    """Posix path of `path` below root (absolute, cwd-relative or root-prefixed), or None when outside."""
    absroot = os.path.abspath(root)
    p = path
    if not os.path.isabs(p):
        pre = os.path.basename(absroot) + "/"
        norm = os.path.normpath(p).replace(os.sep, "/")
        if norm.startswith(pre):
            return norm[len(pre):]
        if not os.path.exists(p):
            return None if norm.startswith("..") else norm
        p = os.path.abspath(p)
    rel = os.path.relpath(os.path.normpath(p), absroot)
    if rel == ".." or rel.startswith(".." + os.sep):
        return None
    return rel.replace(os.sep, "/")


def _moved(man, rel):
    """(move entry, mapped relative path) of the longest old path that is a prefix of rel, else (None, None)."""
    best = None
    for mv in man.get("moves", []):
        old = mv.get("old", "")
        if (rel == old or rel.startswith(old + "/")) and (best is None or len(old) > len(best["old"])):
            best = mv
    if best is None:
        return None, None
    return best, best["new"] + rel[len(best["old"]):]


def migrated(root, path):
    """New path of an OLD plans path (absolute history path, `OLD/ID` ref or `plans/OLD/ID`) per root/MIGRATION.json,
    else None. Longest-prefix match over the applied moves; a path that was never moved gives None."""
    man = _manifest(root)
    rel = _rel_to_root(root, path) if man else None
    if rel is None:
        return None
    _mv, new = _moved(man, rel)
    return os.path.join(root, *new.split("/")) if new else None


def migrated_run_dirs(root, path):
    """Sorted run folders (rel. to root) that the files of an OLD reports folder `path` were moved to, per the applied
    root/MIGRATION.json (a stamp dir moved whole counts as its run folder); [] when path was not moved."""
    man = _manifest(root)
    rel = _rel_to_root(root, path) if man else None
    if not rel:
        return []
    out = set()
    for mv in man.get("moves", []):
        old = mv.get("old", "")
        if old == rel or old.startswith(rel + "/") or rel.startswith(old + "/"):
            parts = mv["new"].split("/")
            i = next((k for k, x in enumerate(parts) if x.startswith(REPORT_PREFIX)), len(parts) - 1)
            out.add("/".join(parts[:i + 1]))
    return sorted(out)


def folder_alias(root, name):
    """(exam, line) an OLD folder name below root was migrated to (MIGRATION.json folders map), else None."""
    man = _manifest(root)
    ent = (man or {}).get("folders", {}).get(name)
    return (ent["exam"], ent["line"]) if isinstance(ent, dict) else None


def migration_folders(root):
    """{old folder: (exam, line)} of the applied MIGRATION.json (kept folders are not listed)."""
    return {k: (v["exam"], v["line"]) for k, v in ((_manifest(root) or {}).get("folders") or {}).items()
            if isinstance(v, dict)}


def exam_line_of_plan_dir(plan_dir):
    """(exam, line) of a plan dir: plan.json plan_exam+line (new runs), else the MIGRATION.json entry of its new
    path, else REQ-0095 runs/<id> -> (exam, '-'), else legacy <exam>/<run> -> (exam, '-')."""
    d = os.path.abspath(plan_dir.rstrip("/"))
    meta = _jload(os.path.join(d, "plan.json")) or {}
    if meta.get("plan_exam") and meta.get("line"):
        return meta["plan_exam"], meta["line"]
    probe = d
    for _ in range(5):
        probe = os.path.dirname(probe)
        if os.path.isfile(os.path.join(probe, MIGRATION_JSON)):
            man = _manifest(probe)
            rel = _rel_to_root(probe, d) if man else None
            for mv in (man or {}).get("moves", []):
                if rel and mv.get("kind") == "run" and mv.get("new") == rel and mv.get("exam"):
                    return mv["exam"], mv["line"]
            break
    parent = os.path.dirname(d)
    if os.path.basename(parent) == RUNS:
        parent = os.path.dirname(parent)
    return os.path.basename(parent), "-"


def plan_run_dir(root, exam_id, run_id, line=None):
    """Plan run dir. line given: root/exam/line/runs/id. Else the one line holding id (ValueError when two do),
    then root/exam/runs/id (REQ-0095), the legacy root/exam/id, the migrated path of exam/id, else the main path."""
    base = os.path.join(root, _safe(exam_id, "exam id"))
    rid = _safe(run_id, "plan run id")
    if line:
        return os.path.join(base, safe_line(line), RUNS, rid)
    hits = [os.path.join(base, ln, RUNS, rid) for ln in line_dirs(base)
            if os.path.isdir(os.path.join(base, ln, RUNS, rid))]
    if len(hits) > 1:
        raise ValueError("ambiguous: %s in lines %s; use EXAM/LINE/ID" % (
            rid, ", ".join(os.path.basename(os.path.dirname(os.path.dirname(h))) for h in hits)))
    if hits:
        return hits[0]
    req95, old = os.path.join(base, RUNS, rid), os.path.join(base, rid)
    if os.path.isdir(req95):
        return req95
    if rid not in (RUNS, CACHE) and os.path.isdir(old):
        return old
    mig = migrated(root, "%s/%s" % (exam_id, rid))
    if mig and os.path.isdir(mig):
        return mig
    return os.path.join(base, LINE_DEFAULT, RUNS, rid)


def new_plan_run(root, exam_id, line=LINE_DEFAULT, subject=None, now=None, publish=False):
    """Claimed plans/<exam>/<line>/runs/<UTC stamp>[-<subject>][-N]. Main of a protected root needs publish."""
    require_publish(line, publish, "new plan run", root, exam_id)
    tag = subject_tag(subject) if subject else None
    return _claim_dir(os.path.join(root, _safe(exam_id, "exam id"), safe_line(line), RUNS),
                      new_run_id(now) + ("-" + tag if tag else ""))


def exam_of_plan_dir(plan_dir):
    """Exam id of a plan dir path (first item of exam_line_of_plan_dir)."""
    return exam_line_of_plan_dir(plan_dir)[0]


def _norm_time(text):
    """ISO or compact timestamp -> 'YYYYMMDDHHMMSS' ('' when it has fewer than 14 digits)."""
    digits = "".join(c for c in str(text or "") if c.isdigit())
    return digits[:14] if len(digits) >= 14 else ""


def _plan_key(run_id, plan):
    """One comparable key: id time (new/old ids), else plan.json started/imported/finished time, then suffix, id."""
    plan = plan or {}
    t = id_time(run_id)
    if not t:
        for k in ("started_utc", "imported_utc", "finished_utc"):
            t = _norm_time(plan.get(k))
            if t:
                break
    return (t, _suffix(run_id), run_id)


def _run_row(d, name, layout, line):
    plan = _jload(os.path.join(d, "plan.json"))
    m = PLAN_ID.match(name)
    alias = (plan or {}).get("plan_run_id")
    return {"id": name, "dir": d, "layout": layout, "line": line, "subject": m.group(2) if m else None,
            "alias": alias if alias and alias != name else None, "plan": plan}


def list_plan_runs(root, exam_id, line=None):
    """[{id, dir, layout 'line'|'runs'|'legacy', line, subject, alias, plan}] of one exam, sorted by (started/imported/id
    time, id), never mtime. line given: only that line folder; else every line, REQ-0095 runs/ (line '-') and legacy."""
    base = os.path.join(root, _safe(exam_id, "exam id"))
    out = []
    for ln in ([safe_line(line)] if line else line_dirs(base)):
        try:
            names = sorted(os.listdir(os.path.join(base, ln, RUNS)))
        except OSError:
            continue
        for n in names:
            d = os.path.join(base, ln, RUNS, n)
            if os.path.isdir(d) and not os.path.islink(d):
                out.append(_run_row(d, n, "line", ln))
    if line:
        out.sort(key=lambda r: _plan_key(r["id"], r["plan"]))
        return out
    try:
        names = sorted(os.listdir(os.path.join(base, RUNS)))
    except OSError:
        names = []
    for n in names:
        d = os.path.join(base, RUNS, n)
        if os.path.isdir(d) and not os.path.islink(d):
            out.append(_run_row(d, n, "runs", "-"))
    try:
        names = sorted(os.listdir(base))
    except OSError:
        names = []
    for n in names:
        d = os.path.join(base, n)
        if n in (RUNS, CACHE, REPORT_RUNS) or os.path.islink(d) or not os.path.isdir(d):
            continue
        if os.path.isfile(os.path.join(d, "plan.json")) or os.path.isfile(os.path.join(d, "result.json")):
            out.append(_run_row(d, n, "legacy", "-"))
    out.sort(key=lambda r: _plan_key(r["id"], r["plan"]))
    return out


def new_report_run(root, exam_id, run_id=None, line=None, publish=False):
    """reports/<exam>[/<line>]/run-<id>. A given id (with or without 'run-') reuses the dir (overwrite); none = fresh id.
    Main (or no line) of a protected root needs publish."""
    require_publish(line, publish, "new report run", root, exam_id)
    base = os.path.join(root, _safe(exam_id, "exam id"))
    if line and line != "-":
        base = os.path.join(base, safe_line(line))
    if run_id:
        rid = run_id[len(REPORT_PREFIX):] if run_id.startswith(REPORT_PREFIX) else run_id
        d = os.path.join(base, REPORT_PREFIX + _safe(rid, "report run id"))
        os.makedirs(d, exist_ok=True)
        drop_report_manifest(d)  # a rebuild in progress is `incomplete`, not complete with the old one
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


def _is_line_report_dir(d):
    """A report line folder: a dir that holds at least one run-<id> dir (it is scanned on its own)."""
    try:
        return any(n.startswith(REPORT_PREFIX) and NEW_ID.match(n[len(REPORT_PREFIX):])
                   and os.path.isdir(os.path.join(d, n)) for n in os.listdir(d))
    except OSError:
        return False


def scan_report_runs(exam_dir, skip_lines=True):
    """[{id, dir, layout 'run'|'incomplete'|'legacy', manifest, warn}] of one reports folder (exam or line folder).
    Line folders below an exam folder (they hold run-<id> dirs) are skipped: list_report_runs scans them."""
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
            mp = manifest_path(d)
            has = os.path.isfile(mp)
            man = _jload(mp) if has else None
            warn = has and man is None
            if not has and os.path.isfile(os.path.join(d, RUN_JSON)):
                warn = "unmigrated"  # old in-folder run.json, no plans manifest: exam report-manifests-migrate
            out.append({"id": rid, "dir": d, "layout": "run" if man else "incomplete", "manifest": man, "warn": warn})
        elif skip_lines and _is_line_report_dir(d):
            continue
        else:
            out.append({"id": n, "dir": d, "layout": "legacy", "manifest": None, "warn": False})
    out.sort(key=lambda r: (id_time(r["id"]) if r["layout"] != "legacy" else "", r["id"]))
    return out


def list_report_runs(root, exam_id, line=None):
    """Report runs of reports/<exam> (line '-') plus those of each line folder (rows get a `line` key).
    line given: only that line folder."""
    base = os.path.join(root, _safe(exam_id, "exam id"))
    out = []
    if not line:
        out = [dict(r, line="-") for r in scan_report_runs(base)]
        lines = [n for n in sorted(os.listdir(base)) if os.path.isdir(os.path.join(base, n))
                 and not os.path.islink(os.path.join(base, n)) and _is_line_report_dir(os.path.join(base, n))] \
            if os.path.isdir(base) else []
    else:
        lines = [safe_line(line)]
    for ln in lines:
        out.extend(dict(r, line=ln) for r in scan_report_runs(os.path.join(base, ln), skip_lines=False))
    return out


def new_run_dirs(folder):
    """Names of the complete new report runs (run-<NEW_ID> with a readable manifest) directly in folder."""
    return [os.path.basename(r["dir"]) for r in scan_report_runs(folder) if r["layout"] == "run"]


def _sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def manifest_path(report_dir):
    """Manifest file of a report run, never inside the run folder. (a) below a dir named `reports`:
    <its parent>/plans/<exam>[/<line>]/report-runs/<run>.json; (b) otherwise a sibling <run>.run.json."""
    d = os.path.abspath(str(report_dir).rstrip("/"))
    base = os.path.basename(d)
    top = os.path.dirname(d)
    while True:
        if os.path.basename(top) == "reports":
            rel = os.path.relpath(d, top)
            return os.path.join(os.path.dirname(top), "plans", os.path.dirname(rel), REPORT_RUNS, base + ".json")
        up = os.path.dirname(top)
        if up == top:
            break
        top = up
    return os.path.join(os.path.dirname(d), base + ".run.json")


def read_report_manifest(report_dir):
    return _jload(manifest_path(report_dir))


def drop_report_manifest(report_dir):
    try:
        os.unlink(manifest_path(report_dir))
    except FileNotFoundError:
        pass


def write_report_manifest(report_dir, plan_dirs, view, engine_git, cmd, repo_root=None, now=None, extra=None):
    """Write the manifest of report_dir (manifest_path; tmp + rename, sorted keys) after a successful build; returns the dict.
    Plan dirs are only read: the plan -> report link lives here and is derived by list_report_runs.
    extra: keys merged over the manifest (plans-migrate: exam_id, migrated_from, link, plan_line, status,
    superseded); its exam_id is the fallback when no plan run names the exam (a line folder's name is not one)."""
    from exam_engine.pipeline import report_kinds as rk
    report_dir = os.path.abspath(report_dir.rstrip("/"))
    repo_root = os.path.abspath(repo_root or os.getcwd())
    plans = []
    for pd in plan_dirs:
        pd = os.path.abspath(pd.rstrip("/"))
        meta = _jload(os.path.join(pd, "plan.json")) or {}
        rel = os.path.relpath(pd, repo_root)
        pexam, pline = exam_line_of_plan_dir(pd)
        ent = {"exam_id": meta.get("exam_id") or pexam,
               "plan_run_id": os.path.basename(pd) if pline != "-" else meta.get("plan_run_id") or os.path.basename(pd),
               "dir": pd if rel.startswith("..") else rel.replace(os.sep, "/"),
               "result_sha256": _sha_file(os.path.join(pd, "result.json"))}
        if pline != "-":  # line layout: exam_id is the plan folder (plan.json exam_id is the subject stem)
            ent.update(exam_id=pexam, line=pline)
        plans.append(ent)
    rid = report_run_id(report_dir)
    exam_folder = os.path.dirname(report_dir)
    prev = None
    if NEW_ID.match(rid):
        earlier = [r["id"] for r in scan_report_runs(exam_folder)
                   if r["layout"] == "run" and (id_time(r["id"]), _suffix(r["id"])) < (id_time(rid), _suffix(rid))]
        prev = earlier[-1] if earlier else None
    man = {"schema": 1, "report_run_id": rid,
           "exam_id": plans[0]["exam_id"] if plans else (extra or {}).get("exam_id") or os.path.basename(exam_folder),
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "cmd": cmd, "view": view,
           "plan_runs": plans, "prev_report_run": prev, "status": "complete",
           "registry_sha256": _sha_file(rk.REGISTRY), "engine_git": engine_git}
    man.update({k: v for k, v in (extra or {}).items() if k != "exam_id" or not plans})
    path = manifest_path(report_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    return man


def migrate_run_json(reports_root, apply=False):
    """TASK-102: move each in-folder run.json of a report run (dir run-<id> holding a manifest dict with a plan_runs
    list) to manifest_path(dir). Returns (moves [(src, dst)], already_migrated count, problems [text]).
    Target missing: os.replace. Target equal (sha256): the source is removed. Target different: problem, nothing
    moved for that run. apply: INDEX.md of each touched run folder, its parent and (exam/line/run) the exam folder
    are rewritten (their text does not change). Idempotent."""
    from exam_engine.pipeline import report_kinds as rk
    moves, problems, touched, done = [], [], [], 0
    for dp, dns, fns in os.walk(reports_root):
        dns.sort()
        dns[:] = [n for n in dns if not os.path.islink(os.path.join(dp, n))]
        base = os.path.basename(os.path.abspath(dp))
        if not base.startswith(REPORT_PREFIX):
            continue
        src, dst = os.path.join(dp, RUN_JSON), manifest_path(dp)
        if RUN_JSON not in fns:
            done += 1 if os.path.isfile(dst) else 0
            continue
        man = _jload(src)
        if man is None or not isinstance(man.get("plan_runs"), list):
            continue
        if os.path.isfile(dst):
            if _sha_file(dst) != _sha_file(src):
                problems.append("%s differs from existing %s; nothing moved" % (src, dst))
                continue
        moves.append((src, dst))
        if not apply:
            continue
        try:
            if os.path.isfile(dst):
                os.unlink(src)
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.replace(src, dst)
        except OSError as exc:
            moves.pop()
            problems.append("%s: %s" % (src, exc))
            continue
        touched.append(os.path.abspath(dp))
    root = os.path.abspath(reports_root)
    idx = []
    for d in touched:
        for x in (d, os.path.dirname(d), os.path.dirname(os.path.dirname(d))):
            if x not in idx and x != root and x.startswith(root + os.sep):
                if x == os.path.dirname(os.path.dirname(d)) and len(os.path.relpath(d, root).split(os.sep)) < 3:
                    continue
                idx.append(x)
    for x in idx:
        rk.write_index(x)
    return moves, done, problems


def finish_report_run(report_dir, plan_dirs, view, engine_git, cmd, repo_root=None, extra=None):
    """manifest, then INDEX.md of the run folder and, for a run folder in the new layout, of its (line or exam) folder;
    a run in a line folder also refreshes the exam folder's INDEX.md (lines table)."""
    from exam_engine.pipeline import report_kinds as rk
    man = write_report_manifest(report_dir, plan_dirs, view, engine_git, cmd, repo_root=repo_root, extra=extra)
    rk.write_index(report_dir)
    ad = os.path.abspath(report_dir)
    if NEW_ID.match(man["report_run_id"]) and os.path.basename(ad).startswith(REPORT_PREFIX):
        parent = os.path.dirname(ad)
        rk.write_index(parent)
        lines = [p.get("line") for p in man["plan_runs"] if p.get("line")]
        if lines and os.path.basename(parent) in (LINE_DEFAULT, lines[0]):
            rk.write_index(os.path.dirname(parent))
    return man


def lines_table(exam_folder):
    """Markdown lines of the lines table of a reports exam folder holding line folders (main first), else []."""
    try:
        names = sorted(os.listdir(exam_folder))
    except OSError:
        return []
    lines = [n for n in names if os.path.isdir(os.path.join(exam_folder, n)) and not os.path.islink(os.path.join(exam_folder, n))
             and _is_line_report_dir(os.path.join(exam_folder, n))]
    if not any(not n.startswith(REPORT_PREFIX) for n in lines):
        return []
    lines = [n for n in lines if not n.startswith(REPORT_PREFIX)]
    lines.sort(key=lambda n: (n != LINE_DEFAULT, n))
    rows = ["## Lines", "", "| Line | Publish | Report runs | Latest |", "| --- | --- | --- | --- |"]
    for n in lines:
        runs = [r for r in scan_report_runs(os.path.join(exam_folder, n), skip_lines=False) if r["layout"] == "run"]
        rows.append("| %s | %s | %d | %s |" % (n, PUBLISHED if is_published_line(n) else DEV, len(runs),
                                              "run-" + runs[-1]["id"] if runs else "-"))
    return rows + [""]


def plan_ref(man_plan, root):
    """Plan run dir named by one run.json plan_runs entry, resolved under root (all layouts, migrated paths)."""
    try:
        d = plan_run_dir(root, man_plan["exam_id"], man_plan["plan_run_id"], line=man_plan.get("line"))
    except (KeyError, ValueError):
        return None
    if not os.path.isdir(d) and man_plan.get("dir"):
        return migrated(root, man_plan["dir"]) or d
    return d


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
