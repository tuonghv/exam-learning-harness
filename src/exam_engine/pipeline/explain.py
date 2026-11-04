"""Answer-driven cause table (TASK-077, 77.1-77.7): why each wrong or flagged-right answer was wrong.

Free and read-only: result.json + exam file (+ calls/, PDF). The official key is read ONLY by
`score_rows`; every check below takes no key. Output cells are numbers, 0/1/na and fixed enums:
never an option letter, option text or message (the row keeps its letters under `_ans` until
`score_rows` turns them into `*_agrees_key` booleans and drops them).

Python 3.8 stdlib only.
"""
import json
import os
import re
import unicodedata

from exam_engine.adapters import claude
from exam_engine.core import schema as sch
from exam_engine.pipeline import metrics, parser, verifier

# V0 calibration (work/TASK-077/evidence/explain-replay.txt): fwd above the best synthetic defect (0.81) and under
# the 5th percentile of real questions (0.87); rev = lowest real score of the reliable subjects (0.68) - 0.05
EXTRACT_FWD_MIN = 0.85
EXTRACT_REV_MIN = 0.63
RELIABLE_SHARE = 0.8  # exam-level: share of questions passing fwd and rev, else the PDF text is the weak side
NA = "na"
CAUSES = ("infrastructure", "extraction", "context_not_delivered", "reply_path", "key_oddity_candidate",
          "image_only", "solver_reasoning", "unknown", "none")
SRC = ("text", "image", "text+image", "adjudicated")
TEXT_TAGS = ("solve", "retry")
_OFFSET = parser._OFFSET_RE
_LABEL_TOKEN = r"(?<![\w]){}(?![\w])"
_IMG_ANS = re.compile(r"image answer: (\S+)")
_SECOND_ANS = re.compile(r"second answer: (\S+)")
_ADJ_ANS = re.compile(r"adjudicated: (.+?) \(text (.+?), image (.+?)\)")
_COMPUTED_VAL = re.compile(r"= (-?[\d.]+(?:e[+-]?\d+)?), answer ")

COLUMNS = (
    "printed", "id", "subject", "outcome", "primary", "prompt_src", "ext", "fwd", "rev", "opt_prompt",
    "opt_mode", "ocr_page", "ctx_passage", "ctx_deps_k", "ctx_deps_n", "ctx_pages", "src", "multi_json",
    "parse_now_ok", "attempts", "call_failed", "marker", "malformed", "text_image_differ", "final_agrees_key",
    "text_agrees_key", "image_agrees_key", "second_agrees_key", "adj_agrees_key", "alt_agrees_key",
    "recompute_agrees_key", "quotes_n", "quotes_in_prompt", "alt_reading", "recompute", "recompute_is_final")


# ---- text normalisation (no language literal) ----

def norm(s):
    """NFKC, casefold, only alphanumeric characters (Unicode isalnum)."""
    return "".join(c for c in unicodedata.normalize("NFKC", str(s or "")).casefold() if c.isalnum())


def grams(n):
    return {n[i:i + 3] for i in range(len(n) - 2)}


def _cov(a_norm, pool_norm, pool_grams):
    """Share of a's 3-grams found in the pool; pieces under 12 chars: exact substring 1/0; None if empty."""
    if not a_norm:
        return None
    if len(a_norm) < 12:
        return 1.0 if a_norm in pool_norm else 0.0
    g = grams(a_norm)
    return len(g & pool_grams) / len(g)


def offset(exam):
    m = _OFFSET.search(exam.get("instructions") or "")
    return int(m.group(1)) if m else 0


def letter_of(ans, options):
    s = str(ans if ans is not None else "").strip()
    if re.fullmatch(r"[A-Za-z]", s):
        return s.upper()
    return verifier.option_for_value(s, options) if s and options else None


def load_key(path):
    """{printed number str: letter} from any answer list that pairs a number with a letter A-D."""
    with open(path, encoding="utf-8") as fh:
        toks = re.findall(r"[^\W\d_]+|\d+", fh.read())
    out = {}
    for a, b in zip(toks, toks[1:]):
        if a.isdigit() and re.fullmatch(r"[A-Da-d]", b):
            out.setdefault(str(int(a)), b.upper())
    return out


# ---- PDF text ----

def pdf_pages(path):
    """Page texts (index 0 = page 1) via PyMuPDF (the ingest dependency), else None (no process is started)."""
    try:
        import fitz
        with fitz.open(path) as doc:
            return [p.get_text() for p in doc]
    except Exception:  # noqa: BLE001 - missing module or unreadable file: try the next reader
        pass
    return None


def _min_chars():
    try:
        from exam_engine.ingest.adapters import pdf
        return pdf.MIN_CHARS
    except Exception:  # noqa: BLE001 - optional ingest stack
        return 20


# ---- 77.1 join ----

def _ids(obj):
    qs = obj.get("questions")
    if isinstance(qs, list):
        return {str(x.get("id")): x for x in qs if isinstance(x, dict)}
    return {str(obj["id"]): obj} if "id" in obj else {}


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def load_calls(calls_dir):
    """[{n, tag, pages, prompt, reply, objs}] from calls/index.jsonl (+ NNN-prompt/reply.txt), or None."""
    idx = os.path.join(calls_dir or "", "index.jsonl")
    if not calls_dir or not os.path.isfile(idx):
        return None
    out = []
    for ln in _read(idx).splitlines():
        try:
            rec = json.loads(ln)
        except ValueError:
            continue
        n = "%03d" % rec.get("n", 0)
        reply = _read(os.path.join(calls_dir, n + "-reply.txt"))
        out.append({"n": rec.get("n"), "tag": rec.get("tag"), "pages": rec.get("pages"),
                    "prompt": _read(os.path.join(calls_dir, n + "-prompt.txt")), "reply": reply,
                    "objs": claude._objects(reply)})
    return out


def _covering(calls, qid, tags):
    return [c for c in calls if c["tag"] in tags and any(qid in _ids(o) for o in c["objs"])]


def join(result, exam, calls_dir=None, subject=""):
    """One row per saved question that exists in the exam; checks and key scoring come later."""
    off, qs = offset(exam), {str(q["id"]): q for q in exam["questions"]}
    calls, dep, rows = load_calls(calls_dir), parser.deps(exam), []
    groups = parser.groups(exam)
    first_of = {}
    for g in groups:
        for i in g["ids"]:
            first_of.setdefault(str(i), str(g["ids"][0]))
    counts = [len(q.get("options") or {}) for q in exam["questions"]]
    mode = max(set(counts), key=counts.count) if counts else 0
    for rec in result.get("questions") or []:
        qid, q = str(rec.get("id")), qs.get(str(rec.get("id")))
        if q is None:
            continue
        txt = _covering(calls, qid, TEXT_TAGS)[-1:] if calls else []
        img = _covering(calls, qid, ("image",))[-1:] if calls else []
        cover = _covering(calls, qid, TEXT_TAGS + ("image",)) if calls else []
        row = {"printed": int(qid) + off if qid.isdigit() else None, "id": qid, "subject": subject,
               "prompt_src": "calls" if calls else "exam", "opt_mode": mode,
               "_q": q, "_rec": rec, "_exam": exam, "_deps": [str(d) for d in dep.get(q["id"], ())],
               "_carrier": first_of.get(qid, qid), "_text": txt[0] if txt else None,
               "_image": img[0] if img else None, "_cover": cover}
        rows.append(row)
    return rows


# ---- 77.2 extraction ----

_POOLS = {}


def _pool(pdf_text):
    """(norm text, grams) of a page stream, cached: the same stream serves every question on its pages."""
    key = tuple(pdf_text)
    if key not in _POOLS:
        if len(_POOLS) > 64:
            _POOLS.clear()
        n = norm("\n".join(pdf_text))
        _POOLS[key] = (n, grams(n))
    return _POOLS[key]


def extract_check(qblock, pdf_text, next_anchor):
    """{fwd, rev, opt_prompt, opt_mode, ocr_page}. qblock: stem, options (list), passage, text, opt_mode,
    n_source (leading pdf_text pages that are the question's Source pages). next_anchor: norm strings
    that start the next question (its group head, its stem)."""
    opts = list(qblock.get("options") or ())
    out = {"fwd": None, "rev": None, "opt_prompt": qblock.get("opt_prompt", len(opts)),
           "opt_mode": qblock.get("opt_mode"), "ocr_page": None}
    if not pdf_text:
        return out
    n_src = qblock.get("n_source") or 0
    out["ocr_page"] = int(any(len(t.strip()) < _min_chars() for t in pdf_text[:n_src]))
    pool, pg = _pool(pdf_text)
    stem = qblock.get("stem") or qblock.get("text") or ""
    covs = [c for c in (_cov(norm(p), pool, pg) for p in [stem] + opts) if c is not None]
    out["fwd"] = sum(covs) / len(covs) if covs else None
    anchor = norm(stem)[:24]
    start = pool.find(anchor, qblock.get("after") or 0) if anchor else -1
    out["pos"] = start if start >= 0 else None
    if start >= 0:
        block = norm(" ".join([qblock.get("passage") or "", qblock.get("text") or stem] + opts))
        # the span ends where the last option ends in the PDF (a cut stem cannot hide: the options still follow
        # it); no option found -> the next question's anchor, else the stream end; never longer than twice the
        # block, so trailing page text is not read as a dropped part. A dropped option is opt_prompt < opt_mode.
        last = norm(opts[-1]) if opts else ""
        at = pool.find(last, start) if len(last) >= 4 else -1
        ends = [e for e in (pool.find(a, start + len(anchor)) for a in next_anchor or () if a) if e > 0]
        end = at + len(last) if at >= 0 else (min(ends) if ends else len(pool))
        span = pool[start:min(end, start + 2 * len(block) + 100)]
        g = grams(span)
        out["rev"] = len(g & grams(block)) / len(g) if g else None
    return out


def _stream(q, pages):
    """(page texts, n_source): the question's Source pages plus the continuation page, else the whole PDF."""
    src = [p for p in (q.get("pages") or []) if isinstance(p, int) and 1 <= p <= len(pages)]
    if not src:
        return list(pages), 0
    nxt = max(src) + 1
    return [pages[p - 1] for p in src] + ([pages[nxt - 1]] if nxt <= len(pages) else []), len(src)


def _anchors(exam, q):
    qs, anchors = exam["questions"], []
    for k, x in enumerate(qs):
        if x is q and k + 1 < len(qs):
            nx = qs[k + 1]
            head = (nx.get("passage") or "") if nx.get("passage") != q.get("passage") else ""
            if not head and nx.get("instruction") != q.get("instruction"):
                head = nx.get("instruction") or ""
            anchors = [norm(head)[:24], norm(nx.get("stem") or nx.get("text"))[:24]]
    return anchors


def run_extract(row, pages, after=0):
    """Fill the 77.2 fields of a row (all na without a PDF); `ext` is set by `set_ext`."""
    q = row["_q"]
    texts, n_src = _stream(q, pages) if pages else (None, 0)
    blk = {"stem": q.get("stem"), "text": q.get("text"), "options": list((q.get("options") or {}).values()),
           "passage": q.get("passage"), "opt_mode": row["opt_mode"], "n_source": n_src,
           "after": 0 if n_src else after}  # no Source pages: questions follow the PDF order
    blk["opt_prompt"] = _block_options(row["_text"]["prompt"], row["id"]) if row.get("_text") else len(blk["options"])
    if blk["opt_prompt"] is None:
        blk["opt_prompt"] = len(blk["options"])
    row.update(extract_check(blk, texts, _anchors(row["_exam"], q)))


def set_ext(rows):
    """`ext` per row. When the PDF text layer does not carry the exam text (under RELIABLE_SHARE of the exam's
    questions pass fwd and rev: formulas or scans as images) no row gets a verdict - the check would only measure the PDF."""
    ev = [r for r in rows if r.get("fwd") is not None and not r.get("ocr_page")]
    ok = sum(1 for r in ev if r["fwd"] >= EXTRACT_FWD_MIN and (r["rev"] is None or r["rev"] >= EXTRACT_REV_MIN))
    reliable = bool(ev) and ok >= RELIABLE_SHARE * len(ev)
    for r in rows:
        st = ext_status(r)
        r["ext"] = st if reliable or st == "ok" else NA  # a bad PDF can only fake failures, never a pass
    return reliable


def ext_status(row):
    if row.get("ocr_page"):
        return "na_ocr"
    if row.get("fwd") is None and row.get("rev") is None:
        return NA
    bad = ((row["fwd"] is not None and row["fwd"] < EXTRACT_FWD_MIN)
           or (row["rev"] is not None and row["rev"] < EXTRACT_REV_MIN)
           or (row["opt_prompt"] is not None and row["opt_mode"] and row["opt_prompt"] < row["opt_mode"]))
    return "fail" if bad else "ok"


# ---- 77.3 context ----

def _block(prompt, qid):
    m = re.search(r"(?ms)^## Question\s+%s\s*$(.*?)(?=^## |\Z)" % re.escape(str(qid)), prompt or "")
    return m.group(1) if m else None


def _block_options(prompt, qid):
    b = _block(prompt, qid)
    return None if b is None else len(re.findall(r"(?m)^[A-Z][.)]\s", b))


def context_check(row):
    """{ctx_passage, ctx_deps_k, ctx_deps_n, ctx_pages}: what the producing call received."""
    out = {"ctx_passage": NA, "ctx_deps_k": NA, "ctx_deps_n": NA, "ctx_pages": NA}
    txt, img, q = row.get("_text"), row.get("_image"), row["_q"]
    if txt is not None and row["prompt_src"] == "calls":
        prompt = txt["prompt"]
        pn = norm(prompt)
        passage = parser._passage(q)
        if passage:
            c = _cov(norm(passage), pn, grams(pn))
            out["ctx_passage"] = NA if c is None else int(c >= EXTRACT_FWD_MIN)
        deps = row.get("_deps") or []
        if deps:
            out["ctx_deps_n"], out["ctx_deps_k"] = len(deps), sum(1 for d in deps if _block(prompt, d) is not None)
    if img is not None and img.get("pages"):
        need = set(q.get("pages") or ())
        carrier = next((x for x in row["_exam"]["questions"] if str(x["id"]) == row.get("_carrier")), None)
        need |= set((carrier or {}).get("pages") or ())
        out["ctx_pages"] = int(need <= set(img["pages"])) if need else NA
    return out


# ---- 77.4 reply path ----

def _findings(rec, code):
    return [f for f in rec.get("qa_findings") or [] if f.get("code") == code]


def path_check(row):
    """Path facts and, under `_ans`, the answer each path gave (letters; dropped by score_rows)."""
    rec, q = row["_rec"], row["_q"]
    opts = q.get("options") or {}
    src = rec.get("source") or "text"
    final = letter_of(rec.get("answer"), opts) if rec.get("answer") is not None else None
    out = {"src": src if src in SRC else "text", "attempts": rec.get("attempts"),
           "marker": int(_has_marker(q)), "multi_json": NA, "parse_now_ok": NA}
    out["call_failed"] = int(bool(_findings(rec, "call_failed")) or bool(rec.get("error")))
    out["malformed"] = int(bool(_findings(rec, "malformed_output")))
    texts = []
    for c in row.get("_cover") or []:
        out["multi_json"] = max(out["multi_json"] if out["multi_json"] != NA else 0, len(c["objs"]))
    tc = row.get("_text")
    if tc is not None:
        solve_out = sch.SOLVE_OUT
        obj, _why = claude.extract_json(tc["reply"], solve_out)  # the rule solve callers apply today
        out["parse_now_ok"] = int(obj is not None and not sch.validate(obj, solve_out))
        ent = [_ids(o)[row["id"]] for o in tc["objs"] if row["id"] in _ids(o)]
        if ent and ent[-1].get("answer") is not None:  # a tentative (uncertain) answer is still the text path's
            texts.append(letter_of(ent[-1].get("answer"), opts))
    msgs = {c: [f.get("message") or "" for f in _findings(rec, c)] for c in
            ("image_agrees", "image_differs", "image_answer", "adjudicated", "second_agrees", "second_differs")}
    adj = _ADJ_ANS.search(" ".join(msgs["adjudicated"]))
    image = second = None
    m = _IMG_ANS.search(" ".join(msgs["image_agrees"] + msgs["image_differs"]))
    if m:
        image = letter_of(m.group(1), opts)
    elif out["src"] == "image":
        image = final
    m = _SECOND_ANS.search(" ".join(msgs["second_agrees"] + msgs["second_differs"]))
    second = letter_of(m.group(1), opts) if m else None
    text = texts[0] if texts else None
    if adj:
        text = text or letter_of(adj.group(2), opts)
        image = image or letter_of(adj.group(3), opts)
    if text is None and not tc and out["src"] in ("text", "text+image"):
        text = final
    out["text_image_differ"] = int(text != image) if text and image else NA
    out["_ans"] = {"final": final, "text": text, "image": image, "second": second,
                   "adj": letter_of(adj.group(1), opts) if adj else None}
    out["unresolved"] = int(bool(rec.get("unresolved")))
    out["declined"] = int(metrics._is_declined(rec) or rec.get("answer") is None)
    return out


def _has_marker(q):
    from exam_engine.core import refcheck
    return refcheck.marker_reasons(q.get("text")) is not None


# ---- 77.5 solver signals ----

def solver_check(row):
    rec, opts = row["_rec"], row["_q"].get("options") or {}
    quotes = [c["detail"].split(": ", 1)[1] for c in rec.get("checks") or []
              if c.get("kind") == "quote" and ": " in (c.get("detail") or "")]
    out = {"quotes_n": len(quotes), "quotes_in_prompt": NA}
    tc = row.get("_text")
    if tc is not None and row["prompt_src"] == "calls" and (rec.get("source") or "text") != "image":
        pn = norm(tc["prompt"])
        out["quotes_in_prompt"] = sum(1 for x in quotes if norm(x) in pn)
    final = letter_of(rec.get("answer"), opts) if rec.get("answer") is not None else None
    reason = " ".join([(rec.get("uncertainty") or {}).get("reason") or ""]
                      + [f.get("message") or "" for f in _findings(rec, "solver_declined")])
    rn = norm(reason)
    rg = grams(rn)
    alts = []
    for lab, text in opts.items():
        if lab == final:
            continue
        hit = re.search(_LABEL_TOKEN.format(re.escape(lab)), reason) is not None
        if not hit and len(norm(text)) >= 12:
            hit = (_cov(norm(text), rn, rg) or 0) >= 0.6
        if hit:
            alts.append(lab)
    out["alt_reading"] = int(bool(alts))
    comp = [c for c in rec.get("checks") or [] if c.get("kind") == "computed" and c.get("independent")]
    out["recompute"], out["recompute_is_final"], opt = NA, NA, None
    if comp:
        out["recompute"] = "pass" if comp[-1].get("result") == "pass" else "fail"
        m = _COMPUTED_VAL.search(comp[-1].get("detail") or "")
        opt = verifier.option_for_value(m.group(1), opts) if m and opts else None
        out["recompute_is_final"] = int(opt is not None and opt == final) if final else NA
    out["_alt"], out["_recompute_opt"] = alts, opt
    return out


def analyze(rows):
    """Run the key-free path and solver checks on every row."""
    for r in rows:
        r.update(path_check(r))
        r.update(solver_check(r))
    return rows


# ---- 77.6 scoring + primary cause ----

def score_rows(rows, key):
    """The ONLY place the key is read: keeps wrong / not answered / flagged-right rows, adds outcome and
    the *_agrees_key booleans, drops every letter."""
    kept = []
    for r in rows:
        want = key.get(str(r["printed"])) if r.get("printed") is not None else None
        a = r.pop("_ans", {})
        alts = r.pop("_alt", [])
        r.pop("_recompute_opt", None)
        if want is None:
            continue
        agree = lambda x: NA if x is None else int(x == want)  # noqa: E731
        final = a.get("final")
        if final is not None and final == want:
            if not metrics._flagged(r["_rec"]):
                continue
            r["outcome"] = "flagged_right"
        else:
            r["outcome"] = "wrong" if final is not None else "not_answered"
        for k in ("final", "text", "image", "second"):
            r[k + "_agrees_key"] = agree(a.get(k))
        r["adj_agrees_key"] = agree(a.get("adj"))
        r["alt_agrees_key"] = NA if not alts else int(want in alts)
        rec_ok = r.get("recompute_is_final")
        r["recompute_agrees_key"] = NA if rec_ok == NA else int(rec_ok == 1 and final == want)
        r["_key_oddity"] = bool(rec_ok == 1 and final != want)
        kept.append(r)
    return kept


def primary(row):
    """First hit of the documented priority (upstream first)."""
    wrong = row["outcome"] != "flagged_right"
    if row.get("call_failed") and (row.get("unresolved") or row.get("declined")):
        return "infrastructure"
    ext = row.get("ext", NA)
    ctx_bad = (row.get("ctx_passage") == 0 or row.get("ctx_pages") == 0
               or (row.get("ctx_deps_n") not in (NA, None) and row["ctx_deps_k"] < row["ctx_deps_n"]))
    if ext == "fail":
        return "extraction"
    if ctx_bad:
        return "context_not_delivered"
    paths = [row.get(k) for k in ("text_agrees_key", "image_agrees_key", "second_agrees_key", "adj_agrees_key")]
    if 1 in paths and row.get("final_agrees_key") != 1:
        return "reply_path"
    if row.get("marker") and ext == "ok":
        return "reply_path"
    if row["outcome"] == "not_answered" and row.get("malformed"):
        return "reply_path"
    if wrong and row.get("_key_oddity"):
        return "key_oddity_candidate"
    if row.get("src") == "image" and row.get("text_agrees_key") == NA:
        return "image_only"
    if not wrong:
        return "none"
    return "solver_reasoning" if ext == "ok" else "unknown"


def explain(result, exam, calls_dir, pages, key, subject=""):
    """(kept rows with primary, n questions with several JSON objects, n ids found in the key, pdf_reliable)."""
    rows = analyze(join(result, exam, calls_dir, subject))
    multi = sum(1 for r in rows if r["multi_json"] != NA and r["multi_json"] >= 2)
    matched = sum(1 for r in rows if str(r["printed"]) in key)
    after = 0
    for r in rows:
        run_extract(r, pages, after)
        after = r.pop("pos", None) or after
    reliable = set_ext(rows)
    kept = score_rows(rows, key)
    for r in kept:
        r.update(context_check(r))
        r["primary"] = primary(r)
    return kept, multi, matched, reliable


# ---- output ----

def _cell(v):
    if v is None:
        return NA
    if isinstance(v, float):
        return "%.3f" % v
    return str(v)


def tsv(rows):
    return "\n".join(["\t".join(COLUMNS)] + ["\t".join(_cell(r.get(c)) for c in COLUMNS) for r in rows])


def footer(rows, multi, pdf_ok, unreliable=0):
    cnt = {c: sum(1 for r in rows if r["primary"] == c) for c in CAUSES}
    wrong = sum(1 for r in rows if r["outcome"] != "flagged_right")
    parts = ["n_wrong=%d" % wrong, "n_flagged_right=%d" % (len(rows) - wrong)]
    parts += ["%s=%d" % (c, n) for c, n in cnt.items() if n]
    return "# " + " ".join(parts + ["multi_json_questions=%d" % multi, "pdf_text=%s" % ("ok" if pdf_ok else "na"),
                              "pdf_unreliable_exams=%d" % unreliable])


# ---- 77.2 calibration ----

def _quant(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return "n=0"
    at = lambda p: xs[int(p * (len(xs) - 1))]  # noqa: E731
    return "n=%d min=%.3f p05=%.3f p25=%.3f p50=%.3f max=%.3f" % (len(xs), xs[0], at(.05), at(.25), at(.5), xs[-1])


def calibrate(rows, pages):
    """Quantiles of fwd/rev over all questions and the best score a synthetic defect still reaches."""
    real = {"fwd": [], "rev": []}
    defect = {"truncated_stem_rev": [], "reversed_all_fwd": []}
    for r in rows:
        q = r["_q"]
        texts, n_src = _stream(q, pages)
        opts = list((q.get("options") or {}).values())
        stem = q.get("stem") or q.get("text") or ""
        base = {"stem": stem, "text": q.get("text"), "options": opts, "passage": q.get("passage"),
                "opt_mode": r["opt_mode"], "n_source": n_src}
        nxt = _anchors(r["_exam"], q)
        c = extract_check(base, texts, nxt)
        if c["ocr_page"]:
            continue
        real["fwd"].append(c["fwd"])
        real["rev"].append(c["rev"])
        cut = dict(base, text=(q.get("text") or "").replace(stem, stem[:len(stem) // 2]))
        defect["truncated_stem_rev"].append(extract_check(cut, texts, nxt)["rev"])
        rev_all = dict(base, stem=stem[::-1], options=[o[::-1] for o in opts])
        defect["reversed_all_fwd"].append(extract_check(rev_all, texts, nxt)["fwd"])
    lines = ["real_%s %s" % (k, _quant(v)) for k, v in real.items()]
    lines += ["defect_%s %s" % (k, _quant(v)) for k, v in defect.items()]
    return lines
