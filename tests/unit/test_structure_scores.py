"""69.x: parsing accuracy apart from solving (metrics.structure_scores, compute(structure=), board lines).
Synthetic data only; expected numbers computed by hand in the comments."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
from test_structure_scope import emit, q as rq  # noqa: E402
import test_run_board as trb  # noqa: E402
from exam_engine.pipeline import metrics, parser  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "structure_gold.json")


def qx(i, section, ins, pas, stem, pages=None):
    return {"id": i, "text": stem, "stem": stem, "section": section, "instruction": ins, "passage": pas,
            "options": {}, "pages": pages or [1]}


def exam3():
    return {"questions": [qx(1, "A", "Read and answer.", "P", "Pick one."),
                          qx(2, "A", "Read and answer.", "P", "Pick two."),
                          qx(3, "B", "Read and answer.", "", "Pick three.", [2, 3])]}


GOLD = [{"id": 1, "stem": "Pick one.", "section": "A", "instruction": "Read and answer.", "shared": "g1"},
        {"id": 2, "stem": "Pick two.", "section": "A", "instruction": "Read and answer.", "shared": "g1"},
        {"id": 3, "stem": "Pick three.", "section": "B", "instruction": "", "pages": [2, 3], "deps": []},
        {"id": 4, "stem": "Pick four.", "section": "B"}]


def kn(s, name):
    return (s["scores"][name]["k"], s["scores"][name]["n"])


class TestScores(unittest.TestCase):
    def test_t1_hand_computed(self):
        s = metrics.structure_scores(exam3(), GOLD)
        self.assertEqual(kn(s, "extraction"), (3, 4))
        self.assertEqual(s["scores"]["extraction"]["miss"], [{"id": 4, "why": "missing"}])
        self.assertEqual(kn(s, "boundary"), (3, 3))
        self.assertEqual(kn(s, "hierarchy"), (3, 3))
        self.assertEqual(kn(s, "instruction"), (2, 3))
        self.assertEqual(s["scores"]["instruction"]["miss"], [{"id": 3, "why": "leak"}])
        self.assertEqual(kn(s, "shared_ref"), (2, 2))
        self.assertEqual(kn(s, "reference"), (1, 1))
        self.assertEqual(kn(s, "cross_page"), (1, 1))
        self.assertEqual(s["scores"]["extraction"]["rate"], 0.75)
        self.assertEqual(s["tokens_per_question_est"], 5.2)  # (17 + 16 + 9 + 9 + 11) / 4 / 3

    def test_t2_extra(self):
        ex = exam3()
        ex["questions"].append(qx(5, "B", "", "", "Pick five."))
        s = metrics.structure_scores(ex, GOLD)
        self.assertEqual(kn(s, "extraction"), (3, 5))
        self.assertEqual(s["extra"], [5])
        self.assertIn({"id": 5, "why": "extra"}, s["scores"]["extraction"]["miss"])

    def test_t3_field_absent(self):
        s = metrics.structure_scores(exam3(), [{"id": 1}, {"id": 2}])
        for name in metrics.STRUCTURE_METRICS[1:]:
            self.assertEqual(s["scores"][name]["n"], 0)
            self.assertIsNone(s["scores"][name]["rate"])

    def test_t4_shared_overlinked(self):
        ex = exam3()
        ex["questions"][2].update(section="A", passage="P")
        s = metrics.structure_scores(ex, GOLD)
        self.assertEqual(kn(s, "shared_ref"), (0, 2))
        self.assertEqual({m["why"] for m in s["scores"]["shared_ref"]["miss"]}, {"overlinked"})

    def test_t5_gold_set(self):
        with open(FIXTURE, encoding="utf-8") as f:
            fx = json.load(f)
        self.assertEqual(fx["schema"], "structure-gold/1")
        for c in fx["cases"]:
            ex = emit(c["refined"])[1]
            s = metrics.structure_scores(ex, c["gold"])
            self.assertEqual(s["extra"], [], c["case"])
            for name, v in s["scores"].items():
                missed = sorted(m["id"] for m in v["miss"])
                self.assertEqual(missed, sorted(c["known_miss"].get(name, [])), "%s %s" % (c["case"], name))

    def test_t5b_each_metric_has_pass_and_known_miss(self):
        with open(FIXTURE, encoding="utf-8") as f:
            cases = json.load(f)["cases"]
        passed, missed = set(), set()
        for c in cases:
            for name, v in metrics.structure_scores(emit(c["refined"])[1], c["gold"])["scores"].items():
                if v["k"]:
                    passed.add(name)
                if name in c["known_miss"]:
                    missed.add(name)
        self.assertEqual(passed, set(metrics.STRUCTURE_METRICS) - {"reference"})  # reference: T1 only
        self.assertEqual(missed, set(metrics.STRUCTURE_METRICS) - {"reference"})

    def test_t10_gold_file_clean(self):
        with open(FIXTURE, encoding="utf-8") as f:
            fx = json.load(f)
        src = ""
        for n in ("test_structure_scope.py", "test_structure_qa.py"):
            with open(os.path.join(HERE, n), encoding="utf-8") as f:
                src += f.read()
        for c in fx["cases"]:
            for g in c["gold"]:
                self.assertFalse({"answer", "key"} & set(g), c["case"])
            for r in c["refined"]:
                self.assertFalse({"answer", "key"} & set(r), c["case"])
                for ln in (r.get("text", "") + "\n" + r.get("context", "")).splitlines():
                    if ln.strip():
                        self.assertIn(ln.strip(), src, c["case"])


def result(rows):
    return {"questions": [dict({"id": i, "answer": a, "verification_status": "PASS"}, **kw)
                          for i, a, kw in rows], "run": {}}


class TestCompute(unittest.TestCase):
    def test_t6_old_output_identical(self):
        r = result([(1, "A", {}), (2, "B", {}), (3, "C", {})])
        self.assertEqual(json.dumps(metrics.compute(r), sort_keys=True),
                         json.dumps(metrics.compute(r, structure=None), sort_keys=True))
        m = metrics.compute(r, structure={"2": ["range_overrun"]})
        self.assertEqual(m["by_parse_flag"]["flagged"]["n"], 1)
        self.assertEqual(m["by_parse_flag"]["clean"]["n"], 2)
        self.assertEqual(m["counts"]["structure_flags"], {"range_overrun": 1})
        self.assertNotIn("by_parse_flag", metrics.compute(r))
        self.assertEqual(metrics.compute(r, structure={})["counts"]["structure_flags"], {})

    def test_t7_split(self):
        r = result([(1, "A", {}), (2, "B", {}), (3, "C", {})])
        key = {"1": "A", "2": "X", "3": "X"}
        m = metrics.compute(r, key=key, quality=True, structure={"2": ["range_overrun"]})
        q = m["quality"]
        self.assertEqual((q["parse_flagged"], q["parse_wrong"], q["solve_wrong"]), (1, 1, 1))
        self.assertEqual(q["wrong_answered"], 2)
        self.assertEqual(q["keyed"], 3)  # solving denominator untouched
        self.assertNotIn("parse_flagged", metrics.compute(r, key=key, quality=True)["quality"])

    def test_t7_qa_basis(self):
        r = result([(1, "A", {}), (2, "B", {})])
        qa = {"1": {"answer": "A", "flawed": False}, "2": {"answer": "C", "flawed": False}}
        q = metrics.compute(r, qa=qa, quality=True, structure={"2": ["x"]})["quality"]
        self.assertEqual((q["basis"], q["parse_differs"]), ("qa", 1))


def side(structure, prompt_kb, key=True):
    r = result([(i, "A", {}) for i in range(1, 5)])
    log = None if prompt_kb is None else ["llm dur=1 prompt_bytes=%d answer_bytes=0" % int(prompt_kb * 1024)]
    m = metrics.compute(r, log_lines=log, key={"1": "A", "2": "B", "3": "B", "4": "A"} if key else None,
                        quality=True, structure=structure)
    return metrics._side([m])


class TestBoard(unittest.TestCase):
    def block(self, cur):
        return {"cur": cur, "base": None, "exams": 1, "runs": 1, "tier": None, "repeat": False,
                "generated": False, "verdict": "-", "flag": None}

    def test_t8_parsing_line(self):
        plain = metrics.board_text("K", self.block(side(None, None)))
        withp = metrics.board_text("K", self.block(side({"2": ["f"], "3": ["f"]}, None)))
        self.assertEqual([ln for ln in withp if not ln.startswith("  parsing")], plain)
        line = [ln for ln in withp if ln.startswith("  parsing")]
        self.assertEqual(line, ["  parsing flagged 2/4 (structure flags, not accuracy)  wrong: "
                                "parse-suspect 2 solver 0"])

    def test_t9_tokens_per_q(self):
        s = side(None, 2.0)
        self.assertEqual(s["in_tok_per_q"], 128.0)  # 2048 / 4 / 4
        self.assertTrue(any("input ~tok/q 128.0" in ln for ln in metrics.board_text("K", self.block(s))))
        none = side(None, None)
        self.assertNotIn("in_tok_per_q", none)
        self.assertFalse(any("input" in ln for ln in metrics.board_text("K", self.block(none))))


class TestBoardCli(trb.Base):
    def setUp(self):
        super().setUp()
        text, self.ex, _ = emit([rq(1, ctx="PART I\nQuestions 1-2: Read."), rq(2)])
        self.exam = os.path.join(self.tmp, "exam.md")
        with open(self.exam, "w", encoding="utf-8") as f:
            f.write(text)
        self.sha = metrics.file_sha256(self.exam)
        self.gold = os.path.join(self.tmp, "gold.json")
        with open(self.gold, "w", encoding="utf-8") as f:
            json.dump([{"id": 1, "stem": "Pick one.", "section": "PART I"}, {"id": 2, "stem": "Pick one."},
                       {"id": 3, "stem": "Pick three."}], f)

    def test_assembly_line_and_old_output(self):
        d = self.run_dir(trb.result(trb.states(2, 1, 0)), sha=self.sha)
        before = self.board()[1]
        self.assertNotIn("parsing", before)
        os.makedirs(os.path.join(d, "input"))
        with open(os.path.join(d, "input", "assembly.json"), "w", encoding="utf-8") as f:
            json.dump({"schema": "assembly/1", "questions": [{"id": 3, "structure": ["range_overrun"]},
                                                              {"id": 1}]}, f)
        after = self.board()[1]
        self.assertEqual([ln for ln in after.splitlines() if "parsing" not in ln], before.splitlines())
        self.assertIn("  parsing flagged 1/3 (structure flags, not accuracy)  wrong: parse-suspect 1 solver 0", after)

    def test_gold_flag(self):
        self.run_dir(trb.result(trb.states(2, 1, 0)), sha=self.sha)
        code, out, _ = self.board("--exam", self.exam, "--structure-gold", self.gold)
        self.assertEqual(code, 0)
        self.assertIn("  parsing gold n=3 extraction 66.7% boundary 100.0% hierarchy 100.0% instruction - "
                      "shared_ref - reference - cross_page - tok/q~", out)
        doc = json.loads(self.board("--exam", self.exam, "--structure-gold", self.gold, "--json")[1])
        self.assertEqual(doc["structure_gold"]["scores"]["extraction"]["k"], 2)
        self.assertNotIn("structure_gold", json.loads(self.board("--json")[1]))

    def test_gold_errors(self):
        code, _, err = self.board("--structure-gold", self.gold)
        self.assertEqual(code, 2)
        self.assertIn("ERROR: --structure-gold", err)
        with open(self.gold, "w", encoding="utf-8") as f:
            f.write("{bad")
        code, _, err = self.board("--exam", self.exam, "--structure-gold", self.gold)
        self.assertEqual(code, 2)
        self.assertIn("ERROR: --structure-gold", err)


if __name__ == "__main__":
    unittest.main()
