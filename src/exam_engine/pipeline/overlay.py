"""Report answer overlay (TASK-096 96.1/96.2): answers of declined questions taken from another plan run.

`--overlay PLAN_DIR:PRINTED[,PRINTED...]` names an overlay plan run and the printed numbers whose answer,
solution, status, doubt and checks come from it. The merge exists only in memory at render time: no result.json
or plan.json is ever written. Every validation runs before any file is written. No model call, no clock.
"""
import copy
import hashlib
import json
import os

from exam_engine.pipeline import explain, parser, planrun, router, runlayout
from exam_engine.pipeline.reporter import _one_line

ANSWER_LETTERS = ("A", "B", "C", "D")


def parse(spec):
    """'PLAN_DIR:64,65' -> (plan_dir, [64, 65]); ValueError on a malformed spec."""
    plan_dir, sep, nums = str(spec).rpartition(":")
    if not sep or not plan_dir:
        raise ValueError("overlay %r: expected PLAN_DIR:PRINTED[,PRINTED...]" % spec)
    out = []
    for tok in nums.split(","):
        if not tok.strip().isdigit():
            raise ValueError("overlay %r: printed number %r is not an integer" % (spec, tok.strip()))
        out.append(int(tok))
    return plan_dir, out


def text_sha256(exam_q):
    """Identity of a question: stem + options, whitespace collapsed. Passage and instruction are excluded on
    purpose (a table fix changes the passage, not the question)."""
    stem = _one_line(exam_q.get("stem") or exam_q.get("text"))
    opts = {str(k): _one_line(v) for k, v in (exam_q.get("options") or {}).items()}
    blob = json.dumps({"stem": stem, "options": opts}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_exam(plan_dir):
    """Parsed input/exam.md of a plan dir with the plan's language applied, or None."""
    try:
        exam = parser.parse_exam(os.path.join(plan_dir, "input", "exam.md"))
        lang = (runlayout._jload(os.path.join(plan_dir, "config.json")) or {}).get("lang")
        router.apply_lang(exam, lang)
        return exam
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def _by_id(items):
    return {str(x.get("id")): x for x in items or []}


def _pageset(q):
    return set(q.get("pages") or [])


def _answered(q):
    a = q.get("answer")
    return isinstance(a, str) and a.strip().upper() in ANSWER_LETTERS


def resolve(specs, plan_dirs, reason):
    """Validate every overlay spec against the base plan dirs; returns [entry] (shape in the design 96.1).
    ValueError naming the printed number on the first refusal. Reads only."""
    if not specs:
        return []
    if not str(reason or "").strip():
        raise ValueError("--overlay needs --overlay-reason")
    base_abs = [os.path.abspath(p.rstrip("/")) for p in plan_dirs]
    base = []
    for pd in base_abs:
        loaded = planrun.load(pd)
        if loaded["result"] is None:
            raise ValueError("base plan %s has no result.json" % pd)
        base.append({"dir": pd, "result": loaded["result"], "exam": load_exam(pd), "plan": loaded["plan"] or {}})
    base_exam_id = runlayout.exam_line_of_plan_dir(base_abs[0])[0] if base_abs else None
    entries, seen = [], set()
    for spec in specs:
        ov_dir, printed = parse(spec)
        ov_dir = os.path.abspath(ov_dir.rstrip("/"))
        if ov_dir in base_abs:
            raise ValueError("overlay %s is one of the base plan runs" % ov_dir)
        ov = planrun.load(ov_dir)
        if ov["result"] is None or ov["exam_text"] is None:
            raise ValueError("overlay %s lacks result.json or input/exam.md" % ov_dir)
        oexam_id, oline = runlayout.exam_line_of_plan_dir(ov_dir)
        if oexam_id != base_exam_id:
            raise ValueError("overlay %s is exam %r, base is %r" % (ov_dir, oexam_id, base_exam_id))
        subject = (ov["result"].get("exam") or {}).get("subject")
        parts = [b for b in base if (b["result"].get("exam") or {}).get("subject") == subject]
        if len(parts) != 1:
            raise ValueError("overlay subject %r matches %d base parts (need exactly 1)" % (subject, len(parts)))
        part, ov_exam = parts[0], load_exam(ov_dir)
        if part["exam"] is None or ov_exam is None:
            raise ValueError("overlay subject %r: parsed exam text missing" % subject)
        boff, ooff = explain.offset(part["exam"]), explain.offset(ov_exam)
        bq, bx = _by_id(part["result"]["questions"]), _by_id(part["exam"]["questions"])
        oq, ox = _by_id(ov["result"]["questions"]), _by_id(ov_exam["questions"])
        qs = []
        for p in printed:
            if p in seen:
                raise ValueError("overlay printed %d: listed twice" % p)
            seen.add(p)
            bid, oid = str(p - boff), str(p - ooff)
            if bid not in bq or bid not in bx or oid not in oq or oid not in ox:
                raise ValueError("overlay printed %d: unknown question (base id %s, overlay id %s)" % (p, bid, oid))
            bsha, osha = text_sha256(bx[bid]), text_sha256(ox[oid])
            if bsha != osha:
                raise ValueError("overlay printed %d: question text differs (stem/options sha %s... vs %s...)"
                                 % (p, bsha[:12], osha[:12]))
            if _pageset(bq[bid]) and _pageset(oq[oid]) and not _pageset(bq[bid]) & _pageset(oq[oid]):
                raise ValueError("overlay printed %d: source pages are disjoint" % p)
            if _answered(bq[bid]) and not bq[bid].get("unresolved"):
                raise ValueError("overlay printed %d: base question is answered (only declined/unresolved "
                                 "questions may be replaced)" % p)
            if not _answered(oq[oid]):
                raise ValueError("overlay printed %d: overlay question has no letter answer" % p)
            qs.append({"printed": p, "base_id": bid, "id": oid, "text_sha256": osha})
        plan = ov["plan"] or {}
        same = [e for e in entries if e["dir"] == _rel(ov_dir)]
        if same:  # the same overlay dir given twice: one entry
            same[0]["questions"] += qs
            continue
        if any(e["subject"] == subject for e in entries):
            raise ValueError("overlay subject %r: two different overlay plan runs (one per subject)" % subject)
        entries.append({"exam_id": oexam_id, "line": oline, "plan_run_id": os.path.basename(ov_dir),
                        "dir": _rel(ov_dir), "result_sha256": runlayout._sha_file(os.path.join(ov_dir, "result.json")),
                        "subject": subject, "base_plan_run_id": os.path.basename(part["dir"]),
                        "reason": _one_line(reason),
                        "cost_usd": (ov["result"].get("run") or {}).get("cost_usd", plan.get("cost_usd", 0)),
                        "questions": qs})
    return entries


def _rel(path):
    rel = os.path.relpath(path, os.getcwd())
    return path if rel.startswith("..") else rel.replace(os.sep, "/")


def _recount(result):
    s = result["summary"]
    qs = result["questions"]
    for key, status in (("pass", "PASS"), ("fail", "FAIL"), ("uncertain", "UNCERTAIN")):
        s[key] = sum(1 for q in qs if q.get("verification_status") == status)
    s["unresolved"] = sum(1 for q in qs if q.get("unresolved"))


def apply(result, exam, entry, ov_result, ov_exam):
    """(result', exam') deep copies with the entry's questions replaced by the overlay questions (id = base id,
    `overlay` marker for the source line); summary counts recounted, points kept."""
    result, exam = copy.deepcopy(result), copy.deepcopy(exam)
    ov_q, ov_x = _by_id(ov_result["questions"]), _by_id(ov_exam["questions"])
    marker = {"plan_run_id": entry["plan_run_id"], "line": entry["line"], "reason": entry["reason"]}
    for item in entry["questions"]:
        nq = copy.deepcopy(ov_q[item["id"]])
        nq["id"], nq["overlay"] = item["base_id"], dict(marker)
        nx = copy.deepcopy(ov_x[item["id"]])
        nx["id"] = type(nx["id"])(item["base_id"]) if isinstance(nx.get("id"), int) else item["base_id"]
        for coll, new in ((result["questions"], nq), (exam["questions"], nx)):
            for i, old in enumerate(coll):
                if str(old.get("id")) == item["base_id"]:
                    coll[i] = new
                    break
    _recount(result)
    return result, exam


def load_for_entry(entry):
    """(ov_result, ov_exam) of an entry's overlay plan dir; ValueError when it vanished."""
    loaded = planrun.load(entry["dir"])
    ov_exam = load_exam(entry["dir"])
    if loaded["result"] is None or ov_exam is None:
        raise ValueError("overlay plan %s is no longer readable" % entry["dir"])
    return loaded["result"], ov_exam
