#!/usr/bin/env python3
"""
Minimal Markdown -> print-ready HTML for this toolkit's reports.

Copied from code-security-scanner/md2html.py (RAW-00037) and trimmed: flow
diagrams and severity pills removed, PASS/FAIL/UNCERTAIN verdict pills added.

Stdlib only, on purpose: the reports have to render on a machine that has
nothing installed but python3 and a browser. It supports exactly the subset
the exam report emits - headings, tables, fenced code,
blockquotes, bullet lists, rules, and inline bold/code/links.

  python3 md2html.py in.md out.html [--page-breaks] [--title "..."] [--lang vi]

--page-breaks starts every "## " section on a new page; --lang sets <html lang>.
"""
import html
import re
import sys

CSS = """
@page { size: A4; margin: 14mm 12mm 16mm 12mm; }
* { box-sizing: border-box; }
body {
  font-family: "DejaVu Sans", "Noto Sans", "Liberation Sans", Arial, sans-serif;
  font-size: 9.6pt; line-height: 1.5; color: #1a1a1a; margin: 0;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1 { font-size: 20pt; margin: 0 0 4pt; padding-bottom: 6pt; border-bottom: 2px solid #1a1a1a; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; padding-bottom: 3pt; border-bottom: 1px solid #c8c8c8; }
h3 { font-size: 11.5pt; margin: 14pt 0 4pt; }
h4 { font-size: 10.5pt; margin: 12pt 0 4pt; color: #333; }
h5 { font-size: 10pt; margin: 12pt 0 4pt; padding: 4pt 6pt; background: #f2f4f7;
     border-left: 3px solid #666; }
h1, h2, h3, h4, h5 { page-break-after: avoid; }
p { margin: 5pt 0; }
ul, ol { margin: 5pt 0 5pt 16pt; padding: 0; }
li { margin: 2pt 0; }
a { color: #0b5cad; text-decoration: none; }
hr { border: 0; border-top: 1px solid #ddd; margin: 10pt 0; }
blockquote { margin: 8pt 0; padding: 6pt 10pt; background: #fbf7e8;
             border-left: 3px solid #d8b33a; }
blockquote p { margin: 2pt 0; }
table { width: 100%; border-collapse: collapse; margin: 6pt 0 10pt;
        font-size: 8.4pt; table-layout: fixed; }
thead { display: table-header-group; }
th, td { border: 1px solid #d0d0d0; padding: 3.5pt 5pt; text-align: left;
         vertical-align: top; word-wrap: break-word; overflow-wrap: anywhere; }
th { background: #eef1f5; font-weight: 600; }
tr { page-break-inside: avoid; }
tbody tr:nth-child(even) { background: #fafbfc; }
code { font-family: "DejaVu Sans Mono", "Noto Sans Mono", "Liberation Mono", Menlo, Consolas,
       "Noto Sans Mono CJK SC", monospace;
       font-size: 0.88em;
       background: #f0f2f4; padding: 0.5pt 3pt; border-radius: 3px;
       overflow-wrap: anywhere; }
pre { background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 4px;
      padding: 6pt 8pt; margin: 6pt 0; font-size: 8pt; line-height: 1.42;
      white-space: pre-wrap; overflow-wrap: anywhere; }
pre code { background: none; padding: 0; font-size: 1em; }
sub { font-size: 0.8em; color: #666; }

/* Verdict pill: filled, and distinguishable in greyscale because the fills
   differ in darkness (FAIL darkest, UNCERTAIN mid, PASS lightest).
   print-color-adjust above keeps the backgrounds when printing to PDF. */
.sev {
  display: inline-block; padding: 0.5pt 5pt; border-radius: 8pt;
  font-weight: 700; font-size: 0.92em; line-height: 1.35;
  letter-spacing: 0.2pt; white-space: nowrap; border: 1px solid;
}
.sev-fail      { background: #a3111b; border-color: #7d0d15; color: #fff; }
.sev-uncertain { background: #f2d16b; border-color: #c8a52f; color: #4a3c00; }
.sev-pass      { background: #dcecd6; border-color: #93b985; color: #294d1e; }
"""

PAGE_BREAK_CSS = ("h2 { page-break-before: always; } "
                  "h2:first-of-type { page-break-before: avoid; }")

# Text the report emits in **bold** that should become a coloured pill.
SEV_CLASS = {"PASS": "sev-pass", "FAIL": "sev-fail", "UNCERTAIN": "sev-uncertain"}


def slug(text):
    """GitHub-compatible heading anchor, so the report's own ToC links work."""
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^a-z0-9 \-]", "", s)
    return s.replace(" ", "-")


SAFE_SCHEMES = ("http", "https", "mailto")


def safe_href(url):
    """Href value for an already html-escaped url, or None when its scheme is
    not allowed. Report text holds model output, so quotes are escaped (no new
    attribute) and only http(s)/mailto/relative/#anchor urls become links."""
    m = re.match(r"([A-Za-z][A-Za-z0-9+.-]*):", re.sub(r"[\x00-\x20\x7f]", "", url))
    if m and m.group(1).lower() not in SAFE_SCHEMES:
        return None
    return url.replace('"', "&quot;").replace("'", "&#x27;")


def inline(text):
    """Inline markdown -> HTML. Code spans are pulled out first so nothing
    inside them is reinterpreted; hrefs are stashed the same way so later
    rules never rewrite text inside an attribute."""
    spans = []
    hrefs = []

    def stash(m):
        spans.append(m.group(1))
        return "\x00%d\x00" % (len(spans) - 1)

    # \x00/\x02 mark the stashes (\x01 is convert()'s hard break); one in
    # the input could pick another stash
    text = re.sub(r"[\x00\x02]", "", text)
    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text, quote=False)

    def link(label, url, source):
        href = safe_href(url)
        if href is None:
            return source
        hrefs.append(href)
        return '<a href="\x02%d\x02">%s</a>' % (len(hrefs) - 1, label)

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: link(m.group(1), m.group(2), m.group(0)), text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w/])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", text)
    # underscore italics; \w includes "_", so snake_case names are never touched
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"(?<![\"'>=])\b(https?://[^\s<)\]\"']+)",
                  lambda m: link(m.group(1), m.group(1), m.group(0)), text)
    # a literal <sub> is the one tag kept
    text = text.replace("&lt;sub&gt;", "<sub>").replace("&lt;/sub&gt;", "</sub>")
    for word, cls in SEV_CLASS.items():
        text = text.replace("<strong>%s</strong>" % word,
                            '<strong class="sev %s">%s</strong>' % (cls, word))
    text = re.sub(r"\x02(\d+)\x02", lambda m: hrefs[int(m.group(1))], text)
    return re.sub(r"\x00(\d+)\x00",
                  lambda m: "<code>%s</code>" % html.escape(spans[int(m.group(1))], quote=False),
                  text)


def is_table_row(line):
    return line.lstrip().startswith("|")


def is_table_sep(line):
    return bool(re.match(r"^\s*\|[\s:|-]+\|\s*$", line)) and "-" in line


def cells(line):
    """Split a table row on unescaped pipes; \\| is a pipe that belongs to the
    cell text."""
    row = line.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") and not row.endswith("\\|") else row
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", row)]


def convert(md, page_breaks=False, title="Report", lang="en"):
    lines = md.split("\n")
    out, para, i = [], [], 0

    def flush():
        if para:
            body = inline(" ".join(para)).replace("\x01 ", "<br>").replace("\x01", "<br>")
            out.append("<p>%s</p>" % body)
            del para[:]

    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            flush()
            fence = line[3:].strip()
            body, i = [], i + 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            cls = ' class="lang-%s"' % html.escape(fence, quote=True) if fence else ""
            out.append("<pre><code%s>%s</code></pre>"
                       % (cls, html.escape("\n".join(body), quote=False)))
            continue

        if is_table_row(line) and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
            flush()
            head = cells(line)
            i += 2
            rows = []
            while i < len(lines) and is_table_row(lines[i]):
                rows.append(cells(lines[i]))
                i += 1
            out.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (
                "".join("<th>%s</th>" % inline(c) for c in head),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r)
                        for r in rows)))
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush()
            lvl, text = len(m.group(1)), m.group(2).strip()
            out.append('<h%d id="%s">%s</h%d>' % (lvl, slug(text), inline(text), lvl))
            i += 1
            continue

        if re.match(r"^\s*(---+|\*\*\*+|___+)\s*$", line):
            flush()
            out.append("<hr>")
            i += 1
            continue

        if line.startswith(">"):
            flush()
            quoted = []
            while i < len(lines) and lines[i].startswith(">"):
                quoted.append(lines[i].lstrip(">").strip())
                i += 1
            chunks = " ".join(quoted).split("  ")
            out.append("<blockquote>%s</blockquote>"
                       % "".join("<p>%s</p>" % inline(c) for c in chunks if c.strip()))
            continue

        m_ol = re.match(r"^\s*\d+\.\s+", line)
        if m_ol:
            flush()
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                item = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                i += 1
                while (i < len(lines) and lines[i].strip()
                       and not re.match(r"^\s*(\d+\.|[-*+])\s+", lines[i])
                       and not lines[i].startswith(("#", "|", ">", "```"))
                       and lines[i].startswith((" ", "\t"))):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            out.append("<ol>%s</ol>" % "".join("<li>%s</li>" % inline(x) for x in items))
            continue

        if re.match(r"^\s*[-*+]\s+", line):
            flush()
            items = []
            while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
                item = re.sub(r"^\s*[-*+]\s+", "", lines[i])
                i += 1
                # continuation lines of the same bullet
                while (i < len(lines) and lines[i].strip()
                       and not re.match(r"^\s*[-*+]\s+", lines[i])
                       and not lines[i].startswith(("#", "|", ">", "```"))
                       and lines[i].startswith((" ", "\t"))):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % inline(x) for x in items))
            continue

        if not line.strip():
            flush()
            i += 1
            continue

        # two trailing spaces = markdown hard break
        para.append(line.strip() + ("\x01" if line.endswith("  ") else ""))
        i += 1

    flush()
    css = CSS + (PAGE_BREAK_CSS if page_breaks else "")
    return ('<!doctype html>\n<html lang="%s"><head><meta charset="utf-8">'
            "<title>%s</title><style>%s</style></head><body>\n%s\n</body></html>\n"
            % (html.escape(lang, quote=True), html.escape(title, quote=False), css,
               "\n".join(out)))


def main():
    args = [a for a in sys.argv[1:]]
    page_breaks = "--page-breaks" in args
    args = [a for a in args if a != "--page-breaks"]
    title, lang = "Report", "en"
    if "--title" in args:
        k = args.index("--title")
        title = args[k + 1]
        del args[k:k + 2]
    if "--lang" in args:
        k = args.index("--lang")
        lang = args[k + 1]
        del args[k:k + 2]
    if len(args) != 2:
        sys.exit("usage: md2html.py in.md out.html [--page-breaks] [--title T] [--lang L]")
    with open(args[0], encoding="utf-8") as fh:
        md = fh.read()
    with open(args[1], "w", encoding="utf-8") as fh:
        fh.write(convert(md, page_breaks, title, lang))


if __name__ == "__main__":
    main()
