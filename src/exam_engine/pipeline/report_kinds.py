"""Report-kind registry (TASK-085, REQ-0092): the only list of report file kinds.

Names are `<exam>_<subject>_<kind>_<run>.<ext>`; kinds, extensions, legacy names and superseded paths
live in config/report_kinds.json. Writers (reporter, report_build, report_pack), INDEX.md and the doc
test all read it; adding a kind = one registry entry. Pure and deterministic: no clock, no model call.
"""
import fnmatch
import json
import os
import re

from exam_engine import settings

REGISTRY = os.path.join(settings.config_dir(), "report_kinds.json")
PART = re.compile(r"^[a-z0-9-]+$")
INDEX_NAME = "INDEX.md"
_cache = {}


def load(path=None):
    """The registry dict (cached per path)."""
    path = path or REGISTRY
    if path not in _cache:
        with open(path, encoding="utf-8") as fh:
            _cache[path] = json.load(fh)
    return _cache[path]


def slug(s):
    """Lower-case name part: runs of anything outside [a-z0-9] become one '-'; '' when nothing is left."""
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")


def short_run(plan_run_id):
    """'run-<short>' from a plan run id or out dir name ('out-Science2' -> 'run-science2')."""
    s = re.sub(r"^(out|run)-", "", slug(plan_run_id))
    return "run-" + (s or "x")


def name(exam, subject, kind, run, ext):
    """The standard file name; ValueError on a bad part, unknown kind or ext, or wrong scope."""
    kinds = load()["kinds"]
    if kind not in kinds:
        raise ValueError("unknown report kind %r" % kind)
    spec = kinds[kind]
    if ext not in spec["ext"]:
        raise ValueError("kind %s has no extension %r" % (kind, ext))
    for label, part in (("exam", exam), ("subject", subject), ("run", run)):
        if not isinstance(part, str) or not PART.match(part):
            raise ValueError("bad %s name part %r (use [a-z0-9-], no '_')" % (label, part))
    if not run.startswith("run-"):
        raise ValueError("run part must start with 'run-': %r" % run)
    if (subject == "all") != (spec["scope"] == "all") and spec["scope"] != "both":
        raise ValueError("kind %s has scope %s, subject %r" % (kind, spec["scope"], subject))
    return "%s_%s_%s_%s.%s" % (exam, subject, kind, run, ext)


def parse(basename):
    """dict(exam, subject, kind, run, ext) for a standard name of a registered kind, else None."""
    stem, dot, ext = basename.rpartition(".")
    parts = stem.split("_")
    if not dot or len(parts) != 4:
        return None
    exam, subject, kind, run = parts
    try:
        if name(exam, subject, kind, run, ext) != basename:
            return None
    except ValueError:
        return None
    return {"exam": exam, "subject": subject, "kind": kind, "run": run, "ext": ext}


def find(directory, kind, subject=None, ext="md"):
    """Path of the report of `kind` in directory: the standard name first (sorted, optional subject), then a legacy name."""
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return None
    for n in names:
        p = parse(n)
        if p and p["kind"] == kind and p["ext"] == ext and (subject is None or p["subject"] == subject):
            return os.path.join(directory, n)
    for n in load()["kinds"].get(kind, {}).get("legacy", []):
        if n.endswith("." + ext) and n in names:
            return os.path.join(directory, n)
    return None


def legacy_kind(basename):
    for kind, spec in load()["kinds"].items():
        if basename in spec.get("legacy", []):
            return kind
    return None


def run_superseded(folder):
    """[{glob, note}] of folder/run.json `superseded` (globs relative to the run folder); [] when absent or unreadable."""
    try:
        with open(os.path.join(folder, "run.json"), encoding="utf-8") as fh:
            sup = json.load(fh).get("superseded") or []
    except (OSError, ValueError, AttributeError):
        return []
    return [s for s in sup if isinstance(s, dict) and isinstance(s.get("glob"), str)]


def nested_superseded(folder, rel, cache):
    """Note of the first `superseded` glob of a run.json in a parent folder of rel (glob matched against the
    path inside that run folder), else None. cache: {dir: [{glob, note}]} shared by the caller (REQ-0104)."""
    parts = rel.split("/")
    for i in range(len(parts) - 1, 0, -1):
        d = "/".join(parts[:i])
        if d not in cache:
            cache[d] = run_superseded(os.path.join(folder, d))
        sub = "/".join(parts[i:])
        for sup in cache[d]:
            if fnmatch.fnmatch(sub, sup["glob"]):
                return sup.get("note", "")
    return None


def classify(rel, root_name=None, extra=None):
    """(kind|None, 'standard'|'legacy'|'superseded'|None) of a path relative to an exam folder.
    Superseded globs (registry + extra, the run.json list of a moved run) match the relative path,
    also with the folder name in front."""
    base = os.path.basename(rel)
    p = parse(base)
    kind = p["kind"] if p else legacy_kind(base)
    cands = [rel] + (["%s/%s" % (root_name, rel)] if root_name else [])
    for sup in list(load().get("superseded", [])) + list(extra or []):
        if any(fnmatch.fnmatch(c, sup["glob"]) for c in cands):
            return kind, "superseded"
    if p:
        return kind, "standard"
    return (kind, "legacy") if kind else (None, None)


def superseded_note(rel, root_name=None, extra=None):
    cands = [rel] + (["%s/%s" % (root_name, rel)] if root_name else [])
    for sup in list(load().get("superseded", [])) + list(extra or []):
        if any(fnmatch.fnmatch(c, sup["glob"]) for c in cands):
            return sup.get("note", "")
    return ""


def expected(exam, subjects, run, key=False, pdf=True, view="sheet"):
    """Sorted basenames a complete pack must hold: every registered kind whose `needs` applies, per scope.
    Optional extensions (html) and pdf=False pdfs are left out."""
    active = {"", view} | ({"key"} if key else set())
    out = []
    for kind, spec in load()["kinds"].items():
        if spec.get("needs", "") not in active:
            continue
        subs = ([slug(s) for s in subjects] if spec["scope"] in ("subject", "both") else []) \
            + (["all"] if spec["scope"] in ("all", "both") else [])
        for ext in spec["ext"]:
            if ext in spec.get("optional_ext", []) or (ext == "pdf" and not pdf):
                continue
            out += [name(exam, s, kind, run, ext) for s in subs]
    return sorted(out)


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def count_of(path, kind):
    """(count, with_text) for the INDEX: questions of an md report/sheet, rows of a tsv; (None, None) otherwise."""
    how = load()["kinds"].get(kind, {}).get("count", "none")
    text = _read(path) if how != "none" and path.endswith((".md", ".tsv")) else None
    if text is None:
        return None, None
    if how == "rows":
        rows = [ln for ln in text.splitlines() if ln.strip()]
        return max(len(rows) - 1, 0), None
    if kind == "answer-sheet":
        m = re.search(r"(\d+) Questions", text)
        return (int(m.group(1)) if m else None), None
    # one heading style only: legacy files repeat "## Question N" inside the raw explanation
    head = r"^### \S+ \d+\s*$"
    if not re.search(head, text, re.M):
        head = r"^## \S+ \d+\s*$"
    blocks = re.split(head, text, flags=re.M)[1:]
    return len(blocks), sum(1 for b in blocks if _has_text(b))


def _has_text(block):
    """True when a stem and >= 2 consecutive own-line options with distinct letters precede the answer line."""
    lines = block.splitlines()
    ans = next((i for i, ln in enumerate(lines) if re.match(r"\s*(\*\*|- )?Đáp án", ln)), None)
    if ans is None:
        return False
    first = None
    run = []
    for i, ln in enumerate(lines[:ans]):
        m = re.match(r"([A-Z])\.\s", ln)
        if m and ((not run and m.group(1) == "A") or (run and ord(m.group(1)) == ord(run[-1]) + 1)):
            if not run:
                first = i
            run.append(m.group(1))
        elif run:
            break
    return len(run) >= 2 and any(ln.strip() for ln in lines[:first])


def _manifest_lines(folder):
    """3 header lines (plan runs, view, registry/engine) + blank from folder/run.json; [] when absent or unreadable."""
    try:
        with open(os.path.join(folder, "run.json"), encoding="utf-8") as fh:
            m = json.load(fh)
        plans = ", ".join("%s/%s" % (p["exam_id"], p["plan_run_id"]) for p in m["plan_runs"]) or "-"
        eng = (m.get("engine_git") or {}).get("commit") or "-"
        return ["Plan runs: %s" % plans, "View: %s (cmd %s)" % (m.get("view"), m.get("cmd")),
                "Registry sha256: %s; engine: %s" % (str(m.get("registry_sha256"))[:12], str(eng)[:12]), ""]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []


def _generated_index(path):
    """True for an INDEX.md that render_index wrote (header line), not a hand-written one."""
    if os.path.basename(path) != INDEX_NAME:
        return False
    try:
        with open(path, encoding="utf-8") as f:
            return f.readline().startswith("# Reports index: ")
    except (OSError, UnicodeDecodeError):
        return False


def _generated_run_json(path):
    """True for a report run's manifest (a JSON object with a plan_runs list), written by the engine."""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return False
    return isinstance(d, dict) and isinstance(d.get("plan_runs"), list)


def render_index(folder):
    """Text of folder/INDEX.md listing every file below it (sorted, no clock, no absolute path).
    A run folder's run.json is not a registered kind: it is skipped and summarised in 3 header lines. A folder
    that holds new report runs (run-<id> with run.json) gets a runs table and lists only files outside them."""
    from exam_engine.pipeline import runlayout
    folder = os.path.abspath(folder)
    root_name = os.path.basename(folder)
    runs_md = runlayout.runs_table(folder)
    skip = set(runlayout.new_run_dirs(folder)) if runs_md else set()
    rels = []
    for dp, dns, fns in os.walk(folder):
        dns.sort()
        if dp == folder:
            dns[:] = [d for d in dns if d not in skip]
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), folder).replace(os.sep, "/")
            if rel in (INDEX_NAME, runlayout.RUN_JSON) or _generated_index(os.path.join(dp, fn)):
                continue
            if fn == runlayout.RUN_JSON and _generated_run_json(os.path.join(dp, fn)):
                continue
            rels.append(rel)
    rels.sort()
    kinds = load()["kinds"]
    sup_extra = run_superseded(folder)
    nest_cache = {}
    rows, per_kind, stat = [], {}, {"standard": 0, "legacy": 0, "superseded": 0, "unregistered": 0}
    for rel in rels:
        kind, status = classify(rel, root_name, sup_extra)
        cnt, wt = count_of(os.path.join(folder, rel), kind) if kind else (None, None)
        nested = nested_superseded(folder, rel, nest_cache) if status != "superseded" else None
        if nested is not None:
            status = "superseded"
        if status is None:
            status = "unregistered"
        stat[status] += 1
        if kind:
            per_kind[kind] = per_kind.get(kind, 0) + 1
        if nested is not None:
            desc = nested
        elif status == "superseded":
            desc = superseded_note(rel, root_name, sup_extra)
        elif status == "legacy" and wt is not None:
            desc = ("old format (before TASK-085): no question text, raw explanation; kept for history" if not wt
                    else "old format (before TASK-085): question text for %d of %d questions; kept for history" % (wt, cnt))
        elif status == "legacy" and kind == "solution-report" and not rel.endswith((".md", ".tsv")):
            # a legacy pdf/html must not claim the new kind's description: say what its sibling report.md shows
            sib = os.path.join(folder, os.path.dirname(rel), "report.md")
            scnt, swt = count_of(sib, kind) if os.path.isfile(sib) else (None, None)
            ext = rel.rsplit(".", 1)[-1].upper()
            if swt is None:
                desc = "old format %s; content not inspected" % ext
            elif swt == 0:
                desc = "old format (before TASK-085): %s of the sibling report.md; no question text; kept for history" % ext
            else:
                desc = ("old format (before TASK-085): %s of the sibling report.md; question text for %d of %d questions; "
                        "kept for history" % (ext, swt, scnt))
        else:
            desc = kinds[kind]["description"] if kind else "not in config/report_kinds.json"
        c = "-" if cnt is None else (str(cnt) if wt is None else "%d (with_text %d/%d)" % (cnt, wt, cnt))
        rows.append("| %s | %s | %s | %s | %s |" % (rel, kind or "-", status, c, desc.replace("|", "/")))
    md = ["# Reports index: %s" % root_name, "",
          "Generated by `exam report-index` from config/report_kinds.json (docs/guide/report-kinds.md); do not edit.",
          "File name = `%s`. Old names (`report.md`, `answers.md`, ...) are `legacy`; replaced formats are `superseded`." %
          load()["pattern"], ""] + _manifest_lines(folder) + runs_md + runlayout.lines_table(folder) + [
          "| File | Kind | Status | Count | Description |", "| --- | --- | --- | --- | --- |"] + rows + ["", "## Totals", ""]
    md += ["- %s: %d" % (k, per_kind[k]) for k in sorted(per_kind)]
    md += ["- standard: %d" % stat["standard"], "- legacy: %d" % stat["legacy"],
           "- superseded: %d" % stat["superseded"], "- unregistered: %d" % stat["unregistered"],
           "- total: %d" % len(rels)]
    return "\n".join(md) + "\n"


def write_index(folder):
    """Write folder/INDEX.md (render_index); returns its path."""
    path = os.path.join(os.path.abspath(folder), INDEX_NAME)
    text = render_index(folder)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path
