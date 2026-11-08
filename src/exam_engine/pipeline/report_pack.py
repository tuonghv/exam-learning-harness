"""Report pack (TASK-085 85.5): several stored plan runs -> one standard-named report folder, $0.

Per plan: report_build.build (solution-report, answer-sheet, metrics, result-data) + a run-log copy; for the
whole exam: a combined solution-report, answer-table and, with an answer key, score-vs-key and score-summary.
Kinds and names come from report_kinds (config/report_kinds.json); build_pack fails when the folder then
holds an unregistered file or lacks a registered kind. No model call, no network, no clock.
"""
import json
import os
import shutil

from exam_engine.pipeline import explain, report_build, report_kinds as rk, reporter, runlayout

LETTERS = "ABCD"


def _level(q):
    return str((q.get("uncertainty") or {}).get("level") or "") or "-"


def _answer(q):
    a = q.get("answer")
    return a.strip().upper() if isinstance(a, str) and a.strip().upper() in tuple(LETTERS) else None


def _tsv(path, header, rows):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join("\t".join(str(c) for c in r) for r in [header] + rows) + "\n")


def _rows(parts):
    """[(subject, printed|'-', q)] over all parts in plan order; printed = id + the exam's offset."""
    out = []
    for p in parts:
        off = explain.offset(p["exam"]) if p["exam"] else None
        for q in p["result"]["questions"]:
            try:
                printed = int(q["id"]) + off if off is not None else "-"
            except ValueError:
                printed = "-"
            out.append((p["result"]["exam"].get("subject") or p["name"], printed, q))
    return out


def _score_rows(rows, key):
    out = []
    for subject, printed, q in rows:
        k = key.get(str(printed))
        ours = _answer(q)
        res = "nokey" if k is None else ("declined" if ours is None else ("correct" if ours == k else "WRONG"))
        out.append({"subject": subject, "printed": printed, "key": k or "-", "ours": ours or "-", "result": res,
                    "status": q["verification_status"], "doubt": _level(q),
                    "flag": "unresolved" if q.get("unresolved") else ""})
    return out


def _summary(parts, scored):
    per = {}
    for p in parts:
        r = p["result"]
        s = r["exam"].get("subject") or p["name"]
        rows = [x for x in scored if x["subject"] == s]
        per[s] = {"n": len(rows), "ok": sum(x["result"] == "correct" for x in rows),
                  "wrong": sum(x["result"] == "WRONG" for x in rows),
                  "none": sum(x["result"] == "declined" for x in rows),
                  "cost": r["run"].get("cost_usd", 0), "calls": r["run"].get("calls", 0)}
    dvo = {}
    for x in scored:
        o = dvo.setdefault(x["result"], {})
        o[x["doubt"]] = o.get(x["doubt"], 0) + 1
    bad = [x for x in scored if x["result"] in ("WRONG", "declined")]
    return {"per": per, "total_correct": sum(v["ok"] for v in per.values()),
            "total": sum(v["n"] for v in per.values()), "not_correct": bad, "doubt_vs_outcome": dvo}


def _summary_md(sm, exam, run):
    t, n = sm["total_correct"], sm["total"]
    md = ["# Score summary: %s %s" % (exam, run), "", "## Score", "",
          "| Subject | Correct | Wrong | Declined | Cost USD | Calls |", "| --- | --- | --- | --- | --- | --- |"]
    for s, v in sm["per"].items():
        md.append("| %s | %d | %d | %d | %.4f | %d |" % (s, v["ok"], v["wrong"], v["none"], v["cost"], v["calls"]))
    md += ["| **Total** | **%d / %d (%.1f%%)** | %d | %d | **%.4f** | %d |" % (
        t, n, 100.0 * t / n if n else 0, sum(v["wrong"] for v in sm["per"].values()),
        sum(v["none"] for v in sm["per"].values()), sum(v["cost"] for v in sm["per"].values()),
        sum(v["calls"] for v in sm["per"].values())), "",
        "## Items that are not correct (%d)" % len(sm["not_correct"]), "",
        "| Printed | Subject | Key | Ours | Result | Status | Doubt | Flag |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for x in sm["not_correct"]:
        md.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            x["printed"], x["subject"], x["key"], x["ours"], x["result"], x["status"], x["doubt"], x["flag"]))
    md += ["", "## Doubt vs outcome", "", "| Outcome | Doubt: count |", "| --- | --- |"]
    for o in sorted(sm["doubt_vs_outcome"]):
        md.append("| %s | %s |" % (o, ", ".join("%s %d" % (k, v) for k, v in sorted(sm["doubt_vs_outcome"][o].items()))))
    return "\n".join(md) + "\n"


def _pdf_siblings(out_dir, lang):
    """A pdf next to every md whose registered kind lists pdf (registry flag pdf_with_md)."""
    kinds = rk.load()["kinds"]
    for f in sorted(os.listdir(out_dir)):
        p = rk.parse(f)
        if not p or p["ext"] != "md" or "pdf" not in kinds[p["kind"]]["ext"]:
            continue
        md = os.path.join(out_dir, f)
        pdf_path = os.path.splitext(md)[0] + ".pdf"
        if os.path.isfile(pdf_path):
            continue
        ok, note = reporter.md_to_pdf(md, pdf_path, lang=lang)
        if not ok:
            raise ValueError("PDF failed for %s: %s" % (f, note))


def build_pack(plan_dirs, out_dir, exam, run, key=None, pdf=True, engine_git=None, view="sheet", cmd="report-pack",
               extra=None):
    """Build the pack in out_dir; returns {files, expected, parts, correct, total}. ValueError on a bad plan, bad
    name part, unregistered extra file or a registered kind without a file."""
    run = run if run.startswith("run-") else "run-" + run
    if pdf and reporter.find_pdf_renderer() is None:
        raise ValueError("no PDF renderer found (Chrome, weasyprint, wkhtmltopdf); install one or use --no-pdf")
    os.makedirs(out_dir, exist_ok=True)
    if pdf:  # a pdf of an earlier run must not stand in for the md written now
        for f in os.listdir(out_dir):
            p = rk.parse(f)
            if p and p["ext"] == "pdf" and os.path.isfile(os.path.join(out_dir, f[:-4] + ".md")):
                os.remove(os.path.join(out_dir, f))
    keymap = explain.load_key(key) if key else None
    if key and not keymap:
        raise ValueError("no letter keys found in %s" % key)
    parts = []
    for pd in plan_dirs:
        info = report_build.build(pd, out_dir, view=view, pdf=pdf, exam_name=exam, run_name=run, engine_git=engine_git)
        nm = info["names"]
        src = os.path.join(pd, "run.log")
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(out_dir, rk.name(exam, nm["subject"], "run-log", run, "log")))
        parts.append({"result": info["result"], "metrics": info["metrics"], "exam": info["exam"],
                      "name": nm["subject"], "plan": pd})
    subjects = [p["name"] for p in parts]
    if len(set(subjects)) != len(subjects):
        raise ValueError("two plans have the same subject name: %s" % subjects)
    combined = reporter.build_combined_markdown([(p["result"], p["metrics"], p["exam"]) for p in parts],
                                                title="Exam report: %s (all subjects, %s)" % (exam, run))
    combined_md = os.path.join(out_dir, rk.name(exam, "all", "solution-report", run, "md"))
    with open(combined_md, "w", encoding="utf-8") as fh:
        fh.write(combined)
    rows = _rows(parts)
    _tsv(os.path.join(out_dir, rk.name(exam, "all", "answer-table", run, "tsv")),
         ["subject", "id", "printed", "answer", "status", "doubt", "error", "score"],
         [[s, q["id"], pr, _answer(q) or "-", q["verification_status"], _level(q),
           (q.get("error") or {}).get("cls") or "", (q.get("score") or {}).get("basis") or ""] for s, pr, q in rows])
    correct = total = None
    if keymap:
        scored = _score_rows(rows, keymap)
        _tsv(os.path.join(out_dir, rk.name(exam, "all", "score-vs-key", run, "tsv")),
             ["printed", "subject", "key", "ours", "result", "status", "doubt", "flag"],
             [[x[c] for c in ("printed", "subject", "key", "ours", "result", "status", "doubt", "flag")] for x in scored])
        sm = _summary(parts, scored)
        with open(os.path.join(out_dir, rk.name(exam, "all", "score-summary", run, "json")), "w", encoding="utf-8") as fh:
            json.dump(sm, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
        with open(os.path.join(out_dir, rk.name(exam, "all", "score-summary", run, "md")), "w", encoding="utf-8") as fh:
            fh.write(_summary_md(sm, exam, run))
        correct, total = sm["total_correct"], sm["total"]
    if pdf:
        _pdf_siblings(out_dir, reporter.learn_lang(parts[0]["result"]))
    want = rk.expected(exam, subjects, run, key=bool(keymap), pdf=pdf, view=view)
    have = sorted(f for f in os.listdir(out_dir) if f not in (rk.INDEX_NAME, runlayout.RUN_JSON))
    missing = [w for w in want if w not in have]
    stray = [h for h in have if rk.classify(h)[1] != "standard"]
    if missing or stray:
        raise ValueError("pack check failed: missing %s; unregistered %s" % (missing, stray))
    meta = dict(extra or {})
    if key:  # recorded so a later publish can reuse the key (repo-relative when inside the cwd)
        rel = os.path.relpath(os.path.abspath(key))
        meta.update(key=os.path.abspath(key) if rel.startswith("..") else rel.replace(os.sep, "/"),
                    key_sha256=runlayout._sha_file(key))
    runlayout.finish_report_run(out_dir, plan_dirs, view, engine_git, cmd, extra=meta or None)
    return {"files": have, "expected": want, "parts": parts, "correct": correct, "total": total}
