"""Question segmentation shared by adapters: numbering and options from plain text lines."""
import re

_Q = re.compile(r"^\s*(?:(?:Câu|Cau|Question)\s*(\d+)\s*[.:)]?|(\d+)\s*[.)])\s*(.*)$", re.I)
_OPT = re.compile(r"^\s*([A-D])\s*[.)]\s*(.*)$")


def segment(lines):
    """-> (intro_lines, questions, ok). questions: [{n, text, options}].

    ok only when numbering is consecutive from 1 and every question has text; the source
    text is never corrected.
    """
    intro, qs = [], []
    for line in lines:
        m = _Q.match(line)
        if m:
            qs.append({"n": int(m.group(1) or m.group(2)), "text": m.group(3).strip(),
                       "options": []})
            continue
        if not qs:
            intro.append(line)
            continue
        o = _OPT.match(line)
        if o:
            qs[-1]["options"].append({"key": o.group(1), "text": o.group(2).strip()})
        elif line.strip():
            if qs[-1]["options"]:
                qs[-1]["options"][-1]["text"] += " " + line.strip()
            else:
                qs[-1]["text"] = (qs[-1]["text"] + " " + line.strip()).strip()
    ok = bool(qs) and [q["n"] for q in qs] == list(range(1, len(qs) + 1)) \
        and all(q["text"] for q in qs)
    return intro, qs, ok
