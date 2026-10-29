"""Test 4 of docs/design/phase-5-report.md (REQ-0011): md2html copy. Pure functions; no browser."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOOLS = os.path.join(ROOT, "tools", "examples")  # the old-command shims
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine.utils import md2html as m  # noqa: E402


def body(md):
    h = m.convert(md)
    return h.split("<body>", 1)[1].rsplit("</body>", 1)[0]


class Blocks(unittest.TestCase):
    def test_4_table(self):
        b = body("| A | B |\n| --- | --- |\n| 1 | 2 |\n")
        self.assertIn("<th>A</th>", b)
        self.assertIn("<td>2</td>", b)
        self.assertEqual(b.count("<tr>"), 2)

    def test_4_table_cell_with_escaped_pipe_stays_one_cell(self):
        b = body("| A | B |\n| --- | --- |\n| x \\| y | 2 |\n")
        self.assertEqual(b.count("<td>"), 2)
        self.assertIn("x | y", b)

    def test_4_lists(self):
        b = body("1. one\n2. two\n\n- a\n- b\n")
        self.assertIn("<ol><li>one</li><li>two</li></ol>", b)
        self.assertIn("<ul><li>a</li><li>b</li></ul>", b)

    def test_4_fenced_code_is_escaped(self):
        b = body("```html\n<script>alert(1)</script>\n```\n")
        self.assertIn("<pre><code", b)
        self.assertIn("&lt;script&gt;", b)
        self.assertNotIn("<script>", b)

    def test_4_quote(self):
        self.assertIn("<blockquote><p>hello</p></blockquote>", body("> hello\n"))

    def test_4_headings_have_ids(self):
        b = body("# Exam report\n\n## Question 1\n")
        self.assertIn('<h1 id="exam-report">', b)
        self.assertIn('<h2 id="question-1">', b)

    def test_4_pills_for_verdicts(self):
        h = m.convert("x")
        for cls in ("sev-pass", "sev-fail", "sev-uncertain"):
            self.assertIn(cls, h)
        self.assertEqual(m.SEV_CLASS["PASS"], "sev-pass")
        self.assertEqual(m.SEV_CLASS["FAIL"], "sev-fail")
        self.assertEqual(m.SEV_CLASS["UNCERTAIN"], "sev-uncertain")

    def test_4_lang_attribute_and_vietnamese_unchanged(self):
        text = "Giải phương trình: đáp án là 3,46 (Việt Nam)"
        h = m.convert("# Báo cáo\n\n" + text + "\n", False, "Báo cáo", "vi")
        self.assertIn('<html lang="vi">', h)
        self.assertIn(text, h)
        self.assertIn("<title>Báo cáo</title>", h)
        self.assertIn('charset="utf-8"', h)


class Escaping(unittest.TestCase):
    def test_4_script_text_is_escaped(self):
        b = body("hello <script>alert(1)</script> world\n")
        self.assertNotIn("<script", b)
        self.assertIn("&lt;script&gt;", b)

    def test_4_script_in_table_cell_and_heading_and_list(self):
        for md in ("| A |\n| --- |\n| <script>x</script> |\n", "# <script>x</script>\n",
                   "- <script>x</script>\n", "1. <img src=x onerror=alert(1)>\n"):
            b = body(md)
            self.assertNotIn("<script", b, md)
            self.assertNotIn("<img", b, md)

    def test_4_javascript_link_refused(self):
        for url in ("javascript:alert(1)", "JaVaScRiPt:alert(1)", "java\tscript:alert(1)",
                    "data:text/html,x", "vbscript:x"):
            b = body("[click](%s)\n" % url)
            self.assertNotIn("<a ", b, url)
            self.assertNotIn('href="%s' % url, b)

    def test_4_http_mailto_relative_links_allowed(self):
        for url in ("https://example.com/a", "http://example.com", "mailto:a@b.c", "#sec", "x.html"):
            self.assertIn('<a href="%s">' % url, body("[t](%s)\n" % url), url)
        self.assertFalse(m.safe_href("javascript:alert(1)"))
        self.assertIsNone(m.safe_href("javascript:alert(1)"))

    def test_4_quote_in_url_cannot_open_attribute(self):
        b = body('[t](https://e.com/"onmouseover="x)\n')
        self.assertNotIn('"onmouseover', b)

    def test_4_title_is_escaped(self):
        h = m.convert("x", False, "<b>t</b>", 'vi"><script>')
        self.assertNotIn("<b>t", h)
        self.assertNotIn("<script>", h.split("<body>")[0].replace(m.CSS, ""))


class Cli(unittest.TestCase):
    def test_4_cli_lang_vi_writes_file(self):
        tmp = tempfile.mkdtemp(prefix="md2html_test_")
        self.addCleanup(shutil.rmtree, tmp, True)
        src, dst = os.path.join(tmp, "a.md"), os.path.join(tmp, "a.html")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("# Tiêu đề\n\nNội dung\n")
        r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "md2html.py"), src, dst,
                            "--lang", "vi", "--title", "T"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(dst, encoding="utf-8") as fh:
            h = fh.read()
        self.assertIn('<html lang="vi">', h)
        self.assertIn("Nội dung", h)

    def test_4_cli_usage_error(self):
        r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "md2html.py")],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
