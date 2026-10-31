"""Phase 42 (TASK-042, REQ-0046): image sequences in ingest-refine. Mock replies, tiny generated PNGs."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.abspath(os.path.join(HERE, "..", "..")), "src"))
from exam_engine import cli  # noqa: E402
from exam_engine.ingest import api, refine  # noqa: E402
from exam_engine.ingest.adapters import image as imgmod  # noqa: E402
from exam_engine.ingest.schema import IngestError, validate_document  # noqa: E402
from test_ingest_image import png_bytes  # noqa: E402
from test_ingest_refine import Fake, q, reply  # noqa: E402

STEM = "Placeholder stem alpha beta gamma delta epsilon, which figure fits?"
OPTS = {"A": "one", "B": "two", "C": "three", "D": "four"}


def cont(text="", options=None, figures=None):
    return json.dumps({"questions": [], "continues": {
        "text": text, "options": options or {}, "figures": figures or [], "passage": False}})


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def files(self, n):
        out = []
        for k in range(1, n + 1):
            p = os.path.join(self.dir, "p%d.png" % k)
            with open(p, "wb") as fh:
                fh.write(png_bytes(3 + k, 2))
            out.append(p)
        return out

    def doc(self, n):
        return imgmod.ingest_sequence(self.files(n))

    def run_refine(self, n, spec, replies):
        return refine.refine(self.doc(n), spec, Fake(replies), all_pages=True)


class TestSequenceDoc(Base):
    def test_pages_order_names_hashes(self):
        d = self.doc(3)
        self.assertEqual([p["n"] for p in d["pages"]], [1, 2, 3])
        self.assertEqual(d["source"]["format"], "image_seq")
        self.assertEqual([f["name"] for f in d["source"]["files"]], ["p1.png", "p2.png", "p3.png"])
        self.assertEqual(validate_document(d), [])
        self.assertEqual(len(set(a["id"] for a in d["assets"])), 3)

    def test_single_image_legacy_unchanged(self):
        p = self.files(1)[0]
        d = imgmod.ingest(p)
        self.assertEqual(d["source"]["format"], "png")
        self.assertNotIn("files", d["source"])
        self.assertEqual(d["pages"][0]["blocks"][0]["id"], "b1")
        self.assertEqual(api.ingest_document(p)["source"]["format"], "png")

    def test_bad_member_refused(self):
        with self.assertRaises(IngestError):
            imgmod.ingest_sequence([])
        bad = os.path.join(self.dir, "x.txt")
        open(bad, "w").close()
        with self.assertRaises(IngestError):
            imgmod.ingest_sequence(self.files(1) + [bad])

    def test_render_is_png_of_file_n(self):
        paths = self.files(2)
        self.assertEqual(imgmod.render(paths, 2), open(paths[1], "rb").read())
        with self.assertRaises(IngestError):
            imgmod.render(paths, 3)


class TestAssembly(Base):
    def test_three_images_stem_figure_options(self):
        out = self.run_refine(3, "1-3", [reply(q(1, STEM)),
                                         cont(figures=["bar chart, values 1 2 3"]),
                                         cont(options=OPTS)])
        qs = out["refined"]["questions"]
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0]["options"], OPTS)
        self.assertEqual(qs[0]["figures"], ["bar chart, values 1 2 3"])
        self.assertEqual(qs[0]["continued_pages"], [2, 3])
        self.assertNotIn("orphans", out["refined"])

    def test_two_images(self):
        out = self.run_refine(2, "1-2", [reply(q(1, STEM)), cont(options=OPTS)])
        qs = out["refined"]["questions"]
        self.assertEqual((len(qs), qs[0]["options"], qs[0]["continued_pages"]), (1, OPTS, [2]))

    def test_tile_overlap_duplicate_not_repeated(self):
        out = self.run_refine(2, "1-2", [reply(q(1, STEM)),
                                         cont(text="epsilon, which figure fits? more tail words")])
        text = out["refined"]["questions"][0]["text"]
        self.assertEqual(text.count("epsilon, which figure fits?"), 1)
        self.assertTrue(text.endswith("more tail words"))

    def test_orphan_names_previous_file(self):
        out = self.run_refine(2, "2", [cont(options=OPTS)])
        self.assertEqual(out["refined"]["orphans"], [{"page": 2, "kind": "no_owner"}])
        msg = [w["message"] for w in out["warnings"] if w["code"] == "orphan_continuation"][0]
        self.assertIn("p1.png", msg)

    def test_no_continuation_unchanged(self):
        out = self.run_refine(2, "1-2", [reply(q(1, STEM, OPTS)), reply(q(2, "Another stem here", OPTS))])
        qs = out["refined"]["questions"]
        self.assertEqual([x["id"] for x in qs], ["1", "2"])
        self.assertTrue(all("continued_pages" not in x for x in qs))
        self.assertNotIn("orphans", out["refined"])

    def test_pdf_style_doc_message_unchanged(self):
        d = {"schema_version": "1", "status": "mixed", "extraction": {"method": "pdf", "tool": "t"},
             "source": {"path": "t.pdf", "name": "t.pdf", "format": "pdf", "sha256": "0" * 64, "size": 1},
             "meta": {}, "assets": [], "warnings": [],
             "pages": [{"n": n, "blocks": []} for n in (1, 2)]}
        out = refine.refine(d, "2", Fake([cont(options=OPTS)]), all_pages=True)
        msg = [w["message"] for w in out["warnings"] if w["code"] == "orphan_continuation"][0]
        self.assertTrue(msg.endswith("add page(s) 1 to --pages"))


class TestSourceGuard(Base):
    def saved(self, d):
        path = os.path.join(self.dir, "doc.json")
        with open(path, "w") as fh:
            json.dump(d, fh)
        return path

    def test_paths_in_order(self):
        d = self.doc(2)
        got = cli._refine_source(SimpleNamespace(file=self.saved(d)), d, images=True)
        self.assertEqual([os.path.basename(p) for p in got], ["p1.png", "p2.png"])

    def test_swapped_order_refused(self):
        d = self.doc(2)
        f = d["source"]["files"]
        f[0]["sha256"], f[1]["sha256"] = f[1]["sha256"], f[0]["sha256"]  # files seen in other order
        with self.assertRaises(IngestError):
            cli._refine_source(SimpleNamespace(file=self.saved(d)), d, images=True)

    def test_changed_content_refused(self):
        d = self.doc(2)
        with open(os.path.join(self.dir, "p2.png"), "wb") as fh:
            fh.write(png_bytes(9, 9))
        with self.assertRaises(IngestError):
            cli._refine_source(SimpleNamespace(file=self.saved(d)), d, images=True)

    def test_images_refused_without_flag(self):
        d = self.doc(2)
        with self.assertRaises(IngestError):
            cli._refine_source(SimpleNamespace(file=self.saved(d)), d)


class TestCli(Base):
    def run_cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["ingest-refine"] + args)
        return code, out.getvalue(), err.getvalue()

    def test_mock_two_files(self):
        paths = self.files(2)
        mock = os.path.join(self.dir, "m.json")
        with open(mock, "w") as fh:
            json.dump([reply(q(1, STEM)), cont(options=OPTS)], fh)
        out = os.path.join(self.dir, "o.json")
        code, _, err = self.run_cli(paths + ["--pages", "1-2", "--all-pages", "--mock", mock,
                                             "--out", out])
        self.assertEqual((code, err), (1, ""))  # 1 = needs_review (no source text to compare)
        with open(out) as fh:
            r = json.load(fh)["refined"]
        self.assertEqual(r["questions"][0]["options"], OPTS)

    def test_dry_run_single_image_flagged(self):
        code, out, _ = self.run_cli(self.files(1) + ["--pages", "1", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("pages [1]", out)

    def test_mixed_inputs_usage_error(self):
        code, _, err = self.run_cli(self.files(1) + ["x.pdf", "--pages", "1", "--dry-run"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
