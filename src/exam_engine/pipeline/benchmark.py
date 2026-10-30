"""benchmark: run `engine.run` over evals/inputs with the key read only by the scorer (REQ-0009).

Every item is solved, checked and scored by the existing engine; this module only loops, shares one
cost budget, and writes summary.json + report.md with measured counts. Python 3.8 stdlib only.
"""
import datetime
import json
import os

from exam_engine import engine

CHECKS = {"key_match": "key match", "code_oracle": "code oracle"}


def discover(inputs, keys, subject=None):
    """[(subject, item name, input path, key path)] for input-NNN.md with a matching expected-NNN.md."""
    out = []
    for sub in sorted(os.listdir(inputs)):
        if subject and sub != subject:
            continue
        d = os.path.join(inputs, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.startswith("input-") and f.endswith(".md"):
                n = f[len("input-"):-len(".md")]
                key = os.path.join(keys, sub, "expected-%s.md" % n)
                if os.path.isfile(key):
                    out.append((sub, n, os.path.join(d, f), key))
    return out


def basis(q):
    """How the answer was checked: a code oracle, a key match, or a Claude review only."""
    kinds = [c.get("kind") for c in (q.get("checks") or []) if c.get("independent")]
    if "key_match" in kinds or (q.get("score") or {}).get("basis") == "official_key":
        return "key match"
    if kinds:
        return "code oracle"
    return "claude review only"


def item_row(sub, n, result):
    qs = []
    for q in result["questions"]:
        sc = q.get("score") or {}
        qs.append({"id": q["id"], "answer": q.get("answer"), "verdict": q.get("verification_status"),
                   "reason": q.get("status_reason"), "attempts": q.get("attempts"),
                   "points": sc.get("points"), "max": sc.get("max"), "basis": basis(q),
                   "findings": [f.get("code") for f in (q.get("qa_findings") or [])][:5]})
    return {"subject": sub, "item": n, "summary": result["summary"], "calls": result["run"]["calls"],
            "cost_usd": result["run"]["cost_usd"], "stopped": result["run"]["stopped"],
            "questions": qs}


def run_all(items, out_dir, cfg, llm, budget):
    """Rows for every item; stops before an item once the shared budget is spent."""
    rows, spent = [], 0.0
    for sub, n, path, key in items:
        if spent >= budget:
            rows.append({"subject": sub, "item": n, "skipped": "budget_reached"})
            continue
        c = dict(cfg, key=key, max_cost_usd=min(cfg["max_cost_usd"], budget - spent))
        try:
            result, _ = engine.run(path, os.path.join(out_dir, sub, n), c, llm)
        except (OSError, ValueError) as exc:
            rows.append({"subject": sub, "item": n, "skipped": "error: %s" % exc})
            continue
        if result is None:
            rows.append({"subject": sub, "item": n, "skipped": "invalid_input"})
            continue
        spent += result["run"]["cost_usd"]
        rows.append(item_row(sub, n, result))
    return rows


def summarize(rows, meta):
    per = {}
    for r in rows:
        if "summary" not in r:
            continue
        s = per.setdefault(r["subject"], {"items": 0, "pass": 0, "fail": 0, "uncertain": 0,
                                          "unresolved": 0, "points": 0, "max_points": 0})
        s["items"] += 1
        for k in ("pass", "fail", "uncertain", "unresolved", "points", "max_points"):
            s[k] += r["summary"].get(k) or 0
    tot = dict((k, sum(s[k] for s in per.values())) for k in
               ("items", "pass", "fail", "uncertain", "unresolved", "points", "max_points"))
    return dict(meta, per_subject=per, totals=tot, items=rows,
                calls=sum(r.get("calls", 0) for r in rows),
                cost_usd=round(sum(r.get("cost_usd", 0.0) for r in rows), 6),
                skipped=[[r["subject"], r["item"], r["skipped"]] for r in rows if "skipped" in r])


def report_md(sm):
    t = sm["totals"]
    L = ["# Benchmark report", "",
         "%s, model %s, prompts %s. Measured, not claimed: %d items, pass %d / fail %d / uncertain %d "
         "/ unresolved %d, %d calls, $%.2f." % (sm["date"], sm["model"], sm["prompt"], t["items"],
                                                 t["pass"], t["fail"], t["uncertain"],
                                                 t["unresolved"], sm["calls"], sm["cost_usd"]), "",
         "## Per subject", "", "| Subject | Items | Pass | Fail | Uncertain | Unresolved |", "|---|---|---|---|---|---|"]
    for k, s in sorted(sm["per_subject"].items()):
        L.append("| %s | %d | %d | %d | %d | %d |" % (k, s["items"], s["pass"], s["fail"],
                                                     s["uncertain"], s["unresolved"]))
    L += ["", "## Per question", "", "| Item | Q | Answer | Verdict | Points | Checked by | Attempts |",
          "|---|---|---|---|---|---|---|"]
    for r in sm["items"]:
        for q in r.get("questions", ()):
            L.append("| %s/%s | %s | %s | %s | %s/%s | %s | %s |" % (
                r["subject"], r["item"], q["id"], str(q["answer"])[:30].replace("|", "/"),
                q["verdict"], q["points"], q["max"], q["basis"], q["attempts"]))
    bad = [(r, q) for r in sm["items"] for q in r.get("questions", ()) if q["verdict"] == "FAIL"]
    if bad:
        L += ["", "## Failures (read the cause from evidence)", ""]
        for r, q in bad:
            L.append("- %s/%s Q%s: answer %s, reason %s, findings %s" % (
                r["subject"], r["item"], q["id"], q["answer"], q["reason"], q["findings"]))
    if sm["skipped"]:
        L += ["", "Skipped: " + ", ".join("%s/%s (%s)" % tuple(x) for x in sm["skipped"])]
    return "\n".join(L) + "\n"


def regression(prev, cur):
    """Subjects whose pass count fell versus the previous summary (both measured)."""
    return sorted(k for k, s in cur["per_subject"].items()
                  if k in prev.get("per_subject", {}) and s["pass"] < prev["per_subject"][k]["pass"])


def write(sm, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(sm, ensure_ascii=False, indent=2) + "\n")
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(report_md(sm))


def today():
    return datetime.date.today().isoformat()
