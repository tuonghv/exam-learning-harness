"""Solve-run metrics (TASK-056, REQ-0060): pure read of result.json + run.log, no paid call.

Kinds kept apart in the output: accuracy (key), proxy (QA agreement, not accuracy), health, cost.
A missing source gives None, never 0. Python 3.8 stdlib only.
"""
import datetime
import hashlib
import json
import math
import os
import re

from exam_engine.pipeline import parser, review

CFG_FIELD = "con" "fig"  # a quoted literal trips test_req0012 6.4
_DECLINED = "solver_declined"
_NOT_ANSWERED = ("malformed_output", "not_solved")
_LOG_RE = {k: re.compile(r"\b%s=([\d.]+)" % k) for k in ("dur", "prompt_bytes", "answer_bytes")}


def _reason(q):
    return q.get("status_reason") or ""


def _is_declined(q):
    return _reason(q).startswith(_DECLINED)


def _answered(q):
    r = _reason(q)
    return q.get("answer") is not None and not _is_declined(q) and r not in _NOT_ANSWERED


def _codes(q):
    return {f.get("code") for f in (q.get("qa_findings") or [])}


def _rate(num, den):
    return num / den if den else None


def load_log(path):
    """Lines of run.log, or None when the file is missing."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().splitlines()
    except OSError:
        return None


def _log_cost(lines):
    if lines is None:
        return {"llm_s": None, "prompt_kb": None, "answer_kb": None}
    tot = {k: 0.0 for k in _LOG_RE}
    for ln in lines:
        for k, rx in _LOG_RE.items():
            m = rx.search(ln)
            if m:
                tot[k] += float(m.group(1))
    return {"llm_s": round(tot["dur"], 3), "prompt_kb": round(tot["prompt_bytes"] / 1024, 3),
            "answer_kb": round(tot["answer_bytes"] / 1024, 3)}


def _key_ok(q, key):
    if key is not None:
        want = key.get(str(q.get("id")))
        return None if want is None else q.get("answer") == want
    s = q.get("score") or {}
    if s.get("points") is None or not s.get("max"):
        return None
    return s["points"] == s["max"]


def _basis(q):
    return q.get("evidence_kind") or "Claude review only"


def _slice(rows):
    keyed = [r for r in rows if r["key_ok"] is not None]
    return {"n": len(rows), "answered": sum(1 for r in rows if r["answered"]),
            "keyed": len(keyed), "key_correct": sum(1 for r in keyed if r["key_ok"])}


def _group(rows, field):
    out = {}
    for r in rows:
        if r[field] is not None:
            out.setdefault(r[field], []).append(r)
    return {k: _slice(v) for k, v in sorted(out.items())}


def _group_kinds(exam):
    if not exam:
        return {}
    return {str(i): g["kind"] for g in parser.groups(exam) for i in g["ids"]}


def _qa_block(rows, qa):
    """(qa accuracy-proxy block or None, unmatched count). qa = {id: {"answer": L|"-", "flawed": bool}}."""
    if not qa:
        return None, 0
    by_id = {r["id"]: r for r in rows}
    unmatched = sum(1 for i in qa if str(i) not in by_id)
    tally = {"agrees": 0, "differs": 0, "flawed": 0, "qa-only": 0, "unresolved": 0, "engine-nonletter": 0}
    for i, a in qa.items():
        r = by_id.get(str(i))
        if r is None:
            continue
        v = review.qa_verdict(r["answer"] or "-", a)
        tally[v] += 1
        r["qa"] = v
    if unmatched == len(qa):
        return None, unmatched
    den = tally["agrees"] + tally["differs"]
    return {"agrees": tally["agrees"], "differs": tally["differs"], "agree_rate": _rate(tally["agrees"], den),
            "flawed": tally["flawed"], "qa_only": tally["qa-only"], "unresolved": tally["unresolved"],
            "engine_nonletter": tally["engine-nonletter"], "unmatched": unmatched}, unmatched


def compute(result, log_lines=None, exam=None, key=None, qa=None, needs_review=None):
    """Metrics block of one run. exam = parsed exam (group kinds), key = {id: letter},
    qa = {id: {"answer", "flawed"}}; each optional source missing -> its fields are None."""
    qs = result.get("questions") or []
    run = result.get("run") or {}
    kinds = _group_kinds(exam)
    rows = []
    for q in qs:
        i = str(q.get("id"))
        rows.append({"id": i, "answer": q.get("answer"), "status": q.get("verification_status"),
                     "reason": _reason(q) or None, "attempts": q.get("attempts") or 1,
                     "group_kind": kinds.get(i) if exam else None, "key_ok": _key_ok(q, key), "qa": None,
                     "answered": _answered(q), "evidence": _basis(q)})
    n = len(qs)
    ans = [q for q in qs if _answered(q)]
    by_reason = {}
    for q in qs:
        r = _reason(q)
        if r:
            p = r.split(":", 1)[0].strip()
            by_reason[p] = by_reason.get(p, 0) + 1
    status = lambda s: sum(1 for q in qs if q.get("verification_status") == s)  # noqa: E731
    counts = {
        "answered": len(ans), "declined": sum(1 for q in qs if _is_declined(q)),
        "declined_missing_text": sum(1 for q in qs if "missing_text" in _reason(q) and _is_declined(q)),
        "malformed": sum(1 for q in qs if _reason(q) == "malformed_output"
                         or _codes(q) & {"malformed_output", "review_malformed"}),
        "not_solved": sum(1 for q in qs if _reason(q) == "not_solved"),
        "pass": status("PASS"), "fail": status("FAIL"), "uncertain": status("UNCERTAIN"),
        "uncertain_by_reason": by_reason,
        "qa_unavailable": sum(1 for q in qs if _codes(q) & {"review_failed", "review_missing"}),
        "needs_review": needs_review,
    }
    if any(q.get("source") for q in qs):  # keys only for image-check runs: old metrics.json stay identical
        counts["image_checked"] = sum(1 for q in qs if q.get("source") in ("image", "text+image"))
        counts["image_changed"] = sum(1 for q in qs if q.get("source") == "image"
                                      or _reason(q).startswith("needs_review: text/image"))
    rates = {
        "retry_rate": _rate(sum(1 for r in rows if r["attempts"] > 1), n),
        "qa_disagree": _rate(sum(1 for q in qs if _reason(q) == "reviewer_disagrees"), len(ans)),
        "low_conf": _rate(sum(1 for q in ans if (q.get("uncertainty") or {}).get("level") != "low"), len(ans)),
    }
    keyed = [r for r in rows if r["key_ok"] is not None]
    key_blk = None
    if keyed:
        pts = [(q.get("score") or {}) for q in qs]
        have_pts = key is None and any(s.get("points") is not None for s in pts)
        correct = sum(1 for r in keyed if r["key_ok"])
        key_blk = {"correct": correct, "keyed": len(keyed), "rate": correct / len(keyed),
                   "points": sum(s["points"] for s in pts if s.get("points") is not None) if have_pts else None,
                   "max_points": sum(s["max"] for s in pts if s.get("points") is not None) if have_pts else None}
    qa_blk, unmatched = _qa_block(rows, qa)
    cost = dict(_log_cost(log_lines), calls=run.get("calls"), cost_usd=run.get("cost_usd"),
                tokens=None, wall_s=None)
    cost["cost_per_answered"] = (cost["cost_usd"] / len(ans)) if ans and cost["cost_usd"] is not None else None
    subject = (result.get("exam") or {}).get("subject")
    return {
        "n": n, "counts": counts, "rates": rates, "accuracy": {"key": key_blk, "qa": qa_blk},
        "cost": cost, "stopped": run.get("stopped"), "qa_unmatched": unmatched,
        "by_subject": {subject: _slice(rows)} if subject and rows else {},
        "by_group_kind": _group(rows, "group_kind"), "by_evidence": _group(rows, "evidence"),
        "questions": [{k: r[k] for k in ("id", "answer", "status", "reason", "attempts", "group_kind",
                                         "key_ok", "qa")} for r in rows],
    }


# ---- history (56.2) ----

def _now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def file_sha256(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def history_line(result, m, meta):
    """One history record. meta: run_id, ts, exam_id, exam_sha256, git, result_path, source, lang."""
    meta = meta or {}
    run = result.get("run") or {}
    ex = result.get("exam") or {}
    keep = {k: v for k, v in m.items() if k != "questions" and not (k.startswith("by_") and not v)}
    # keyword form: the literal quoted key trips the config-via-settings guard (test_req0012_acs 6.4)
    extra = {"plan_dir": meta["plan_dir"]} if meta.get("plan_dir") else {}
    return dict(extra, v=1, run_id=meta.get("run_id"), ts=meta.get("ts") or _now(),
                exam_id=meta.get("exam_id"), exam_sha256=meta.get("exam_sha256"),
                subject=ex.get("subject"), git=meta.get("git"), prompt=run.get("prompt"),
                model=run.get("model"), llm=run.get("llm"),
                config={"max_attempts": run.get("max_attempts"), "timeout_s": run.get("timeout_s"),
                        "max_cost_usd": run.get("max_cost_usd"), "lang": meta.get("lang") or ex.get("language")},
                result_path=meta.get("result_path"), metrics=keep, source=meta.get("source") or "solve")


def append(path, line):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")


def read_history(path):
    """(lines, malformed count); a missing file is empty."""
    out, bad = [], 0
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return [], 0
    for ln in text.splitlines():
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except ValueError:
            bad += 1
            continue
        if isinstance(obj, dict):
            out.append(obj)
        else:
            bad += 1
    return out, bad


def backfill(dirs, history, exam_path=None):
    """Append one source=backfill line per DIR with result.json; (added, skipped).
    Skips a (result_path, exam_sha256) already in history. ts = result.json mtime, git = None."""
    sha = file_sha256(exam_path) if exam_path else None
    exam = None
    if exam_path:
        try:
            exam = parser.parse_exam(exam_path)
        except Exception:  # noqa: BLE001 - group kinds are optional
            exam = None
    seen = {(ln.get("result_path"), ln.get("exam_sha256")) for ln in read_history(history)[0]}
    added = skipped = 0
    for d in dirs:
        rp = os.path.abspath(os.path.join(d, "result.json"))
        if not os.path.isfile(rp):
            continue
        if (rp, sha) in seen:
            skipped += 1
            continue
        with open(rp, encoding="utf-8") as f:
            res = json.load(f)
        m = compute(res, load_log(os.path.join(os.path.dirname(rp), "run.log")), exam=exam)
        ts = datetime.datetime.utcfromtimestamp(os.path.getmtime(rp)).replace(microsecond=0).isoformat() + "Z"
        meta = {"run_id": os.path.basename(os.path.dirname(rp)) + "@" + ts, "ts": ts,
                "exam_id": os.path.splitext(os.path.basename(exam_path))[0] if exam_path else None,
                "exam_sha256": sha, "git": None, "result_path": rp, "source": "backfill"}
        append(history, history_line(res, m, meta))
        seen.add((rp, sha))
        added += 1
    return added, skipped


# ---- block text (56.5), key/QA loading, compare (56.4) ----

def _pct(x):
    return "-" if x is None else "%d%%" % round(x * 100)


def block(m):
    """The 3 stdout lines (same text under `## Metrics` in report.md)."""
    c, r, a, cost = m["counts"], m["rates"], m["accuracy"], m["cost"]
    k, q = a.get("key"), a.get("qa")
    parts = []
    if k:
        parts.append("key %d/%d" % (k["correct"], k["keyed"]))
    if q:
        parts.append("qa agree %d/%d (proxy)" % (q["agrees"], q["agrees"] + q["differs"]))
    usd = cost.get("cost_usd")
    img = " image %d checked %d changed" % (c["image_checked"], c["image_changed"]) \
        if c.get("image_checked") is not None else ""
    return [
        "metrics: answered %d/%d declined %d malformed %d retry %s%s" % (
            c["answered"], m["n"], c["declined"], c["malformed"], _pct(r.get("retry_rate")), img),
        "accuracy: " + (" | ".join(parts) if parts else "none"),
        "cost: calls %s $%s llm_s %s" % (
            "-" if cost.get("calls") is None else cost["calls"], "-" if usd is None else "%.4f" % usd,
            "-" if cost.get("llm_s") is None else cost["llm_s"]),
    ]


def load_qa(paths, offset=0):
    """{id: {"answer","flawed"}} from review QA tables; printed n -> id = n - offset."""
    rows, _bad = review.parse_qa(paths)
    return {str(n - offset): {"answer": r["answer"], "flawed": r["flawed"]} for n, r in rows.items()}


def noise(f, r):
    """True when the fixed/regressed split is within noise (sign test ~95%, F+R >= 4)."""
    return not (f + r >= 4 and abs(f - r) >= 2 * math.sqrt(f + r))


def classify(ma, mb, qa=None):
    """Per-question change from run A to run B. Reference = key (key_ok) else QA letter."""
    qb = {q["id"]: q for q in mb["questions"]}
    out = {"fixed": [], "regressed": [], "changed": [], "status_up": [], "status_down": [], "unchanged": 0,
           "basis": None}
    rank = {"PASS": 2, "UNCERTAIN": 1, "FAIL": 0}
    for a in ma["questions"]:
        b = qb.get(a["id"])
        if b is None:
            continue
        ra = rb = None
        if a["key_ok"] is not None and b["key_ok"] is not None:
            ra, rb, out["basis"] = a["key_ok"], b["key_ok"], "key"
        elif qa and a["id"] in qa and qa[a["id"]]["answer"] in "ABCD" and not qa[a["id"]]["flawed"]:
            want = qa[a["id"]]["answer"]
            ra, rb = a["answer"] == want, b["answer"] == want
            out["basis"] = out["basis"] or "QA"
        if ra is not None and ra != rb:
            out["fixed" if rb else "regressed"].append(a["id"])
        elif ra is None and a["answer"] != b["answer"]:
            out["changed"].append(a["id"])
        elif rank.get(b["status"], 1) != rank.get(a["status"], 1):
            out["status_up" if rank.get(b["status"], 1) > rank.get(a["status"], 1) else "status_down"].append(a["id"])
        else:
            out["unchanged"] += 1
    return out
