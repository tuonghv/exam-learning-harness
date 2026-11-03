"""PDF adapter (PyMuPDF via the optional loader): native text first, OCR only on flagged pages,
crops only where text cannot carry the content. No network, original never written."""
import difflib
import glob
import hashlib
import os
import re
import shutil
import subprocess
import unicodedata

from exam_engine.core.refcheck import _TRAIL
from exam_engine.ingest import boundary, optional, segment
from exam_engine.ingest.schema import SCHEMA_VERSION, IngestError
from exam_engine.utils import langtable

CROP_DPI = 150
OCR_DPI = 200
OCR_GAP = 0.15  # char gap / median char height that becomes a space (51.7 sweep: ocr-gap-sweep.tsv)
OCR_CONF_DEFAULT = "auto"  # 71.5 gate passed: family C unmarked 10 -> 3 at 0 false alarms; "off" skips the CLI run
# 71.2 floor 60, margin 0 (work/TASK-071/qa/conf-sweep.tsv): 0 false alarms on families A, B, D and on the
# unaccented family Cm (0/18); accented correct text is unmeasured; 60 sits just below the 70 cliff (A: 4 false alarms)
OCR_LOW_CONF = 60
TOKEN_MARGIN = 0  # 71.3 weak shapes flag below floor + margin
TSV_TIMEOUT = 60
MAX_CROPS = 6
MIN_CHARS = 20
MATH_FONTS = ("math", "cmsy", "cmmi", "cmex", "symbol")
TESSDATA_DIRS = ["/usr/share/tesseract-ocr/*/tessdata", "/usr/local/share/tessdata",
                 "/usr/share/tessdata", "/usr/share/tesseract-ocr/tessdata"]


def _warn(code, msg, page=None, level="warning"):
    w = {"level": level, "code": code, "message": msg}
    if page is not None:
        w["page"] = page
    return w


def tessdata_candidates(config=None):
    """Existing tessdata folders in priority order (config, $TESSDATA_PREFIX, known dirs)."""
    cands = [(config or {}).get("tessdata"), os.environ.get("TESSDATA_PREFIX")]
    for pat in TESSDATA_DIRS:
        cands.extend(sorted(glob.glob(pat)))
    out = []
    for c in cands:
        if not c:
            continue
        for d in (c, os.path.join(c, "tessdata")):
            if os.path.isdir(d) and d not in out:
                out.append(d)
    return out


def _langs(folder):
    return set(os.path.basename(p)[:-len(".traineddata")]
               for p in glob.glob(os.path.join(folder, "*.traineddata")))


def pick_ocr_language(config=None):
    """(folder, 'vie+eng' | 'vie' | 'eng' | None, available wanted langs)."""
    best_dir, best = None, []
    for d in tessdata_candidates(config):
        have = [lg for lg in ("vie", "eng") if lg in _langs(d)]
        if len(have) > len(best):
            best_dir, best = d, have
    return best_dir, ("+".join(best) if best else None), best


def _nfc(s):
    return unicodedata.normalize("NFC", s)


def _page_blocks(page, textpage=None):
    """[(bbox, text, fonts)] of the text blocks of one page, PyMuPDF order."""
    d = page.get_text("dict", textpage=textpage) if textpage else page.get_text("dict")
    out = []
    for b in d.get("blocks", ()):
        if b.get("type") != 0:
            continue
        lines, fonts = [], set()
        for ln in b.get("lines", ()):
            spans = ln.get("spans", ())
            fonts.update(s.get("font", "") for s in spans)
            lines.append("".join(s.get("text", "") for s in spans))
        text = _nfc("\n".join(lines)).strip()
        if text:
            out.append((tuple(round(v, 2) for v in b["bbox"]), text, fonts))
    return out


def _ocr_line_text(line, gap):
    """Line text rebuilt from rawdict char boxes: a space where the gap exceeds gap * median height."""
    chars = [c for sp in line.get("spans", ()) for c in sp.get("chars", ())]
    plain = "".join(sp.get("text", "") for sp in line.get("spans", ()))
    if not chars:
        return plain
    boxes = [c.get("bbox") for c in chars]
    if any(not b or len(b) < 4 for b in boxes):
        return plain
    hs = sorted(b[3] - b[1] for b in boxes)
    limit = gap * hs[len(hs) // 2]
    out, prev = [], None
    for c, b in zip(chars, boxes):
        ch = c.get("c", "")
        if ch.isspace():
            if out and out[-1] != " ":
                out.append(" ")
            prev = None
            continue
        if prev is not None and out and out[-1] != " " and b[0] - prev > limit:
            out.append(" ")
        out.append(ch)
        prev = b[2]
    return "".join(out)


def _ocr_blocks(page, tp, gap=OCR_GAP):
    """`_page_blocks` shape for an OCR textpage, spacing rebuilt from char boxes (bridge glues words)."""
    try:
        d = page.get_text("rawdict", textpage=tp)
    except Exception:  # noqa: BLE001 - no boxes: today's text
        return _page_blocks(page, tp)
    out = []
    for b in d.get("blocks", ()):
        if b.get("type") != 0:
            continue
        lines, fonts = [], set()
        for ln in b.get("lines", ()):
            fonts.update(s.get("font", "") for s in ln.get("spans", ()))
            lines.append(_ocr_line_text(ln, gap))
        text = _nfc("\n".join(lines)).strip()
        if text:
            out.append((tuple(round(v, 2) for v in b["bbox"]), text, fonts))
    return out


def _line_blocks(page):
    """Line-level (bbox, text, fonts) items, used when MuPDF merged both columns into one block."""
    out = []
    for b in page.get_text("dict").get("blocks", ()):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", ()):
            text = _nfc("".join(s.get("text", "") for s in ln.get("spans", ()))).strip()
            if text:
                out.append((tuple(round(v, 2) for v in ln["bbox"]), text,
                            set(s.get("font", "") for s in ln.get("spans", ()))))
    return out


def _merge_column(lines):
    """Merge vertically adjacent lines of one column back into paragraphs."""
    out = []
    for bb, text, fonts in sorted(lines, key=lambda b: b[0][1]):
        if out and bb[1] - out[-1][0][3] < 0.6 * (bb[3] - bb[1]):
            pb = out[-1][0]
            out[-1] = ((min(pb[0], bb[0]), pb[1], max(pb[2], bb[2]), bb[3]),
                       out[-1][1] + "\n" + text, out[-1][2] | fonts)
        else:
            out.append((bb, text, set(fonts)))
    return out


def _inside(box, outer):
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]


def _overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 1 and min(a[3], b[3]) - max(a[1], b[1]) > 1


def _order(blocks, width):
    """Conservative reading order; returns (blocks, two_column)."""
    mid = width / 2.0
    left = [b for b in blocks if b[0][2] <= mid]
    right = [b for b in blocks if b[0][0] >= mid]
    if len(left) >= 2 and len(right) >= 2 and len(left) + len(right) == len(blocks):
        return sorted(left, key=lambda b: b[0][1]) + sorted(right, key=lambda b: b[0][1]), True
    return blocks, False


def _order_page(page, blocks, width):
    """_order on blocks; if that fails, retry on lines (MuPDF merges same-baseline columns)."""
    res, two = _order(blocks, width)
    if two or not blocks:
        return res, two
    lines = _line_blocks(page)
    mid = width / 2.0
    if not any(b[0][0] < mid < b[0][2] for b in blocks):
        return res, False
    res2, two2 = _order(lines, width)
    if two2:
        lf = [b for b in res2 if b[0][2] <= mid]
        return _merge_column(lf) + _merge_column(res2[len(lf):]), True
    return res, False


def _suspect(text):
    """Heuristic flags (warnings, not proof) for one page's text."""
    flags = []
    if len(text.strip()) < MIN_CHARS:
        return ["missing_text"]
    bad = sum(1 for c in text if c == "�" or (unicodedata.category(c) == "Cc"
                                                     and c not in "\n\t\r"))
    if bad / float(len(text)) > 0.01:
        flags.append("bad_encoding")
    if not any(c.isalpha() for c in text):
        flags.append("no_letters")
    return flags


def page_re(table):
    """Page-number furniture line: Trang|Page|extra word N[/N]; `- N -` needs no word."""
    return re.compile(r"^\s*(?:" + langtable.alt("(?:Trang|Page)", "page", table)
                      + r"\s*\d+(?:\s*(?:/|of)\s*\d+)?|-\s*\d+\s*-)\s*$", re.I)


_PAGE_NO = page_re(langtable.load())
FURNITURE_EDGE = 2   # first / last non-empty lines of a page that can be furniture
LEAK_RATIO = 0.8      # edge line this close to a dropped header is an OCR-garbled leak
LEAK_MIN_KEY = 8      # shorter keys are too easy to match by chance
FURNITURE_PAGES = 3  # a repeated header / footer needs at least max(3, half the pages)


def _strip_furniture(pages, leaks=None):
    """-> (pages without page numbers and repeated headers/footers, removed count).

    pages: one list of text lines per page. Only the first / last FURNITURE_EDGE non-empty
    lines count; a line is furniture when it is a page number or its key (digits folded,
    whitespace removed, case folded: OCR spacing differs per page) sits in the edge of
    >= max(FURNITURE_PAGES, half) pages. Blocks are not touched. A kept edge line that nearly
    equals a dropped key (OCR garble) is a leak: (page, line index in the returned pages) is
    added to `leaks` when given.
    """
    def edge(lines):
        idx = [i for i, ln in enumerate(lines) if ln.strip()]
        return sorted(set(idx[:FURNITURE_EDGE] + idx[-FURNITURE_EDGE:]))

    def content(ln):  # a numbered question / option line is never a repeated header
        return bool(segment._Q.match(ln) or segment._OPT.match(ln))

    def key(ln):
        return re.sub(r"\s+", "", re.sub(r"\d+", "#", _nfc(ln))).casefold()

    seen = {}
    for lines in pages:
        for k in set(key(lines[i]) for i in edge(lines) if not content(lines[i])):
            seen[k] = seen.get(k, 0) + 1
    need = max(FURNITURE_PAGES, (len(pages) + 1) // 2)
    dropped = [k for k, c in seen.items() if c >= need and len(k) >= LEAK_MIN_KEY]
    out, removed = [], 0
    for pi, lines in enumerate(pages):
        drop = set(i for i in edge(lines)
                   if _PAGE_NO.match(lines[i]) or (not content(lines[i]) and seen[key(lines[i])] >= need))
        removed += len(drop)
        kept = [i for i in range(len(lines)) if i not in drop]
        if leaks is not None and dropped:
            for i in edge(lines):
                if i in drop or content(lines[i]):
                    continue
                k = key(lines[i])
                if any(difflib.SequenceMatcher(None, d, k).ratio() >= LEAK_RATIO for d in dropped):
                    leaks.add((pi, kept.index(i)))
        out.append([lines[i] for i in kept])
    return out, removed


_VOWELS = frozenset("aeiouyAEIOUY")
_MATH_OK = frozenset("+-*/=<>()[]{}^_.,;:%'\"≤≥≠±×÷√π°")
_TOKEN = re.compile(r"[^\W\d_]+")


def _glued(word):
    """True when a letter run holds >= 2 vowel clusters that each carry a mark (words run together)."""
    clusters, cur, marked = 0, False, False
    for ch in unicodedata.normalize("NFD", word) + " ":
        if unicodedata.combining(ch):
            marked = marked or cur
        elif ch in _VOWELS:
            cur = True
        else:
            if cur and marked:
                clusters += 1
            cur, marked = False, False
    return clusters >= 2


_SCRIPTS = tuple(w.upper() for w in langtable.raw("scripts", langtable.load()))


def _odd_chars(tok, scripts=None):
    """True when a token holds a char outside Latin/Vietnamese letters, digits, punctuation, common math;
    `scripts` = extra allowed Unicode script prefixes (config/lang.json "scripts", e.g. GREEK)."""
    allowed = ("LATIN",) + tuple(scripts if scripts is not None else _SCRIPTS)
    for ch in unicodedata.normalize("NFC", tok):
        if ch.isspace() or ch in _MATH_OK or ch.isdigit() or ord(ch) < 128:
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("L") and unicodedata.name(ch, "").startswith(allowed):
            continue
        if cat in ("Sm", "Mn", "Mc") or 0x2010 <= ord(ch) <= 0x2027:
            continue
        return True
    return False


def _tok_key(tok):
    """NFC token without edge punctuation (the key shared by the TSV map and the OCR lines)."""
    t = unicodedata.normalize("NFC", tok)
    i, j = 0, len(t)
    while i < j and unicodedata.category(t[i]).startswith("P"):
        i += 1
    while j > i and unicodedata.category(t[j - 1]).startswith("P"):
        j -= 1
    return t[i:j]


def _parse_tsv(text):
    """{word: conf} from tesseract TSV: word rows (level 5) with conf >= 0; duplicates keep the lower median
    (min flagged every "hơn" of a page for one bad read: 71.5 sweep, family D)."""
    seen = {}
    for ln in (text or "").splitlines()[1:]:
        f = ln.split("\t", 11)
        if len(f) < 12 or f[0] != "5":
            continue
        try:
            c = float(f[10])
        except ValueError:
            continue
        w = _tok_key(f[11].strip())
        if c >= 0 and w:
            seen.setdefault(w, []).append(c)
    return dict((w, sorted(v)[(len(v) - 1) // 2]) for w, v in seen.items())


def _tsv_conf(page, lang, tess_dir, config, why=None):
    """{word: conf 0-100} of one page from the tesseract CLI (same pixels as the bridge), else None;
    the reason goes to `why` (list). Untrusted PDF reaches the binary only as PNG pixels on stdin."""
    if (config or {}).get("ocr_conf", OCR_CONF_DEFAULT) == "off":
        return None
    why = why if why is not None else []
    exe = shutil.which("tesseract")
    if not exe:
        why.append("tesseract binary not found")
        return None
    argv = [exe, "stdin", "stdout", "-l", lang, "--psm", "3"]
    if tess_dir:
        argv += ["--tessdata-dir", tess_dir]
    argv.append("tsv")
    try:
        png = page.get_pixmap(dpi=OCR_DPI).tobytes("png")
        r = subprocess.run(argv, input=png, capture_output=True, timeout=TSV_TIMEOUT)
        if r.returncode != 0:
            why.append("tesseract exit %d" % r.returncode)
            return None
        return _parse_tsv(r.stdout.decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001 - confidence is optional data
        why.append("%s" % (exc.__class__.__name__,))
        return None


def _floor(lang, config=None):
    """Low-confidence floor for the first OCR language: config/lang.json "ocr_low_conf" {code: n}, else the default."""
    try:
        v = (langtable.load() or {}).get("ocr_low_conf", {}).get((lang or "").split("+")[0])
    except (ValueError, AttributeError):
        v = None
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else OCR_LOW_CONF


_WEAK = re.compile(r"^(?:\$\d+|[A-Z]\d+)$")


def _odd_token(tok, conf=None, floor=None):
    """71.3 glyph plausibility. Strong (no confidence needed): a digit between two lower-case letters
    ("h0n"), an ASCII dollar sign touching a lower-case letter ("$o"). Weak: "$6", "S6" only when the word's
    TSV conf is below floor + TOKEN_MARGIN (no conf: never, protects money and math)."""
    t = _tok_key(tok)
    for a, b, c in zip(t, t[1:], t[2:]):
        if unicodedata.category(a) == "Ll" and b.isdecimal() and unicodedata.category(c) == "Ll":
            return True
    for a, b in zip(t, t[1:]):
        if (a == "$" and unicodedata.category(b) == "Ll") or (unicodedata.category(a) == "Ll" and b == "$"):
            return True
    if conf is not None and _WEAK.match(t):
        return conf < (OCR_LOW_CONF if floor is None else floor) + TOKEN_MARGIN
    return False


def _ocr_doubt(qs, starts, lines, page_len, ocr_pages, leaks, lang_ok, suspect_pages=(), conf=None,
               floor=None):
    """Set q["ocr_doubt"] = sorted kinds (glued / chars / furniture / lang_missing / low_conf / token) on
    every question with lines on an OCR page; returns their indexes. starts: first flat line of each
    question; page_len: lines per page; leaks: {(page, line)} from _strip_furniture; lang_ok: vie
    available; conf: {page: {word: conf}} from _tsv_conf (None = 71.2 off, strong token shapes still run)."""
    ocr_q = []
    if len(starts) != len(qs):
        return ocr_q
    flat = [(pi, j) for pi, ln in enumerate(page_len) for j in range(ln)]
    fl = OCR_LOW_CONF if floor is None else floor
    for k, q in enumerate(qs):
        end = starts[k + 1] if k + 1 < len(starts) else len(flat)
        idx = [i for i in range(starts[k], end) if flat[i][0] in ocr_pages]
        if not idx:
            continue
        ocr_q.append(k)
        kinds = set()
        if not lang_ok:
            kinds.add("lang_missing")
        if any(flat[i] in leaks for i in idx):
            kinds.add("furniture")
        if any(flat[i][0] in suspect_pages for i in idx):
            kinds.add("chars")
        for i in idx:
            cp = (conf or {}).get(flat[i][0])
            for tok in lines[i].split():
                if _odd_chars(tok):
                    kinds.add("chars")
                if any(_glued(w) for w in _TOKEN.findall(tok)):
                    kinds.add("glued")
                c = cp.get(_tok_key(tok)) if cp else None
                if c is not None and c < fl:
                    kinds.add("low_conf")
                if _odd_token(tok, c, fl):
                    kinds.add("token")
        if kinds:
            q["ocr_doubt"] = sorted(kinds)
    return ocr_q


def _opt_class(text):
    for ch in text.strip():
        cat = unicodedata.category(ch)
        return "L" if cat.startswith("L") else "D" if cat.startswith("N") else "S"
    return "S"


def _option_parity(qs, ocr_q):
    """71.4 soft structure flag "option_parity" on OCR questions: exactly one option starts with another
    glyph class (letter/digit/symbol) than >= 3 others, or the option count differs from the mode of the
    OCR questions while that mode covers >= 80% of them. Text is never changed."""
    opts = dict((k, [o.get("text", "") for o in qs[k].get("options") or () if isinstance(o, dict)])
                for k in ocr_q)
    counts = [len(v) for v in opts.values() if v]
    mode = max(set(counts), key=counts.count) if counts else 0
    mode_ok = bool(counts) and counts.count(mode) * 5 >= len(counts) * 4
    for k, v in opts.items():
        if not v:
            continue
        cls = [_opt_class(t) for t in v]
        odd = len(set(cls)) == 2 and min(cls.count(c) for c in set(cls)) == 1 and len(v) >= 4
        if odd or (mode_ok and len(v) != mode):
            qs[k].setdefault("structure", [])
            if "option_parity" not in qs[k]["structure"]:
                qs[k]["structure"] = qs[k]["structure"] + ["option_parity"]


def _cut_boundaries(pages, page_lines):
    """page_cut_suspect warnings for boundaries n|n+1 where a question seems to run over (phase 47).

    Both pages need native text; scanned pages are left to the reply-side test in refine.
    S1 last numbered line of n has < 4 option lines after it and n+1 starts unnumbered;
    S2 last line of n has no sentence end (or ends in an operator) and S3 n+1 starts unnumbered;
    S4 an image of n+1 sits above its first numbered line while n ends inside a question.
    """
    def ok(p):
        return p.get("status") != "ocr" and p.get("chars", 0) > 0

    out = []
    for i in range(len(pages) - 1):
        a, b = pages[i], pages[i + 1]
        la = [ln for ln in page_lines[i] if ln.strip()]
        lb = [ln for ln in page_lines[i + 1] if ln.strip()]
        if not (ok(a) and ok(b) and la and lb):
            continue
        last_q = max((k for k, ln in enumerate(la) if segment._Q.match(ln)), default=None)
        n_opts = (sum(1 for ln in la[last_q + 1:] if segment._OPT.match(ln))
                  if last_q is not None else None)
        short = n_opts is not None and n_opts < 4
        unnumbered = not segment._Q.match(lb[0])
        tail = la[-1].rstrip()
        s1 = short and unnumbered
        s2 = tail[-1:] not in tuple(".?!:") or tail[-1:] in tuple(_TRAIL)
        s4 = short and _image_before_question(b)
        why = [name for name, hit in (("S1", s1), ("S2+S3", s2 and unnumbered), ("S4", s4)) if hit]
        if why:
            out.append(_warn("page_cut_suspect", "boundary %d|%d (%s)" % (a["n"], b["n"], ",".join(why)),
                             page=a["n"], level="info"))
    return out


def _image_before_question(page):
    """True when an image block comes before the first paragraph holding a numbered line."""
    for blk in page.get("blocks", ()):
        if blk.get("type") == "image":
            return True
        if blk.get("type") == "paragraph" and any(segment._Q.match(ln)
                                                  for ln in blk.get("text", "").split("\n")):
            return False
    return False


def _save_crop(page, rect, folder, rel_dir, name):
    os.makedirs(folder, exist_ok=True)
    full = os.path.join(folder, name)
    page.get_pixmap(clip=rect, dpi=min(CROP_DPI, 200)).save(full)
    with open(full, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    return "/".join([rel_dir, name]), sha


def _rel_dir(folder):
    rel = os.path.relpath(folder).replace(os.sep, "/")
    return os.path.basename(os.path.normpath(folder)) if rel.startswith("..") else rel


def ingest(path, config=None):
    config = config or {}
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise IngestError("corrupt", "cannot read %s: %s" % (path, exc))
    if not raw:
        raise IngestError("empty", "%s has no content" % path)
    fitz = optional.load("fitz", "pymupdf")
    try:
        pdf = fitz.open(stream=raw, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - any parse failure is data
        raise IngestError("corrupt", "cannot open PDF %s: %s" % (os.path.basename(path), exc))
    try:
        return _extract(fitz, pdf, raw, path, config)
    finally:
        pdf.close()


def _extract(fitz, pdf, raw, path, config):
    name = os.path.basename(path)
    if pdf.needs_pass:
        raise IngestError("encrypted", "%s is password protected" % name)
    if pdf.page_count == 0:
        raise IngestError("empty", "%s has no pages" % name)
    sha = hashlib.sha256(raw).hexdigest()
    ocr_mode = config.get("ocr", "auto")
    asset_dir = config.get("asset_dir") or os.path.join("work", "ingest", sha[:8])
    rel_dir = _rel_dir(asset_dir)
    warnings, assets, pages, page_lines = [], [], [], []
    counter = [0]
    tess_dir, lang, have = (None, None, [])
    if ocr_mode != "off":
        tess_dir, lang, have = pick_ocr_language(config)
    lang_warned = False
    conf_pages, conf_why = {}, []
    any_content = False

    for pno in range(pdf.page_count):
        n = pno + 1
        page = pdf[pno]
        pw, ph = page.rect.width, page.rect.height
        pwarn, items, tables = [], [], []
        try:
            for t in page.find_tables().tables:
                rows = [[_nfc(c or "") for c in r] for r in t.extract()]
                if rows:
                    tables.append((tuple(round(v, 2) for v in t.bbox), rows))
        except Exception:  # noqa: BLE001 - table detection is best effort
            tables = []
        tbbox = [t[0] for t in tables]
        text_blocks = [b for b in _page_blocks(page) if not any(_inside(b[0], t) for t in tbbox)]
        text_blocks, two_col = _order_page(page, text_blocks, pw)
        native_text = "\n".join(b[1] for b in text_blocks)
        fonts = set()
        for b in text_blocks:
            fonts |= b[2]
        try:
            images = [tuple(i["bbox"]) for i in page.get_image_info()]
        except Exception:  # noqa: BLE001
            images = []
        try:
            drawings = page.get_drawings()
        except Exception:  # noqa: BLE001
            drawings = []
        flags = _suspect(native_text)
        method, status = "native", "native_text"
        if not two_col and any(_overlap(a[0], b[0]) for i, a in enumerate(text_blocks)
                               for b in text_blocks[i + 1:]):
            pwarn.append(_warn("reading_order_uncertain", "text blocks overlap", n))
        for f in flags:
            code = "missing_text" if f == "missing_text" else "bad_encoding"
            pwarn.append(_warn(code, "page text suspicious (%s)" % f, n))
        if flags:
            status = "needs_review"
            if ocr_mode == "off":
                pass
            elif not lang:
                pwarn.append(_warn("ocr_unavailable", "no tesseract language data found", n))
            else:
                if "vie" not in have and not lang_warned:
                    warnings.append(_warn(
                        "ocr_language_missing",
                        "vie.traineddata not found in %s; every OCR question is marked ocr_doubt "
                        "(lang_missing), using %s. Put vie.traineddata in /usr/share/tesseract-ocr/<ver>/"
                        "tessdata/ or $TESSDATA_PREFIX (or config tessdata); the engine never fetches it"
                        % (", ".join(tessdata_candidates(config)) or "no tessdata folder", lang),
                        level="error"))
                    lang_warned = True
                try:
                    tp = page.get_textpage_ocr(language=lang, dpi=OCR_DPI, full=True,
                                               tessdata=tess_dir)
                    ocr_blocks = [b for b in _ocr_blocks(page, tp)
                                  if not any(_inside(b[0], t) for t in tbbox)]
                    ocr_text = "\n".join(b[1] for b in ocr_blocks)
                    if len(ocr_text.strip()) >= MIN_CHARS and len(ocr_text) > len(native_text):
                        text_blocks, method = ocr_blocks, "ocr"
                        native_text = ocr_text
                        status = "needs_review" if _suspect(ocr_text) else "ocr"
                        c = _tsv_conf(page, lang, tess_dir, config, conf_why)
                        if c is not None:
                            conf_pages[pno] = c
                except Exception as exc:  # noqa: BLE001 - OCR failure is data
                    pwarn.append(_warn("ocr_unavailable", "OCR failed: %s" % exc, n))
        extra = {"method": "ocr"} if method == "ocr" else {}
        for b in text_blocks:
            items.append(("paragraph", b[0], b[1], dict(extra)))
        for bbox, rows in tables:
            tx = "\n".join(" | ".join(r) for r in rows)
            pos = next((i for i, it in enumerate(items) if it[1][1] > bbox[1]), len(items))
            items.insert(pos, ("table", bbox, tx, {"rows": rows}))
        # visual preservation
        crops = []
        for bb in images:
            whole = (bb[2] - bb[0]) * (bb[3] - bb[1]) >= 0.9 * pw * ph
            if not (whole and method == "ocr"):  # OCR text already carries a scanned page
                crops.append(tuple(bb))
        try:
            clusters = page.cluster_drawings(drawings=drawings) if drawings else []
        except Exception:  # noqa: BLE001
            clusters = []
        for c in clusters:
            c = tuple(c)
            if (c[2] - c[0] >= 30 and c[3] - c[1] >= 30
                    and not any(_inside(c, t) for t in tbbox)):
                crops.append(c)
        if len(crops) > MAX_CROPS:
            pwarn.append(_warn("crops_capped", "more than %d visuals; kept first" % MAX_CROPS, n))
            crops = crops[:MAX_CROPS]
        jobs = [(c, "p%d_v%d.png" % (n, i + 1)) for i, c in enumerate(crops)]
        if any(m in f.lower() for f in fonts for m in MATH_FONTS):
            pwarn.append(_warn("math_possible", "math fonts on page; page image kept", n))
            jobs.append((None, "p%d_page.png" % n))
        for c, fname in jobs:
            rect = (fitz.Rect(c) if c else fitz.Rect(page.rect)) & page.rect
            if rect.is_empty:
                continue
            rel, h = _save_crop(page, rect, asset_dir, rel_dir, fname)
            aid = "a%d" % (len(assets) + 1)
            bbox = [round(v, 2) for v in tuple(rect)]
            assets.append({"id": aid, "path": rel, "mime": "image/png", "sha256": h,
                           "page": n, "bbox": bbox})
            pos = next((i for i, it in enumerate(items) if it[1][1] > bbox[1]), len(items))
            items.insert(pos, ("image", tuple(bbox), "", {"asset": aid}))
        blocks = []
        for kind, bbox, text, ex in items:
            counter[0] += 1
            blk = {"id": "b%d" % counter[0], "order": len(blocks), "type": kind, "text": text,
                   "level": None, "bbox": list(bbox), "origin": "extracted", "asset": None}
            blk.update(ex)
            blocks.append(blk)
        if native_text.strip() or images or drawings:
            any_content = True
        page_lines.append([])
        for kind, _bb, text, _ex in items:
            if kind == "paragraph":
                page_lines[-1].extend(text.split("\n"))
        pages.append({"n": n, "width": round(pw, 2), "height": round(ph, 2), "blocks": blocks,
                      "chars": len(native_text.strip()), "images": len(images),
                      "drawings": len(drawings), "status": status, "method": method,
                      "warnings": pwarn})
        warnings.extend(pwarn)
    if not any_content:
        raise IngestError("empty", "%s has no text and no images" % name)
    leaks = set()
    page_lines, removed = _strip_furniture(page_lines, leaks)
    if removed:
        warnings.append(_warn("page_furniture_removed", "%d page number / repeated header or "
                              "footer line(s) left out of the question text" % removed,
                              level="info"))
    warnings.extend(_cut_boundaries(pages, page_lines))
    flat = [ln for lines in page_lines for ln in lines]
    starts = []
    intro, qs, ok, bw = boundary.segment_reviewed(config, flat, starts=starts)
    warnings.extend(bw)
    keep = ok
    if not qs:
        warnings.append(_warn("no_question_numbering", "no question numbering found"))
    elif ok:
        pass
    elif segment.numbering(qs)["usable"]:
        keep = True
        warnings.extend(_warn(c, m) for c, m in segment.numbering_warnings(qs))
    else:
        warnings.append(_warn("segmentation_skipped",
                              "question numbering not consecutive or a question has no text"))
        warnings.extend(_warn(c, m) for c, m in segment.numbering_warnings(qs))
    sts = [p["status"] for p in pages]
    if "needs_review" in sts:
        status = "needs_review"
    elif all(s == "ocr" for s in sts):
        status = "ocr"
    elif "ocr" in sts:
        status = "mixed"
    else:
        status = "native_text"
    doc = {"schema_version": SCHEMA_VERSION, "status": status,
           "extraction": {"method": "pdf", "tool": "pymupdf %s" % fitz.VersionBind,
                          "ocr": ocr_mode},
           "meta": {}, "pages": pages, "assets": assets, "warnings": warnings,
           "source": {"path": name, "name": name, "format": "pdf", "sha256": sha,
                      "size": len(raw)}}
    if keep:
        ocr_pages = set(i for i, p in enumerate(pages) if p["method"] == "ocr")
        if ocr_pages:
            sus = set(i for i, p in enumerate(pages) if p["method"] == "ocr"
                      and any(w.get("code") == "bad_encoding" for w in p["warnings"]))
            ocr_q = _ocr_doubt(qs, starts, flat, [len(x) for x in page_lines], ocr_pages, leaks,
                               "vie" in have, sus, conf=conf_pages or None, floor=_floor(lang))
            _option_parity(qs, ocr_q)
            if conf_why and ocr_mode != "off" and config.get("ocr_conf", OCR_CONF_DEFAULT) != "off":
                warnings.append(_warn("ocr_conf_unavailable", "per-word OCR confidence skipped (%s)"
                                      % conf_why[0], level="info"))
        doc["questions"] = qs
        doc["intro"] = "\n".join(intro).strip()
    return doc
