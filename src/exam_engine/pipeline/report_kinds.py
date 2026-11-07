"""Report-kind registry (TASK-085, REQ-0092): the only list of report file kinds.

Names are `<exam>_<subject>_<kind>_<run>.<ext>`; kinds, extensions, legacy names and superseded paths
live in config/report_kinds.json. Writers (reporter, report_build, report_pack), INDEX.md and the doc
test all read it; adding a kind = one registry entry. Pure and deterministic: no clock, no model call.
"""
import fnmatch
import json
import os
import re

REGISTRY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))), "config", "report_kinds.json")
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


def classify(rel, root_name=None):
    """(kind|None, 'standard'|'legacy'|'superseded'|None) of a path relative to an exam folder.
    Superseded globs match the relative path, also with the folder name in front."""
    base = os.path.basename(rel)
    p = parse(base)
    kind = p["kind"] if p else legacy_kind(base)
    cands = [rel] + (["%s/%s" % (root_name, rel)] if root_name else [])
    for sup in load().get("superseded", []):
        if any(fnmatch.fnmatch(c, sup["glob"]) for c in cands):
            return kind, "superseded"
    if p:
        return kind, "standard"
    return (kind, "legacy") if kind else (None, None)


def superseded_note(rel, root_name=None):
    cands = [rel] + (["%s/%s" % (root_name, rel)] if root_name else [])
    for sup in load().get("superseded", []):
        if any(fnmatch.fnmatch(c, sup["glob"]) for c in cands):
            return sup["note"]
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


def _no_text_lines():
    from exam_engine.pipeline import reporter
    return {v["no_text"] for v in reporter.LABELS.values()}


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
    n = len(re.findall(r"^#{2,3} \S+ \d+\s*$", text, re.M))
    miss = sum(1 for ln in text.splitlines() if ln.strip() in _no_text_lines())
    return n, n - miss


def write_index(folder):
    """Write folder/INDEX.md listing every file below it (sorted, no clock, no absolute path); returns its path."""
    folder = os.path.abspath(folder)
    root_name = os.path.basename(folder)
    rels = []
    for dp, dns, fns in os.walk(folder):
        dns.sort()
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), folder).replace(os.sep, "/")
            if rel != INDEX_NAME:
                rels.append(rel)
    rels.sort()
    kinds = load()["kinds"]
    rows, per_kind, stat = [], {}, {"standard": 0, "legacy": 0, "superseded": 0, "unregistered": 0}
    for rel in rels:
        kind, status = classify(rel, root_name)
        cnt, wt = count_of(os.path.join(folder, rel), kind) if kind else (None, None)
        if status is None:
            status = "unregistered"
        stat[status] += 1
        if kind:
            per_kind[kind] = per_kind.get(kind, 0) + 1
        if status == "superseded":
            desc = superseded_note(rel, root_name)
        else:
            desc = kinds[kind]["description"] if kind else "not in config/report_kinds.json"
        c = "-" if cnt is None else (str(cnt) if wt is None else "%d (with_text %d/%d)" % (cnt, wt, cnt))
        rows.append("| %s | %s | %s | %s | %s |" % (rel, kind or "-", status, c, desc.replace("|", "/")))
    md = ["# Reports index: %s" % root_name, "",
          "Generated by `exam report-index` from config/report_kinds.json (docs/guide/report-kinds.md); do not edit.",
          "File name = `%s`. Old names (`report.md`, `answers.md`, ...) are `legacy`; replaced formats are `superseded`." %
          load()["pattern"], "",
          "| File | Kind | Status | Count | Description |", "| --- | --- | --- | --- | --- |"] + rows + ["", "## Totals", ""]
    md += ["- %s: %d" % (k, per_kind[k]) for k in sorted(per_kind)]
    md += ["- standard: %d" % stat["standard"], "- legacy: %d" % stat["legacy"],
           "- superseded: %d" % stat["superseded"], "- unregistered: %d" % stat["unregistered"],
           "- total: %d" % len(rels)]
    path = os.path.join(folder, INDEX_NAME)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    return path
