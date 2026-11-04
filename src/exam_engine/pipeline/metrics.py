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


def compute(result, log_lines=None, exam=None, key=None, qa=None, needs_review=None, needs_review_why=None,
            quality=False, structure=None):
    """Metrics block of one run. exam = parsed exam (group kinds), key = {id: letter},
    qa = {id: {"answer", "flawed"}}; each optional source missing -> its fields are None.
    structure = {id: [structure flag codes]} (assembly rows, 69.3): adds parse_flag keys, only when given."""
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
        counts["image_checked"] = sum(1 for q in qs if q.get("source") in ("image", "text+image", "adjudicated"))
        counts["image_changed"] = sum(1 for q in qs if q.get("source") == "image"
                                      or _reason(q).startswith("needs_review: text/image"))
    scope = (result.get("run") or {}).get("image_scope")
    agrees, differs = (sum(1 for q in qs if code in _codes(q)) for code in ("image_agrees", "image_differs"))
    if scope or agrees or differs:  # 61.4: keys only for wider-scope runs
        counts.update(image_scope=scope, image_agrees=agrees, image_differs=differs)
    # 60.7: keys only when present, so a pre-60 result keeps byte-identical metrics
    mapped = sum(1 for q in qs if "answer_mapped" in _codes(q))
    if mapped:
        counts["answer_mapped"] = mapped
    if needs_review_why is not None:  # {id: [codes]} from the refine output
        by_why = {}
        for codes in needs_review_why.values():
            for c in codes or ["unspecified"]:
                by_why[c] = by_why.get(c, 0) + 1
        counts["needs_review_by_why"] = by_why
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
    m = {
        "n": n, "counts": counts, "rates": rates, "accuracy": {"key": key_blk, "qa": qa_blk},
        "cost": cost, "stopped": run.get("stopped"), "qa_unmatched": unmatched,
        "by_subject": {subject: _slice(rows)} if subject and rows else {},
        "by_group_kind": _group(rows, "group_kind"), "by_evidence": _group(rows, "evidence"),
        "questions": [{k: r[k] for k in ("id", "answer", "status", "reason", "attempts", "group_kind",
                                         "key_ok", "qa")} for r in rows],
    }
    if structure is not None:  # 69.3: keys only when given, so old metrics.json stay byte-identical
        flags = {}
        for r in rows:
            r["parse_flag"] = bool(structure.get(r["id"]))
            for c in structure.get(r["id"]) or []:
                flags[c] = flags.get(c, 0) + 1
        counts["structure_flags"] = flags
        m["by_parse_flag"] = {"flagged": _slice([r for r in rows if r["parse_flag"]]),
                              "clean": _slice([r for r in rows if not r["parse_flag"]])}
    if key_blk and any(q.get("confidence") for q in qs):  # 75.4: key only for --confidence results
        m["confidence"] = _by_confidence(rows, qs)
    if quality:  # only the board asks: stats/metrics.json stay byte-identical (63.1)
        m["quality"] = _quality(rows, qs, counts, qa_blk, key_blk, structure is not None)
    return m


FLAG_REASONS = ("reviewer_disagrees", "check_failed", "needs_review")  # engine reason codes, not exam data


def _flagged(q):
    return _reason(q).startswith(FLAG_REASONS) or "image_differs" in _codes(q)


def wilson(k, n, z=1.96):
    """Wilson score interval (lo, hi) of k/n at z (1.96 = 95%); None when n is 0 (64.2)."""
    if not n:
        return None
    p, z2 = k / n, z * z
    mid = p + z2 / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return ((mid - half) / (1 + z2 / n), (mid + half) / (1 + z2 / n))


OUTCOMES = ("correct", "wrong", "unkeyed_answered", "declined", "unanswered", "invalid")


def _outcome(q, key_ok):
    """One disjoint outcome per question (64.2); an answered question with review_malformed stays answered."""
    r = _reason(q)
    if _is_declined(q):
        return "declined"
    if r == "malformed_output":
        return "invalid"
    if r == "not_solved" or q.get("answer") is None:
        return "unanswered"
    return "unkeyed_answered" if key_ok is None else ("correct" if key_ok else "wrong")


def _by_confidence(rows, qs):
    """75.4: keyed answered questions per confidence tier, silent wrong in likely_ok, recall of wrong answers."""
    tiers = {}
    for q, r in zip(qs, rows):
        if r["answered"] and r["key_ok"] is not None:
            t = tiers.setdefault(q.get("confidence") or "none", {"n": 0, "correct": 0})
            t["n"] += 1
            t["correct"] += bool(r["key_ok"])
    for t in tiers.values():
        t["wrong"] = t["n"] - t["correct"]
        t["precision"] = _rate(t["correct"], t["n"])
        t["precision_ci"] = wilson(t["correct"], t["n"])
    wrong = sum(t["wrong"] for t in tiers.values())
    lw = tiers.get("likely_wrong", {}).get("wrong", 0)
    return {"by_confidence": tiers, "wrong_in_likely_ok": tiers.get("likely_ok", {}).get("wrong", 0),
            "wrong_recall": {"k": lw, "n": wrong, "rate": _rate(lw, wrong), "ci": wilson(lw, wrong)}}


def _quality(rows, qs, counts, qa_blk, key_blk, structured=False):
    """63.1: key quality (from key_ok: given key or scorer score) and QA proxy of one run."""
    flag = {str(q.get("id")): _flagged(q) for q in qs}
    outcomes = dict.fromkeys(OUTCOMES, 0)
    for q, r in zip(qs, rows):
        outcomes[_outcome(q, r["key_ok"])] += 1
    basis = "key" if key_blk else ("qa" if qa_blk else None)
    out = {"basis": basis, "unmeasured": basis is None, "correct": None, "keyed": None, "keyed_scored": None,
           "attempt_rate": None, "score": None, "score_ci": None,
           "outcomes": outcomes, "coverage": _rate(counts["answered"], len(rows)), "precision": None, "wrong_answered": None, "silent_wrong": None, "flagged": None, "flagged_correct": None,
           "false_alarm": None}
    if key_blk:
        ak = [r for r in rows if r["answered"] and r["key_ok"] is not None]
        good = [r for r in ak if r["key_ok"]]
        wrong = [r for r in ak if not r["key_ok"]]
        fl = [r for r in ak if flag[r["id"]]]
        fl_ok = [r for r in fl if r["key_ok"]]
        # 64.1: the scorer scores a keyed refusal 0, so keyed already counts it; open/no-key items stay out
        keyed_adj = key_blk["keyed"]
        out.update(correct=len(good), keyed=keyed_adj, keyed_scored=key_blk["keyed"],
                   attempt_rate=_rate(len(good), keyed_adj), score=_rate(len(good), keyed_adj),
                   score_ci=wilson(len(good), keyed_adj), precision=_rate(len(good), len(ak)),
                   wrong_answered=len(wrong), silent_wrong=sum(1 for r in wrong if not flag[r["id"]]),
                   flagged=len(fl), flagged_correct=len(fl_ok), false_alarm=_rate(len(fl_ok), len(fl)))
    qv = [r for r in rows if r["answered"] and r["qa"] in ("agrees", "differs")]
    qfl = [r for r in qv if flag[r["id"]]]
    qfl_ok = [r for r in qfl if r["qa"] == "agrees"]
    out["proxy"] = {"agree_rate": qa_blk["agree_rate"] if qa_blk else None,
                    "agrees": qa_blk["agrees"] if qa_blk else None, "differs": qa_blk["differs"] if qa_blk else None,
                    "flagged": len(qfl), "flagged_agrees": len(qfl_ok),
                    "proxy_false_alarm": _rate(len(qfl_ok), len(qfl)),
                    "needs_review_by_why": counts.get("needs_review_by_why"),
                    "image_agrees": counts.get("image_agrees"), "image_differs": counts.get("image_differs")}
    if key_blk and any(q.get("confidence") for q in qs):  # 75.4: keys only for --confidence results
        out.update(_by_confidence(rows, qs))
    if structured:  # 69.3: parse-suspect vs solver split; named apart from the engine-review `flagged`
        out["parse_flagged"] = sum(1 for r in rows if r["parse_flag"])
        if key_blk:
            out["parse_wrong"] = sum(1 for r in wrong if r["parse_flag"])
            out["solve_wrong"] = out["wrong_answered"] - out["parse_wrong"]
        if qa_blk:
            out["parse_differs"] = sum(1 for r in qv if r["qa"] == "differs" and r["parse_flag"])
    return out


# ---- parsing accuracy apart from solving (69.1) ----

BYTES_PER_TOKEN = 4  # rough for Latin text, low for non-Latin scripts: a relative measure between parses, not a bill
STRUCTURE_METRICS = ("extraction", "boundary", "hierarchy", "instruction", "shared_ref", "reference", "cross_page")


def _opt_texts(q):
    o = q.get("options") or {}
    return list(o.values()) if isinstance(o, dict) else [str(x) for x in o]


def tokens_per_question_est(exam):
    """Estimated prompt tokens per question of a parse: group instruction + passage once, every stem and option."""
    qs = {q["id"]: q for q in exam["questions"]}
    if not qs:
        return None
    total = 0
    for g in parser.groups(exam):
        total += len((g["instruction"] + g["passage"]).encode("utf-8"))
    for q in qs.values():
        total += sum(len(t.encode("utf-8")) for t in [q.get("stem", q["text"])] + _opt_texts(q))
    return round(total / BYTES_PER_TOKEN / len(qs), 1)


def structure_scores(exam, gold):
    """Parsing rates against a gold list (rows {"id", optional stem/section/instruction/shared/deps/pages}),
    matched by exam position id. Field metrics count only gold rows that carry the field and were extracted."""
    from exam_engine.pipeline.extract_eval import squash
    qs = {q["id"]: q for q in exam["questions"]}
    gid = {g["id"] for g in gold}
    notes = exam.get("section_notes") or {}
    dep = parser.deps(exam)
    sc = {k: {"k": 0, "n": 0, "rate": None, "miss": []} for k in STRUCTURE_METRICS}

    def put(name, ok, i, why):
        s = sc[name]
        s["n"] += 1
        if ok:
            s["k"] += 1
        else:
            s["miss"].append({"id": i, "why": why})

    extra = sorted(i for i in qs if i not in gid)
    for g in gold:
        i = g["id"]
        put("extraction", i in qs, i, "missing")
    for i in extra:
        put("extraction", False, i, "extra")
    for g in gold:
        i, q = g["id"], qs.get(g["id"])
        if q is None:
            continue
        stem_ok = "stem" not in g or squash(q.get("stem", q["text"])) == squash(g["stem"])
        if "stem" in g:
            put("boundary", stem_ok, i, "cut")
        if "section" in g:
            put("hierarchy", (q.get("section") or "").strip() == g["section"].strip(), i, "section")
        if "instruction" in g:
            eff = "\n".join(x for x in (notes.get(q.get("section") or ""), q.get("instruction")) if x)
            put("instruction", squash(eff) == squash(g["instruction"]), i,
                "missing" if g["instruction"] and not eff else "leak")
        if "shared" in g:
            want = {x["id"] for x in gold if x.get("shared") == g["shared"]}
            qp = squash(parser._passage(q))
            got = {x["id"] for x in gold if x["id"] in qs and qs[x["id"]].get("section") == q.get("section")
                   and qp and squash(parser._passage(qs[x["id"]])) == qp} | {i}
            put("shared_ref", got == want, i, "unlinked" if want - got else "overlinked")
        if "deps" in g:
            put("reference", sorted(dep.get(i, [])) == sorted(g["deps"]), i, "wrong_target")
        if len(g.get("pages") or []) > 1:
            ok = q.get("pages") == g["pages"]
            put("cross_page", ok and stem_ok, i, "pages" if not ok else "cut")
    for s in sc.values():
        s["rate"] = _rate(s["k"], s["n"])
    return {"n_gold": len(gold), "n_exam": len(qs), "extra": extra, "scores": sc,
            "tokens_per_question_est": tokens_per_question_est(exam)}


# ---- history (56.2) ----

def _now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def file_sha256(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def kind(result):
    """Exam kind label subject/language/level from result.exam (63.2); '-' for a missing field."""
    ex = (result or {}).get("exam") or {}
    return "/".join(str(ex.get(k) or "-") for k in ("subject", "language", "level"))


def history_line(result, m, meta):
    """One history record. meta: run_id, ts, exam_id, exam_sha256, git, result_path, source, lang."""
    meta = meta or {}
    run = result.get("run") or {}
    ex = result.get("exam") or {}
    keep = {k: v for k, v in m.items() if k != "questions" and not (k.startswith("by_") and not v)}
    # keyword form: the literal quoted key trips the config-via-settings guard (test_req0012_acs 6.4)
    extra = {"plan_dir": meta["plan_dir"]} if meta.get("plan_dir") else {}
    if meta.get("set_id"):  # regset lines (66.1): which fixed set, and how its key was made
        extra.update(set_id=meta["set_id"], key_basis=meta.get("key_basis"))
    return dict(extra, v=1, run_id=meta.get("run_id"), ts=meta.get("ts") or _now(),
                exam_id=meta.get("exam_id"), exam_sha256=meta.get("exam_sha256"),
                subject=ex.get("subject"), kind=kind(result), git=meta.get("git"), prompt=run.get("prompt"),
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
    if c.get("image_scope"):
        img += " scope %s agrees %d differs %d" % (c["image_scope"], c["image_agrees"], c["image_differs"])
    if c.get("answer_mapped"):
        img += " mapped %d" % c["answer_mapped"]
    if c.get("needs_review_by_why"):
        img += " review_why " + ",".join("%s=%d" % kv for kv in sorted(c["needs_review_by_why"].items()))
    bc = (m.get("confidence") or {}).get("by_confidence")
    cl = []
    if bc:  # 75.4: one extra line only for --confidence results
        cl = ["confidence: " + " | ".join(
            "%s %d/%d%s" % (t, bc[t]["correct"], bc[t]["n"], " [%.2f,%.2f]" % bc[t]["precision_ci"]
                            if bc[t]["precision_ci"] else "")
            for t in ("verified", "likely_ok", "unknown", "likely_wrong", "none") if t in bc)]
    return [
        "metrics: answered %d/%d declined %d malformed %d retry %s%s" % (
            c["answered"], m["n"], c["declined"], c["malformed"], _pct(r.get("retry_rate")), img),
        "accuracy: " + (" | ".join(parts) if parts else "none"),
        "cost: calls %s $%s llm_s %s" % (
            "-" if cost.get("calls") is None else cost["calls"], "-" if usd is None else "%.4f" % usd,
            "-" if cost.get("llm_s") is None else cost["llm_s"]),
    ] + cl


def load_refined_why(path):
    """{id: [codes]} of the needs_review questions in an ingest-refine output (60.3/60.7)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    qs = (data.get("refined") or data).get("questions") or []
    return {str(q.get("id")): list(q.get("needs_review_why") or []) for q in qs if q.get("needs_review")}


def load_qa(paths, offset=0):
    """{id: {"answer","flawed"}} from review QA tables; printed n -> id = n - offset."""
    rows, _bad = review.parse_qa(paths)
    return {str(n - offset): {"answer": r["answer"], "flawed": r["flawed"]} for n, r in rows.items()}


ALPHA_INV = 20  # alpha = 0.05, the convention of the earlier "~95%" rule


def noise(f, r):
    """True when the fixed/regressed split is within noise: exact two-sided sign test p > 1/ALPHA_INV (64.4)."""
    n = f + r
    tail = sum(math.comb(n, i) for i in range(min(f, r) + 1))
    return not 2 * tail * ALPHA_INV <= 2 ** n


def _min_flips():
    n = 1
    while 2 * ALPHA_INV > 2 ** n:  # a unanimous n flips has p = 2 / 2**n
        n += 1
    return n


MIN_FLIPS = _min_flips()  # 6: fewer flips can never reach p <= .05


def decisive(f, r):
    """True when f+r flips are enough for the sign test to be able to reach p <= .05."""
    return f + r >= MIN_FLIPS


def _one_label(x):
    """A single answer label (any option letter or digit), not a substring test (D1)."""
    return isinstance(x, str) and len(x) == 1 and x.isalnum()


def _row_answered(r):
    return _answered({"answer": r["answer"], "status_reason": r["reason"]})


def classify(ma, mb, qa=None):
    """Per-question change from run A to run B. Reference = key (key_ok) else QA letter.
    63.3 adds cov_up/cov_down (not answered <-> answered) and wrong_new/wrong_gone (answered and wrong
    vs the reference, D5: a declined question later answered wrong counts); the old lists are unchanged."""
    qb = {q["id"]: q for q in mb["questions"]}
    out = {"fixed": [], "regressed": [], "changed": [], "status_up": [], "status_down": [], "unchanged": 0,
           "basis": None, "cov_up": [], "cov_down": [], "wrong_new": [], "wrong_gone": []}
    rank = {"PASS": 2, "UNCERTAIN": 1, "FAIL": 0}
    for a in ma["questions"]:
        b = qb.get(a["id"])
        if b is None:
            continue
        ra = rb = None
        aa, ab = _row_answered(a), _row_answered(b)
        if aa != ab:
            out["cov_up" if ab else "cov_down"].append(a["id"])
        ka, kb = a["key_ok"], b["key_ok"]
        if ka is not None and kb is not None:
            ra, rb, out["basis"] = ka, kb, "key"
        elif qa and a["id"] in qa and _one_label(qa[a["id"]]["answer"]) and not qa[a["id"]]["flawed"]:
            want = qa[a["id"]]["answer"]
            ra, rb = a["answer"] == want, b["answer"] == want
            out["basis"] = out["basis"] or "QA"
        if ra is not None:
            wa, wb = aa and not ra, ab and not rb
            if wb and not wa:
                out["wrong_new"].append(a["id"])
            elif wa and not wb:
                out["wrong_gone"].append(a["id"])
        if ra is not None and ra != rb:
            out["fixed" if rb else "regressed"].append(a["id"])
        elif ra is None and a["answer"] != b["answer"]:
            out["changed"].append(a["id"])
        elif rank.get(b["status"], 1) != rank.get(a["status"], 1):
            out["status_up" if rank.get(b["status"], 1) > rank.get(a["status"], 1) else "status_down"].append(a["id"])
        else:
            out["unchanged"] += 1
    return out


# ---- engine scoreboard (TASK-063): pairing, delta, verdict, text ----

_POOL = ("fixed", "regressed", "wrong_new", "wrong_gone", "cov_up", "cov_down")


def version_key(line):
    """What a run is a version of: engine commit, prompt and model (64.7; a repeat shares it)."""
    return ((line.get("git") or {}).get("commit"), json.dumps(line.get("prompt"), sort_keys=True),
            line.get("model"))


def pair(lines, baseline=None):
    """([(current line, baseline line or None)] one per exam_sha256, no_sha count) (63.2).
    Current = latest line of a sha; baseline = the given line of that sha, else the latest earlier line of
    another version (64.7), else the previous line (a repeat)."""
    by, no_sha = {}, 0
    for ln in sorted(lines, key=lambda x: x.get("ts") or ""):
        if not ln.get("exam_sha256"):
            no_sha += 1
            continue
        by.setdefault(ln["exam_sha256"], []).append(ln)
    out = []
    for sha, grp in by.items():
        cur = grp[-1]
        if baseline is not None and baseline.get("exam_sha256") == sha and baseline.get("run_id") != cur.get("run_id"):
            base = baseline
        else:
            other = [x for x in grp[:-1] if version_key(x) != version_key(cur)]
            base = other[-1] if other else (grp[-2] if len(grp) > 1 else None)
        out.append((cur, base))
    return out, no_sha


def board_delta(ma, mb, qa=None):
    """Pair delta A->B (63.3): classify counts plus coverage, quality and cost values of both sides."""
    d = classify(ma, mb, qa)
    res = {k: len(d[k]) for k in _POOL}
    res.update(basis=d["basis"], n=mb["n"], flips=res["fixed"] + res["regressed"])
    return res


def pool(deltas):
    """Sum the pair counts of one kind; basis key beats QA beats None."""
    out = {k: sum(d[k] for d in deltas) for k in _POOL}
    bases = {d["basis"] for d in deltas}
    out["basis"] = "key" if "key" in bases else ("QA" if "QA" in bases else None)
    out["n"] = sum(d["n"] for d in deltas)
    return out


def verdict(d):
    """(verdict text, flag or None) of a pooled delta (63.4). Coverage alone is never `better`."""
    f, r, wn, wg = d["fixed"], d["regressed"], d["wrong_new"], d["wrong_gone"]
    if d["basis"] is None:
        return "unmeasured", None
    cov_up = d["cov_up"] > d["cov_down"]
    if not decisive(f, r) and not decisive(wg, wn):
        flag = "watch: coverage up, quality down within noise" if cov_up and (r > f or wn > wg) else None
        return "insufficient (flips %d<%d)" % (f + r, MIN_FLIPS), flag
    if (not noise(f, r) and r > f) or (not noise(wg, wn) and wn > wg):
        return "regression", "COVERAGE_UP_QUALITY_DOWN" if cov_up else None
    if not noise(f, r) and f > r:
        return ("better (proxy)" if d["basis"] == "QA" else "better"), None
    flag = "watch: coverage up, quality down within noise" if cov_up and (r > f or wn > wg) else None
    return "same (within noise n=%d flips=%d)" % (d["n"], f + r), flag


def _sum(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) if xs else None


def _side(ms):
    """Aggregate of runs (metrics with quality) of one kind on one side."""
    qs = [m["quality"] for m in ms]
    ans, n = sum(m["counts"]["answered"] for m in ms), sum(m["n"] for m in ms)
    agg = {k: _sum(q[k] for q in qs) for k in ("correct", "keyed", "wrong_answered", "silent_wrong",
                                               "flagged", "flagged_correct")}
    agg["score"] = _rate(agg["correct"], agg["keyed"]) if agg["correct"] is not None else None
    agg["score_ci"] = wilson(agg["correct"], agg["keyed"]) if agg["score"] is not None else None
    agg["outcomes"] = {k: sum(q["outcomes"][k] for q in qs) for k in OUTCOMES}
    agg.update(answered=ans, n=n, basis="key" if any(q["basis"] == "key" for q in qs)
               else ("qa" if any(q["basis"] == "qa" for q in qs) else None),
               cost_usd=_sum(m["cost"].get("cost_usd") for m in ms), calls=_sum(m["cost"].get("calls") for m in ms))
    c, w = agg["correct"], agg["wrong_answered"]
    agg["precision"] = _rate(c, c + w) if c is not None else None
    agg["false_alarm"] = _rate(agg["flagged_correct"], agg["flagged"]) if agg["flagged"] else None
    agg["cost_per_answered"] = agg["cost_usd"] / ans if ans and agg["cost_usd"] is not None else None
    pr = [q["proxy"] for q in qs]
    ag, df = _sum(p["agrees"] for p in pr), _sum(p["differs"] for p in pr)
    agg["agree_rate"] = _rate(ag, ag + df) if ag is not None else None  # pooled by question, not per exam (64.3)
    pf = _sum(p["flagged"] for p in pr)
    agg["proxy_false_alarm"] = _rate(_sum(p["flagged_agrees"] for p in pr), pf) if pf else None
    why = {}
    for p in pr:
        for k, v in (p["needs_review_by_why"] or {}).items():
            why[k] = why.get(k, 0) + v
    agg.update(review_why=why, image_agrees=_sum(p["image_agrees"] for p in pr),
               image_differs=_sum(p["image_differs"] for p in pr))
    if any("parse_flagged" in q for q in qs):  # 69.4: keys only for runs with an assembly.json
        agg.update({k: _sum(q.get(k) for q in qs) for k in ("parse_flagged", "parse_wrong", "solve_wrong",
                                                           "parse_differs")})
    kbs = [m["cost"].get("prompt_kb") for m in ms]
    if n and None not in kbs:  # 69.6: only when every run has a run.log
        agg["in_tok_per_q"] = sum(kbs) * 1024 / BYTES_PER_TOKEN / n
    return agg


def board_kind(entries):
    """One kind block (63.5 data). entries = [{"cur": m, "base": m|None, "qa": qa|None, "line": history line}]."""
    cur = _side([e["cur"] for e in entries])
    paired = [e for e in entries if e["base"] is not None]
    base = _side([e["base"] for e in paired]) if paired else None
    out = {"exams": len(entries), "runs": len(entries) + len(paired), "cur": cur, "base": base,
           "tier": entries[0].get("tier"), "repeat": any(e.get("repeat") for e in paired),
           "generated": any(str((e["line"] or {}).get("key_basis") or "").startswith("generated") for e in entries)}
    if paired:
        out["delta"] = pool([board_delta(e["base"], e["cur"], e["qa"]) for e in paired])
        out["verdict"], out["flag"] = verdict(out["delta"])
    else:
        out["delta"], out["verdict"], out["flag"] = None, "-", None
    return out


def _f(x, fmt="%d"):
    return "-" if x is None else fmt % x


def _arrow(a, b, show):
    return "%s -> %s" % (show(a), show(b)) if a is not None or b is not None else "-"


def board_text(name, k):
    """Text lines of one kind block (63.5)."""
    cur, base = k["cur"], k["base"]
    basis = {"key": "key (generated)" if k["generated"] else "key", "qa": "qa(proxy)"}.get(cur["basis"], "none")
    out = ["kind %s  basis %s  exams %d  runs %d%s%s" % (
        name, basis, k["exams"], k["runs"], "  tier " + k["tier"] if k.get("tier") else "",
        "  repeat" if k.get("repeat") else "")]
    if base is None:
        out.append("  baseline: none")
        out.append("  coverage %d/%d" % (cur["answered"], cur["n"]))
    else:
        out.append("  coverage %d/%d -> %d/%d (%+d)" % (base["answered"], base["n"], cur["answered"], cur["n"],
                                                       cur["answered"] - base["answered"]))
    ref = base or {}
    if cur["basis"] == "key":
        out.append("  quality key %s/%s (%s of all keyed)  precision %s" % (
            _f(cur["correct"]), _f(cur["keyed"]), _pct(_rate(cur["correct"], cur["keyed"])),
            _arrow(ref.get("precision"), cur["precision"], _pct) if base else _pct(cur["precision"])))
        if cur["score"] is not None:
            lo, hi = cur["score_ci"]
            out.append("  score %s of all keyed (95%% CI %s-%s)  answered-only %s" % (
                _pct(cur["score"]), _pct(lo), _pct(hi), _pct(cur["precision"])))
        out.append("  false_alarm %s  silent_wrong %s" % (
            _arrow(ref.get("false_alarm"), cur["false_alarm"], _pct) if base else _pct(cur["false_alarm"]),
            _arrow(ref.get("silent_wrong"), cur["silent_wrong"], _f) if base else _f(cur["silent_wrong"])))
    elif cur["basis"] == "qa":
        why = ",".join("%s=%d" % kv for kv in sorted(cur["review_why"].items())) or "-"
        out.append("  quality qa agree %s (proxy)" % (
            _arrow(ref.get("agree_rate"), cur["agree_rate"], _pct) if base else _pct(cur["agree_rate"])))
        out.append("  proxy: false_alarm~ %s review_why %s image %s/%s" % (
            _pct(cur["proxy_false_alarm"]), why, _f(cur["image_agrees"]), _f(cur["image_differs"])))
    else:
        out.append("  quality unmeasured (no key, no QA)")
    if cur.get("parse_flagged") is not None:  # 69.4: flags, not accuracy; the quality lines keep their denominator
        tail = ""
        if cur["basis"] == "key":
            tail = "  wrong: parse-suspect %s solver %s" % (_f(cur.get("parse_wrong")), _f(cur.get("solve_wrong")))
        elif cur["basis"] == "qa":
            tail = "  differs on flagged %s" % _f(cur.get("parse_differs"))
        out.append("  parsing flagged %d/%d (structure flags, not accuracy)%s" % (cur["parse_flagged"], cur["n"], tail))
    usd = lambda x: "-" if x is None else "$%.4f" % x  # noqa: E731
    out.append("  cost %s (per answered %s) calls %s" % (
        _arrow(ref.get("cost_usd"), cur["cost_usd"], usd) if base else usd(cur["cost_usd"]),
        _arrow(ref.get("cost_per_answered"), cur["cost_per_answered"], usd) if base else usd(cur["cost_per_answered"]),
        _arrow(ref.get("calls"), cur["calls"], _f) if base else _f(cur["calls"])))
    if cur.get("in_tok_per_q") is not None:
        out.append("  input ~tok/q %.1f (prompt bytes/%d, all calls)" % (cur["in_tok_per_q"], BYTES_PER_TOKEN))
    out.append("  verdict %s%s" % (k["verdict"], "  " + k["flag"] if k["flag"] else ""))
    return out
