"""Engine: solve -> checks -> QA -> decide -> (key) -> result.json + reports.

Counts calls and cost, enforces the caps, logs one line per call. run() returns
(result, exit_code); exit 0 all PASS, 1 any FAIL/UNCERTAIN/unresolved, 2 invalid input,
3 blocking stop.
"""
import hashlib
import json
import os
import re
import sys

from exam_engine.adapters import claude
from exam_engine.core import refcheck, schema as sch
from exam_engine.core.decision import decide_rec, evidence_kind, is_open, new_rec
from exam_engine.core.decision import declined, finding
from exam_engine.pipeline import cross, metrics, parser, prompts, reporter, router, scorer, solver, verifier

BLOCKING = ("auth", "rate_limit", "service")


def call_cap(cfg):
    return 1 + 2 * cfg["max_attempts"] + (1 if cfg.get("image_pdf") else 0)


PNG_SIG = b"\x89PNG\r\n\x1a\n"
MAX_PNG_BYTES = 8 * 1024 * 1024


class Stop(Exception):
    def __init__(self, cls, message):
        Exception.__init__(self, message)
        self.cls, self.message = cls, message


class Runner(object):
    """Counts calls and cost, enforces the caps, logs one line per call."""

    def __init__(self, cfg, llm, log, sink=None, llm_images=None):
        self.cfg, self.llm, self.log, self.sink = cfg, llm, log, sink
        self.llm_images = llm_images
        self.calls, self.cost = 0, 0.0

    def call(self, prompt, tag=None, images=None, pages=None):
        if self.cost >= self.cfg["max_cost_usd"]:
            raise Stop("cost_cap", "cost cap $%.2f reached" % self.cfg["max_cost_usd"])
        if self.calls >= call_cap(self.cfg):
            raise Stop("call_cap", "call cap %d reached" % call_cap(self.cfg))
        c = self.llm_images(prompt, images) if images else self.llm(prompt)
        self.calls += 1
        self.cost += c.cost_usd or 0.0
        self.log.append("call %d ok=%s cls=%s dur=%.1fs cost=%.4f prompt_bytes=%d answer_bytes=%d" % (
            self.calls, c.ok, c.cls or "-", c.duration_s or 0.0, c.cost_usd or 0.0,
            len(prompt.encode("utf-8")), len((c.text or "").encode("utf-8")))
            + (" images=%d" % len(images) if images else ""))
        if self.sink:  # before any Stop, so a crash loses no paid reply
            if images:
                self.sink(self.calls, tag, prompt, c, pages=pages,
                          page_sha256=[hashlib.sha256(b).hexdigest() for b in images])
            else:
                self.sink(self.calls, tag, prompt, c)
        if not c.ok and c.cls in BLOCKING:
            raise Stop(c.cls, c.reason)
        return c


def retry_ids(recs):
    return [i for i, r in recs.items()
            if r["status"] in ("FAIL", "UNCERTAIN") and not is_open(r["ans"])
            and r["reason"] != "no_independent_check"]  # a re-solve cannot create one


def incomplete_ids(exam):
    """{id: reasons} of questions carrying the `[Incomplete: missing_text ...]` marker line, or whose
    group context (a referenced question, a promised passage) is not in the file (labelled files)."""
    out = {}
    for q in exam["questions"]:
        why = refcheck.marker_reasons(q["text"])
        if why is not None:
            out[q["id"]] = why
    if parser.labelled(exam):
        for i, why in refcheck.missing_group_parts(
                exam, parser.groups(exam), parser.deps(exam)).items():
            out[i] = ", ".join(([out[i]] if i in out else []) + why)
    return out


def without_questions(text, ids):
    """Exam text without the `## Question N` sections of `ids` (a fragment is never sent to the solver)."""
    keep = []
    for chunk in re.split(r"(?m)^(?=## )", text):
        m = re.match(r"## Question\s+(\d+)\s*$", chunk.split("\n", 1)[0])
        if not (m and int(m.group(1)) in ids):
            keep.append(chunk)
    return "".join(keep)


def visual_flags(exam):
    """{id: [missing parts]} of questions that refer to a figure/table/passage not in their text."""
    return dict(zip((q["id"] for q in exam["questions"]), refcheck.missing_by_question(
        [q["text"] + "\n" + exam["passage"] for q in exam["questions"]])))


def _span(pages):
    return "pages unknown" if not pages else "pages %d" % pages[0] if len(pages) == 1 else \
        "pages %d-%d" % (min(pages), max(pages))


def warn_flags(exam, flags, skip, image_on):
    qs = {q["id"]: q for q in exam["questions"]}
    for i in sorted(flags):
        if not flags[i] or i in skip:
            continue
        pg = qs[i].get("pages") or []
        state = "off (no --pdf)" if not image_on else "on" if pg else "off (no pages)"
        print("WARN: question %d refers to %s not in text (%s); image check: %s" % (
            i, ", ".join(flags[i]), _span(pg), state), file=sys.stderr)


def image_targets(exam, flags, skip, max_pages, key_pages, have_pages):
    """(targets [id], pages [int], skipped {id: reason}); flagged ids not in `skip`, ascending.
    have_pages None = page count unknown (nothing is `page_absent`)."""
    qs = {q["id"]: q for q in exam["questions"]}
    targets, union, skipped = [], set(), {}
    for i in sorted(flags):
        if not flags[i] or i in skip:
            continue
        pg = set(qs[i].get("pages") or [])
        if max_pages <= 0:
            skipped[i] = "disabled"
        elif not pg:
            skipped[i] = "no_pages"
        elif pg & set(key_pages or ()):
            skipped[i] = "answer_key_page"
        elif have_pages is not None and not pg <= set(have_pages):
            skipped[i] = "page_absent"
        elif len(union | pg) > max_pages:
            skipped[i] = "page_cap"
        else:
            targets.append(i)
            union |= pg
    return targets, sorted(union), skipped


def apply_image(exam, recs, got, targets, flags, fail=None):
    """Reconcile the image reply `got` ({id str: answer}) with the text records of `targets`.
    `fail` = (code, message) when the image call gave nothing: findings only, text records kept.
    Returns the reply ids that were not asked (ignored)."""
    qs = {q["id"]: q for q in exam["questions"]}
    for i in targets:
        r = recs[i]
        if fail:
            r["findings"].append(finding("image", fail[0], fail[1]))
            continue
        g = got.get(str(i))
        text_ok = r["ans"] is not None and not declined(r["ans"]) and not is_open(r["ans"])
        if g is not None and not declined(g):
            if text_ok and cross.same_answer(r["ans"]["answer"], g["answer"]):
                r["source"] = "text+image"
            elif text_ok:
                r["source"] = "text+image"
                r["status"], r["reason"] = "UNCERTAIN", "needs_review: text/image differ"
                r["findings"].append(finding("image", "image_differs", "image answer: %s" % g["answer"]))
            else:
                r["attempts"] += 1
                r.update(ans=g, review=None, source="image")
                r["code_checks"] = verifier.det_checks(qs[i], g, exam)
                r["checks"] = list(r["code_checks"])
                r["findings"].append(finding("image", "image_answer", "answered from the page image"))
                for k in r["code_checks"]:
                    if k["result"] == "fail":
                        r["findings"].append(finding("deterministic", k["kind"], k["detail"]))
                decide_rec(r)
            continue
        why = ("; ".join(g.get("issues") or []) or "declined") if g is not None else "not in reply"
        r["source"] = "text"
        r["findings"].append(finding("image", "image_unreadable" if g is not None else "image_missing",
                                     "image: %s" % why))
        if text_ok:  # G1: keep the text answer, never overwrite it
            r["status"], r["reason"] = "UNCERTAIN", "needs_review: image unreadable (%s)" % why
        elif r["ans"] is None or declined(r["ans"]):
            r["reason"] = "solver_declined: missing_text (%s; image: %s)" % (", ".join(flags.get(i) or []), why)
    return sorted(k for k in got if not any(str(t) == k for t in targets))


def image_check(exam, recs, rn, flags, skip, cfg, image):
    """The one image call for the flagged questions (after the text rounds)."""
    targets, pages, skipped = image_targets(
        exam, flags, skip, cfg.get("max_image_pages", 4), image.get("key_pages"), image.get("have_pages"))
    for i, why in skipped.items():
        recs[i]["findings"].append(finding("image", "image_skipped", why))
    if not targets:
        return
    try:
        pngs = [image["render"](n) for n in pages]
        for b in pngs:  # the render is injected: send only real, bounded PNGs
            if not isinstance(b, bytes) or not b.startswith(PNG_SIG) or len(b) > MAX_PNG_BYTES:
                raise ValueError("render did not return a PNG within %d bytes" % MAX_PNG_BYTES)
    except Exception as exc:  # noqa: BLE001 - render is injected; any failure means no call
        apply_image(exam, recs, {}, targets, flags, ("image_unavailable", str(exc)[:200]))
        return
    c = rn.call(cross.flagged_prompt(exam, cross.flagged_items(exam, targets)), "image", images=pngs, pages=pages)
    if not c.ok:
        apply_image(exam, recs, {}, targets, flags, ("image_call_failed", c.reason or c.cls or "failed"))
        return
    got, err = cross.parse_reply(c.text)
    if got is None:
        apply_image(exam, recs, {}, targets, flags, ("image_malformed", err))
        return
    extra = apply_image(exam, recs, got, targets, flags)
    if extra:
        print("WARN: image reply ids not asked, ignored: %s" % ", ".join(extra), file=sys.stderr)


def build_result(exam, exam_path, recs, cfg, rn, stopped):
    miss = visual_flags(exam)
    pgs = {q["id"]: q["pages"] for q in exam["questions"] if q.get("pages")}
    qs = []
    for i in sorted(recs):
        r = recs[i]
        a = r["ans"] or {}
        if stopped and r["status"] != "PASS" and r["error"] is None:
            r["error"] = {"cls": stopped[0], "message": claude.mask(stopped[1])[:200]}
        if r["status"] is None:
            r["status"], r["reason"] = "UNCERTAIN", "not_solved"
        if r["reason"] == "solver_declined" and miss.get(i):
            r["reason"] = "solver_declined: missing_text (%s)" % ", ".join(miss[i])
        sc = r["score"] or {"points": None, "max": None, "basis": "none", "detail": "no key"}
        qs.append({
            "id": str(i), "evidence_kind": evidence_kind(r), "answer": a.get("answer"), "solution": a.get("solution") or [],
            "explanation": a.get("explanation") or "",
            "uncertainty": a.get("uncertainty") or {"level": "high", "reason": "no answer"},
            "checks": r["checks"], "verification_status": r["status"],
            "status_reason": r["reason"], "qa_findings": r["findings"], "score": sc,
            "attempts": max(1, r["attempts"]), "unresolved": r["status"] != "PASS" and r["reason"] != "no_independent_check",
            "error": r["error"], **({"pages": pgs[i]} if pgs.get(i) else {}),
            **({"source": r["source"]} if r.get("source") else {})})
    pts = [q["score"]["points"] for q in qs if q["score"]["points"] is not None]
    mx = [q["score"]["max"] for q in qs if q["score"]["max"] is not None]
    f = exam["fields"]
    return {
        "schema_version": 1,
        "exam": {"path": exam_path, "subject": f.get("Subject"), "level": f.get("Level"),
                 "exam_type": f.get("Exam type"), "task": f.get("Task"), "mode": f.get("Mode"),
                 "language": router.language(exam)},
        "run": {"llm": cfg["llm_name"], "model": cfg["model"], "max_attempts": cfg["max_attempts"],
                "timeout_s": cfg["timeout"], "max_cost_usd": cfg["max_cost_usd"],
                "cost_usd": round(rn.cost, 6), "calls": rn.calls,
                "stopped": stopped[0] if stopped else None,
                "prompt": prompts.prompt_info()},
        "questions": qs,
        "summary": {"pass": sum(q["verification_status"] == "PASS" for q in qs),
                    "fail": sum(q["verification_status"] == "FAIL" for q in qs),
                    "uncertain": sum(q["verification_status"] == "UNCERTAIN" for q in qs),
                    "unresolved": sum(q["unresolved"] for q in qs),
                    "points": sum(pts) if pts else None, "max_points": sum(mx) if mx else None}}


def run(exam_path, out_dir, cfg, llm, sink=None, reports=True, image=None):
    """(result, exit_code); result is None on exit 2. `image` = {"llm": f(prompt, pngs), "render": f(page),
    "key_pages": set, "have_pages": set|None} enables the page-image check (cfg["image_pdf"])."""
    try:
        text = parser.read_text(exam_path)
    except (OSError, UnicodeDecodeError) as exc:
        print("ERROR: input: cannot read %s: %s" % (exam_path, exc), file=sys.stderr)
        return None, 2
    exam = parser.parse_exam(exam_path)
    router.apply_lang(exam, cfg.get("lang"))
    errs = parser.validate_exam(exam)
    if errs:
        for e in errs:
            print("ERROR: input: %s" % e, file=sys.stderr)
        return None, 2
    for w in parser.exam_warnings(exam):
        print("WARN: %s" % w, file=sys.stderr)
    log = []
    image = image if cfg.get("image_pdf") else None
    rn = Runner(cfg, llm, log, sink, image["llm"] if image else None)
    recs = {q["id"]: new_rec() for q in exam["questions"]}
    stopped = None
    skip = incomplete_ids(exam)
    for i, why in skip.items():
        recs[i]["status"], recs[i]["reason"] = "UNCERTAIN", "solver_declined: missing_text (%s)" % why
    flags = visual_flags(exam)
    warn_flags(exam, flags, skip, image is not None)
    try:
        ids = [i for i in sorted(recs) if i not in skip]
        prompt = solver.solve_prompt(exam, without_questions(text, skip) if skip else text,
                                     cfg.get("key"), ids)
        for attempt in range(1, cfg["max_attempts"] + 1):
            if not ids:
                break
            solver.solve_round(exam, rn, recs, ids, prompt if attempt == 1 else solver.retry_prompt(exam, recs, ids),
                               tag="solve" if attempt == 1 else "retry")
            verifier.qa_round(exam, rn, recs, ids)
            ids = [i for i in retry_ids(recs) if i not in skip]
            if not ids:
                break
        if image:
            image_check(exam, recs, rn, flags, skip, cfg, image)
    except Stop as stop:
        stopped = (stop.cls, stop.message)
        for i, r in recs.items():  # a stop inside a round: decide what has an answer
            if r["ans"] is not None and r["status"] is None:
                decide_rec(r)
    if (not stopped and cfg.get("key")
            and router.policy(exam["fields"].get("Subject"))["score_basis"] != "none"):
        scorer.apply_key(recs, cfg["key"])
    result = build_result(exam, exam_path, recs, cfg, rn, stopped)
    problems = sch.validate(result, sch.RESULT)
    if problems:
        print("ERROR: internal: result.json invalid: %s" % problems[0], file=sys.stderr)
        return result, 2
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(os.path.join(out_dir, "run.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log) + ("\n" if log else ""))
    try:
        result["metrics"] = metrics.compute(result, metrics.load_log(os.path.join(out_dir, "run.log")), exam=exam)
    except Exception:  # noqa: BLE001 - metrics are extra; they must never fail a run
        result["metrics"] = None
    result["reports"] = (reporter.write_reports(result, out_dir, pdf=cfg.get("pdf", False),
                                                metrics=result["metrics"]) if reports else None)
    if stopped:
        return result, 3
    s = result["summary"]
    return result, 0 if s["pass"] == len(result["questions"]) and not s["unresolved"] else 1


def mock_llm(path):
    with open(path, encoding="utf-8") as fh:
        replies = json.load(fh)
    if not isinstance(replies, list) or not all(isinstance(x, str) for x in replies):
        raise ValueError("mock file must be a JSON list of reply strings")
    it = iter(replies)

    def llm(prompt):
        try:
            return claude.Call(True, next(it), 0.0, "", "", 0.0)
        except StopIteration:
            return claude.Call(False, "", 0.0, "other", "mock replies exhausted", 0.0)
    return llm
