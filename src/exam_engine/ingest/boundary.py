"""Optional AI hints for rule-uncertain boundary lines (REQ-0053; design phase-50). Stdlib only.

The rules in segment.py stay primary. This module finds the few lines the rules cannot place
(`suspects`), cuts small windows around them (`windows`), asks a cheap model to label only those
lines (`Reviewer`), validates the strict JSON reply (`validate`) and hands `{line: (label, conf)}`
to `segment.segment(lines, hints)`. A hint is never proof: numbering and completeness gates run
after it, and answer-key lines are never sent. Default OFF: without config["boundary"] nothing
here runs.
"""
import hashlib
import json
import os

from exam_engine import settings
from exam_engine.adapters import claude
from exam_engine.ingest import parts, replycache, segment
from exam_engine.utils.text import fold

PROMPT_REL = os.path.join("dev", "ingest", "boundary.md")
LABELS = ("question_start", "subject_start", "section_start", "question_end", "passage",
          "option_continuation", "other")
KINDS = ("QS1", "QS2", "SH", "QE", "NB", "RC")  # priority = send order
MAX_BATCH = 4  # windows per call
EST_CALL_USD = 0.003  # planning estimate of one Haiku call; the cap uses the reported cost
DEFAULT_MAX_COST = 0.10
NS = "boundary"


def template():
    with open(os.path.join(settings.PROMPTS_DIR, PROMPT_REL), encoding="utf-8") as fh:
        return fh.read()


def prompt_sha256():
    return hashlib.sha256(template().encode("utf-8")).hexdigest()


def _is_key(line):
    return bool(parts._KEY.match(fold(line.strip())))


def _strong(line):
    return segment._INTRO.match(line) or segment._READ.match(line) or segment._PART_ANY.match(line)


def _marker(line, expected):
    """-> token (folded) when `line` starts with an unseen marker word + the expected number."""
    mk = segment.MARK.match(line)
    if not mk or int(mk.group(2)) != expected or str(expected) != mk.group(2) \
            or mk.group(3)[0].isdigit():  # not "03-05" / "2.5": a range or a decimal
        return None
    tok = mk.group(1)
    if tok.startswith("(") or not any(c.isalpha() for c in tok) or fold(tok) in ("a", "b", "c", "d"):
        return None
    return fold(tok)


def _heading_like(line):
    s = line.strip()
    words = s.split()
    letters = [c for c in s if c.isalpha()]
    if not letters or len(s) > 60 or len(words) > 8 or s[-1] in ".?!,;":
        return False
    upper = sum(1 for c in letters if c.isupper()) / float(len(letters))
    return upper >= 0.6 or all(w[0].isupper() for w in words if w[0].isalpha())


def suspects(lines, page_of=None, known=None):
    """-> [{line, kind, token}] sorted by (kind priority, line); pure, no model.

    Only lines the rules do not place AND that break a sequence / shape fact qualify, so a normal
    exam gives none. Nothing before the first rule question or from the answer key on.
    `known`: folded subject names that are never headings. `page_of` is reserved (page cuts).
    """
    known = set(known or ())
    nz = [i for i, ln in enumerate(lines) if ln.strip()]
    pos = dict((i, k) for k, i in enumerate(nz))
    out = []

    def add(i, kind, token=""):
        out.append({"line": i, "kind": kind, "token": token})

    def ahead(i, k):
        return [lines[j] for j in nz[pos[i] + 1: pos[i] + 1 + k]]

    started, last_n, keys, dtext, ended = False, 0, [], "", False
    for i in nz:
        line = lines[i]
        if _is_key(line):
            break
        m = segment._Q.match(line)
        if m:
            n = int(m.group(1) or m.group(2))
            # a bare `2)` that is not the next number while the numbering resumes right after it
            if started and m.group(2) and n != last_n + 1 and n != 1 \
                    and segment._next_n(lines, i + 1) == last_n + 1:
                add(i, "NB")
            if segment._INTRO.match(line):
                add(i, "RC")
            started, last_n, keys, dtext, ended = True, n, [], "", False
            continue
        if not started:
            continue
        o = segment._OPT.match(line)
        if o:
            keys.append(o.group(1))
            dtext = o.group(2)
            continue
        if _strong(line) or segment._is_subheading(lines, i):
            ended = True  # the rules hold everything up to the next question as its context
            continue
        tok = _marker(line, last_n + 1)
        if tok:
            add(i, "QS1", tok)
            last_n, keys, dtext, ended = last_n + 1, [], "", False
            continue
        complete = keys == segment._KEYS
        nxt = ahead(i, 4)
        if complete and not ended and not segment.MARK.match(line):
            first_q = next((k for k, ln in enumerate(nxt) if segment._Q.match(ln)), len(nxt))
            if any(segment._OPT.match(ln) and segment._OPT.match(ln).group(1) == "A"
                   for ln in nxt[:first_q]):
                add(i, "QS2")
                continue
        if keys and not ended and _heading_like(line) and fold(line).rstrip(": ") not in known \
                and nxt and (segment._Q.match(nxt[0]) or segment._INTRO.match(nxt[0])
                             or _marker(nxt[0], last_n + 1)):
            add(i, "SH")
            ended = True
            continue
        s = line.strip()
        if "D" in keys and not ended and (dtext[-1:] in ".?!)" or len(dtext) <= 60) \
                and (s[0].isupper() or s[0] in "\"'“‘" or s[0].isdigit()) \
                and (len(s) >= 40 or s.endswith(":")):
            add(i, "QE")
            ended = True
            continue
        if keys and not ended:
            dtext += " " + s
    out.sort(key=lambda d: (KINDS.index(d["kind"]), d["line"]))
    return out


def windows(lines, sus, span=8, max_lines=40, max_windows=12, per_token=2):
    """-> (windows, skipped). window: {id, start, end, lines, suspects {abs line: kind}}.

    Span +-`span` lines around each sent suspect (first `per_token` QS1 lines per token), merged,
    cut to `max_lines`, never past the first answer-key line. Over `max_windows`: top by priority.
    """
    cut = next((i for i, ln in enumerate(lines) if _is_key(ln)), len(lines))
    seen, send = {}, []
    for s in sus:
        if s["line"] >= cut:
            continue
        if s["kind"] == "QS1":
            seen[s["token"]] = seen.get(s["token"], 0) + 1
            if seen[s["token"]] > per_token:
                continue
        send.append(s)
    spans = []
    for s in sorted(send, key=lambda d: d["line"]):
        lo, hi = max(0, s["line"] - span), min(cut - 1, s["line"] + span)
        if spans and lo <= spans[-1]["end"] + 1:
            spans[-1]["end"] = max(spans[-1]["end"], hi)
            spans[-1]["sus"].append(s)
        else:
            spans.append({"start": lo, "end": hi, "sus": [s]})
    wins = []
    for sp in spans:
        end = min(sp["end"], sp["start"] + max_lines - 1)
        mine = dict((s["line"], s["kind"]) for s in sp["sus"] if s["line"] <= end)
        wins.append({"start": sp["start"], "end": end, "lines": lines[sp["start"]:end + 1],
                     "suspects": mine,
                     "prio": min(KINDS.index(k) for k in mine.values())})
    skipped = 0
    if len(wins) > max_windows:
        keep = sorted(wins, key=lambda w: (w["prio"], w["start"]))[:max_windows]
        skipped = len(wins) - len(keep)
        wins = sorted(keep, key=lambda w: w["start"])
    for k, w in enumerate(wins, 1):
        w["id"] = "w%d" % k
        del w["prio"]
    return wins, skipped


def window_text(w):
    return "\n".join("L%d| %s" % (w["start"] + k, ln) for k, ln in enumerate(w["lines"])
                     if ln.strip())


def window_key(w):
    """Cache key part: the window's raw lines (position independent, so --pages reuses it)."""
    return hashlib.sha256(("boundary\0" + "\n".join(w["lines"])).encode("utf-8")).hexdigest()


def build_prompt(wins):
    out = [template().rstrip("\n"), ""]
    for w in wins:
        out.append("Window %s (classify %s)" % (w["id"], ", ".join(str(n) for n in sorted(w["suspects"]))))
        out.append(window_text(w))
        out.append("")
    return "\n".join(out)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _items(entry, w, max_items=40):
    """-> (items [(line, label, conf)], None) or (None, reason) for one window's reply entry."""
    items = entry.get("items") if isinstance(entry, dict) else None
    if not isinstance(items, list):
        return None, "schema"
    if len(items) > max_items:
        return None, "too_many"
    out, seen = [], set()
    for it in items:
        if not isinstance(it, dict):
            return None, "schema"
        line, label, conf = it.get("line"), it.get("label"), it.get("confidence")
        if not isinstance(line, int) or isinstance(line, bool) or not w["start"] <= line <= w["end"]:
            return None, "index"
        if label not in LABELS:
            return None, "label"
        if not _num(conf) or not 0 <= conf <= 1:
            return None, "confidence"
        if line in seen:
            return None, "duplicate"
        seen.add(line)
        out.append((line, label, float(conf)))
    return out, None


def _invalid(w, reason):
    return {"level": "warning", "code": "boundary_ai_invalid", "window": w["id"], "reason": reason,
            "origin": "ai", "message": "window %s ignored: %s" % (w["id"], reason)}


def _hints(items, w, min_conf):
    """-> ({line: (label, conf)}, low_confidence count): suspect lines only."""
    hints, low = {}, 0
    for line, label, conf in items:
        if line not in w["suspects"]:
            continue
        if conf < min_conf:
            low += 1
        else:
            hints[line] = (label, conf)
    return hints, low


def parse_reply(obj, wins, max_items=40):
    """-> {window id: (items, None) | (None, reason)} for a decoded reply (obj None = bad JSON)."""
    res = {}
    entries = {}
    if isinstance(obj, dict) and isinstance(obj.get("windows"), list):
        for e in obj["windows"]:
            if isinstance(e, dict) and isinstance(e.get("window_id"), str):
                entries[e["window_id"]] = e
    for w in wins:
        if obj is None:
            res[w["id"]] = (None, "json")
        elif w["id"] not in entries:
            res[w["id"]] = (None, "schema")
        else:
            res[w["id"]] = _items(entries[w["id"]], w, max_items)
    return res


def validate(obj, wins, min_conf=0.7, max_items=40):
    """-> (hints {line: (label, conf)}, warnings): a window with any defect is ignored whole."""
    hints, warns = {}, []
    for w in wins:
        items, reason = parse_reply(obj, [w], max_items)[w["id"]]
        if items is None:
            warns.append(_invalid(w, reason))
        else:
            hints.update(_hints(items, w, min_conf)[0])
    return hints, warns


class Reviewer:
    """reviewer(lines, page_of=None) -> hints; `.warnings` of the last call, `.stats` of all calls.

    ask(prompt) -> claude.Call-like (ok, text, cost_usd, reason): real, mock or None (dry run).
    """

    def __init__(self, ask=None, model="haiku", max_cost=DEFAULT_MAX_COST, cache=None,
                 dry_run=False, min_conf=0.7, keep_text=False, known=None):
        self.ask, self.model, self.max_cost = ask, model, max_cost
        self.cache = cache if cache is not None else replycache.ReplyCache()
        self.dry_run, self.min_conf, self.keep_text = dry_run, min_conf, keep_text
        self.known = known
        self.trace, self.warnings = [], []
        self.spent = 0.0
        self.stats = {"windows": 0, "suspects": 0, "skipped": 0, "cached": 0, "calls": 0,
                      "est_calls": 0, "invalid": 0, "low_confidence": 0, "hints": 0}
        self.last_windows = []

    def _key(self, w, sha):
        return "%s|%s|%s" % (window_key(w), sha, self.model)

    def __call__(self, lines, page_of=None):
        self.warnings = []
        st = self.stats
        sus = suspects(lines, page_of, self.known)
        wins, skipped = windows(lines, sus)
        self.last_windows = wins
        st["suspects"] += len(sus)
        st["windows"] += len(wins)
        st["skipped"] += skipped
        if skipped:
            self.warnings.append({"level": "warning", "code": "boundary_ai_skipped", "origin": "ai",
                                  "message": "%d uncertain window(s) not sent (limit)" % skipped})
        if not wins:
            return {}
        sha = prompt_sha256()
        hints, todo = {}, []
        for w in wins:
            got = self.cache.get(NS, self._key(w, sha))
            if got is None:
                todo.append(w)
                continue
            items = [(w["start"] + r, lab, c) for r, lab, c in got]
            h, low = _hints(items, w, self.min_conf)
            hints.update(h)
            st["cached"] += 1
            st["low_confidence"] += low
            self.trace.append({"window_id": w["id"], "window_sha256": window_key(w), "cached": True,
                               "ok": True, "cost_usd": 0.0, "reason": ""})
        batches = [todo[i:i + MAX_BATCH] for i in range(0, len(todo), MAX_BATCH)]
        if self.dry_run:
            st["est_calls"] += len(batches)
        else:
            self._calls(batches, sha, hints)
        self._promote(sus, hints)
        st["hints"] += len(hints)
        self.warnings.append({"level": "info", "code": "boundary_ai_summary", "origin": "ai",
                              "message": "%d window(s), %d call(s), %d cached, cost $%.4f"
                              % (len(wins), st["calls"], st["cached"], self.spent)})
        return hints

    def _calls(self, batches, sha, hints):
        st = self.stats
        for b, batch in enumerate(batches):
            if self.spent + EST_CALL_USD > self.max_cost:
                self.warnings.append({"level": "warning", "code": "boundary_ai_budget", "origin": "ai",
                                      "message": "cost cap $%.2f reached: %d call(s) not made, rules kept"
                                      % (self.max_cost, len(batches) - b)})
                return
            call = self.ask(build_prompt(batch))
            st["calls"] += 1
            self.spent += float(call.cost_usd or 0.0)
            if call.ok:
                obj, _why = claude.extract_json(call.text)
                res = parse_reply(obj, batch)
            else:
                res = dict((w["id"], (None, "call")) for w in batch)
            for w in batch:
                items, reason = res[w["id"]]
                row = {"window_id": w["id"], "window_sha256": window_key(w), "cached": False,
                       "ok": items is not None, "cost_usd": call.cost_usd, "reason": reason or ""}
                if self.keep_text:
                    row["text"] = call.text
                self.trace.append(row)
                if items is None:
                    st["invalid"] += 1
                    self.warnings.append(_invalid(w, reason))
                    continue
                self.cache.put(NS, self._key(w, sha), [[ln - w["start"], lab, c] for ln, lab, c in items])
                h, low = _hints(items, w, self.min_conf)
                hints.update(h)
                st["low_confidence"] += low

    def _promote(self, sus, hints):
        """Two accepted exemplars of one marker word: its other QS1 lines get the same hint, no call."""
        by_tok = {}
        for s in sus:
            if s["kind"] == "QS1":
                by_tok.setdefault(s["token"], []).append(s["line"])
        for tok, lns in sorted(by_tok.items()):
            ex = [hints[n] for n in lns if n in hints and hints[n][0] == "question_start"]
            if len(ex) < 2:
                continue
            conf = min(c for _l, c in ex)
            for n in lns:
                hints.setdefault(n, ("question_start", conf))
            self.warnings.append({"level": "warning", "code": "boundary_ai_marker", "origin": "ai",
                                  "token": tok, "count": len(lns),
                                  "message": "marker word %r accepted for %d line(s); add it to "
                                  "segment._Q to stop asking" % (tok, len(lns))})


def make_real_ask(model, timeout_s, cwd, runner=None):
    """ask(prompt) through the Claude CLI (tools off, empty cwd); the only real call site."""
    extra = {"runner": runner} if runner else {}
    return lambda prompt: claude.run_claude(prompt, model=model, timeout_s=timeout_s, cwd=cwd, **extra)


def report_warnings(rep):
    """segment's decision records -> warnings (rule overrules are one info line)."""
    out, over = [], 0
    for r in rep:
        if r["code"] == "boundary_ai_overruled":
            over += 1
            continue
        if r["code"] == "boundary_ai_applied":
            text = "line %d taken as %s (AI hint, confidence %.2f)" % (r["line"], r["label"], r["conf"])
        elif r["code"] == "boundary_ai_rejected":
            text = "line %d: AI hint %s rejected (%s)" % (r["line"], r["label"], r.get("reason", ""))
        else:
            text = "line %d looks like a new subject title; Subject unchanged" % r["line"]
        out.append({"level": "warning", "code": r["code"], "message": text, "line": r["line"],
                    "label": r["label"], "conf": r["conf"], "origin": "ai"})
    if over:
        out.append({"level": "info", "code": "boundary_ai_overruled", "origin": "ai",
                    "message": "%d AI hint(s) ignored: a strong rule match wins" % over})
    return out


def segment_reviewed(config, lines, page_of=None, starts=None):
    """-> (intro, questions, ok, warnings): segment.segment, with AI hints when config["boundary"]."""
    rv = (config or {}).get("boundary")
    if rv is None:
        intro, qs, ok = segment.segment(lines, starts=starts)
        return intro, qs, ok, []
    hints = rv(lines, page_of)
    rep = []
    intro, qs, ok = segment.segment(lines, hints, rep, starts)
    return intro, qs, ok, list(rv.warnings) + report_warnings(rep)


def trace_lines(rows):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
