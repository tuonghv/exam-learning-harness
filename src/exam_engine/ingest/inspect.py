"""Read-only report of what ingestion produced: blocks, warnings, suspicious spots."""
import re

from exam_engine.ingest import parts as partsmod

_OPT_EMPTY = re.compile(r"^[A-D]\.\s*[-—.]?$")
_OK_CHARS = re.compile(r"[\w\s.,;:!?'\"()\[\]{}<>/\\|+\-*=%&@#$^_~`°·–—…’‘“”]", re.U)
DISCLAIMER = "Heuristics, not proof of correctness: check the source file."


def _page_part(doc, n):
    for p in doc.get("parts") or ():
        if p["pages"][0] <= n <= p["pages"][1]:
            return p["kind"]
    return "exam"


def suspicious(doc):
    """-> [{page, block, code, detail}] from block text heuristics plus adapter warnings."""
    out = []
    for page in doc.get("pages", ()):
        n = page["n"]
        for blk in page["blocks"]:
            text = blk.get("text", "")
            lines = [ln for ln in text.split("\n") if ln.strip()]
            if sum(1 for ln in lines if len(ln.strip()) <= 2) >= 6:
                out.append({"page": n, "block": blk["id"], "code": "split_formula",
                            "detail": "6+ very short lines (formula split by extraction)"})
            for ln in lines:
                if _OPT_EMPTY.match(ln.strip()):
                    out.append({"page": n, "block": blk["id"], "code": "option_without_text",
                                "detail": ln.strip()})
            if text.strip():
                bad = sum(1 for c in text if not _OK_CHARS.match(c))
                if bad * 100 > 3 * len(text):
                    out.append({"page": n, "block": blk["id"], "code": "stray_chars",
                                "detail": "%d of %d chars unusual" % (bad, len(text))})
    qs = [q["n"] for q in doc.get("questions") or ()]
    if qs and qs != list(range(1, len(qs) + 1)):
        out.append({"page": None, "block": None, "code": "numbering_gap",
                    "detail": "questions %s" % qs})
    for w in doc.get("warnings", ()):
        out.append({"page": w.get("page"), "block": None, "code": w["code"],
                    "detail": w.get("message", "")})
    return out


def report(doc):
    """Markdown report of `doc`; never changes it."""
    src = doc["source"]
    sus = suspicious(doc)
    parts = doc.get("parts") or partsmod.find_parts(doc)
    L = ["# Ingest report: %s" % src["name"], "",
         "- source: %s (%s, sha256 %s...)" % (src["name"], src["format"], src["sha256"][:12]),
         "- status: %s" % doc["status"],
         "- pages: %d" % len(doc["pages"]),
         "- blocks: %d, assets: %d, warnings: %d, suspicious: %d"
         % (sum(len(p["blocks"]) for p in doc["pages"]), len(doc["assets"]),
            len(doc["warnings"]), len(sus)),
         "- parts: " + (", ".join("%s p%d-%d" % (p["kind"], p["pages"][0], p["pages"][1])
                                 for p in parts) or "none"),
         "- questions found: %d" % len(doc.get("questions") or ())]
    L.append("- per page status: " + ", ".join(
        "p%d=%s" % (p["n"], p.get("status", "-")) for p in doc["pages"]))
    if any(p["kind"] == "answer_key" for p in parts):
        L += ["", "**ANSWER KEY PRESENT**: keep these pages away from the solver "
              "(use --pages with the exam range)."]
    for page in doc["pages"]:
        n = page["n"]
        L += ["", "## Page %d (%s, %s)" % (n, page.get("status", "-"), _page_part(doc, n)), ""]
        for blk in page["blocks"]:
            if blk["type"] == "image":
                body = "asset %s bbox %s" % (blk.get("asset"), blk.get("bbox"))
            else:
                body = blk["text"].replace("\n", "\n  ")
            L.append("- [%s] %s (%s): %s" % (blk["type"], blk["id"], blk["origin"], body))
        for w in doc["warnings"]:
            if w.get("page") == n:
                L.append("- warning %s: %s" % (w["code"], w["message"]))
        for s in sus:
            if s["page"] == n and s["block"]:
                L.append("- suspicious %s (%s): %s" % (s["code"], s["block"], s["detail"]))
    gen = [s for s in sus if s["block"] is None and s["page"] is None]
    if gen:
        L += ["", "## Document-level"] + ["- %s: %s" % (s["code"], s["detail"]) for s in gen]
    L += ["", "_%s_" % DISCLAIMER, ""]
    return "\n".join(L)
