"""Question segmentation shared by adapters: numbering and options from plain text lines."""
import re
import types

from exam_engine.utils import langtable

_OPT = re.compile(r"^\s*([A-D])\s*[.)]\s*(.*)$")


def build(table):
    """Compiled start/group/part regexes: the vi+en literals plus the words of an extra-language table
    (utils/langtable). An empty table gives today's patterns byte for byte."""
    q = langtable.alt("(?:Câu|Cau|Question)", "question", table)
    grp = langtable.alt(r"(?:Questions?|[Cc]âu(?:\s*hỏi)?)", "group", table)
    rng = langtable.alt("(?:-|–|đến|to)", "range", table)
    lead = langtable.alt("(?:Dựa vào|Đọc|Hãy đọc|Based on|Read|Use|Study)", "intro", table)
    part = langtable.alt("(?:PH[ẦA]N|PART)", "part", table)
    span = (grp + r"\s*(?:từ\s*)?(\d+)"
            r"(?:\s*" + rng + r"\s*(?:[Cc]âu\s*)?(\d+)|\s+and\s+(\d+)|((?:\s*,\s*\d+)+))")
    # intro only: group word in any case (`CÂU 31 - 35`, `Cau`); scoped so the lead words stay case-sensitive
    grp_i = "(?i:" + langtable.alt(r"(?:Questions?|C[aâ]u(?:\s*hỏi)?)", "group", table) + ")"
    span_i = span.replace(grp, grp_i, 1)
    return types.SimpleNamespace(
        _Q=re.compile(r"^\s*(?:" + q + r"\s*(\d+)\s*[.:)]?|(\d+)(?!\.\d)\s*[.)])\s*(.*)$", re.I),  # `3.1.` is a sub-number, not question 3
        # a group passage intro ("Questions 46-52 ...") or a part heading is not part of option D
        # forms: `N-M`, `N đến (câu )M`, `N to M`, `N and M`, `N, M(, K)`; read the span with group_span()
        GROUP_RE=re.compile(span),
        # opens a context only at the line start (short prefix allowed), so a wrapped option that
        # mentions "câu 3-5" stays in option D
        _INTRO=re.compile(r"^\s*(?:" + lead + r"\b[^\n]{0,120}?)?" + span_i),
        _PART=re.compile(r"^\s*" + part + r"\s+(IV|V|I{1,3})\b", re.I),  # as refine.PART_RE (refine imports this module)
        # a heading that must not be glued into option D: Roman or Arabic part heading
        _PART_ANY=re.compile(r"^\s*" + part + r"\s+(?:IV|V|I{1,3}|\d{1,2})\b", re.I),
        part_word=part,
        # group word in any case, with or without diacritics (`Cau 2 - 3`, "answer questions 5-7")
        GROUP_ANY=re.compile(span_i, re.I))


_NS = build(langtable.load())
_Q, GROUP_RE, _INTRO, _PART, _PART_ANY = _NS._Q, _NS.GROUP_RE, _NS._INTRO, _NS._PART, _NS._PART_ANY
PART_WORD = _NS.part_word


def group_span(m):
    """(first, last) question numbers of a GROUP_RE match; a list form spans min..max."""
    nums = [int(m.group(1))] + [int(n) for n in re.findall(r"\d+", m.group(4) or "")]
    nums += [int(g) for g in m.group(2, 3) if g]
    return min(nums), max(nums)
_READ = re.compile(r"^\s*(?:Read|Study|Use)\s+the\s+(?:following\s+)?(?:passage|text|article)\b", re.I)
# an unseen question-start word: `Bài 3:`, `Item 3)`, `Q3.` (token, number, rest); boundary.py suspects
MARK = re.compile(r"^\s*(\S{1,12}?)\s*(\d{1,3})\s*[.:)\]–-]\s*(\S.*)$")
_KEYS = ["A", "B", "C", "D"]
_ENDS = ("passage", "section_start", "subject_start", "question_end")


def _q_start(line):
    """_Q match unless the line is a group intro (`Câu 31-35: Đọc ...`), which is context."""
    return None if _INTRO.match(line) else _Q.match(line)


def _opens_next(line, n):
    """A part heading, or a group intro starting at question n+1: never the stem of question n."""
    if _PART_ANY.match(line):
        return True
    m = _INTRO.match(line)
    return bool(m) and group_span(m)[0] == n + 1


def _next_n(lines, i):
    for ln in lines[i:]:
        m = _q_start(ln)
        if m:
            return int(m.group(1) or m.group(2))
    return None


def _implausible(n, prev, later):
    """True when start number n breaks the sequence (n != prev+1) while prev+1 still starts a
    later line, unless n == 1 opens a run that counts up to prev first (a section restart)."""
    run = 1 if n == 1 else None
    for x in later:
        if x == prev + 1:
            return run != prev
        if run is not None and x == run + 1:
            run = x
    return False


def _after(nums, k):
    for j in range(k + 1, len(nums)):  # no slice copy: the check stops at the first prev+1
        yield nums[j]


_SUBHEAD = re.compile(r"^\s*\d+\.\d+\.?\s+\S")
_ENUM = re.compile(r"^(?:([IVXLC]{1,4})|([A-Z])|(\d{1,2}))[.)]\s+\S")  # `I. X`, `B. Y`, `3. Z`
GROUP_ANY = _NS.GROUP_ANY


def _mostly_upper(line):
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) >= 0.6 * len(letters)


def _is_heading_line(line):
    """A section heading: `PHẦN 1: ...`, or `1.2. TIẾNG ANH` (short, mostly upper), or a bare
    upper-case line naming a subject (router.heading_subject)."""
    s = line.strip()
    if _PART_ANY.match(s):
        return True
    if _SUBHEAD.match(s) or _ENUM.match(s):
        return len(s) <= 60 and _mostly_upper(s)
    if s and len(s) <= 40 and s == s.upper() and any(c.isalpha() for c in s):
        from exam_engine.pipeline import router  # lazy: ingest does not depend on pipeline at import
        fn = getattr(router, "heading_subject", None)
        return bool(fn and fn(s))
    return False


def heading_kind(line):
    """Level family of a heading line: part, sub (`1.2.`), roman, letter, arabic, else subject."""
    s = line.strip()
    if _PART_ANY.match(s):
        return "part"
    if _SUBHEAD.match(s):
        return "sub"
    m = _ENUM.match(s)
    if m:
        if m.group(1) and (len(m.group(1)) > 1 or m.group(1) in "IVX"):
            return "roman"
        return "letter" if m.group(1) or m.group(2) else "arabic"
    return "subject"


def push_heading(stack, line):
    """Section stack after `line`: pops down to and including the last entry of its kind, then pushes."""
    kind = heading_kind(line)
    for i in range(len(stack) - 1, -1, -1):
        if stack[i][0] == kind:
            del stack[i:]
            break
    stack.append((kind, line.strip()))


_BANK = re.compile(r"^[A-E][.)]\s+\S")  # an answer-option label line, any case


def _next_line(lines, i):
    return next((ln for ln in lines[i + 1:] if ln.strip()), "")


def _enum_bank(lines, i):
    """True when lines[i] is an `A.`-`E.` label that starts or continues a run of option labels:
    in doubt it is an option, never a heading (the choices must not be deleted)."""
    s = lines[i].strip()
    return bool(_BANK.match(s)) and bool(_BANK.match(_next_line(lines, i).strip()))


def split_heading(context):
    """-> (headings, rest): leading heading lines peeled off a question context; stops at the
    first non-heading line (guide or passage, so an upper-case passage title stays) or at an
    option bank (`A. x` / `B. y` lines)."""
    lines = (context or "").split("\n")
    heads, i = [], 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
        elif _is_heading_line(lines[i]) and not _enum_bank(lines, i):
            heads.append(lines[i].strip())
            i += 1
        else:
            break
    return heads, "\n".join(lines[i:]).strip("\n") if heads else (context or "")


def ambiguous_heading(context):
    """True when the first line looks like an enumerated heading but is kept because it opens an option bank."""
    lines = (context or "").split("\n")
    i = next((k for k, ln in enumerate(lines) if ln.strip()), None)
    return i is not None and bool(_ENUM.match(lines[i].strip())) and _is_heading_line(lines[i]) \
        and _enum_bank(lines, i)


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


def segment(lines, hints=None, report=None, starts=None):
    """-> (intro_lines, questions, ok). questions: [{n, text, options}].

    ok only when numbering is consecutive from 1 and every question has text; the source
    text is never corrected.

    starts, when a list, receives the start line index of each question (parallel to the result).

    hints {line index: (label, confidence)} (boundary.py, AI origin) are consulted only at those
    lines and only where the rules are silent: a strong rule match always wins, a start that
    breaks the numbering is rejected. Every decision is appended to `report` (dicts with code
    boundary_ai_applied / _rejected / _overruled / _subject). hints=None is the plain rule result.
    """
    hints = hints or {}
    rep = report if report is not None else []
    intro, qs, pending = [], [], []
    closed = False  # a question_end hint: later free lines are context of the next question
    st = starts if starts is not None else []

    def note(code, i, hint, **extra):
        rep.append(dict(extra, code=code, line=i, label=hint[0], conf=hint[1]))

    cand = [(i, int(m.group(1) or m.group(2))) for i, ln in enumerate(lines)
            for m in (_q_start(ln),) if m]
    nums = [n for _, n in cand]
    pos = {i: k for k, (i, _) in enumerate(cand)}

    for i, line in enumerate(lines):
        hint = hints.get(i) if qs else None
        m = _q_start(line)
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
                    if pending:  # an open context owns the line, not the last option
                        pending.append(line.strip())
                    elif qs[-1]["options"]:
                        qs[-1]["options"][-1]["text"] += " " + line.strip()
                    else:
                        qs[-1]["text"] = (qs[-1]["text"] + " " + line.strip()).strip()
                    continue
            if qs and n != qs[-1]["n"] + 1 and _implausible(n, qs[-1]["n"], _after(nums, pos[i])):
                if hint:
                    note("boundary_ai_rejected", i, hint, reason="numbering")
                hint = None  # text, not a start: falls to the free-line path below
                m = None
        if m:
            qs.append({"n": n, "text": m.group(3).strip(), "options": []})
            st.append(i)
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
                    st.append(i)
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
                    if hint[0] == "question_end" and not pending:
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
            elif not qs[-1]["options"] and _opens_next(line, qs[-1]["n"]):
                pending.append(line.strip())  # option-less question: a heading/intro is the next one's context
            elif qs[-1]["options"]:
                qs[-1]["options"][-1]["text"] += " " + line.strip()
            else:
                qs[-1]["text"] = (qs[-1]["text"] + " " + line.strip()).strip()
    if pending:  # no question follows: nothing to attach to, keep the text as before
        if qs[-1]["options"]:
            qs[-1]["options"][-1]["text"] += " " + " ".join(pending)
        else:
            qs[-1]["text"] = (qs[-1]["text"] + " " + " ".join(pending)).strip()
    rs = runs(qs)
    if _is_cover_run(qs, rs, lines, st):
        k = len(rs[0])
        n_ctx = len(qs[k]["context"].split("\n")) if qs[k].get("context") else 0
        intro = lines[:_ctx_start(lines, st[k], n_ctx)]
        qs = qs[k:]
        st[:] = st[k:]
    for q in qs:
        if not q["text"]:
            q["unreadable"] = True  # an image-only question: kept, declined downstream as missing_text
    ok = bool(qs) and [q["n"] for q in qs] == list(range(1, len(qs) + 1)) \
        and all(q["text"] for q in qs)
    return intro, qs, ok


def _ctx_start(lines, end, n):
    """Line index where the n non-blank lines just before `end` begin (end itself when n == 0)."""
    i = end
    while n > 0 and i > 0:
        i -= 1
        if lines[i].strip():
            n -= 1
    return i


def _is_cover_run(qs, rs, lines, st):
    """A leading option-less run (cover headings `1`, `2`) before the real section 1: it is
    shorter than the next run, the next run has options, and only the next one opens under a part heading."""
    if len(rs) < 2 or len(rs[0]) >= len(rs[1]):
        return False
    k, k2 = len(rs[0]), len(rs[0]) + len(rs[1])
    if any(q["options"] for q in qs[:k]) or not any(q["options"] for q in qs[k:k2]):
        return False
    before = [ln for ln in lines[:st[0]] if ln.strip()]  # the first question has no context: its heading is intro
    return not (before and _is_heading_line(before[-1])) \
        and not split_heading(qs[0].get("context", ""))[0] \
        and bool(split_heading(qs[k].get("context", ""))[0])


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
    sane = bool(qs) and all(q["text"] or q.get("unreadable") for q in qs) \
        and any(q["text"] for q in qs) and all(1 <= n <= MAX_N for n in flat)
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
