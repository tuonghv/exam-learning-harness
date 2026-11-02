"""Phase 47 (REQ-0051 AC1/AC2): cut detector, cut test, window extraction, bounded recovery.
Mock replies keyed by the page label of the prompt ("Page: 2" / "Pages: 1, 2"); $0, no network."""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.ingest import refine  # noqa: E402
from exam_engine.ingest.adapters import pdf  # noqa: E402

FULL = {"A": "a", "B": "b", "C": "c", "D": "d"}


def qq(i, text, opts=None, **kw):
    d = {"id": str(i), "text": text, "options": FULL if opts is None else opts,
         "figures": [], "unreadable": False}
    d.update(kw)
    return d


def rep(*qs, **kw):
    return json.dumps(dict({"questions": list(qs)}, **kw))



def label(prompt):
    m = re.search(r"^Pages: ([\d, ]+?) \(", prompt, re.M)
    if m:
        ps = [x.strip() for x in m.group(1).split(",")]
        return "%s-%s" % (ps[0], ps[-1])
    return re.search(r"^Page: (\d+)", prompt, re.M).group(1)


class Keyed:
    """llm(prompt, png): replies keyed by label; a list = replies popped in order; Exception = failed call."""
    def __init__(self, replies, cost=0.01):
        self.replies, self.calls, self.cost, self.pngs = dict(replies), [], cost, []

    def __call__(self, prompt, png):
        k = label(prompt)
        self.calls.append(k)
        self.pngs.append(png)
        r = self.replies.get(k)
        if isinstance(r, list):
            r = r.pop(0) if r else None
        if r is None:
            return claude.Call(False, "", 0.0, "other", "no reply for %s" % k, 0.0)
        return claude.Call(True, r, self.cost, "", "", 0.0)


def blk(i, text):
    return {"id": "b%d" % i, "order": i, "type": "paragraph", "text": text, "origin": "extracted"}


def doc(n=3, warnings=(), status="native_text"):
    pages = [{"n": i, "status": status, "blocks": [blk(i, "Cau %d. text" % i)]}
             for i in range(1, n + 1)]
    return {"schema_version": "1", "source": {"path": "t.pdf", "name": "t.pdf", "format": "pdf",
            "sha256": "0" * 64, "size": 1}, "status": status,
            "extraction": {"method": "pdf", "tool": "t"}, "meta": {}, "pages": pages,
            "assets": [], "warnings": list(warnings)}


def run(llm, n=3, spec=None, **kw):
    kw.setdefault("all_pages", True)
    kw.setdefault("min_similarity", 0.0)  # the fake page text does not hold the reply text
    return refine.refine(doc(n, kw.pop("warnings", ())), spec or "1-%d" % n, llm, **kw)


STEM1 = "Compute the value of the long expression ending with an operator +"
WHOLE1 = "Compute the value of the long expression ending with an operator + 5 using all numbers"


class TestWindow(unittest.TestCase):
    def test1_stem_split(self):
        # page 1 last question is cut (reply says so); page 2 window returns it whole
        llm = Keyed({"1": rep(qq(1, "first", ), qq(2, STEM1, {}, cut=True)),
                     "1-2": rep(qq(2, WHOLE1), qq(3, "third")), "3": rep(qq(4, "four"))})
        out = run(llm)
        r = out["refined"]
        self.assertEqual(llm.calls, ["1", "1-2", "3"])
        by = dict((x["id"], x) for x in r["questions"])
        self.assertEqual(by["2"]["text"], WHOLE1)
        self.assertEqual(by["2"]["continued_pages"], [2])
        self.assertEqual(by["2"]["window"], [1, 2])
        self.assertEqual(by["2"]["page"], 1)
        self.assertNotIn("cut", by["2"])
        self.assertFalse(by["2"]["needs_review"])
        self.assertEqual([x["id"] for x in r["questions"]], ["1", "2", "3", "4"])
        self.assertNotIn("orphans", r)
        self.assertEqual(r["windows"], [{"pages": [1, 2], "id": "2", "result": "whole"}])
        self.assertEqual(len(llm.pngs[1]), 2)  # window: tuple of 2 images

    def test2_options_on_next_page(self):
        llm = Keyed({"1": rep(qq(1, "Pick the right one", {"A": "a", "B": "b"})),
                     "1-2": rep(qq(1, "Pick the right one", FULL)), "3": rep(qq(5, "x"))})
        r = run(llm, spec="1-3")["refined"]
        self.assertEqual(sorted(r["questions"][0]["options"]), list("ABCD"))
        self.assertEqual(r["questions"][0]["window"], [1, 2])

    def test3_figure_on_next_page(self):
        llm = Keyed({"1": rep(qq(1, "See the figure and decide", {}, cut=True)),
                     "1-2": rep(qq(1, "See the figure and decide", FULL, figures=["graph"]))})
        r = run(llm, n=2)["refined"]
        self.assertEqual(r["questions"][0]["figures"], ["graph"])
        self.assertEqual(llm.calls, ["1", "1-2"])

    def test4_three_pages_then_bridge(self):
        t = "Long passage question that goes on and on over many pages"
        llm = Keyed({"1": rep(qq(1, t, {}, cut=True)),
                     "1-2": rep(qq(1, t + " and on", {}, cut=True)),
                     "1-3": rep(qq(1, t + " and on and on", {}, cut=True)),
                     "4": rep(qq(2, "next"), continues={"text": "and finally the end", "options": FULL})})
        out = run(llm, n=4)
        r = out["refined"]
        self.assertEqual(llm.calls, ["1", "1-2", "1-3", "4"])
        q1 = r["questions"][0]
        self.assertEqual(q1["window"], [1, 2, 3])
        self.assertEqual(r["windows"][0]["result"], "still_cut")
        self.assertNotIn("orphans", r)
        self.assertIn("and finally the end", q1["text"])  # K exceeded -> bridge (cut kept for page 4 attach)
        self.assertEqual(q1["continued_pages"], [2, 3, 4])

    def test5_no_cut_unchanged(self):
        llm = Keyed({"1": rep(qq(1, "one")), "2": rep(qq(2, "two")), "3": rep(qq(3, "three"))})
        r = run(llm)["refined"]
        self.assertEqual(llm.calls, ["1", "2", "3"])
        self.assertNotIn("windows", r)
        self.assertNotIn("recovered_pages", r)
        self.assertEqual(r["calls"], 3)

    def test6_failed_window_falls_back_to_bridge(self):
        llm = Keyed({"1": rep(qq(1, STEM1, {}, cut=True)), "1-2": None,
                     "2": rep(qq(2, "next"), continues={"text": "5 using all numbers"})})
        out = run(llm, n=2)
        r = out["refined"]
        self.assertEqual(llm.calls, ["1", "1-2", "2"])  # a failed call is not retried (as single pages)
        self.assertTrue(r["questions"][0].get("cut"))
        self.assertIn("5 using all numbers", r["questions"][0]["text"])
        self.assertIn("window_fallback", [w["code"] for w in out["warnings"]])
        self.assertEqual(r["windows"][0]["result"], "fallback")

    def test7_duplicate_guard(self):
        llm = Keyed({"1": rep(qq(1, "one"), qq(2, STEM1, {}, cut=True)),
                     "1-2": rep(qq(2, WHOLE1), qq(1, "one"), qq(3, "three"))})
        out = run(llm, n=2)
        self.assertEqual([x["id"] for x in out["refined"]["questions"]], ["1", "2", "3"])
        self.assertEqual([w["code"] for w in out["warnings"]].count("window_duplicate"), 1)

    def test8_missing_open_id_falls_back(self):
        llm = Keyed({"1": rep(qq(1, STEM1, {}, cut=True)), "1-2": rep(qq(7, "other")),
                     "2": rep(qq(2, "next"))})
        out = run(llm, n=2)
        self.assertEqual(llm.calls, ["1", "1-2", "2"])
        self.assertTrue(out["refined"]["questions"][0].get("cut"))
        self.assertIn("window_fallback", [w["code"] for w in out["warnings"]])

    def test9_scanned(self):
        # no native text, no warning: reply cut alone triggers; 4 options, no cut -> no window
        llm = Keyed({"1": rep(qq(1, "a complete one")), "2": rep(qq(2, "two"))})
        run(llm, n=2)
        self.assertEqual(llm.calls, ["1", "2"])
        llm = Keyed({"1": rep(qq(1, "x", {}, cut=True)), "1-2": rep(qq(1, "x whole"))})
        run(llm, n=2)
        self.assertEqual(llm.calls, ["1", "1-2"])

    def test_suspect_boundary_triggers_window(self):
        w = [{"level": "warning", "code": "page_cut_suspect", "page": 1, "message": "m"}]
        llm = Keyed({"1": rep(qq(1, "complete looking")), "1-2": rep(qq(1, "complete looking"))})
        run(llm, n=2, warnings=w)
        self.assertEqual(llm.calls, ["1", "1-2"])

    def test15_cost_cap_before_window(self):
        llm = Keyed({"1": rep(qq(1, STEM1, {}, cut=True)), "1-2": rep(qq(1, WHOLE1))}, cost=0.6)
        with self.assertRaises(refine.RefineError) as cm:
            run(llm, n=2, max_cost=0.5)
        self.assertEqual(cm.exception.code, "cost_cap")
        self.assertEqual(llm.calls, ["1"])

    def test_cost_cap_before_fallback_call(self):
        llm = Keyed({"1": rep(qq(1, STEM1, {}, cut=True)), "1-2": rep(qq(9, "bad"))}, cost=0.3)
        with self.assertRaises(refine.RefineError) as cm:
            run(llm, n=2, max_cost=0.5)
        self.assertEqual(cm.exception.code, "cost_cap")
        self.assertEqual(llm.calls, ["1", "1-2"])


class TestIsCut(unittest.TestCase):
    def test_signals(self):
        f = refine._is_cut
        self.assertTrue(f(qq(1, "x", cut=True), []))
        self.assertTrue(f(qq(1, "x", {"A": "a", "B": "b"}), []))
        self.assertFalse(f(qq(1, "x"), []))
        self.assertTrue(f(qq(2, "x", {}), [qq(1, "y")]))
        self.assertFalse(f(qq(2, "x", {}), [qq(1, "y", {})]))
        self.assertTrue(f(qq(1, "a = b +", {}), []))
        self.assertTrue(f(qq(1, "f(x = (1", {}), []))
        self.assertFalse(f(qq(1, "plain."), [], False))
        self.assertTrue(f(qq(1, "plain."), [], True))


class TestRecovery(unittest.TestCase):
    def test13_forward_adds_next_page(self):
        llm = Keyed({"1": rep(qq(1, STEM1, {}, cut=True)), "1-2": rep(qq(1, WHOLE1))})
        out = run(llm, n=3, spec="1")
        self.assertEqual(llm.calls, ["1", "1-2"])
        self.assertEqual(out["refined"]["recovered_pages"], [2])
        self.assertIn("recovered_pages", [w["code"] for w in out["warnings"]])
        self.assertEqual(out["refined"]["pages"], [1])

    def test13_no_recover(self):
        llm = Keyed({"1": rep(qq(1, STEM1, {}, cut=True))})
        out = run(llm, n=3, spec="1", recover=False)
        self.assertEqual(llm.calls, ["1"])
        self.assertNotIn("recovered_pages", out["refined"])

    def test13_key_page_never_added(self):
        d = doc(3)
        d["pages"][1]["blocks"] = [{"id": "b9", "order": 9, "type": "heading", "text": "Dap an",
                                    "origin": "extracted"}]
        llm = Keyed({"1": rep(qq(1, STEM1, {}, cut=True))})
        out = refine.refine(d, "1", llm, all_pages=True)
        self.assertEqual(llm.calls, ["1"])
        self.assertNotIn("recovered_pages", out["refined"])

    def test13_run_cap_four(self):
        # every page ends cut: pages 1,3,5,7,9 selected singly; each adds a neighbour until 4 extra
        rs = {}
        for p in (1, 3, 5, 7, 9):
            rs[str(p)] = rep(qq(p, STEM1, {}, cut=True))
            rs["%d-%d" % (p, p + 1)] = rep(qq(p, WHOLE1))
        llm = Keyed(rs)
        out = run(llm, n=11, spec="1,3,5,7,9")
        self.assertEqual(out["refined"]["recovered_pages"], [2, 4, 6, 8])
        self.assertEqual(llm.calls.count("9-10"), 0)

    def test13_backward_orphan_rerun(self):
        # page 2 selected alone: continuation has no owner -> re-run with page 1 added, memo = no repaid pages
        llm = Keyed({"2": rep(qq(2, "next"), continues={"text": "tail of earlier question"}),
                     "1": rep(qq(1, STEM1, {}, cut=True)), "1-2": rep(qq(1, WHOLE1), qq(2, "next"))})
        out = run(llm, n=3, spec="2")
        r = out["refined"]
        self.assertEqual(r["recovered_pages"], [1])
        self.assertEqual(llm.calls, ["2", "1", "1-2"])
        self.assertNotIn("orphans", r)
        self.assertEqual(r["questions"][0]["window"], [1, 2])
        self.assertEqual(r["pages"], [2])

    def test13_owner_has_options_not_recovered(self):
        llm = Keyed({"1": rep(qq(1, "complete", FULL)),
                     "2": rep(qq(2, "next"), continues={"text": "tail", "options": FULL})})
        out = run(llm, n=3, spec="1-2")
        self.assertEqual(llm.calls, ["1", "2"])
        self.assertEqual(out["refined"]["orphans"][0]["kind"], "owner_has_options")
        self.assertNotIn("recovered_pages", out["refined"])


class TestDetector(unittest.TestCase):
    def pages(self, *texts, status="native_text", images=()):
        out = []
        for i, t in enumerate(texts, 1):
            blocks = [{"type": "paragraph", "text": t}]
            if i in images:
                blocks.insert(0, {"type": "image", "text": ""})
            out.append({"n": i, "status": status, "chars": len(t), "blocks": blocks})
        return out

    def warns(self, *texts, **kw):
        ps = self.pages(*texts, **kw)
        lines = [t.split("\n") for t in texts]
        return pdf._cut_boundaries(ps, lines)

    def test_s1_options_incomplete(self):
        w = self.warns("Cau 1. Stem.\nA. a\nB. b", "C. c\nD. d\nCau 2. next")
        self.assertEqual([x["code"] for x in w], ["page_cut_suspect"])
        self.assertEqual(w[0]["page"], 1)

    def test_s2_s3_prose(self):
        w = self.warns("Cau 1. Stem.\nA. a\nB. b\nC. c\nD. d\nthe sum of", "continues here")
        self.assertEqual(len(w), 1)

    def test_s4_image(self):
        ps = self.pages("Cau 1. Stem ok.\nA. a\nB. b\nC. c\nD. d", "Cau 2. next", images=(2,))
        # S4 needs the question to be open at the end of page 1: complete one -> no warning
        self.assertEqual(pdf._cut_boundaries(ps, [t["blocks"][-1]["text"].split("\n") for t in ps]), [])
        ps = self.pages("Cau 1. Stem ok.\nA. a\nB. b", "Cau 2. next", images=(2,))
        w = pdf._cut_boundaries(ps, [["Cau 1. Stem ok.", "A. a", "B. b"], ["Cau 2. next"]])
        self.assertEqual(len(w), 1)
        self.assertIn("S4", w[0]["message"])

    def test_complete_boundary_and_s2_alone(self):
        self.assertEqual(self.warns("Cau 1. Stem.\nA. a\nB. b\nC. c\nD. d", "Cau 2. next"), [])
        # S2 alone: unfinished last line but next page starts a numbered question
        self.assertEqual(self.warns("Cau 1. Stem.\nA. a\nB. b\nC. c\nD. d\nthe sum of",
                                  "Cau 2. next"), [])

    def test_ocr_page_no_warning(self):
        self.assertEqual(self.warns("Cau 1. Stem.\nA. a", "x", status="ocr"), [])


if __name__ == "__main__":
    unittest.main()


class TestCacheTrace(unittest.TestCase):
    CUT = {"1": rep(qq(1, STEM1, {}, cut=True)), "1-2": rep(qq(1, WHOLE1))}

    def test11_cache(self):
        from exam_engine.ingest import replycache
        cache = replycache.ReplyCache(None)
        a = Keyed(self.CUT)
        run(a, n=2, cache=cache)
        self.assertEqual(a.calls, ["1", "1-2"])
        b = Keyed({})
        out = run(b, n=2, cache=cache)  # same cache: 0 calls
        self.assertEqual(b.calls, [])
        self.assertEqual(out["refined"]["calls"], 0)
        self.assertEqual(out["refined"]["questions"][0]["text"], WHOLE1)
        keys = [k[1] for k in cache.mem if k[0] == "page"]
        self.assertEqual(len(keys), len(set(keys)))  # window key != single key
        self.assertEqual(len(keys), 2)

    def test11_template_change_misses(self):
        from exam_engine.ingest import replycache
        cache = replycache.ReplyCache(None)
        run(Keyed(self.CUT), n=2, cache=cache)
        orig = refine.template
        try:
            refine.template = lambda: orig() + "\nextra rule\n"
            c = Keyed(self.CUT)
            run(c, n=2, cache=cache)
        finally:
            refine.template = orig
        self.assertEqual(c.calls, ["1", "1-2"])

    def test11_mock_never_reads_disk(self):
        import tempfile
        from exam_engine.ingest import replycache
        d = tempfile.mkdtemp()
        run(Keyed(self.CUT), n=2, cache=replycache.ReplyCache(d))
        self.assertTrue(os.listdir(d))
        self.assertEqual(replycache.ReplyCache(None).get("page", "k"), None)
        self.assertIsNone(replycache.ReplyCache(None).dir)

    def test12_trace_rows(self):
        tr = []
        run(Keyed(self.CUT), n=2, trace=tr)
        self.assertEqual([r["pages"] for r in tr], [[1], [1, 2]])
        for r in tr:
            self.assertEqual(sorted(r), ["cached", "cls", "cost_usd", "ok", "page", "pages",
                                         "png_sha256", "reason", "text"])
            self.assertFalse(r["cached"])
        self.assertEqual(len(tr[1]["png_sha256"]), 2)
        tr2 = []
        from exam_engine.ingest import replycache
        cache = replycache.ReplyCache(None)
        run(Keyed(self.CUT), n=2, cache=cache)
        run(Keyed({}), n=2, cache=cache, trace=tr2)
        self.assertTrue(all(r["cached"] for r in tr2) and tr2)

    def test14_old_refined_unchanged(self):
        # no cut, no window: no new fields appear
        out = run(Keyed({"1": rep(qq(1, "Plain question text"))}), n=1)
        r = out["refined"]
        for k in ("windows", "recovered_pages"):
            self.assertNotIn(k, r)
        self.assertNotIn("window", r["questions"][0])
        self.assertEqual(sorted(r), ["calls", "cost_usd", "model", "pages", "prompt_sha256",
                                     "questions"])

    def test_keyed_mock_file(self):
        import tempfile
        p = os.path.join(tempfile.mkdtemp(), "m.json")
        with open(p, "w") as fh:
            json.dump(self.CUT, fh)
        llm = refine.mock_llm(p)
        out = run(llm, n=2)
        self.assertEqual(out["refined"]["questions"][0]["text"], WHOLE1)
        miss = llm(refine.build_prompt(9), b"")
        self.assertFalse(miss.ok)

    def test_dry_run_line(self):
        w = [{"level": "info", "code": "page_cut_suspect", "page": 1, "message": "m"}]
        d = doc(2, w)
        self.assertEqual(refine.planned_windows(d, [1, 2]), [1])
        self.assertEqual(refine.planned_windows(d, [2]), [])
