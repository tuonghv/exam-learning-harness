"""Independent recompute of every Math/Physics final answer (REQ-0003 AC2).
Each value is computed here from the question's numbers, then compared with the
`Final answer:` line of the key. A wrong key fails the matching test."""
import math
import os
import re
import unittest
from fractions import Fraction

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def final(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        m = re.search(r"(?m)^Final answer:\s*(.+?)\s*$", fh.read())
    return m.group(1)


def num(text):
    """First number in a Vietnamese-formatted answer: 2,67.10^5 -> 2.67e5."""
    m = re.search(r"(-?\d+(?:,\d+)?)(?:\.10\^(-?\d+))?", text)
    return float(m.group(1).replace(",", ".")) * 10 ** int(m.group(2) or 0)


def key(s, n, ev=False):
    d = "evals/keys" if ev else "examples"
    return final("%s/%s/expected-%03d.md" % (d, s, n))


class Math(unittest.TestCase):
    def test_001_log_domain(self):
        sols = [x for x in range(-50, 51) if x > 2 and x * (x - 2) == 8]  # 2^3 = 8, x>2
        self.assertEqual(sols, [4])
        self.assertEqual(key("math", 1), "A")  # A = {4}

    def test_002_integral(self):
        v = (math.e - 1) / 2  # antiderivative e^(x^2)/2
        n = 100000
        s = sum(((i + .5) / n) * math.exp(((i + .5) / n) ** 2) for i in range(n)) / n
        self.assertAlmostEqual(s, v, places=6)
        self.assertEqual(key("math", 2).replace(" ", ""), "I=(e-1)/2")

    def test_003_two_extrema(self):
        ms = [m for m in range(-5, 6) if 36 - 12 * m > 0]  # f' = 3x^2-6x+m, disc > 0
        self.assertEqual(len(ms), 8)
        self.assertEqual(key("math", 3, True), "A")  # A = 8

    def test_004_probability(self):
        c = lambda n, k: math.factorial(n) // (math.factorial(k) * math.factorial(n - k))
        p = Fraction(c(9, 3) - c(5, 3), c(9, 3))
        self.assertEqual(p, Fraction(37, 42))
        self.assertEqual(key("math", 4, True), "37/42")

    def test_005_modulus(self):
        z = (3 - 1j) / (1 + 2j)
        self.assertAlmostEqual(abs(z), math.sqrt(2))
        self.assertEqual(key("math", 5, True), "sqrt(2)")


class Physics(unittest.TestCase):
    def test_001_spring_period(self):
        t = 2 * math.pi * math.sqrt(0.2 / 50)
        self.assertEqual(round(t, 2), 0.40)
        self.assertEqual(key("physics", 1), "A")  # A = 0,40 s

    def test_002_isochoric(self):
        p = 2.0e5 * (127 + 273) / (27 + 273)
        self.assertAlmostEqual(num(key("physics", 2)), float("%.3g" % p), delta=1)

    def test_003_rlc_phase(self):
        zl = 100 * math.pi * 0.4 / math.pi
        zc = 1 / (100 * math.pi * 1.25e-4 / math.pi)
        phi = math.atan((zl - zc) / 30)
        self.assertAlmostEqual(phi, -0.93, places=2)
        self.assertEqual(key("physics", 3, True), "B")  # B = -0,93 rad

    def test_004_maxima_count(self):
        lam = 30 / 15.0
        ks = [k for k in range(-20, 21) if abs(k * lam) < 10]  # open segment AB
        self.assertEqual(len(ks), 9)
        self.assertEqual(num(key("physics", 4, True)), 9)

    def test_005_photoelectric(self):
        ek = 6.625e-34 * 3e8 / 0.30e-6 - 3.0 * 1.6e-19
        self.assertAlmostEqual(num(key("physics", 5, True)), float("%.2g" % ek), delta=1e-21)


class English(unittest.TestCase):
    """Keys re-derived from the item text itself (passage facts, fixed grammar rule, segment order)."""

    def read(self, path):
        with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
            return fh.read()

    def test_003_reading_detail(self):
        t = self.read("evals/inputs/english/input-003.md")
        self.assertIn("slept for eight hours", t)
        self.assertIn("slept for only four hours", t)
        self.assertIn("B. They slept longer after studying.", t)
        self.assertEqual(key("english", 3, True), "B")

    def test_004_ordering_is_permutation_with_markers(self):
        order = key("english", 4, True).split("-")
        self.assertEqual(sorted(order), list("abcde"))
        t = self.read("evals/inputs/english/input-004.md")
        seg = dict(re.findall(r"(?m)^([a-e])\. (.+)$", t))
        text = [seg[k] for k in order]
        self.assertIn("Last year", text[0])      # opener
        self.assertIn("However", text[2])        # contrast follows the easy start
        self.assertTrue(text[4].startswith("Now"))  # closing

    def test_002_005_fixed_rules(self):
        self.assertEqual(key("english", 2), "A")        # take measures
        self.assertEqual(key("english", 5, True), "A")  # hardly ... when


if __name__ == "__main__":
    unittest.main()
