"""Tests 1 and 2 of docs/design/phase-4-engine-core.md; REQ-0010 AC1. A fake runner only:
the real subprocess is never reached (Popen is patched to fail the test)."""
import json
import os
import subprocess
import sys
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOOLS = os.path.join(ROOT, "tools", "examples")  # the old-command shims
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.adapters import claude as L  # noqa: E402

ARGV = ["claude", "-p", "--output-format", "json", "--model", "sonnet", "--tools", "",
        "--disable-slash-commands", "--no-session-persistence", "--strict-mcp-config"]


class Fake(object):
    def __init__(self, rc=0, out="", err="", exc=None):
        self.rc, self.out, self.err, self.exc, self.calls = rc, out, err, exc, []

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        if self.exc:
            raise self.exc
        return types.SimpleNamespace(returncode=self.rc, stdout=self.out, stderr=self.err)


def env(result="hi", **kw):
    d = {"type": "result", "is_error": False, "result": result, "total_cost_usd": 0.0123}
    d.update(kw)
    return json.dumps(d)


class NoRealProcess(unittest.TestCase):
    def setUp(self):
        p = mock.patch("subprocess.Popen", side_effect=AssertionError("real subprocess reached"))
        p.start()
        self.addCleanup(p.stop)


class ExtractJson(unittest.TestCase):
    def test_1_strict(self):
        self.assertEqual(L.extract_json('{"a": 1}'), ({"a": 1}, None))
        self.assertEqual(L.extract_json('  \n{"a": 1}\n ')[0], {"a": 1})

    def test_1_fenced(self):
        self.assertEqual(L.extract_json('Here:\n```json\n{"a": 2}\n```\nDone')[0], {"a": 2})
        self.assertEqual(L.extract_json('```\n{"a": 3}\n```')[0], {"a": 3})

    def test_1_outer_braces_in_prose(self):
        self.assertEqual(L.extract_json('Sure! {"a": {"b": 1}} hope it helps')[0], {"a": {"b": 1}})

    def test_1_two_fences_is_ambiguous(self):
        obj, err = L.extract_json('```json\n{"a":1}\n```\ntext\n```json\n{"a":2}\n```')
        self.assertIsNone(obj)
        self.assertIn("fence", err)

    def test_1_malformed_empty_and_non_object(self):
        for text in ('{"a": ', "no json here", "", "   ", None, "[1, 2]", "42", "{not json}"):
            obj, err = L.extract_json(text)
            self.assertIsNone(obj, text)
            self.assertTrue(err, text)


class RunClaude(NoRealProcess):
    def test_2_argv_stdin_no_shell_cwd(self):
        f = Fake(out=env("answer"))
        c = L.run_claude("PROMPT TEXT", model="sonnet", timeout_s=7, runner=f, cwd="/some/dir")
        self.assertEqual(len(f.calls), 1)
        argv, kw = f.calls[0]
        self.assertEqual(argv, ARGV)
        self.assertIsInstance(argv, list)
        self.assertEqual(kw["input"], "PROMPT TEXT")
        self.assertNotIn("PROMPT TEXT", " ".join(argv))
        self.assertIs(kw["shell"], False)
        self.assertEqual(kw["cwd"], "/some/dir")
        self.assertEqual(kw["timeout"], 7)
        self.assertTrue(c.ok)
        self.assertEqual((c.text, c.cls), ("answer", ""))
        self.assertAlmostEqual(c.cost_usd, 0.0123)

    def test_2_model_goes_into_argv(self):
        f = Fake(out=env())
        L.run_claude("p", model="haiku", timeout_s=1, runner=f)
        a = f.calls[0][0]
        self.assertEqual(a[a.index("--model") + 1], "haiku")
        self.assertIsNone(f.calls[0][1]["cwd"])

    def test_2_error_classes(self):
        cases = [
            (Fake(rc=1, err="401 Unauthorized: please login"), "auth"),
            (Fake(rc=1, err="429 rate limit hit"), "rate_limit"),
            (Fake(rc=1, err="Claude AI usage limit reached"), "rate_limit"),
            (Fake(rc=1, err="503 service unavailable"), "service"),
            (Fake(rc=1, err="boom"), "other"),
            (Fake(out=env("Invalid API key", is_error=True)), "auth"),
            (Fake(out=env("")), "empty"),
            (Fake(out=env("   ")), "empty"),
            (Fake(out="not json at all"), "empty"),
            (Fake(out=""), "empty"),
            (Fake(exc=subprocess.TimeoutExpired("claude", 3)), "timeout"),
            (Fake(exc=FileNotFoundError("claude")), "other"),
        ]
        for f, want in cases:
            c = L.run_claude("p", model="m", timeout_s=3, runner=f)
            self.assertFalse(c.ok, want)
            self.assertEqual(c.cls, want)
            self.assertEqual(c.text, "")

    def test_2_failed_call_keeps_cost_and_masks_reason(self):
        f = Fake(out=env("authentication failed for me@example.com", is_error=True))
        c = L.run_claude("p", model="m", timeout_s=3, runner=f)
        self.assertFalse(c.ok)
        self.assertEqual(c.cls, "auth")
        self.assertNotIn("me@example.com", c.reason)
        self.assertAlmostEqual(c.cost_usd, 0.0123)

    def test_2_mask(self):
        s = L.mask("mail a.b@c.io key sk-abcdefgh12345 Bearer abc.def " + "x" * 40)
        self.assertNotIn("a.b@c.io", s)
        self.assertNotIn("sk-abcdefgh12345", s)
        self.assertNotIn("x" * 40, s)
        self.assertEqual(L.mask("plain words"), "plain words")

    def test_2_default_runner_is_not_used_when_fake_given(self):
        f = Fake(out=env())
        L.run_claude("p", model="m", timeout_s=1, runner=f)
        self.assertEqual(len(f.calls), 1)  # Popen patched: a real run would have failed the test


if __name__ == "__main__":
    unittest.main()
