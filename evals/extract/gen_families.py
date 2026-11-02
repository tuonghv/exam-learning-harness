"""Synthetic completeness fixtures F1-F8 (REQ-0050, phase 46): 25 questions each, synthetic text only.

F1 single page | F2 stem over 2 pages | F3 options on the next page | F4 passage over 3 pages + group of 3 |
F5 figure stand-in on the next page | F6 many questions per page | F7 formula cut at the break |
F8 header/footer/page number on every page (+ stem over 2 pages).
Layout arithmetic (gold_pdf split layout): CAP lines per page; a block of n lines takes n + 1 (gap).
Usage: python3 -I evals/extract/gen_families.py OUTDIR  -> OUTDIR/F1.gold.json ... F8.gold.json + families.json
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.pipeline import gold_pdf  # noqa: E402

CAP = (gold_pdf.PAGE_H - 2 * gold_pdf.MARGIN) // gold_pdf.LEAD  # 53 lines per page
N = 25
LAYOUT = {"F1": "block", "F6": "block"}  # the others cross the page at a line
FURNITURE = ("F8",)


WORDS = ("lực", "khối", "nhiệt", "sóng", "điện", "từ", "quang", "hạt", "năng", "áp", "suất", "dòng", "thế",
         "ánh", "sáng", "phân", "tử", "hóa", "trị", "tốc", "độ", "quãng", "đường", "gia", "tăng", "chu", "kỳ",
         "tần", "số", "biên", "pha", "dao", "động", "lò", "xo", "con", "lắc", "đơn", "mạch", "tụ", "cuộn")


def _line(tag, qid, j):
    """A short Vietnamese-like line that differs from every other line beyond digits: the text route drops
    lines that repeat at page edges as furniture, which is not what these fixtures measure."""
    h = (qid * 7919 + j * 104729) % 1000003
    ws = []
    for _ in range(5):
        h = (h * 48271 + 11) % 2147483647
        ws.append(WORDS[h % len(WORDS)])
    return "Xét %s %s %s %s %s (%s%d.%d)" % (ws[0], ws[1], ws[2], ws[3], ws[4], tag, qid, j + 1)


def _q(qid, stem_lines, formula="", fig=False, tag="x"):
    """One question whose block has stem_lines stem lines (+ formula lines + 4 options)."""
    text = "\n".join(_line(tag, qid, j) for j in range(stem_lines))
    return {"id": str(qid), "text": text, "formula": formula,
            "options": dict((k, "phương án %s%d%s" % (tag, qid, k.lower())) for k in "ABCD"),
            "figures": [1] if fig else []}


def _lines(q):
    return len(q["text"].split("\n")) + (len(q["formula"].split("\n")) if q["formula"] else 0) + 4


class _Plan:
    """Builds questions while tracking the line fill of the current page (split layout)."""

    def __init__(self, tag):
        self.tag, self.qs, self.used = tag, [], 0

    def add(self, stem, formula="", fig=False):
        q = _q(len(self.qs) + 1, stem, formula, fig, self.tag)
        if fig:  # the stem points at the figure, as an exam does
            q["text"] += "\nQuan sát hình vẽ bên dưới để trả lời."
        self.qs.append(q)
        for _ in range(_lines(q)):
            if self.used >= CAP:
                self.used = 0
            self.used += 1
        if fig:
            if self.used + 5 > CAP:  # a figure needs 5 free lines (64 pt)
                self.used = 0
            self.used += 5  # 70 pt of figure
        self.used += 1  # gap after the block
        return q

    def fill_to(self, left):
        """Add one single-page filler so that `left` lines stay free on the page."""
        free = CAP - self.used if self.used < CAP else CAP
        stem = free - left - 5  # stem + 4 options + 1 gap line = free - left
        if stem < 1:
            raise ValueError("cannot leave %d lines (free %d)" % (left, free))
        self.add(stem)

    def close(self):
        """Filler that uses the rest of the page, so the next block starts at its top."""
        free = CAP - self.used if self.used < CAP else 0
        if free >= 6:
            self.add(free - 5)


def _units(tag, cut, formula="", fig=False, stem=4):
    """A, T, B per unit: T is cut by the page break after `cut` of its own lines."""
    p = _Plan(tag)
    while len(p.qs) + 3 <= N:
        p.fill_to(cut)
        p.add(stem, formula, fig)
        p.close()
    while len(p.qs) < N:
        p.add(1)
    return p.qs


def f2(tag="a"):
    return _units(tag, 3, stem=6)  # 3 stem lines before the break, 3 + options after


def f3():
    return _units("c", 2, stem=2)  # the whole stem fits, the options are on the next page


def f5():
    p = _Plan("e")
    while len(p.qs) + 3 <= N:
        p.fill_to(7)  # stem 2 + options 4 = 6 of the 7 free lines; the figure (5 lines) lands on the next page
        p.add(1, fig=True)
        p.close()
    while len(p.qs) < N:
        p.add(1)
    return p.qs


def f7():
    return _units("g", 2, formula="x^{2}+3x\n=7+y_{1}", stem=1)  # the break falls inside the two formula lines


def f4():
    p = _Plan("d")
    while len(p.qs) + 3 <= N:
        p.add(110)  # the passage: over 3 pages; first question of the group
        p.add(1)
        p.add(1)
        p.close()
    while len(p.qs) < N:
        p.add(1)
    return p.qs


def f1():
    return [_q(i, 1, tag="b") for i in range(1, N + 1)]


def f6():
    return [_q(i, 1, tag="f") for i in range(1, N + 1)]


FAMILIES = {"F1": f1, "F2": f2, "F3": f3, "F4": f4, "F5": f5, "F6": f6, "F7": f7, "F8": lambda: f2("h")}


def write_all(outdir):
    os.makedirs(outdir, exist_ok=True)
    meta = {}
    for name, make in sorted(FAMILIES.items()):
        qs = make()
        assert len(qs) == N, name
        path = os.path.join(outdir, name + ".gold.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"gold_version": "1", "origin": "synthetic", "questions": qs}, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        meta[name] = {"gold": path, "layout": LAYOUT.get(name, "split"), "furniture": name in FURNITURE}
    with open(os.path.join(outdir, "families.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
        fh.write("\n")
    return meta


def main(argv):
    if len(argv) != 1:
        print("usage: gen_families.py OUTDIR", file=sys.stderr)
        return 2
    write_all(argv[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
