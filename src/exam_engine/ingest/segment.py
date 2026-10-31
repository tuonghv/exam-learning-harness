"""Question segmentation shared by adapters: numbering and options from plain text lines."""
import re

_Q = re.compile(r"^\s*(?:(?:Câu|Cau|Question)\s*(\d+)\s*[.:)]?|(\d+)\s*[.)])\s*(.*)$", re.I)
_OPT = re.compile(r"^\s*([A-D])\s*[.)]\s*(.*)$")
# a group passage intro ("Questions 46-52 ...") or a part heading is not part of option D
GROUP_RE = re.compile(r"(?:Questions?|Câu|câu)\s*(?:từ\s*)?(\d+)\s*(?:-|–|đến|to)\s*(\d+)")
_PART = re.compile(r"^\s*PH[ẦA]N\s+(IV|V|I{1,3})\b", re.I)  # as refine.PART_RE (refine imports this module)


def segment(lines):
    """-> (intro_lines, questions, ok). questions: [{n, text, options}].

    ok only when numbering is consecutive from 1 and every question has text; the source
    text is never corrected.
    """
    intro, qs, pending = [], [], []
    for line in lines:
        m = _Q.match(line)
        if m:
            qs.append({"n": int(m.group(1) or m.group(2)), "text": m.group(3).strip(),
                       "options": []})
            if pending:
                qs[-1]["context"] = "\n".join(pending)
                pending = []
            continue
        if not qs:
            intro.append(line)
            continue
        if pending:
            if line.strip():
                pending.append(line.strip())
            continue
        o = _OPT.match(line)
        if o:
            qs[-1]["options"].append({"key": o.group(1), "text": o.group(2).strip()})
        elif line.strip():
            if qs[-1]["options"] and (GROUP_RE.search(line) or _PART.match(line)):
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
