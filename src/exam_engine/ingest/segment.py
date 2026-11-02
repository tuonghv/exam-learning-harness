"""Question segmentation shared by adapters: numbering and options from plain text lines."""
import re

_Q = re.compile(r"^\s*(?:(?:Câu|Cau|Question)\s*(\d+)\s*[.:)]?|(\d+)(?!\.\d)\s*[.)])\s*(.*)$", re.I)  # `3.1.` is a sub-number, not question 3
_OPT = re.compile(r"^\s*([A-D])\s*[.)]\s*(.*)$")
# a group passage intro ("Questions 46-52 ...") or a part heading is not part of option D
# forms: `N-M`, `N đến (câu )M`, `N to M`, `N and M`, `N, M(, K)`; read the span with group_span()
GROUP_RE = re.compile(r"(?:Questions?|[Cc]âu(?:\s*hỏi)?)\s*(?:từ\s*)?(\d+)"
                      r"(?:\s*(?:-|–|đến|to)\s*(?:[Cc]âu\s*)?(\d+)|\s+and\s+(\d+)|((?:\s*,\s*\d+)+))")


def group_span(m):
    """(first, last) question numbers of a GROUP_RE match; a list form spans min..max."""
    nums = [int(m.group(1))] + [int(n) for n in re.findall(r"\d+", m.group(4) or "")]
    nums += [int(g) for g in m.group(2, 3) if g]
    return min(nums), max(nums)
# opens a context only at the line start (short prefix allowed), so a wrapped option that
# mentions "câu 3-5" stays in option D
_INTRO = re.compile(r"^\s*(?:(?:Dựa vào|Đọc|Hãy đọc|Based on|Read|Use|Study)\b[^\n]{0,120}?)?"
                    r"(?:Questions?|[Cc]âu(?:\s*hỏi)?)\s*(?:từ\s*)?\d+\s*(?:-|–|đến|to)\s*\d+")
_READ = re.compile(r"^\s*(?:Read|Study|Use)\s+the\s+(?:following\s+)?(?:passage|text|article)\b", re.I)
_PART = re.compile(r"^\s*PH[ẦA]N\s+(IV|V|I{1,3})\b", re.I)  # as refine.PART_RE (refine imports this module)


# a heading that must not be glued into option D: Roman or Arabic PHẦN / PART (the Roman-only _PART
# stays equal to refine.PART_RE, which strips the heading from a context)
_PART_ANY = re.compile(r"^\s*(?:PH[ẦA]N|PART)\s+(?:IV|V|I{1,3}|\d{1,2})\b", re.I)
# an unseen question-start word: `Bài 3:`, `Item 3)`, `Q3.` (token, number, rest); boundary.py suspects
MARK = re.compile(r"^\s*(\S{1,12}?)\s*(\d{1,3})\s*[.:)\]–-]\s*(\S.*)$")
_KEYS = ["A", "B", "C", "D"]
_ENDS = ("passage", "section_start", "subject_start", "question_end")


def _next_n(lines, i):
    for ln in lines[i:]:
        m = _Q.match(ln)
        if m:
            return int(m.group(1) or m.group(2))
    return None


_SUBHEAD = re.compile(r"^\s*\d+\.\d+\.?\s+\S")


def _mostly_upper(line):
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) >= 0.6 * len(letters)


def _is_heading_line(line):
    """A section heading: `PHẦN 1: ...`, or `1.2. TIẾNG ANH` (short, mostly upper), or a bare
    upper-case line naming a subject (router.heading_subject)."""
    s = line.strip()
    if _PART_ANY.match(s):
        return True
    if _SUBHEAD.match(s):
        return len(s) <= 60 and _mostly_upper(s)
    if s and len(s) <= 40 and s == s.upper() and any(c.isalpha() for c in s):
        from exam_engine.pipeline import router  # lazy: ingest does not depend on pipeline at import
        fn = getattr(router, "heading_subject", None)
        return bool(fn and fn(s))
    return False


def split_heading(context):
    """-> (headings, rest): leading heading lines peeled off a question context; stops at the
    first non-heading line (guide or passage, so an upper-case passage title stays)."""
    lines = (context or "").split("\n")
    heads, i = [], 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
        elif _is_heading_line(lines[i]):
            heads.append(lines[i].strip())
            i += 1
        else:
            break
    return heads, "\n".join(lines[i:]).strip("\n") if heads else (context or "")


def split_guide(rest):
    """-> (guide, passage): a leading `Questions 31-35: ...` / `Read the following passage` line is the guide."""
    first, _, tail = (rest or "").partition("\n")
    if first.strip() and (_INTRO.match(first) or _READ.match(first)):
        return first.strip(), tail.strip("\n")
    return "", rest or ""


def _is_subheading(lines, i):
    """`3.2 TITLE` (<= 60 chars, mostly upper case) whose next non-empty line opens a group or a question."""
    line = lines[i]
    if not _SUBHEAD.match(line) or len(line.strip()) > 60:
        return False
    if not _mostly_upper(line):  # a heading is mostly upper case; "1.5 m/s" is a tail
        return False
    nxt = next((ln for ln in lines[i + 1:] if ln.strip()), "")
    return bool(_Q.match(nxt) or _INTRO.match(nxt) or _READ.match(nxt) or _PART_ANY.match(nxt))


def _hint_start(line, qs, lines, i):
    """-> (n, text) for a question_start hint that keeps the numbering consecutive, else None."""
    prev = qs[-1]["n"]
    m = MARK.match(line)
    if m:
        return (prev + 1, m.group(3).strip()) if int(m.group(2)) == prev + 1 else None
    if [o["key"] for o in qs[-1]["options"]] != _KEYS:
        return None
    nxt = _next_n(lines, i + 1)
    if nxt is None or nxt == prev + 2:  # an unmarked stem that closes the gap exactly
        return prev + 1, line.strip()
    return None


def segment(lines, hints=None, report=None):
    """-> (intro_lines, questions, ok). questions: [{n, text, options}].

    ok only when numbering is consecutive from 1 and every question has text; the source
    text is never corrected.

    hints {line index: (label, confidence)} (boundary.py, AI origin) are consulted only at those
    lines and only where the rules are silent: a strong rule match always wins, a start that
    breaks the numbering is rejected. Every decision is appended to `report` (dicts with code
    boundary_ai_applied / _rejected / _overruled / _subject). hints=None is the plain rule result.
    """
    hints = hints or {}
    rep = report if report is not None else []
    intro, qs, pending = [], [], []
    closed = False  # a question_end hint: later free lines are context of the next question

    def note(code, i, hint, **extra):
        rep.append(dict(extra, code=code, line=i, label=hint[0], conf=hint[1]))

    for i, line in enumerate(lines):
        hint = hints.get(i) if qs else None
        m = _Q.match(line)
        if m:
            n = int(m.group(1) or m.group(2))
            if hint and n == qs[-1]["n"] + 1:
                if hint[0] != "question_start":
                    note("boundary_ai_overruled", i, hint)
            elif hint and n != 1 and hint[0] != "question_start" \
                    and _next_n(lines, i + 1) == qs[-1]["n"] + 1:
                # a weak `2)` / `3.1.` that is no question: the numbering resumes right after it
                if hint[0] in ("passage", "section_start", "subject_start") and qs[-1]["options"]:
                    note("boundary_ai_applied", i, hint)
                    pending.append(line.strip())
                    continue
                if hint[0] in ("other", "option_continuation"):
                    note("boundary_ai_applied", i, hint)
                    if qs[-1]["options"]:
                        qs[-1]["options"][-1]["text"] += " " + line.strip()
                    else:
                        qs[-1]["text"] = (qs[-1]["text"] + " " + line.strip()).strip()
                    continue
            qs.append({"n": n, "text": m.group(3).strip(), "options": []})
            closed = False
            if pending:
                qs[-1]["context"] = "\n".join(pending)
                pending = []
            continue
        if not qs:
            intro.append(line)
            continue
        strong = _OPT.match(line) or _INTRO.match(line) or _READ.match(line) or _PART_ANY.match(line)
        if hint and strong:
            natural = ("other", "option_continuation") if _OPT.match(line) \
                else ("passage", "section_start", "subject_start")
            if hint[0] not in natural:
                note("boundary_ai_overruled", i, hint)
        elif hint and line.strip():
            if hint[0] == "question_start":
                got = _hint_start(line, qs, lines, i)
                if got is None:
                    note("boundary_ai_rejected", i, hint, reason="numbering")
                else:
                    qs.append({"n": got[0], "text": got[1], "options": []})
                    closed = False
                    if pending:
                        qs[-1]["context"] = "\n".join(pending)
                        pending = []
                    note("boundary_ai_applied", i, hint)
                    continue
            elif hint[0] in _ENDS:
                if not qs[-1]["options"]:
                    note("boundary_ai_rejected", i, hint, reason="no_options")
                else:
                    note("boundary_ai_applied", i, hint)
                    if hint[0] == "subject_start":
                        note("boundary_ai_subject", i, hint)
                    if hint[0] == "question_end":
                        qs[-1]["options"][-1]["text"] += " " + line.strip()
                        closed = True
                    else:
                        pending.append(line.strip())
                    continue
        if pending:
            if line.strip():
                pending.append(line.strip())
            continue
        o = _OPT.match(line)
        if o:
            qs[-1]["options"].append({"key": o.group(1), "text": o.group(2).strip()})
        elif line.strip():
            if qs[-1]["options"] and (closed or _INTRO.match(line) or _READ.match(line)
                                      or _PART_ANY.match(line) or _is_subheading(lines, i)):
                pending.append(line.strip())
            elif qs[-1]["options"]:
                qs[-1]["options"][-1]["text"] += " " + line.strip()
            else:
                qs[-1]["text"] = (qs[-1]["text"] + " " + line.strip()).strip()
    if pending:  # no question follows: nothing to attach to, keep the text as before
        qs[-1]["options"][-1]["text"] += " " + " ".join(pending)
    ok = bool(qs) and [q["n"] for q in qs] == list(range(1, len(qs) + 1)) \
        and all(q["text"] for q in qs)
    return intro, qs, ok


MAX_N = 999  # a larger "question number" is a year or a stray figure, never a question


def ranges(nums):
    """[2, 3, 4, 9] -> "2-4, 9"."""
    out, nums = [], sorted(nums)
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else "%d-%d" % (nums[i], nums[j]))
        i = j + 1
    return ", ".join(out)


def runs(qs):
    """Question numbers split into runs; a new run starts at each n == 1 after the first."""
    out = []
    for q in qs:
        if not out or q["n"] == 1:
            out.append([])
        out[-1].append(q["n"])
    return out


def _span(run):
    """Run as printed, consecutive stretches compacted: [1,2,3,6] -> "1-3, 6"; [3,2,1] -> "3, 2, 1"."""
    out, i = [], 0
    while i < len(run):
        j = i
        while j + 1 < len(run) and run[j + 1] == run[j] + 1:
            j += 1
        out.append(str(run[i]) if i == j else "%d-%d" % (run[i], run[j]))
        i = j + 1
    return ", ".join(out)


def numbering(qs):
    """-> {usable, runs, missing}: numbering that keeps the questions found (gaps / restarts).

    usable: every question has text, numbers in 1..MAX_N, and either one strictly increasing
    run (gaps allowed) or several runs that each count 1..k. missing: [[run_idx, "2-149"], ...].
    """
    rs = runs(qs)
    flat = [n for r in rs for n in r]
    sane = bool(qs) and all(q["text"] for q in qs) and all(1 <= n <= MAX_N for n in flat)
    if len(rs) == 1:
        usable = sane and all(a < b for a, b in zip(rs[0], rs[0][1:]))
    else:
        usable = sane and all(r == list(range(1, len(r) + 1)) for r in rs)
    missing = []
    for i, r in enumerate(rs):
        if len(set(r)) == len(r):
            gone = sorted(set(range(1, max(r) + 1)) - set(r))
            if gone:
                missing.append([i, ranges(gone)])
    return {"usable": usable, "runs": rs, "missing": missing}


def numbering_warnings(qs):
    """[(code, message)] for the adapters: numbering_gap and / or numbering_restarted."""
    info = numbering(qs)
    out = []
    if len(info["runs"]) > 1:
        out.append(("numbering_restarted", "numbering restarts at 1: %d sections (%s)"
                    % (len(info["runs"]), ", ".join(_span(r) for r in info["runs"]))))
    if info["usable"] and info["missing"]:
        if len(info["runs"]) == 1:
            msg = "missing question numbers: %s" % info["missing"][0][1]
        else:
            msg = "; ".join("section %d: missing %s" % (i + 1, m) for i, m in info["missing"])
        out.append(("numbering_gap", msg))
    return out
