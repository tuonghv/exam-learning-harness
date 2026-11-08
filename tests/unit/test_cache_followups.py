"""TASK-084 84.1-84.5 (REQ-0090): solve-cache follow-ups. Fake llm, tmp dirs, no paid calls."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exam_engine import cli, engine, settings  # noqa: E402
from exam_engine.adapters import claude  # noqa: E402
from exam_engine.ingest import api, boundary, refine  # noqa: E402
from exam_engine.ingest.replycache import ReplyCache  # noqa: E402
from exam_engine.pipeline import metrics, planrun  # noqa: E402
import test_ingest_refine as R  # noqa: E402
import test_solve_cache as S  # noqa: E402

PINS = {"sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5", "haiku": "claude-haiku-5-5"}


class T1LastSolvedPaid(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="followups_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.exam = os.path.join(self.tmp, "exam-a.md")
        with open(self.exam, "w", encoding="utf-8") as fh:
            fh.write(S.EXAM)
        self.sha = metrics.file_sha256(self.exam)
        self.root = os.path.join(self.tmp, "plans")

    def plan(self, name, finished, **kw):
        d = os.path.join(self.root, "exam-a", name)
        os.makedirs(d)
        p = {"source": "solve", "status": "done", "llm": "claude-p", "exam": {"sha256": self.sha},
             "finished_utc": finished, "model": S.PIN}
        p.update(kw)
        with open(os.path.join(d, "plan.json"), "w") as fh:
            json.dump(p, fh)

    def test_84_1_paid_run_wins_over_newer_cached_run(self):
        self.plan("a", "2026-01-01T00:00:00Z", calls=5, cost_usd=0.12, cached=0)
        self.plan("b", "2026-02-01T00:00:00Z", calls=0, cost_usd=0.0, cached=5)
        got = planrun.last_solved(self.root, self.exam)
        self.assertEqual((got["calls"], got["cost_usd"]), (5, 0.12))
        self.assertTrue(got["dir"].endswith("a"))

    def test_84_1_only_cached_run_is_returned(self):
        self.plan("b", "2026-02-01T00:00:00Z", calls=0, cost_usd=0.0, cached=5)
        self.assertTrue(planrun.last_solved(self.root, self.exam)["dir"].endswith("b"))

    def test_84_1_run_without_cached_key_counts_as_paid(self):
        self.plan("a", "2026-01-01T00:00:00Z", calls=0, cost_usd=0.2)  # pre-83 plan: no `cached`
        self.plan("b", "2026-02-01T00:00:00Z", calls=0, cost_usd=0.0, cached=5)
        self.assertTrue(planrun.last_solved(self.root, self.exam)["dir"].endswith("a"))

    def test_84_1_newest_of_two_paid(self):
        self.plan("a", "2026-01-01T00:00:00Z", calls=5, cost_usd=0.12, cached=0)
        self.plan("c", "2026-03-01T00:00:00Z", calls=2, cost_usd=0.05, cached=3)
        self.assertTrue(planrun.last_solved(self.root, self.exam)["dir"].endswith("c"))


class NoCache(object):
    """Runner stub without a `cache` attribute (84.2)."""
    calls, cost, hits, saved = 0, 0.0, 0, 0.0
    cache_dir = None


class T2BuildResultNoCache(S.Base):
    def test_84_2_runner_without_cache_attr_does_not_raise(self):
        cache = ReplyCache(os.path.join(self.tmp, "c"))
        r, _ = self.run_engine(S.Fake(), cache, os.path.join(self.tmp, "o"))
        from exam_engine.pipeline import parser
        exam = parser.parse_exam(self.exam)
        rn = NoCache()
        out = engine.build_result(exam, self.exam, {}, S.cfg(), rn, None)
        self.assertNotIn("cached", out["run"])
        self.assertNotIn("cost_saved_usd", out["run"])


class T3BadCachedCost(S.Base):
    def _poison(self, value, raw=None):
        self.cli()
        cdir = os.path.join(self.tmp, "plans", "exam-a", "cache")
        files = [f for f in os.listdir(cdir) if f.startswith("solve-")]
        self.assertTrue(files)
        for f in files:
            p = os.path.join(cdir, f)
            with open(p, encoding="utf-8") as fh:
                e = json.load(fh)
            e["cost_usd"] = value
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(raw if raw is not None else json.dumps(e))
        return len(files)

    def test_84_3_invalid_cached_cost_is_a_miss(self):
        for label, value in (("neg", -1), ("true", True), ("str", "0.1"), ("none", None)):
            with self.subTest(label):
                self.setUp()
                n = self._poison(value)
                code, _, _, l = self.cli("--yes")
                self.assertGreaterEqual(len(l.prompts), 1, label)
                self.assertGreaterEqual(n, 1)

    def test_84_3_nan_and_inf_are_misses(self):
        for label, lit in (("nan", "NaN"), ("inf", "Infinity"), ("ninf", "-Infinity")):
            with self.subTest(label):
                self.setUp()
                self.cli()
                cdir = os.path.join(self.tmp, "plans", "exam-a", "cache")
                for f in [x for x in os.listdir(cdir) if x.startswith("solve-")]:
                    with open(os.path.join(cdir, f), "w", encoding="utf-8") as fh:
                        fh.write('{"text": %s, "cost_usd": %s}' % (json.dumps(S.solve_json()), lit))
                code, _, _, l = self.cli("--yes")
                self.assertGreaterEqual(len(l.prompts), 1, label)

    def test_84_3_zero_and_positive_cost_still_hit(self):
        for value in (0, 0.05):
            with self.subTest(value):
                self.setUp()
                self._poison(value)
                code, _, err, l = self.cli("--yes")
                self.assertEqual(len(l.prompts), 0, err)


class Boom(Exception):
    pass


class T4Resolve(unittest.TestCase):
    def test_84_4_resolve_table(self):
        for m, want in (("sonnet", PINS["sonnet"]), ("opus", PINS["opus"]), ("haiku", PINS["haiku"]),
                        ("claude-x-1", "claude-x-1"), ("unknown", "unknown")):
            self.assertEqual(claude.resolve(m, PINS), want)
        self.assertEqual(claude.resolve("sonnet"), "sonnet")
        self.assertEqual(claude.resolve("sonnet", None), "sonnet")

    def test_84_4_shipped_config_pins_all_three_aliases(self):
        pins = settings.load_config("engine")["model_pins"]
        for m in ("sonnet", "opus", "haiku"):
            self.assertTrue(claude.pinned(claude.resolve(m, pins), pins)[0], m)


class T4RefineReal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="followups_ref_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = os.path.join(self.tmp, "d.json")
        with open(self.path, "w") as fh:
            json.dump(R.make_doc(), fh)

    def run_cli(self, *extra):
        o, e = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            code = cli.main(["ingest-refine", self.path, "--pages", "1-3"] + list(extra))
        return code, o.getvalue(), e.getvalue()

    def test_84_4_real_alias_resolves_to_pin_for_llm(self):
        seen = []

        def mk(model, *a, **k):
            seen.append(model)
            raise Boom()
        with mock.patch.object(refine, "make_real_llm", mk), mock.patch.object(cli, "_refine_source", return_value=None):
            for extra, want in ((["--real"], PINS["sonnet"]), (["--real", "--model", "opus"], PINS["opus"]),
                                (["--real", "--model", "claude-sonnet-5-5"], "claude-sonnet-5-5")):
                with self.subTest(extra):
                    with self.assertRaises(Boom):
                        self.run_cli(*extra)
                    self.assertEqual(seen[-1], want)

    def test_84_4_real_unresolvable_alias_exits_2_before_any_call(self):
        with mock.patch.object(refine, "make_real_llm", side_effect=AssertionError("llm built")) as m, \
                mock.patch.object(claude, "run_claude", side_effect=AssertionError("call")), \
                mock.patch.object(claude, "run_claude_images", side_effect=AssertionError("call")), \
                mock.patch.object(api, "ingest_document", side_effect=AssertionError("ingest ran")):
            for model in ("foo-latest", "claude-sonnet", "weird"):
                with self.subTest(model):
                    code, _o, err = self.run_cli("--real", "--model", model)
                    self.assertEqual(code, 2)
                    self.assertIn("alias", err)
            self.assertEqual(m.call_count, 0)

    def test_84_4_mock_path_unchanged_keeps_alias(self):
        mf = os.path.join(self.tmp, "m.json")
        with open(mf, "w") as fh:
            fh.write(json.dumps([json.loads(R.GOOD1)]) if False else "{}")
        out = os.path.join(self.tmp, "out.json")
        with mock.patch.object(claude, "resolve", side_effect=AssertionError("resolve on mock")):
            code, _o, err = self.run_cli("--dry-run")
        self.assertEqual(code, 0, err)
        m = R.Fake([R.GOOD1])
        with mock.patch.object(refine, "mock_llm", return_value=m):
            code, _o, err = self.run_cli("--mock", mf, "--out", out)
        self.assertNotEqual(code, 2, err)
        if os.path.exists(out):
            with open(out) as fh:
                self.assertEqual(json.load(fh)["refined"]["model"], "sonnet")


class T4Boundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="followups_bnd_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = os.path.join(self.tmp, "x.md")
        with open(self.src, "w") as fh:
            fh.write("# t\n")
        self.real_load = settings.load_config

    def cfgs(self, pins):
        def load(name, *a, **k):
            c = dict(self.real_load(name, *a, **k))
            if name == "engine":
                c["model_pins"] = pins
            return c
        return load

    def run_ingest(self, *extra):
        o, e = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            code = cli.main(["ingest", self.src, "--boundary-ai", "haiku"] + list(extra))
        return code, e.getvalue()

    def test_84_4_boundary_real_uses_pinned_haiku(self):
        asked, built = [], []

        def ingest(path, config=None, meta=None):
            built.append(config["boundary"].model)
            raise Boom()
        with mock.patch.object(settings, "load_config", self.cfgs(PINS)), \
                mock.patch.object(boundary, "make_real_ask", lambda m, *a, **k: asked.append(m) or (lambda p, **kw: None)), \
                mock.patch.object(api, "ingest_document", ingest):
            with self.assertRaises(Boom):
                self.run_ingest("--real")
        self.assertEqual((asked, built), ([PINS["haiku"]], [PINS["haiku"]]))

    def test_84_4_boundary_real_unpinned_exits_2_before_any_call(self):
        with mock.patch.object(settings, "load_config", self.cfgs({})), \
                mock.patch.object(boundary, "make_real_ask", side_effect=AssertionError("ask built")), \
                mock.patch.object(claude, "run_claude", side_effect=AssertionError("call")), \
                mock.patch.object(api, "ingest_document", side_effect=AssertionError("ingest ran")):
            code, err = self.run_ingest("--real")
        self.assertEqual(code, 2)
        self.assertIn("not pinned", err)

    def test_84_4_boundary_mock_keeps_alias(self):
        built = []

        def ingest(path, config=None, meta=None):
            built.append(config["boundary"].model)
            raise Boom()
        with mock.patch.object(api, "ingest_document", ingest):
            with self.assertRaises(Boom):
                self.run_ingest("--dry-run")
        self.assertEqual(built, ["haiku"])


def metrics_dict(cost):
    return {"counts": {"total": 2, "pass": 2, "fail": 0, "uncertain": 0, "error": 0, "declined": 0},
            "rates": {}, "accuracy": {}, "cost": cost}


class T5MetricsBlock(S.Base):
    def _block(self, **cost):
        res = {"questions": [], "run": {"calls": 0, "cost_usd": 0.0}, "summary": {}}
        res["run"].update(cost)
        m = metrics.compute(res)
        return "\n".join(metrics.block(m)), m

    def test_84_5_block_has_exact_cache_line(self):
        text, m = self._block(cached=3, cost_saved_usd=0.1234)
        self.assertEqual(m["cost"]["cached"], 3)
        self.assertIn("cache: hits=3 saved=$0.1234", text.splitlines())

    def test_84_5_no_cache_line_without_cache(self):
        text, m = self._block()
        self.assertNotIn("cache:", text)

    def test_84_5_real_run_block_shows_hits(self):
        self.cli()
        self.cli("--yes")
        d = os.path.join(self.tmp, "plans", "exam-a", "runs", self.plans()[-1])
        with open(os.path.join(d, "result.json"), encoding="utf-8") as fh:
            res = json.load(fh)
        n = res["run"]["cached"]
        self.assertGreater(n, 0)
        line = [x for x in metrics.block(metrics.compute(res)) if x.startswith("cache: ")]
        self.assertEqual(line, ["cache: hits=%d saved=$%.4f" % (n, res["run"]["cost_saved_usd"])])


if __name__ == "__main__":
    unittest.main()
