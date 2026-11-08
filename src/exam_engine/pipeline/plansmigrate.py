"""plans-migrate (TASK-090, REQ-0098; reports TASK-091, REQ-0099): move the old plans (or reports) folders into
<exam>/<line>/ by a reviewed map. Reports: every old folder becomes report runs <exam>/<line>/run-<id>/ with a
generated run.json + INDEX.md (design phase-91); undo restores the overwritten INDEX.md from MIGRATION.index.

Steps of --apply (design 90.3): validate -> baseline -> free space -> tar.gz backup (listing verified) -> MIGRATION.json
`applying` -> os.rename per move -> history rewrite (.bak) -> rmdir of emptied old folders -> verify -> `applied`.
A failure after the first rename reverses the done moves and restores the history (`rolled_back`, exit 1).
--undo restores from the manifest. Only os.rename inside the root is used to move data: no copy, no delete of data;
os.rmdir only on empty folders. Pure stdlib, no model call, no clock except the stamps of the manifest and the archive.
Exit codes: 0 ok, 1 failed (rolled back), 2 refused / usage.
"""
import argparse
import calendar
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import time

from exam_engine import settings
from exam_engine.pipeline import report_kinds as rk
from exam_engine.pipeline import runlayout

SCHEMA = 1
HISTORY = "run-history.jsonl"
MIN_FREE = 64 * 1024 * 1024
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
DEFAULT_MAP = os.path.join(settings.config_dir(), "plans_migration.json")
SECTIONS = {"plans": ("folders", "moves"), "reports": ("report_folders", "report_moves")}
GEN_NAMES = (runlayout.RUN_JSON, rk.INDEX_NAME)  # generated per run folder; never part of the content set
STASH = "MIGRATION.index"  # reports: copies of every INDEX.md / run.json the generation step overwrites


def _f(exam, line):
    return {"exam": exam, "line": line}


DEFAULT_FOLDERS = {
    "dgnl2025": _f("dgnl2025", "main"), "dgnl2025-fix": _f("dgnl2025", "fix"), "dgnl2025-fix2": _f("dgnl2025", "fix2"),
    "dgnl2025-noise": _f("dgnl2025", "noise"), "dgnl2025-noise2": _f("dgnl2025", "noise2"),
    "dgnl2025-v2": _f("dgnl2025", "v2"), "dgnl2026f": _f("dgnl2026", "f"), "dgnl2026-t80": _f("dgnl2026", "t80"),
    "dgnl2026-v2": _f("dgnl2026", "v2"), "dhqg2024": _f("dhqg2024", "main"), "dhqg2024-t81": _f("dhqg2024", "t81"),
    "dhqg2024-t82": _f("dhqg2024", "t82"), "cacheproof-en": _f("cacheproof-en", "main"),
    "confidence": "keep", "trial-image": "keep", "dgnl-window": "keep", "dgnl-retry": "keep",
    "crosssolve-070": "keep", "regset": "keep"}
DEFAULT_REPORT_FOLDERS = {
    "dgnl2025": _f("dgnl2025", "main"), "dgnl2026": _f("dgnl2026", "f"), "dgnl2026-crosscheck": _f("dgnl2026", "f"),
    "dgnl2026f": _f("dgnl2026", "f"), "dgnl2026-t80": _f("dgnl2026", "t80"), "dhqg2024": _f("dhqg2024", "main"),
    "dhqg2024-t81": _f("dhqg2024", "t81"), "dhqg2024-t82": _f("dhqg2024", "t82"),
    "cacheproof-en": _f("cacheproof-en", "main"), "input-001": _f("input-001", "main")}


def section_of(root):
    return "reports" if os.path.basename(os.path.abspath(root)) == "reports" else "plans"


def _jload(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _dump_atomic(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def _sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _abs(root, rel):
    return os.path.join(os.path.abspath(root), *rel.split("/"))


# ---------------------------------------------------------------- map and move table

def load_map(path, section):
    """(folders, moves or None, raw dict) of the map file; a missing file gives the built-in folders and no moves."""
    fkey, mkey = SECTIONS[section]
    raw = _jload(path) if os.path.isfile(path) else None
    raw = raw if isinstance(raw, dict) else {}
    default = DEFAULT_FOLDERS if section == "plans" else DEFAULT_REPORT_FOLDERS
    return raw.get(fkey) or default, raw.get(mkey), raw


def map_sha(folders, moves, runs=None):
    """sha256 of the map; runs (reports section only) joins the digest, plans keep the original digest."""
    obj = {"folders": folders, "moves": moves}
    if runs is not None:
        obj["runs"] = runs
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def _stamp(plan, old_name):
    digits = "".join(c for c in str((plan or {}).get("started_utc") or "") if c.isdigit())
    if len(digits) >= 14:
        return digits[:8] + "-" + digits[8:14]
    t = runlayout.id_time(old_name)
    return t[:8] + "-" + t[8:] if t else None


def _tag(name):
    """Subject tag of an old run dir name: out-English -> english, run-Math -> math, run / stamp ids -> None."""
    if runlayout._OLD_ID.match(name) or runlayout.PLAN_ID.match(name):
        return None
    base = re.sub(r"^(out|run)(-|$)", "", name, flags=re.I)
    return runlayout.subject_tag(base) if base else None


def build_moves(root, folders, section):
    """(moves, keep, problems) from the live tree and the folders map. moves: sorted by old path, each
    {old,new,kind run|file|cache,exam,line,subject,plan_run_id,plan_sha256}; problems: [(path, reason)]."""
    root = os.path.abspath(root)
    moves, keep, problems, used = [], [], [], set()
    targets_exam = set(v["exam"] for v in folders.values() if isinstance(v, dict) and "exam" in v)
    try:
        top = sorted(os.listdir(root))
    except OSError as exc:
        return [], [], [(root, "unreadable: %s" % exc)]
    for name in top:
        path = os.path.join(root, name)
        if os.path.islink(path):
            problems.append((name, "symlink"))
            continue
        if not os.path.isdir(path):
            keep.append(name)
            continue
        ent = folders.get(name)
        if ent == "keep":
            keep.append(name)
            continue
        if not isinstance(ent, dict):
            if name not in targets_exam:
                problems.append((name, "UNMAPPED folder (add it to the map as {exam,line} or \"keep\")"))
            else:
                keep.append(name)
            continue
        try:
            exam = runlayout._safe(ent["exam"], "exam id")
            line = runlayout.safe_line(ent["line"])
        except (KeyError, ValueError) as exc:
            problems.append((name, "bad map entry: %s" % exc))
            continue
        for child in sorted(os.listdir(path)):
            cpath, old = os.path.join(path, child), "%s/%s" % (name, child)
            if os.path.islink(cpath):
                problems.append((old, "symlink"))
                continue
            mv = {"old": old, "exam": exam, "line": line, "subject": None, "plan_run_id": None, "plan_sha256": None}
            if child in (runlayout.RUNS,):
                problems.append((old, "reserved name %r below a mapped folder" % child))
                continue
            if child == runlayout.CACHE and os.path.isdir(cpath):
                if name == exam:
                    continue  # the exam-level solve cache stays where it is
                mv.update(kind="cache", new="%s/%s/%s" % (exam, line, child))
            elif section == "plans" and os.path.isdir(cpath) and (
                    os.path.isfile(os.path.join(cpath, "plan.json")) or os.path.isfile(os.path.join(cpath, "result.json"))):
                plan = _jload(os.path.join(cpath, "plan.json")) or {}
                stamp, tag = _stamp(plan, child), _tag(child)
                if not stamp:
                    problems.append((old, "no started_utc and no stamp in the name"))
                    continue
                rid = stamp + ("-" + tag if tag else "")
                n, cand = 1, rid
                while "%s/%s/runs/%s" % (exam, line, cand) in used:
                    n += 1
                    cand = "%s-%d" % (rid, n)
                mv.update(kind="run", new="%s/%s/runs/%s" % (exam, line, cand), subject=tag,
                          plan_run_id=plan.get("plan_run_id") or child,
                          plan_sha256=_sha_file(os.path.join(cpath, "plan.json"))
                          if os.path.isfile(os.path.join(cpath, "plan.json")) else None)
            else:
                mv.update(kind="file", new="%s/%s/%s" % (exam, line, child))
            if mv["new"] in used:
                problems.append((old, "target %s used twice" % mv["new"]))
                continue
            used.add(mv["new"])
            moves.append(mv)
    moves.sort(key=lambda m: m["old"])
    return moves, keep, problems


# ---------------------------------------------------------------- reports: run grouping (design 91.1)

def _utc_id(epoch):
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime(epoch))


def _id_epoch(run_id):
    return calendar.timegm(time.strptime(run_id[:15], "%Y%m%d-%H%M%S"))


def _newest_mtime(paths):
    """Newest st_mtime (int seconds) of the files below the given paths, INDEX.md/run.json ignored; None when empty."""
    best = None
    for p in paths:
        walk = [(os.path.dirname(p), [], [os.path.basename(p)])] if os.path.isfile(p) else os.walk(p)
        for base, _dns, fns in walk:
            for fn in fns:
                if fn not in GEN_NAMES:
                    t = int(os.path.getmtime(os.path.join(base, fn)))
                    best = t if best is None or t > best else best
    return best


def _result_shas(paths):
    """result_sha256 values of the result-data json files among/below the given files and dirs (depth <= 2)."""
    out = []
    for top in paths:
        walk = [(os.path.dirname(top), [], [os.path.basename(top)])] if os.path.isfile(top) else os.walk(top)
        for dp, dns, fns in walk:
            dns.sort()
            if os.path.isdir(top) and os.path.relpath(dp, top).count(os.sep) >= 2:
                dns[:] = []
            for fn in sorted(fns):
                p = rk.parse(fn)
                if p and p["kind"] == "result-data" and p["ext"] == "json":
                    meta = _jload(os.path.join(dp, fn)) or {}
                    if isinstance(meta.get("result_sha256"), str):
                        out.append(meta["result_sha256"])
    return out


def _plan_runs_of(plans_root, exam):
    """[(line, run dir)] of plans/<exam>/<line>/runs/<id>/ holding a result.json, sorted."""
    out = []
    base = os.path.join(plans_root, exam)
    try:
        lines = sorted(os.listdir(base))
    except OSError:
        return out
    for ln in lines:
        rd = os.path.join(base, ln, runlayout.RUNS)
        if os.path.isdir(rd):
            out += [(ln, os.path.join(rd, r)) for r in sorted(os.listdir(rd))
                    if os.path.isfile(os.path.join(rd, r, "result.json"))]
    return out


def _link(plans_root, repo, exam, line, src_dirs, stamp):  # src_dirs: files and dirs of the report run
    """(link, plan_line, [plan dir rel to repo], note) of one report run: result_sha256 (result-data json sha matches a
    plan run's result.json), name (a plan run of the same stamp), line (the plan line exists, run unknown), unknown."""
    runs = _plan_runs_of(plans_root, exam)
    shas = _result_shas(src_dirs)
    hit = [(ln, d) for ln, d in runs if os.path.isfile(os.path.join(d, "result.json"))
           and _sha_file(os.path.join(d, "result.json")) in shas] if shas else []
    rel = lambda ds: sorted(os.path.relpath(d, repo).replace(os.sep, "/") for _l, d in ds)
    note = ""
    if hit:
        return "result_sha256", hit[0][0], rel(hit), note
    if shas:
        note = "result-data sha256 matches no plan run"
    if stamp:
        hit = [(ln, d) for ln, d in runs if ln == line and (os.path.basename(d) == stamp
                                                             or os.path.basename(d).startswith(stamp + "-"))]
        if hit:
            return "name", line, rel(hit), note
    if os.path.isdir(os.path.join(plans_root, exam, line)):
        return "line", line, [], note
    return "unknown", None, [], note


def build_report_moves(root, folders, runs_map=None, plans_root=None):
    """(moves, runs, keep, problems) of the reports tree: every mapped old folder becomes report runs below
    <exam>/<line>/run-<id>/. A child dir named like a stamp (YYYYMMDDTHHMMSSZ / NEW_ID) is its own run (kind run, whole
    dir); the other children of a folder form one run (kind file) whose id is the newest file mtime (UTC) of them.
    A taken id in the same line gets -2, -3 (old-folder name order). runs_map: the reviewed `report_runs`; its id,
    status and superseded win. moves: {old,new,kind run|file,exam,line,run}; runs: see design 91.2."""
    root = os.path.abspath(root)
    plans_root = os.path.abspath(plans_root or os.path.join(os.path.dirname(root), "plans"))
    repo = os.path.dirname(root)
    ov = {r["from"]: r for r in runs_map or [] if isinstance(r, dict) and "from" in r}
    moves, runs, keep, problems, used = [], [], [], [], set()
    targets_exam = set(v["exam"] for v in folders.values() if isinstance(v, dict) and "exam" in v)
    try:
        top = sorted(os.listdir(root))
    except OSError as exc:
        return [], [], [], [(root, "unreadable: %s" % exc)]
    sup_reg = rk.load().get("superseded", [])

    def take(exam, line, base, pref, src):
        cand = pref or base
        if pref and not runlayout.NEW_ID.match(pref):
            problems.append((src, "REFUSED: map id %r is not YYYYMMDD-HHMMSS[-N]" % pref))
            return None
        n = 1
        while (exam, line, cand) in used or os.path.lexists(os.path.join(root, exam, line, runlayout.REPORT_PREFIX + cand)):
            if pref:
                problems.append((src, "REFUSED: map id %s is taken in %s/%s" % (pref, exam, line)))
                return None
            n += 1
            cand = "%s-%d" % (base, n)
        used.add((exam, line, cand))
        return cand

    def add_run(exam, line, src, src_dirs, base, how, stamp):
        pref = (ov.get(src) or {}).get("id")
        rid = take(exam, line, base, pref, src)
        if rid is None:
            return None
        link, pline, plan_runs, note = _link(plans_root, repo, exam, line, src_dirs, stamp)
        sup = [{"glob": g["glob"][len(src) + 1:], "note": g.get("note", "")} for g in sup_reg
               if g["glob"].startswith(src + "/")]
        status = "superseded" if any(x["glob"] == "*" for x in sup) else "complete"
        o = ov.get(src) or {}
        run = {"id": rid, "exam": exam, "line": line, "from": src, "id_source": how, "link": link,
               "plan_runs": plan_runs, "plan_line": pline, "status": o.get("status", status),
               "superseded": o.get("superseded", sup)}
        if note:
            run["note"] = note
        runs.append(run)
        return rid

    def add_move(mv):
        if mv["new"] in used_new:
            problems.append((mv["old"], "target %s used twice" % mv["new"]))
            return
        used_new.add(mv["new"])
        moves.append(mv)

    used_new = set()
    for name in top:
        path = os.path.join(root, name)
        if name.startswith("MIGRATION."):
            continue
        if os.path.islink(path):
            problems.append((name, "symlink"))
            continue
        if not os.path.isdir(path):
            keep.append(name)
            continue
        ent = folders.get(name)
        if ent == "keep":
            keep.append(name)
            continue
        if not isinstance(ent, dict):
            if name not in targets_exam:
                problems.append((name, "UNMAPPED folder (add it to the map as {exam,line} or \"keep\")"))
            else:
                keep.append(name)
            continue
        try:
            exam = runlayout._safe(ent["exam"], "exam id")
            line = runlayout.safe_line(ent["line"])
        except (KeyError, ValueError) as exc:
            problems.append((name, "bad map entry: %s" % exc))
            continue
        stamps, loose, index = [], [], []
        for child in sorted(os.listdir(path)):
            cpath = os.path.join(path, child)
            if os.path.islink(cpath):
                problems.append(("%s/%s" % (name, child), "symlink"))
            elif os.path.isdir(cpath) and (runlayout._OLD_ID.match(child) or runlayout.NEW_ID.match(child)):
                stamps.append(child)
            elif os.path.isdir(cpath) and (runlayout._is_line_report_dir(cpath) or (
                    child.startswith(runlayout.REPORT_PREFIX) and runlayout.NEW_ID.match(child[len(runlayout.REPORT_PREFIX):]))):
                continue  # already in the run layout (rerun safe)
            elif child == rk.INDEX_NAME and os.path.isfile(cpath):
                index.append(child)
            else:
                loose.append(child)
        for child in stamps:
            m = runlayout._OLD_ID.match(child)
            base = (m.group(1) + "-" + m.group(2) + (m.group(3) or "")) if m else child
            src = "%s/%s" % (name, child)
            rid = add_run(exam, line, src, [os.path.join(path, child)], base, "name", base[:15])
            if rid:
                add_move({"old": src, "new": "%s/%s/%s%s" % (exam, line, runlayout.REPORT_PREFIX, rid), "kind": "run",
                          "exam": exam, "line": line, "run": rid})
        rid = None
        if loose:
            t = _newest_mtime([os.path.join(path, c) for c in loose])
            if t is None:
                t = int(os.path.getmtime(path))
            rid = add_run(exam, line, name, [os.path.join(path, c) for c in loose], _utc_id(t), "mtime", None)
            for child in loose:
                if rid:
                    add_move({"old": "%s/%s" % (name, child), "new": "%s/%s/%s%s/%s" % (
                        exam, line, runlayout.REPORT_PREFIX, rid, child), "kind": "file", "exam": exam, "line": line,
                        "run": rid})
        for child in index:  # the old index goes with its run, else (split folder) into the line folder
            if loose and not rid:
                continue
            new = "%s/%s/%s%s/%s" % (exam, line, runlayout.REPORT_PREFIX, rid, child) if rid else \
                "%s/%s/%s" % (exam, line, child)
            add_move({"old": "%s/%s" % (name, child), "new": new, "kind": "file", "exam": exam, "line": line, "run": rid})
    moves.sort(key=lambda m: m["old"])
    runs.sort(key=lambda r: (r["exam"], r["line"], r["id"]))
    return moves, runs, keep, problems


def validate(root, moves):
    """[(path, reason)] that make --apply refuse: missing source, existing target, target under its source,
    symlink inside a source, a different filesystem, duplicate target."""
    root = os.path.abspath(root)
    bad, seen = [], set()
    dev = os.stat(root).st_dev
    for mv in moves:
        src, dst = _abs(root, mv["old"]), _abs(root, mv["new"])
        if not os.path.lexists(src):
            bad.append((mv["old"], "source missing"))
            continue
        if os.path.lexists(dst):
            bad.append((mv["new"], "target exists"))
        if mv["new"] in seen:
            bad.append((mv["new"], "duplicate target"))
        seen.add(mv["new"])
        if mv["new"].startswith(mv["old"] + "/"):
            bad.append((mv["old"], "target below its own source"))
        for base, dns, fns in os.walk(src):
            if os.stat(base).st_dev != dev:
                bad.append((mv["old"], "other filesystem"))
                break
            if any(os.path.islink(os.path.join(base, n)) for n in dns + fns):
                bad.append((mv["old"], "symlink inside"))
                break
        else:
            if os.stat(src).st_dev != dev:
                bad.append((mv["old"], "other filesystem"))
    return bad


# ---------------------------------------------------------------- counts

def _is_skipped(rel, section):
    """Files outside the counts: MIGRATION.json[.tmp] and the history with its .bak/.undone/.tmp copies."""
    if section == "reports":
        return rel.startswith("MIGRATION.")  # MIGRATION.json[.tmp] and the MIGRATION.index copies
    return rel.startswith("MIGRATION.json") or (rel == HISTORY or rel.startswith(HISTORY + "."))


def tree_stats(root, section, only=None, content=False):
    """(files, bytes, {rel path: sha256}) of root, excluding MIGRATION.json and the history files (the history is
    rewritten by design: it is checked line by line). The sha map holds every plan.json (plans) or EVERY file (reports).
    only: rel prefixes (folders) to restrict to. content (reports): leave out the generated INDEX.md / run.json."""
    root = os.path.abspath(root)
    files = size = 0
    shas = {}
    for base, dns, fns in os.walk(root):
        dns.sort()
        for fn in fns:
            p = os.path.join(base, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if _is_skipped(rel, section) or os.path.islink(p):
                continue
            if only is not None and rel.split("/")[0] not in only:
                continue
            if content and fn in GEN_NAMES:
                continue
            files += 1
            size += os.path.getsize(p)
            if fn == "plan.json" or section == "reports":
                shas[rel] = _sha_file(p)
    return files, size, shas


def _map_rel(moves, rel, rev=False):
    """Mapped relative path (old->new, or new->old with rev) by the longest matching move, else rel."""
    best = None
    k_from, k_to = ("new", "old") if rev else ("old", "new")
    for mv in moves:
        k = mv[k_from]
        if (rel == k or rel.startswith(k + "/")) and (best is None or len(k) > len(best[k_from])):
            best = mv
    return best[k_to] + rel[len(best[k_from]):] if best else rel


def _source_bytes(root, moves):
    n = b = 0
    for mv in moves:
        src = _abs(root, mv["old"])
        if os.path.isfile(src):
            n, b = n + 1, b + os.path.getsize(src)
            continue
        for base, _d, fns in os.walk(src):
            for fn in fns:
                n, b = n + 1, b + os.path.getsize(os.path.join(base, fn))
    return n, b


# ---------------------------------------------------------------- history

def _jesc(text):
    return json.dumps(text, ensure_ascii=True)[1:-1]


def _history_pairs(root, moves, rev=False):
    root = os.path.abspath(root)
    return [(os.path.join(root, *(m["new"] if rev else m["old"]).split("/")),
             os.path.join(root, *(m["old"] if rev else m["new"]).split("/"))) for m in moves]


def _map_str(text, pairs):
    best = None
    for o, n in pairs:
        if (text == o or text.startswith(o + "/")) and (best is None or len(o) > len(best[0])):
            best = (o, n)
    return best[1] + text[len(best[0]):] if best else text


def _same_mapped(orig, new, pairs):
    if isinstance(orig, dict):
        return isinstance(new, dict) and orig.keys() == new.keys() and all(_same_mapped(orig[k], new[k], pairs) for k in orig)
    if isinstance(orig, list):
        return isinstance(new, list) and len(orig) == len(new) and all(_same_mapped(a, b, pairs) for a, b in zip(orig, new))
    if isinstance(orig, str):
        return new == _map_str(orig, pairs)
    return orig == new


def rewrite_history(path, pairs, backup=None):
    """Rewrite abs paths in the JSONL history: a JSON string value that starts with an old path (followed by end or '/')
    gets the new path. Untouched lines stay byte-identical; each changed line is re-parsed and compared with the
    original under the same mapping. backup: copy2 target made first. tmp + os.replace. Returns
    {"lines": n, "changed": k}; ValueError (nothing written) when a changed line fails the comparison."""
    if not pairs or not os.path.isfile(path):
        return {"lines": 0, "changed": 0}
    table = {_jesc(o): _jesc(n) for o, n in pairs}
    pat = re.compile('"(' + "|".join(re.escape(k) for k in sorted(table, key=len, reverse=True)) + ')(?=["/])')

    def sub(m):
        return '"' + table[m.group(1)]

    with open(path, "rb") as fh:
        raw = fh.read()
    out, lines, changed = [], 0, 0
    for ln in raw.splitlines(True):
        lines += 1
        text = ln.decode("utf-8", "surrogateescape")
        new = pat.sub(sub, text)
        if new != text:
            try:
                ok = _same_mapped(json.loads(text), json.loads(new), pairs)
            except ValueError:
                ok = False
            if not ok:
                raise ValueError("history line %d: rewritten line differs from the original beyond the mapped paths" % lines)
            changed += 1
        out.append(new.encode("utf-8", "surrogateescape"))
    if backup:
        shutil.copy2(path, backup)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(b"".join(out))
    os.replace(tmp, path)
    return {"lines": lines, "changed": changed}


def history_scan(root, moves):
    """{lines, with_paths, missing, would_change}: JSONL lines, lines carrying plan_dir/result_path, paths that do not
    exist, lines the old->new map would change (dry-run)."""
    path = os.path.join(os.path.abspath(root), HISTORY)
    res = {"lines": 0, "with_paths": 0, "missing": 0, "would_change": 0}
    if not os.path.isfile(path):
        return res
    pairs = _history_pairs(root, moves)
    with open(path, encoding="utf-8", errors="surrogateescape") as fh:
        for ln in fh:
            res["lines"] += 1
            try:
                obj = json.loads(ln)
            except ValueError:
                continue
            ps = [obj.get(k) for k in ("plan_dir", "result_path") if isinstance(obj.get(k), str)]
            if not ps:
                continue
            res["with_paths"] += 1
            res["missing"] += sum(1 for p in ps if not os.path.exists(p))
            if any(_map_str(p, pairs) != p for p in ps):
                res["would_change"] += 1
    return res


# ---------------------------------------------------------------- dry-run

def dry_run(root, map_path, write_map=False, force=False, plans_root=None):
    section = section_of(root)
    man = _jload(os.path.join(root, runlayout.MIGRATION_JSON))
    if man and man.get("state") == "applying":
        print("plans-migrate: an apply is unfinished (state applying): --apply resumes it, --undo restores")
        return 0
    if man and man.get("state") == "applied":
        print("plans-migrate: already applied (%d moves, map %s); --verify checks it, --undo restores" % (
            len(man.get("moves", [])), str(man.get("map_sha256"))[:12]))
        return 0
    folders, moves_map, raw = load_map(map_path, section)
    runs = None
    if section == "reports":
        moves, runs, keep, problems = build_report_moves(root, folders, raw.get("report_runs"), plans_root)
    else:
        moves, keep, problems = build_moves(root, folders, section)
    bad = validate(root, moves) if not problems else []
    kinds = {k: sum(1 for m in moves if m["kind"] == k) for k in ("run", "file", "cache")}
    print("plans-migrate dry-run root=%s section=%s map=%s (%s)" % (
        root, section, map_path if os.path.isfile(map_path) else "built-in folders",
        "reviewed moves present" if moves_map is not None else "no moves yet"))
    print("== moves (%d) ==" % len(moves))
    for m in moves:
        extra = " [alias %s]" % m["plan_run_id"] if m["kind"] == "run" and m.get("plan_run_id") not in (
            None, os.path.basename(m["old"])) else ""
        print("%-5s %s -> %s%s" % (m["kind"], m["old"], m["new"], extra))
    print("== per line ==")
    per = {}
    for m in moves:
        per.setdefault("%s/%s" % (m["exam"], m["line"]), {"run": 0, "file": 0, "cache": 0})[m["kind"]] += 1
    for k in sorted(per):
        print("%-24s runs=%d files=%d caches=%d%s" % (k, per[k]["run"], per[k]["file"], per[k]["cache"],
              " report_runs=%d" % sum(1 for r in runs if "%s/%s" % (r["exam"], r["line"]) == k) if runs is not None else ""))
    if runs is not None:
        print("== report runs (%d) ==" % len(runs))
        for r in runs:
            print("run   %s/%s/run-%s from=%s id=%s link=%s plan_line=%s plan_runs=%d status=%s superseded=%d" % (
                r["exam"], r["line"], r["id"], r["from"], r["id_source"], r["link"], r["plan_line"] or "-",
                len(r["plan_runs"]), r["status"], len(r["superseded"])))
            for pr in r["plan_runs"]:
                print("        plan run %s" % pr)
            if r.get("note"):
                print("        NOTE: %s" % r["note"])
    print("== keep (%d) ==" % len(keep))
    for k in keep:
        print("keep  %s" % k)
    unmapped = problems + bad
    print("== UNMAPPED / refused (%d) ==" % len(unmapped))
    for path, why in unmapped:
        print("UNMAPPED %s: %s" % (path, why))
    hs = history_scan(root, moves) if section == "plans" else None
    if hs:
        print("== history == %s: %d lines, %d carry plan_dir/result_path (%d paths missing today), %d lines rewritten" % (
            HISTORY, hs["lines"], hs["with_paths"], hs["missing"], hs["would_change"]))
    print("summary: runs=%d files=%d caches=%d keep=%d unmapped=%d%s%s" % (
        kinds["run"], kinds["file"], kinds["cache"], len(keep), len(unmapped),
        " history_lines_rewritten=%d" % hs["would_change"] if hs else "",
        " report_runs=%d" % len(runs) if runs is not None else ""))
    print("map sha256 (folders+moves): %s" % map_sha(folders, moves, runs))
    if (moves_map is not None and moves_map != moves) or (runs is not None and raw.get("report_runs") not in (None, runs)):
        print("NOTE: the moves in %s differ from the live tree (stale map); --apply would refuse" % map_path)
    if write_map:
        fkey, mkey = SECTIONS[section]
        if raw.get(mkey) is not None and not force:
            print("ERROR: %s already has %s; pass --force to overwrite" % (map_path, mkey), file=sys.stderr)
            return 2
        if unmapped:
            print("ERROR: not writing the map while UNMAPPED entries exist", file=sys.stderr)
            return 2
        raw = dict(raw, schema=SCHEMA)
        raw[fkey], raw[mkey] = folders, moves
        if runs is not None:
            raw["report_runs"] = runs
        os.makedirs(os.path.dirname(os.path.abspath(map_path)), exist_ok=True)
        _dump_atomic(map_path, raw)
        print("wrote %s (%s: %d moves)" % (map_path, mkey, len(moves)))
    return 2 if unmapped else 0


# ---------------------------------------------------------------- apply / undo / verify

def _save(root, man):
    _dump_atomic(os.path.join(os.path.abspath(root), runlayout.MIGRATION_JSON), man)


def _ensure_parent(root, rel_new, created):
    d, missing = os.path.dirname(_abs(root, rel_new)), []
    while not os.path.isdir(d):
        missing.append(d)
        d = os.path.dirname(d)
    for d in reversed(missing):
        os.mkdir(d)
        created.append(os.path.relpath(d, os.path.abspath(root)).replace(os.sep, "/"))


def make_backup(root, backup_dir, moves, extra, stamp):
    """tar.gz of the move sources + extra [(abs path, arcname)] in backup_dir (outside root); the listing is re-read and
    must match the expected member count and bytes. Returns the manifest "backup" dict; ValueError on any refusal."""
    root = os.path.abspath(root)
    bd = os.path.realpath(backup_dir)
    rr = os.path.realpath(root)
    if bd == rr or bd.startswith(rr + os.sep):
        raise ValueError("backup dir %s is inside %s" % (backup_dir, root))
    n_src, b_src = _source_bytes(root, moves)
    n_ext = sum(1 for p, _a in extra if os.path.isfile(p))
    b_ext = sum(os.path.getsize(p) for p, _a in extra if os.path.isfile(p))
    need = b_src + b_ext + MIN_FREE
    os.makedirs(bd, exist_ok=True)
    free = shutil.disk_usage(bd).free
    if free < need:
        raise ValueError("not enough free space in %s: need %d bytes, have %d" % (backup_dir, need, free))
    base = os.path.basename(root)
    path = os.path.join(bd, "%s-backup-%s.tar.gz" % (base, stamp))
    with tarfile.open(path, "w:gz") as tf:
        for mv in moves:
            tf.add(_abs(root, mv["old"]), arcname="%s/%s" % (base, mv["old"]))
        for p, arc in extra:
            if os.path.isfile(p):
                tf.add(p, arcname=arc)
    with tarfile.open(path, "r:gz") as tf:
        members = [m for m in tf.getmembers() if m.isfile()]
    if len(members) != n_src + n_ext or sum(m.size for m in members) != b_src + b_ext:
        raise ValueError("backup listing mismatch: %d files / %d bytes, expected %d / %d" % (
            len(members), sum(m.size for m in members), n_src + n_ext, b_src + b_ext))
    return {"path": path, "sha256": _sha_file(path), "members": len(members), "bytes": b_src + b_ext}


def _gen_targets(runs):
    """[(rel path, kind)] the generation step writes: run.json + INDEX.md per run (oldest first), INDEX.md per line."""
    out = []
    for r in sorted(runs, key=lambda r: (r["exam"], r["line"], _id_epoch(r["id"]), r["id"])):
        d = "%s/%s/%s%s" % (r["exam"], r["line"], runlayout.REPORT_PREFIX, r["id"])
        out += [(d + "/" + runlayout.RUN_JSON, "run.json"), (d + "/" + rk.INDEX_NAME, "run-index")]
    for ln in sorted(set("%s/%s" % (r["exam"], r["line"]) for r in runs)):
        out.append((ln + "/" + rk.INDEX_NAME, "line-index"))
    return out


def _stash(root, moves, targets):
    """Copy every INDEX.md / run.json the generation overwrites to MIGRATION.index/<old rel> (moved ones) or
    MIGRATION.index/<rel> (already at a target). Returns {target rel: stash rel}."""
    root = os.path.abspath(root)
    orig = {}
    for mv in moves:
        src = _abs(root, mv["old"])
        walk = [(os.path.dirname(src), [], [os.path.basename(src)])] if os.path.isfile(src) else os.walk(src)
        for base, _dns, fns in walk:
            for fn in sorted(fns):
                if fn in GEN_NAMES:
                    old = os.path.relpath(os.path.join(base, fn), root).replace(os.sep, "/")
                    orig[_map_rel(moves, old)] = STASH + "/" + old
                    dst = _abs(root, STASH + "/" + old)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(os.path.join(base, fn), dst)
    for rel, _k in targets:
        if rel not in orig and os.path.isfile(_abs(root, rel)):
            orig[rel] = STASH + "/" + rel
            dst = _abs(root, STASH + "/" + rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(_abs(root, rel), dst)
    return orig


def _generate(root, man, plans_root=None):
    """run.json (runlayout.write_report_manifest + migration keys), INDEX.md per run, then per line folder; the sha256 of
    every written file is recorded in man["generated"]."""
    root = os.path.abspath(root)
    repo = os.path.dirname(root)
    by_id = {"%s/%s/%s%s" % (r["exam"], r["line"], runlayout.REPORT_PREFIX, r["id"]): r for r in man["report_runs"]}
    for rel, kind in _gen_targets(man["report_runs"]):
        if kind == "run.json":
            d = rel.rsplit("/", 1)[0]
            r = by_id[d]
            runlayout.write_report_manifest(
                _abs(root, d), [os.path.join(repo, *p.split("/")) for p in r["plan_runs"]], "-", None, "plans-migrate",
                repo_root=repo, now=_id_epoch(r["id"]),
                extra={"exam_id": r["exam"], "migrated_from": r["from"], "link": r["link"], "plan_line": r["plan_line"],
                       "status": r["status"], "superseded": r["superseded"], "id_source": r["id_source"]})
        else:
            rk.write_index(_abs(root, rel.rsplit("/", 1)[0]))
    for g in man["generated"]:
        g["sha"] = _sha_file(_abs(root, g["path"]))


def _unwind_generated(root, man):
    """Remove the generated files, put back the stashed originals at their (moved) place, drop the stash."""
    root = os.path.abspath(root)
    for g in man.get("generated") or []:
        p = _abs(root, g["path"])
        if g.get("orig"):
            if os.path.lexists(p) and os.path.isfile(_abs(root, g["orig"])):
                shutil.copy2(_abs(root, g["orig"]), p)
        elif os.path.isfile(p):
            os.remove(p)
    sd = _abs(root, STASH)
    for base, dns, fns in os.walk(sd, topdown=False):
        for fn in fns:
            os.remove(os.path.join(base, fn))
        os.rmdir(base)


def _rollback(root, man):
    """Reverse done renames, restore the history, rmdir created dirs. True when clean."""
    root_abs = os.path.abspath(root)
    try:
        if man.get("generated"):
            _unwind_generated(root, man)
            man["generated"] = []
        for rel in man.get("removed_dirs", []):
            os.makedirs(_abs(root, rel), exist_ok=True)
        for mv in reversed(man["moves"]):
            if mv.get("state") == "done":
                os.rename(_abs(root, mv["new"]), _abs(root, mv["old"]))
                mv["state"] = "todo"
        hist = man.get("history") or {}
        bak = os.path.join(root_abs, hist.get("bak", "")) if hist.get("bak") else None
        if hist.get("rewritten") and bak and os.path.isfile(bak):
            shutil.copy2(bak, os.path.join(root_abs, hist["file"]))
            os.replace(bak, bak + ".rolledback")
            hist["rewritten"] = False
        for rel in reversed(man.get("created_dirs", [])):
            try:
                os.rmdir(_abs(root, rel))
            except OSError:
                pass
        man["removed_dirs"], man["created_dirs"] = [], []
        man["state"] = "rolled_back"
        _save(root, man)
        return True
    except OSError as exc:
        print("ERROR: rollback failed: %s; state stays `applying`: restore with --undo or from %s" % (
            exc, (man.get("backup") or {}).get("path")), file=sys.stderr)
        return False


def _verify_reports(root, man, base, chk):
    """Reports checks: content files (everything but the generated INDEX.md / run.json) by count, bytes and sha256 at
    the mapped path; every run folder has run.json + INDEX.md; every INDEX.md equals a fresh render."""
    moves = man.get("moves", [])
    cfiles, csize, cshas = tree_stats(root, "reports", content=True)
    want = {_map_rel(moves, k): v for k, v in (base.get("file_sha") or {}).items() if os.path.basename(k) not in GEN_NAMES}
    chk("content files", base.get("content_files"), cfiles)
    chk("content bytes", base.get("content_bytes"), csize)
    chk("content sha256 equal (%d)" % len(want), [], sorted(k for k, v in want.items() if cshas.get(k) != v)[:5])
    runs = man.get("report_runs") or []
    dirs = ["%s/%s/%s%s" % (r["exam"], r["line"], runlayout.REPORT_PREFIX, r["id"]) for r in runs]
    chk("run.json per run (%d)" % len(runs), [],
        [d for d in dirs if runlayout._jload(_abs(root, d + "/" + runlayout.RUN_JSON)) is None][:5])
    chk("INDEX.md per run (%d)" % len(runs), [], [d for d in dirs if not os.path.isfile(_abs(root, d + "/" + rk.INDEX_NAME))][:5])
    stale = []
    for rel, kind in _gen_targets(runs):
        if kind != "run.json":
            d = _abs(root, rel.rsplit("/", 1)[0])
            try:
                with open(_abs(root, rel), encoding="utf-8") as fh:
                    if fh.read() != rk.render_index(d):
                        stale.append(rel)
            except OSError:
                stale.append(rel)
    chk("INDEX.md == fresh render (%d)" % sum(1 for _r, k in _gen_targets(runs) if k != "run.json"), [], stale[:5])


def verify(root, man=None):
    """[(check, expected, got, ok)] of the 90.7 checks against the manifest (read-only)."""
    root = os.path.abspath(root)
    section = section_of(root)
    man = man or _jload(os.path.join(root, runlayout.MIGRATION_JSON)) or {}
    base = man.get("baseline") or {}
    rows = []

    def chk(name, exp, got):
        rows.append((name, exp, got, "ok" if exp == got else "FAIL"))

    if section == "reports":
        _verify_reports(root, man, base, chk)
    else:
        files, size, shas = tree_stats(root, section)
        chk("file count", base.get("files"), files)
        chk("total bytes", base.get("bytes"), size)
        bad = sorted(k for k, v in (base.get("plan_json") or {}).items() if shas.get(k) != v)
        chk("plan.json sha256 equal (%d)" % len(base.get("plan_json") or {}), [], bad[:5])
        chk("plan.json files", len(base.get("plan_json") or {}), len(shas))
    left = sorted(m["new"] for m in man.get("moves", []) if not os.path.lexists(_abs(root, m["new"])))
    chk("targets exist", [], left[:5])
    stale = sorted(m["old"] for m in man.get("moves", []) if os.path.lexists(_abs(root, m["old"])))
    chk("old paths gone", [], stale[:5])
    for name, st in sorted((base.get("keep") or {}).items()):
        f2, b2, s2 = tree_stats(root, section, only=(name,))
        chk("keep %s" % name, [st["files"], st["bytes"]], [f2, b2])
    hist = man.get("history") or {}
    if hist.get("file") and "history_lines" in base:
        path = os.path.join(root, hist["file"])
        lines = with_paths = missing = 0
        try:
            with open(path, encoding="utf-8", errors="surrogateescape") as fh:
                for ln in fh:
                    lines += 1
                    try:
                        obj = json.loads(ln)
                    except ValueError:
                        continue
                    ps = [obj.get(k) for k in ("plan_dir", "result_path") if isinstance(obj.get(k), str)]
                    if ps:
                        with_paths += 1
                        missing += sum(1 for p in ps if not os.path.exists(p))
        except OSError:
            pass
        chk("history lines", base["history_lines"], lines)
        chk("history lines with paths", base["history_with_paths"], with_paths)
        chk("history paths missing (<= before)", True, missing <= base["history_missing"])
    return rows


def _print_rows(rows):
    print("check\texpected\tgot\tok")
    for r in rows:
        print("\t".join(str(c) for c in r))
    bad = sum(1 for r in rows if r[3] != "ok")
    print("RESULT\t%d checks\t%d failed\t%s" % (len(rows), bad, "FAIL" if bad else "PASS"))
    return bad


def apply(root, map_path, backup_dir, now=None, plans_root=None):
    root = os.path.abspath(root)
    section = section_of(root)
    man_path = os.path.join(root, runlayout.MIGRATION_JSON)
    folders, moves_map, _raw = load_map(map_path, section)
    if moves_map is None:
        print("ERROR: %s has no reviewed moves; run --dry-run --write-map, review, then --apply" % map_path, file=sys.stderr)
        return 2
    runs_map = _raw.get("report_runs") if section == "reports" else None
    if section == "reports" and runs_map is None:
        print("ERROR: %s has no report_runs; regenerate with --dry-run --write-map --force" % map_path, file=sys.stderr)
        return 2
    sha = map_sha(folders, moves_map, runs_map)
    man = _jload(man_path)
    if man and man.get("state") == "applied":
        if man.get("map_sha256") == sha:
            print("plans-migrate: nothing to do (already applied, map %s)" % sha[:12])
            return 0
        print("ERROR: already applied with another map (%s); --undo first" % str(man.get("map_sha256"))[:12], file=sys.stderr)
        return 2
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime(now))
    if man and man.get("state") == "applying":
        if man.get("map_sha256") != sha:
            print("ERROR: an unfinished apply used another map; run --undo", file=sys.stderr)
            return 2
        for mv in man["moves"]:
            o, n = os.path.lexists(_abs(root, mv["old"])), os.path.lexists(_abs(root, mv["new"]))
            if o and n or not o and not n:
                print("ERROR: resume refused: %s and %s are %s" % (mv["old"], mv["new"], "both present" if o else "both gone"),
                      file=sys.stderr)
                return 2
            mv["state"] = "done" if n else "todo"
        print("plans-migrate: resuming an unfinished apply (%d of %d moves done)" % (
            sum(1 for m in man["moves"] if m["state"] == "done"), len(man["moves"])))
    else:
        if not backup_dir:
            print("ERROR: --apply needs --backup-dir DIR (outside %s)" % root, file=sys.stderr)
            return 2
        if section == "reports":
            moves, runs, _keep, problems = build_report_moves(root, folders, runs_map, plans_root)
        else:
            moves, _keep, problems = build_moves(root, folders, section)
            runs = None
        if problems:
            for p, why in problems:
                print("UNMAPPED %s: %s" % (p, why), file=sys.stderr)
            return 2
        if moves != moves_map or (runs is not None and runs != runs_map):
            print("ERROR: the moves in %s differ from the live tree (stale map); regenerate with --dry-run --write-map --force"
                  % map_path, file=sys.stderr)
            return 2
        bad = validate(root, moves)
        hist_path = os.path.join(root, HISTORY)
        has_hist = section == "plans" and os.path.isfile(hist_path)
        if has_hist and os.path.lexists(hist_path + ".bak"):
            bad.append((HISTORY + ".bak", "exists; move it away first"))
        if bad:
            for p, why in bad:
                print("REFUSED %s: %s" % (p, why), file=sys.stderr)
            return 2
        files, size, shas = tree_stats(root, section)
        cfiles, csize, _cs = tree_stats(root, section, content=True) if runs is not None else (None, None, None)
        targets = set(v["exam"] for v in folders.values() if isinstance(v, dict))  # a kept exam folder may gain lines
        keep_names = [k for k, v in folders.items() if v == "keep" and k not in targets and os.path.isdir(os.path.join(root, k))]
        keep_base = {}
        for k in keep_names:
            f2, b2, _s = tree_stats(root, section, only=(k,))
            keep_base[k] = {"files": f2, "bytes": b2}
        hs = history_scan(root, moves) if has_hist else {"lines": 0, "with_paths": 0, "missing": 0}
        extra = [(map_path, "%s-map/%s" % (os.path.basename(root), os.path.basename(map_path)))]
        if has_hist:
            extra.append((hist_path, "%s/%s" % (os.path.basename(root), HISTORY)))
        try:
            backup = make_backup(root, backup_dir, moves, extra, stamp)
        except (OSError, ValueError, tarfile.TarError) as exc:
            print("ERROR: backup refused/failed: %s; nothing moved" % exc, file=sys.stderr)
            return 2
        print("backup ok: %s (%d files, %d bytes, sha256 %s)" % (backup["path"], backup["members"], backup["bytes"], backup["sha256"][:12]))
        man = {"schema": SCHEMA, "state": "applying", "section": section, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
               "map_sha256": sha, "folders": folders, "created_dirs": [], "removed_dirs": [],
               "moves": [dict(m, state="todo") for m in moves],
               "history": {"file": HISTORY, "bak": HISTORY + ".bak", "rewritten": False} if has_hist else {},
               "baseline": {"files": files, "bytes": size, "keep": keep_base,
                            "plan_json": {_map_rel(moves, k): v for k, v in shas.items()} if runs is None else {},
                            "history_lines": hs["lines"], "history_with_paths": hs["with_paths"], "history_missing": hs["missing"]},
               "backup": backup}
        if runs is not None:
            man["baseline"].update(file_sha=shas, content_files=cfiles, content_bytes=csize)
            man["report_runs"] = runs
            try:
                targets_rel = _gen_targets(runs)
                orig = _stash(root, moves, targets_rel)
            except OSError as exc:
                print("ERROR: could not stash INDEX.md copies: %s; nothing moved" % exc, file=sys.stderr)
                _unwind_generated(root, {"generated": []})
                return 2
            man["generated"] = [{"path": rel, "orig": orig.get(rel), "sha": None} for rel, _k in targets_rel]
        _save(root, man)
    try:
        for mv in man["moves"]:
            if mv.get("state") == "done":
                continue
            _ensure_parent(root, mv["new"], man["created_dirs"])
            os.rename(_abs(root, mv["old"]), _abs(root, mv["new"]))
            mv["state"] = "done"
            _save(root, man)
        hist = man.get("history") or {}
        if hist.get("file") and not hist.get("rewritten"):
            hp = os.path.join(root, hist["file"])
            bak = os.path.join(root, hist["bak"])
            if os.path.isfile(bak):  # resumed after a crash inside the rewrite: start from the saved original
                shutil.copy2(bak, hp)
                os.remove(bak)
            hist.update(rewrite_history(hp, _history_pairs(root, man["moves"]), backup=bak), rewritten=True)
            _save(root, man)
        for old in sorted(set(m["old"].split("/")[0] for m in man["moves"])):
            if old in man["folders"] and man["folders"][old].get("exam") != old:
                try:
                    os.rmdir(_abs(root, old))
                    man["removed_dirs"].append(old)
                except OSError:
                    print("NOTE: %s not empty after the moves, left in place" % old, file=sys.stderr)
        _save(root, man)
        if man.get("report_runs") is not None:
            _generate(root, man, plans_root)
            _save(root, man)
        rows = verify(root, man)
        if any(r[3] != "ok" for r in rows):
            _print_rows(rows)
            raise ValueError("post-move verification failed")
    except (OSError, ValueError) as exc:
        print("ERROR: %s; rolling back" % exc, file=sys.stderr)
        done = sum(1 for m in man["moves"] if m.get("state") == "done")
        if _rollback(root, man):
            print("rolled back %d moves; backup kept at %s" % (done, (man.get("backup") or {}).get("path")), file=sys.stderr)
        return 1
    man["state"] = "applied"
    _save(root, man)
    n = {k: sum(1 for m in man["moves"] if m["kind"] == k) for k in ("run", "file", "cache")}
    print("plans-migrate applied: %d runs, %d files, %d caches moved; history lines rewritten: %s; manifest %s" % (
        n["run"], n["file"], n["cache"], (man.get("history") or {}).get("changed", "-"), man_path))
    if man.get("report_runs") is not None:
        print("plans-migrate: %d report runs, %d generated files (run.json + INDEX.md)" % (
            len(man["report_runs"]), len(man["generated"])))
    return 0


def undo(root):
    root = os.path.abspath(root)
    section = section_of(root)
    man = _jload(os.path.join(root, runlayout.MIGRATION_JSON))
    if not man or man.get("state") not in ("applied", "applying", "rolled_back"):
        print("ERROR: nothing to undo (no MIGRATION.json in state applied/applying/rolled_back)", file=sys.stderr)
        return 2
    todo = []
    for mv in man["moves"]:
        o, n = os.path.lexists(_abs(root, mv["old"])), os.path.lexists(_abs(root, mv["new"]))
        if n and not o:
            todo.append(mv)
        elif o and not n:
            continue
        else:
            print("ERROR: undo refused: %s / %s are %s" % (mv["old"], mv["new"], "both present" if o else "both gone"), file=sys.stderr)
            return 2
    gen = man.get("generated") or []
    changed = [g["path"] for g in gen if g.get("sha") and (
        not os.path.isfile(_abs(root, g["path"])) or _sha_file(_abs(root, g["path"])) != g["sha"])]
    if changed:  # a regenerated file was edited after the apply: keep it, the original is in MIGRATION.index
        for rel in changed:
            print("ERROR: undo refused: %s changed since the apply (original copy: %s/%s)" % (
                rel, STASH, next((g["orig"][len(STASH) + 1:] for g in gen if g["path"] == rel and g.get("orig")), "-")),
                file=sys.stderr)
        return 2
    try:
        if gen:
            _unwind_generated(root, man)
        for rel in man.get("removed_dirs", []):
            os.makedirs(_abs(root, rel), exist_ok=True)
        for mv in reversed(todo):
            os.makedirs(os.path.dirname(_abs(root, mv["old"])), exist_ok=True)
            os.rename(_abs(root, mv["new"]), _abs(root, mv["old"]))
        hist = man.get("history") or {}
        if hist.get("file"):
            rewrite_history(os.path.join(root, hist["file"]), _history_pairs(root, man["moves"], rev=True))
            bak = os.path.join(root, hist.get("bak", ""))
            if hist.get("bak") and os.path.isfile(bak):
                os.replace(bak, bak + ".undone")
        for rel in reversed(man.get("created_dirs", [])):
            try:
                os.rmdir(_abs(root, rel))
            except OSError:
                pass
    except (OSError, ValueError) as exc:
        print("ERROR: undo failed: %s; restore from %s" % (exc, (man.get("backup") or {}).get("path")), file=sys.stderr)
        return 1
    files, size, shas = tree_stats(root, section)
    base = man.get("baseline") or {}
    if section == "reports":
        back, want = shas, base.get("file_sha") or {}
    else:
        back = {_map_rel(man["moves"], k, rev=True): v for k, v in shas.items()}
        want = {_map_rel(man["moves"], k, rev=True): v for k, v in (base.get("plan_json") or {}).items()}
    man["state"] = "undone"
    man["removed_dirs"], man["created_dirs"], man["generated"] = [], [], []
    _save(root, man)
    ok = (files, size) == (base.get("files"), base.get("bytes")) and back == want
    print("plans-migrate undone: %d moves reversed; files %s bytes %s %s sha256 %s" % (
        len(todo), files, size, "every-file" if section == "reports" else "plan.json", "equal" if ok else "DIFFER"))
    return 0 if ok else 1


# ---------------------------------------------------------------- CLI

def main(argv):
    ap = argparse.ArgumentParser(prog="exam plans-migrate", description=(
        "Move the old plans/ (or reports/) folders into <exam>/<line>/ by the reviewed map config/plans_migration.json. "
        "Default is --dry-run (prints the whole move table, writes nothing)."))
    ap.add_argument("--root", default="plans", help="plans (default) or reports")
    ap.add_argument("--map", default=DEFAULT_MAP, help="map file (default config/plans_migration.json)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print the move table, write nothing (default)")
    mode.add_argument("--apply", action="store_true", help="backup, move, rewrite the history, verify (needs --backup-dir)")
    mode.add_argument("--undo", action="store_true", help="restore the old layout from MIGRATION.json")
    mode.add_argument("--verify", action="store_true", help="read-only before/after checks against MIGRATION.json")
    ap.add_argument("--backup-dir", metavar="DIR", help="--apply: tar.gz target dir, outside the root")
    ap.add_argument("--plans-root", metavar="DIR", help="plan-run links of a reports root are read here (default: plans next to the root)")
    ap.add_argument("--write-map", action="store_true", help="--dry-run: write the generated moves into the map file")
    ap.add_argument("--force", action="store_true", help="--write-map: overwrite existing moves")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if not os.path.isdir(a.root):
        print("ERROR: no such root dir: %s" % a.root, file=sys.stderr)
        return 2
    if a.write_map and (a.apply or a.undo or a.verify):
        print("usage: --write-map goes with --dry-run only", file=sys.stderr)
        return 2
    if a.apply:
        return apply(a.root, a.map, a.backup_dir, plans_root=a.plans_root)
    if a.undo:
        return undo(a.root)
    if a.verify:
        man = _jload(os.path.join(a.root, runlayout.MIGRATION_JSON))
        if not man:
            print("ERROR: no MIGRATION.json in %s" % a.root, file=sys.stderr)
            return 2
        print("state: %s" % man.get("state"))
        return 1 if _print_rows(verify(a.root, man)) else 0
    return dry_run(a.root, a.map, write_map=a.write_map, force=a.force, plans_root=a.plans_root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
