"""Report pack (TASK-085 85.5): several stored plan runs -> one standard-named report folder, $0.

Per plan: report_build.build (solution-report, answer-sheet, public report); no json/log files (provenance is run.json); for the
whole exam: a combined solution-report, answer-table and, with an answer key, score-vs-key and score-summary.
Kinds and names come from report_kinds (config/report_kinds.json); build_pack fails when the folder then
holds an unregistered file or lacks a registered kind. No model call, no network, no clock.
"""
import os
import sys

from exam_engine.pipeline import explain, planrun, report_build, report_kinds as rk, reporter, runlayout

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


def _why(q):
    """One line of the engine's reasoning: first 3 solution steps, else the explanation (as review._engine_line)."""
    steps = [s for s in (q.get("solution") or []) if str(s).strip()][:3]
    return (" / ".join(reporter._one_line(s) for s in steps) or reporter._one_line(q.get("explanation")))[:300]


def _score_rows(rows, key, issues=()):
    """Rows scored against key; a printed number named in issues is `keybad` (never guessed, not scorable)."""
    bad = {str(i["printed"]) for i in issues}
    out = []
    for subject, printed, q in rows:
        k = key.get(str(printed))
        ours = _answer(q)
        if k is None and str(printed) in bad:
            toks = [i["token"] for i in issues if str(i["printed"]) == str(printed) and i["token"]]
            res, k = "keybad", "?" + "/".join(toks)
        else:
            res = "nokey" if k is None else ("declined" if ours is None else ("correct" if ours == k else "WRONG"))
        a = q.get("answer")
        out.append({"subject": subject, "printed": printed, "key": k or "-", "ours": ours or "-", "result": res,
                    "status": q["verification_status"], "doubt": _level(q),
                    "flag": "unresolved" if q.get("unresolved") else "",
                    "answer_text": "" if a is None else reporter._one_line(a)[:300], "why": _why(q)})
    return out


SCORABLE = ("correct", "WRONG", "declined")


def _pct(a, b):
    return 100.0 * a / b if b else 0.0


def _summary(parts, scored, issues=()):
    per = {}
    for p in parts:
        r = p["result"]
        s = r["exam"].get("subject") or p["name"]
        rows = [x for x in scored if x["subject"] == s]
        per[s] = {"n": len(rows), "ok": sum(x["result"] == "correct" for x in rows),
                  "wrong": sum(x["result"] == "WRONG" for x in rows),
                  "none": sum(x["result"] == "declined" for x in rows),
                  "scorable": sum(x["result"] in SCORABLE for x in rows),
                  "nokey": sum(x["result"] == "nokey" for x in rows),
                  "keybad": sum(x["result"] == "keybad" for x in rows),
                  "cost": r["run"].get("cost_usd", 0), "calls": r["run"].get("calls", 0)}
    dvo, cal = {}, {}
    for x in scored:
        o = dvo.setdefault(x["result"], {})
        o[x["doubt"]] = o.get(x["doubt"], 0) + 1
        if x["result"] in SCORABLE:
            c = cal.setdefault(x["doubt"], {"n": 0, "correct": 0, "wrong": 0, "declined": 0})
            c["n"] += 1
            c[{"correct": "correct", "WRONG": "wrong", "declined": "declined"}[x["result"]]] += 1
    for c in cal.values():
        c["accuracy"] = round(_pct(c["correct"], c["n"]), 1)
    bad = [x for x in scored if x["result"] in ("WRONG", "declined")]
    return {"per": per, "total_correct": sum(v["ok"] for v in per.values()),
            "total": sum(v["scorable"] for v in per.values()), "n_items": sum(v["n"] for v in per.values()),
            "not_correct": bad, "doubt_vs_outcome": dvo, "calibration": cal, "scored": scored,
            "key_issues": list(issues)}


def _cell(v):
    return str(v).replace("|", "/").replace("\n", " ")


def _summary_md(sm, exam, run):
    t, n = sm["total_correct"], sm["total"]
    md = ["# Score summary: %s %s" % (exam, run), "", "## Score", "",
          "Accuracy = correct / scorable (correct + wrong + declined); items without a usable key are excluded.", "",
          "| Subject | Correct | Wrong | Declined | Scorable | Accuracy % | No key | Bad key | Cost USD | Calls |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s, v in sm["per"].items():
        md.append("| %s | %d | %d | %d | %d | %.1f | %d | %d | %.4f | %d |" % (
            s, v["ok"], v["wrong"], v["none"], v["scorable"], _pct(v["ok"], v["scorable"]), v["nokey"], v["keybad"],
            v["cost"], v["calls"]))
    pv = sm["per"].values()
    md += ["| **Total** | **%d / %d** | %d | %d | %d | **%.1f** | %d | %d | **%.4f** | %d |" % (
        t, n, sum(v["wrong"] for v in pv), sum(v["none"] for v in pv), n, _pct(t, n),
        sum(v["nokey"] for v in pv), sum(v["keybad"] for v in pv), sum(v["cost"] for v in pv),
        sum(v["calls"] for v in pv)), "",
        "## Per question", "",
        "| Printed | Subject | Key | Ours | Result | Doubt | Status |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for x in sm["scored"]:
        md.append("| %s | %s | %s | %s | %s | %s | %s |" % tuple(
            _cell(x[c]) for c in ("printed", "subject", "key", "ours", "result", "doubt", "status")))
    md += ["", "## Calibration", "", "| Doubt | n | Correct | Wrong | Declined | Accuracy % |",
           "| --- | --- | --- | --- | --- | --- |"]
    for lv, c in sorted(sm["calibration"].items()):
        md.append("| %s | %d | %d | %d | %d | %.1f |" % (lv, c["n"], c["correct"], c["wrong"], c["declined"], c["accuracy"]))
    md += ["", "## Mismatches (%d)" % len(sm["not_correct"]), "",
           "| Printed | Subject | Key | Ours | Doubt | Status | Why |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for x in sm["not_correct"]:
        md.append("| %s | %s | %s | %s | %s | %s | %s |" % tuple(
            _cell(x[c]) for c in ("printed", "subject", "key", "ours", "doubt", "status", "why")))
    md += ["", "## Key issues", ""]
    md += ["- %s: %s%s" % (i["printed"], i["kind"], " " + i["token"] if i["token"] else "")
           for i in sm["key_issues"]] or ["none"]
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
               extra=None, overlays=None):
    """overlays: entries from overlay.resolve (validated by the caller before any write); each is applied in
    memory to the plan of its subject and recorded in run.json `overlays`.
    Build the pack in out_dir; returns {files, expected, parts, correct, total}. ValueError on a bad plan, bad
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
    keymap, key_issues = explain.parse_key(key) if key else (None, [])
    if key and not keymap:
        raise ValueError("no letter keys found in %s" % key)
    parts = []
    for pd in plan_dirs:
        subj = ((planrun.load(pd)["result"] or {}).get("exam") or {}).get("subject")
        mine = [o for o in overlays or [] if o["subject"] == subj]
        info = report_build.build(pd, out_dir, view=view, pdf=False, exam_name=exam, run_name=run, engine_git=engine_git,
                                  overlay=mine[0] if mine else None)
        nm = info["names"]
        for kind, spec in rk.load()["kinds"].items():  # a pack keeps only the `all` file of these kinds
            if spec.get("pack_subject") is False:
                for ext in spec["ext"]:
                    try:
                        os.remove(os.path.join(out_dir, rk.name(exam, nm["subject"], kind, run, ext)))
                    except (OSError, ValueError):
                        pass
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
    pub_all = os.path.join(out_dir, rk.name(exam, "all", "solution_public-report", run, "md"))
    with open(pub_all, "w", encoding="utf-8") as fh:
        fh.write(reporter.build_public_combined([(p["result"], p["exam"]) for p in parts],
                                                "%s (%s)" % (exam, run)))
    rows = _rows(parts)
    _tsv(os.path.join(out_dir, rk.name(exam, "all", "answer-table", run, "tsv")),
         ["subject", "id", "printed", "answer", "status", "doubt", "error", "score"],
         [[s, q["id"], pr, _answer(q) or "-", q["verification_status"], _level(q),
           (q.get("error") or {}).get("cls") or "", (q.get("score") or {}).get("basis") or ""] for s, pr, q in rows])
    correct = total = None
    if keymap:
        for i in key_issues:
            print("key issue: %s %s %s" % (i["printed"], i["kind"], i["token"]), file=sys.stderr)
        scored = _score_rows(rows, keymap, key_issues)
        _tsv(os.path.join(out_dir, rk.name(exam, "all", "score-vs-key", run, "tsv")),
             ["printed", "subject", "key", "ours", "result", "status", "doubt", "flag"],
             [[x[c] for c in ("printed", "subject", "key", "ours", "result", "status", "doubt", "flag")] for x in scored])
        sm = _summary(parts, scored, key_issues)
        with open(os.path.join(out_dir, rk.name(exam, "all", "score-summary", run, "md")), "w", encoding="utf-8") as fh:
            fh.write(_summary_md(sm, exam, run))
        correct, total = sm["total_correct"], sm["total"]
    if pdf:
        _pdf_siblings(out_dir, reporter.learn_lang(parts[0]["result"]))
    want = rk.expected(exam, subjects, run, key=bool(keymap), pdf=pdf, view=view, pack=True)
    have = sorted(f for f in os.listdir(out_dir) if f not in (rk.INDEX_NAME, runlayout.RUN_JSON))
    missing = [w for w in want if w not in have]
    stray = [h for h in have if rk.classify(h)[1] != "standard"]
    if missing or stray:
        raise ValueError("pack check failed: missing %s; unregistered %s" % (missing, stray))
    meta = dict(extra or {})
    if total is not None:  # the score-summary json is retired; run-list reads this
        meta["score"] = {"total_correct": correct, "total": total}
    if overlays:
        meta["overlays"] = list(overlays)
    if key:  # recorded so a later publish can reuse the key (repo-relative when inside the cwd)
        rel = os.path.relpath(os.path.abspath(key))
        meta.update(key=os.path.abspath(key) if rel.startswith("..") else rel.replace(os.sep, "/"),
                    key_sha256=runlayout._sha_file(key), key_issues=key_issues)
    runlayout.finish_report_run(out_dir, plan_dirs, view, engine_git, cmd, extra=meta or None)
    return {"files": have, "expected": want, "parts": parts, "correct": correct, "total": total}
