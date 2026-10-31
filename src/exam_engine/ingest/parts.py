"""Exam / answer-key parts of a document and page selection (heuristics on headings, vi/en)."""
import copy
import re

from exam_engine.ingest import segment
from exam_engine.ingest.schema import IngestError
from exam_engine.utils.text import fold

_KEY = re.compile(r"(huong dan giai|dap an|loi giai|answer key|solutions?|marking scheme)\b")
_HEAD_BLOCKS = 6


def _starts_key(page):
    for blk in page.get("blocks", ())[:_HEAD_BLOCKS]:
        if _KEY.match(fold(blk.get("text", ""))):
            return True
    return False


def find_parts(doc):
    """-> [{kind, pages:[first,last]}]: pages from the first key heading on are the key."""
    pages = doc.get("pages") or []
    parts, cur = [], None
    in_key = False
    for page in pages:
        in_key = in_key or _starts_key(page)
        kind = "answer_key" if in_key else "exam"
        n = page["n"]
        if cur is not None and cur["kind"] == kind:
            cur["pages"][1] = n
        else:
            cur = {"kind": kind, "pages": [n, n]}
            parts.append(cur)
    return parts


def has_key(doc):
    found = doc["parts"] if "parts" in doc else find_parts(doc)
    return any(p.get("kind") == "answer_key" for p in found)


def parse_pages(spec):
    """'1-4' / '1,3,5-6' -> sorted page numbers; IngestError('invalid_pages') on bad input."""
    out = set()
    for item in str(spec or "").split(","):
        m = re.match(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*$", item)
        if not m:
            raise IngestError("invalid_pages", "bad page spec %r (use 1-4 or 1,3,5-6)" % spec)
        lo = int(m.group(1))
        hi = int(m.group(2) or lo)
        if lo < 1 or hi < lo:
            raise IngestError("invalid_pages", "bad page range %r" % item.strip())
        out.update(range(lo, hi + 1))
    return sorted(out)


def select_pages(doc, spec):
    """Copy of `doc` keeping only the pages in `spec` (original numbers kept)."""
    want = parse_pages(spec)
    have = [p["n"] for p in doc["pages"]]
    bad = [n for n in want if n not in have]
    if bad:
        raise IngestError("invalid_pages", "page(s) %s not in the document (pages %s-%s)"
                          % (", ".join(map(str, bad)), min(have), max(have)))
    new = copy.deepcopy(doc)
    new["pages"] = [p for p in new["pages"] if p["n"] in want]
    keep_ids = set(b["asset"] for p in new["pages"] for b in p["blocks"] if b.get("asset"))
    new["assets"] = [a for a in new["assets"] if a["id"] in keep_ids]
    new["warnings"] = [w for w in new["warnings"] if w.get("page") in (None,) + tuple(want)
                       and w["code"] not in ("no_question_numbering", "segmentation_skipped",
                                        "numbering_gap", "numbering_restarted")]
    new.pop("questions", None)
    new.pop("intro", None)
    if new["source"].get("format") != "md":
        lines = []
        for p in new["pages"]:
            for b in p["blocks"]:
                if b["type"] == "paragraph":
                    lines.extend(b["text"].split("\n"))
        intro, qs, ok = segment.segment(lines)
        if ok or segment.numbering(qs)["usable"]:
            new["questions"], new["intro"] = qs, "\n".join(intro).strip()
            new["warnings"].extend({"level": "warning", "code": c, "message": m}
                                   for c, m in ([] if ok else segment.numbering_warnings(qs)))
        else:
            code = "segmentation_skipped" if qs else "no_question_numbering"
            new["warnings"].append({"level": "warning", "code": code,
                                    "message": "question numbering not usable after page selection"})
            new["warnings"].extend({"level": "warning", "code": c, "message": m}
                                   for c, m in segment.numbering_warnings(qs))
    new["warnings"].append({"level": "info", "code": "pages_selected",
                            "message": "pages %s of %d kept" % (spec, len(have))})
    new["parts"] = find_parts(new)
    return new
