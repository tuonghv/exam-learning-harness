#!/usr/bin/env python3
"""req.py - requirement ledger for Claude Code projects (stdlib only).

Layout (default docs/req, override with env REQ_DIR):
  raw/RAW-00001.md     verbatim user prompts (captured by hook)
  items/REQ-0001.md    one requirement per file
  epics/EPIC-001.md    big requests, decomposed into REQs
  STATE.json           current focus + next concrete step
  INDEX.md             generated overview (do not edit)
  config.json          optional: checks per status, task_glob, capture_min_chars

Lifecycle: TODO -> DESIGN -> IMPLEMENTING -> UNIT_TESTED -> VERIFIED -> DONE
Side states: SUPERSEDED, REJECTED
"""
import argparse, contextlib, datetime, json, os, re, subprocess, sys, unicodedata
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: no locking
    fcntl = None

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
DATA = ROOT / os.environ.get("REQ_DIR", "docs/req")
RAW_DIR, REQ_DIR, EPIC_DIR = DATA / "raw", DATA / "items", DATA / "epics"
STATE_FILE, INDEX_FILE, CONFIG_FILE = DATA / "STATE.json", DATA / "INDEX.md", DATA / "config.json"

ORDER = ["TODO", "DESIGN", "IMPLEMENTING", "UNIT_TESTED", "VERIFIED", "DONE"]
SIDE = ["SUPERSEDED", "REJECTED"]
CLOSED = {"DONE", *SIDE}
PREFIX = {"RAW": (RAW_DIR, 5), "REQ": (REQ_DIR, 4), "EPIC": (EPIC_DIR, 3)}
TOOL = "python3 .claude/req/req.py"


# ---------------------------------------------------------------- utilities
def die(msg, code=2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


@contextlib.contextmanager
def lock():
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / ".lock", "w") as fh:
        if fcntl:
            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl:
                fcntl.flock(fh, fcntl.LOCK_UN)


def parse(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        raise ValueError(f"{path.name}: missing frontmatter")
    meta = {}
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        k, sep, v = line.partition(":")
        if not sep:
            raise ValueError(f"{path.name}: bad frontmatter line: {line!r}")
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        meta[k.strip()] = v
    return meta, m.group(2)


def one_line(v):
    """Frontmatter is line-based: a newline in a value (e.g. --reason) would corrupt the file."""
    return " ".join(str(v).split("\n")).strip()


def dump(path, meta, body):
    out = ["---"]
    for k, v in meta.items():
        v = [one_line(x) for x in v] if isinstance(v, list) else one_line(v)
        out.append(f"{k}: [{', '.join(v)}]" if isinstance(v, list) else f"{k}: {v}")
    out.append("---")
    path.write_text("\n".join(out) + "\n" + body.rstrip() + "\n", encoding="utf-8")


def as_list(v):
    return v if isinstance(v, list) else ([v] if v else [])


def section_re(name):
    return re.compile(rf"^## {re.escape(name)}[^\n]*\n(.*?)(?=^## |\Z)", re.S | re.M)


def get_section(body, name):
    m = section_re(name).search(body)
    return m.group(1) if m else None


def append_section(body, name, text):
    m = section_re(name).search(body)
    if not m:
        return body.rstrip() + f"\n\n## {name}\n{text.rstrip()}\n"
    content = m.group(1).rstrip("\n")
    new = (content + "\n" if content.strip() else content) + text.rstrip() + "\n\n"
    return body[: m.start(1)] + new + body[m.end(1):]


def strip_comments(s):
    return re.sub(r"<!--.*?-->", "", s or "", flags=re.S).strip()


def acceptance(body):
    """[(checked, text)] for non-empty acceptance items."""
    items = []
    for chk, txt in re.findall(r"^\s*- \[( |x|X)\]\s*(.*)$", strip_comments(get_section(body, "Acceptance")), re.M):
        if re.sub(r"^AC\d+:\s*", "", txt).strip():
            items.append((chk.lower() == "x", txt.strip()))
    return items


def open_questions(body):
    return re.findall(r"^\s*- \[ \]\s*(.+)$", strip_comments(get_section(body, "Open questions")), re.M)


def fold(s):
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def next_id(prefix):
    d, width = PREFIX[prefix]
    d.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for p in d.glob(f"{prefix}-*.md") if (m := re.match(rf"{prefix}-(\d+)\.md$", p.name))]
    return f"{prefix}-{(max(nums) + 1 if nums else 1):0{width}d}"


def norm_id(i):
    i = i.strip().upper()
    m = re.match(r"^(RAW|REQ|EPIC)-?(\d+)$", i)
    if not m:
        die(f"bad id: {i}")
    d, width = PREFIX[m.group(1)]
    return f"{m.group(1)}-{int(m.group(2)):0{width}d}"


def path_of(i):
    i = norm_id(i)
    p = PREFIX[i.split("-")[0]][0] / f"{i}.md"
    if not p.exists():
        die(f"{i} not found")
    return p


def load_all(prefix):
    d = PREFIX[prefix][0]
    out, errors = {}, []
    for p in sorted(d.glob(f"{prefix}-*.md")) if d.exists() else []:
        try:
            meta, body = parse(p)
            out[meta.get("id", p.stem)] = (meta, body, p)
        except Exception as e:
            errors.append(str(e))
    return out, errors


def state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(s):
    s["updated"] = now()
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def quote_raw(rid, limit=3000):
    meta, body = parse(path_of(rid))
    text = body.strip()
    if len(text) > limit:
        text = text[:limit] + f"\n...(truncated, full text in {rid})"
    return "\n".join(f"> {line}" if line else ">" for line in [f"**[{rid}]** {meta.get('created', '')}"] + text.splitlines())


def epic_status(eid, reqs):
    kids = [m for m, _, _ in reqs.values() if m.get("epic") == eid and m.get("status") not in SIDE]
    if not kids:
        return "TODO"
    return ORDER[min(ORDER.index(m["status"]) if m["status"] in ORDER else 0 for m in kids)]


# ---------------------------------------------------------------- templates
REQ_TMPL = """## Original (verbatim, never edit)
{original}

## Requirement
<!-- Clear, testable statement in one language (English preferred). EARS: "WHEN <trigger>, the <system> SHALL <response>." -->
{text}

## Acceptance
<!-- Each item objectively verifiable. VERIFIED requires every box ticked. -->
- [ ] AC1:

## Open questions
<!-- "- [ ] Q1: ..." = unresolved (blocks TODO->DESIGN). Resolved: "- [x] Q1: ... -> answer (date)". -->

## Design
<!-- Filled in DESIGN. Keep it short; link existing design docs/TASK files instead of duplicating. -->

## Progress log

## Evidence
"""

EPIC_TMPL = """## Original (verbatim, never edit)
{original}

## Goal
{text}

## Decomposition
<!-- One line per child: "- REQ-0012" (auto-added) or "- [ ] TBD: <coarse item not yet specified>". TBD lines are tracked until converted into REQs. -->

## Notes
"""


# ---------------------------------------------------------------- commands
def cmd_init(a):
    for d in (RAW_DIR, REQ_DIR, EPIC_DIR):
        d.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps({
            "checks": {"UNIT_TESTED": "", "VERIFIED": ""},
            "task_glob": "",
            "capture_min_chars": 25,
        }, indent=2) + "\n", encoding="utf-8")
    if not STATE_FILE.exists():
        save_state({"focus": "", "next": ""})
    cmd_index(a, quiet=True)
    print(f"initialized {DATA.relative_to(ROOT)}")


def capture_raw(text, session="", ignore_reason=""):
    """Used by the UserPromptSubmit hook. Returns RAW id. ignore_reason saves it already IGNORED (short ack, RAW-00380)."""
    if len(text) > 20000:
        text = text[:20000] + "\n...(truncated at 20000 chars)"
    meta = {"id": "", "status": "NEW", "created": now(), "session": session or "-", "links": []}
    if ignore_reason:
        meta["status"] = "IGNORED"
        meta["reason"] = ignore_reason
    with lock():
        rid = next_id("RAW")
        meta["id"] = rid
        dump(RAW_DIR / f"{rid}.md", meta, text + "\n")
    return rid


def cmd_raw(a):
    raws, _ = load_all("RAW")
    if a.action == "add":
        if not (a.text or "").strip():
            die("raw add needs --text")
        print(capture_raw(a.text))
    elif a.action == "list":
        rows = [(i, m) for i, (m, _, _) in raws.items() if not a.new or m.get("status") == "NEW"]
        for i, m in rows[-a.limit:]:
            first = raws[i][1].strip().splitlines()[0][:100] if raws[i][1].strip() else ""
            print(f"{i}  {m.get('status'):8} {m.get('created')}  {first}")
        if not rows:
            print("(none)")
    elif a.action == "show":
        for i in a.ids:
            print(path_of(i).read_text(encoding="utf-8"))
    elif a.action in ("ignore", "link"):
        if a.action == "link" and not a.target:
            die("raw link needs --to REQ-xxxx|EPIC-xxx")
        if a.action == "ignore" and not a.reason:
            die("raw ignore needs --reason (e.g. 'question', 'chatter', 'instruction for current step')")
        if a.ac and (a.action != "link" or len(a.ids) != 1 or "," in a.target):
            die("--ac needs raw link with one RAW and one --to item")
        if a.ac and parse(path_of(norm_id(a.target)))[0].get("status") in ("VERIFIED", "DONE"):
            die(f"{norm_id(a.target)} is VERIFIED/DONE: reopen it with `req.py status` before adding an AC (nothing written)")
        added = []
        with lock():
            for i in a.ids:
                p = path_of(i)
                meta, body = parse(p)
                rid = meta["id"]
                if a.action == "ignore":
                    meta["status"] = "IGNORED"
                    meta["reason"] = a.reason
                else:
                    for t in a.target.split(","):
                        t = norm_id(t)
                        tp = path_of(t)
                        tm, tb = parse(tp)
                        if rid not in as_list(tm.get("source")):
                            tm["source"] = as_list(tm.get("source")) + [rid]
                            tb = append_section(tb.replace("> (entered directly, no RAW)\n", ""), "Original", quote_raw(rid))
                            tb = append_section(tb, "Progress log", f"- {now()} linked {rid} (new input from user; re-check scope)")
                            tm["updated"] = now()
                            dump(tp, tm, tb)
                        if a.ac:
                            added.append((t, add_ac(tp, a.ac, rid)))
                        meta["links"] = sorted(set(as_list(meta.get("links")) + [t]))
                    meta["status"] = "TRIAGED"
                dump(p, meta, body)
                print(f"{rid} -> {meta['status']}")
        for t, n in added:
            print(f"{t} +AC{n}")
        if a.note is not None:
            for i in a.ids:
                note_raw(a.note or "active", norm_id(i), a.ac or "linked to " + a.target)
        cmd_index(a, quiet=True)


def add_ac(tp, text, rid):
    """98.2: append the next ACn to a REQ's Acceptance (caller holds lock()); refuses VERIFIED/DONE items."""
    tm, tb = parse(tp)
    if tm.get("status") in ("VERIFIED", "DONE"):
        die(f"{tm['id']} is {tm.get('status')}: reopen it with `req.py status` before adding an AC")
    sec = get_section(tb, "Acceptance")
    if sec is None:
        die(f"{tm['id']}: no Acceptance section")
    clean = strip_comments(sec)
    nums = [int(x) for x in re.findall(r"^\s*- \[(?: |x|X)\]\s*AC(\d+):(?=[ \t]*\S)", clean, re.M)]
    n = max(nums) + 1 if nums else 1
    line = f"- [ ] AC{n}: {' '.join(text.split())} ({rid})"
    lines = sec.rstrip("\n").split("\n")
    # drop an empty template placeholder ("- [ ] AC1:"), then append after the last line of the section
    lines = [l for l in lines if not re.match(r"^\s*- \[ \]\s*AC\d+:\s*$", l)]
    new_sec = "\n".join(lines + [line]) + "\n"
    tb = tb.replace(sec, new_sec if sec.endswith("\n") else new_sec.rstrip("\n"), 1)
    tb = append_section(tb, "Progress log", f"- {now()} {rid}: added AC{n}")
    tm["updated"] = now()
    dump(tp, tm, tb)
    return n


def note_raw(task, rid, text):
    """98.2 --note: record the RAW on the task via backlog.sh note (its own lock); a failure only warns."""
    sh = Path(__file__).resolve().parent.parent / "scripts" / "backlog.sh"
    try:
        r = subprocess.run(["bash", str(sh), "note", task, rid, text[:200]], capture_output=True, text=True, timeout=60)
        out = (r.stdout + r.stderr).strip().splitlines()
        print(out[-1] if r.returncode == 0 and out else f"WARN note: {(out or ['rc %d' % r.returncode])[-1]}")
    except Exception as e:  # the ledger write stands; the note can be re-run
        print(f"WARN note: {e}")


def create_item(prefix, a, tmpl):
    raws = [norm_id(r) for r in (a.frm or "").split(",") if r.strip()]
    with lock():
        iid = next_id(prefix)
        original = "\n\n".join(quote_raw(r) for r in raws) or "> (entered directly, no RAW)"
        meta = {"id": iid, "title": a.title.replace("\n", " ")}
        if prefix == "REQ":
            meta.update({"status": "TODO", "epic": norm_id(a.epic) if a.epic else "", "area": a.area or "",
                         "source": raws, "tasks": [], "supersedes": norm_id(a.supersedes) if a.supersedes else ""})
        else:
            meta.update({"source": raws})
        meta.update({"created": now(), "updated": now()})
        body = tmpl.format(original=original, text=a.text or "")
        path = PREFIX[prefix][0] / f"{iid}.md"
        dump(path, meta, body)
        for r in raws:
            rp = path_of(r)
            rm, rb = parse(rp)
            rm["status"] = "TRIAGED"
            rm["links"] = sorted(set(as_list(rm.get("links")) + [iid]))
            dump(rp, rm, rb)
        if prefix == "REQ" and meta["epic"]:
            ep = path_of(meta["epic"])
            em, eb = parse(ep)
            eb = append_section(eb, "Decomposition", f"- {iid}")
            em["updated"] = now()
            dump(ep, em, eb)
        if prefix == "REQ" and meta["supersedes"]:
            sp = path_of(meta["supersedes"])
            sm, sb = parse(sp)
            if sm.get("status") not in CLOSED:
                sm["status"] = "SUPERSEDED"
            sb = append_section(sb, "Progress log", f"- {now()} superseded by {iid}")
            sm["updated"] = now()
            dump(sp, sm, sb)
    cmd_index(a, quiet=True)
    hint = "fill Requirement / Acceptance / Open questions" if prefix == "REQ" else "fill Goal, then Decomposition (REQs or '- [ ] TBD:' lines)"
    print(f"{iid} created: {path.relative_to(ROOT)}  ({hint})")


def cmd_new(a):
    create_item("REQ", a, REQ_TMPL)


def cmd_epic(a):
    if a.action == "new":
        if not a.title:
            die("epic new needs --title")
        create_item("EPIC", a, EPIC_TMPL)
    else:
        reqs, _ = load_all("REQ")
        epics, _ = load_all("EPIC")
        for eid, (m, b, _) in epics.items():
            kids = [i for i, (rm, _, _) in reqs.items() if rm.get("epic") == eid]
            done = sum(reqs[i][0].get("status") in CLOSED for i in kids)
            tbd = len(re.findall(r"^\s*- \[ \]\s*TBD", b, re.M))
            print(f"{eid}  {epic_status(eid, reqs):12} {done}/{len(kids)} closed  TBD={tbd}  {m.get('title')}")
        if not epics:
            print("(no epics)")


GATES = {
    "DESIGN": "Requirement filled, no unresolved '- [ ]' in Open questions",
    "IMPLEMENTING": "Design section filled",
    "UNIT_TESTED": "at least one Acceptance item + --evidence (test command/result)",
    "VERIFIED": "every Acceptance box ticked + --evidence (independent verification)",
    "DONE": "nothing extra (reported/merged)",
}


def gate_problems(new, meta, body, evidence):
    probs = []
    if new == "DESIGN":
        if not strip_comments(get_section(body, "Requirement")):
            probs.append("Requirement section is empty")
        q = open_questions(body)
        if q:
            probs.append(f"{len(q)} unresolved open question(s) - ask the user: " + " | ".join(q[:5]))
    elif new == "IMPLEMENTING":
        if not strip_comments(get_section(body, "Design")):
            probs.append("Design section is empty")
    elif new == "UNIT_TESTED":
        if not acceptance(body):
            probs.append("no Acceptance items")
        if not evidence:
            probs.append("--evidence required (which tests, result)")
    elif new == "VERIFIED":
        ac = acceptance(body)
        if not ac:
            probs.append("no Acceptance items")
        left = [t for c, t in ac if not c]
        if left:
            probs.append(f"{len(left)} Acceptance item(s) not ticked: " + " | ".join(left[:5]))
        if not evidence:
            probs.append("--evidence required (how it was verified)")
    return probs


def run_check(new, rid):
    cmd = (config().get("checks") or {}).get(new, "")
    if not cmd:
        return None
    cmd = cmd.replace("{id}", rid)
    print(f"running configured check for {new}: {cmd}")
    r = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "REQ_ID": rid}, timeout=3600)
    tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-15:])
    if r.returncode != 0:
        die(f"configured check failed (exit {r.returncode}):\n{tail}")
    return f"check `{cmd}` passed"


def cmd_status(a):
    new = a.new.upper()
    if new not in ORDER + SIDE:
        die(f"unknown status {new}; valid: {' '.join(ORDER + SIDE)}")
    # Gates and the configured check run unlocked: a check may take minutes, and the
    # UserPromptSubmit hook must not wait on the lock (its timeout would drop the RAW).
    p = path_of(a.id)
    meta, body = parse(p)
    rid, cur = meta["id"], meta.get("status", "TODO")
    if new == cur:
        die(f"{rid} already {cur}")
    forced, chk = False, None
    if new in SIDE or cur in SIDE:
        if not a.reason:
            die(f"{cur} -> {new} requires --reason")
    else:
        ci, ni = ORDER.index(cur), ORDER.index(new)
        if ni < ci and not a.reason:
            die(f"moving back {cur} -> {new} requires --reason (what regressed)")
        if ni > ci + 1:
            if not (a.force and a.reason):
                die(f"cannot skip {cur} -> {new}; next allowed is {ORDER[ci + 1]} (or --force --reason)")
            forced = True
        if ni > ci:
            probs = gate_problems(new, meta, body, a.evidence)
            if probs and not (a.force and a.reason):
                die(f"gate for {new} not met ({GATES[new]}):\n  - " + "\n  - ".join(probs))
            forced = forced or bool(probs)
            chk = run_check(new, rid)
    with lock():
        meta, body = parse(p)
        if meta.get("status", "TODO") != cur:
            die(f"{rid} changed to {meta.get('status')} while checking; re-run")
        if chk:
            body = append_section(body, "Evidence", f"- {now()} [{new}] {chk}")
        if a.evidence:
            body = append_section(body, "Evidence", f"- {now()} [{new}] {a.evidence}")
        note = "; ".join(x for x in [a.reason, "FORCED" if forced else ""] if x)
        body = append_section(body, "Progress log", f"- {now()} {cur} -> {new}" + (f" ({note})" if note else ""))
        meta["status"], meta["updated"] = new, now()
        dump(p, meta, body)
        if a.next and new not in CLOSED:  # one call: move and set the next step
            body = append_section(body, "Progress log", f"- {now()} next: {a.next}")
            dump(p, meta, body)
        s = state()
        if a.next and new not in CLOSED:
            s["focus"], s["next"] = rid, a.next
            save_state(s)
        elif s.get("focus") == rid:
            s["next"] = ""  # old step belongs to the previous phase
            if new in CLOSED:
                s["focus"] = ""
            save_state(s)
    cmd_index(a, quiet=True)
    print(f"{rid}: {cur} -> {new}")
    if new in CLOSED:
        print("focus cleared. Run: " + TOOL + " next")
    else:
        cmd_gaps(argparse.Namespace(id=rid))
        if a.next:
            print(f"focus={rid}  next={a.next}")
        else:
            print(f"now set the next concrete step: {TOOL} focus {rid} --next \"...\" (or pass --next to status)")


def cmd_ac(a):
    """Tick Acceptance items by id (the TASK's verification is the evidence); no hand edits."""
    want = [x.strip().upper() for x in a.items.split(",") if x.strip()]
    with lock():
        p = path_of(a.id)
        meta, body = parse(p)
        sec = get_section(body, "Acceptance") or ""
        ids = []  # only filled items outside comments, once each (template placeholder is empty)
        for i in re.findall(r"^\s*- \[(?: |x|X)\]\s*(AC\d+):(?=[ \t]*\S)", strip_comments(sec), re.M):
            if i not in ids:
                ids.append(i)
        if want == ["ALL"]:
            want = ids
        miss = [w for w in want if w not in ids]
        if miss or not want:
            die(f"{meta['id']}: unknown Acceptance id(s) {', '.join(miss) or '(none given)'}; have: {', '.join(ids) or 'none'}")
        new_sec = sec
        for w in want:
            new_sec = re.sub(r"^(\s*- )\[ \](\s*%s:)(?=[ \t]*\S)" % re.escape(w), r"\1[x]\2", new_sec, flags=re.M)
        body = body.replace(sec, new_sec, 1)
        body = append_section(body, "Evidence", f"- {now()} [AC {','.join(want)}] {a.evidence}")
        meta["updated"] = now()
        dump(p, meta, body)
    left = [t for c, t in acceptance(body) if not c]
    print(f"{meta['id']}: ticked {','.join(want)}; {len(left)} Acceptance item(s) left")


def cmd_log(a):
    with lock():
        p = path_of(a.id)
        meta, body = parse(p)
        body = append_section(body, "Progress log", f"- {now()} {a.message}")
        meta["updated"] = now()
        dump(p, meta, body)
    print(f"logged on {meta['id']}")


def cmd_task(a):
    with lock():
        p = path_of(a.id)
        meta, body = parse(p)
        meta["tasks"] = sorted(set(as_list(meta.get("tasks")) + [t.strip() for t in a.tasks.split(",") if t.strip()]))
        meta["updated"] = now()
        dump(p, meta, body)
    print(f"{meta['id']} tasks: {', '.join(meta['tasks'])}")


def cmd_focus(a):
    with lock():
        s = state()
        if a.clear:
            s = {"focus": "", "next": ""}
        if a.id:
            path_of(a.id)
            s["focus"] = norm_id(a.id)
        if a.next is not None:
            if not s.get("focus"):
                die("no focus set; pass an id")
            s["next"] = a.next
            p = path_of(s["focus"])
            meta, body = parse(p)
            body = append_section(body, "Progress log", f"- {now()} next: {a.next}")
            meta["updated"] = now()
            dump(p, meta, body)
        save_state(s)
    print(f"focus={s.get('focus') or '-'}  next={s.get('next') or '-'}")


def cmd_gaps(a):
    """Everything still missing for one REQ to reach DONE. The single source for 'am I done?'."""
    rid = a.id or state().get("focus")
    if not rid:
        die("no id and no focus")
    p = path_of(rid)
    meta, body = parse(p)
    rid, cur = meta["id"], meta.get("status", "TODO")
    print(f"{rid} [{cur}] {meta.get('title')}")
    if cur in CLOSED:
        print("  closed - nothing left")
        return
    ac = acceptance(body)
    q = open_questions(body)
    todo = []
    if not strip_comments(get_section(body, "Requirement")):
        todo.append("write Requirement statement")
    if q:
        todo.append(f"{len(q)} open question(s) waiting for user: " + " | ".join(q[:5]))
    if not ac:
        todo.append("define Acceptance items")
    if ORDER.index(cur) >= 1 and not strip_comments(get_section(body, "Design")):
        todo.append("fill Design section")
    left = [t for c, t in ac if not c]
    if left:
        todo.append(f"{len(left)}/{len(ac)} Acceptance not met: " + " | ".join(left[:8]))
    if not as_list(meta.get("tasks")) and ORDER.index(cur) >= 2:
        todo.append("no TASK linked (req.py task)")
    nxt = ORDER[ORDER.index(cur) + 1]
    probs = gate_problems(nxt, meta, body, evidence="(to be given)")
    print("  remaining:" if todo else "  remaining: none on content")
    for t in todo:
        print(f"   - {t}")
    print(f"  next status: {nxt}  gate: {GATES[nxt]}" + ("  -> READY" if not probs else "  -> BLOCKED: " + "; ".join(probs)))
    s = state()
    if s.get("focus") == rid and s.get("next"):
        print(f"  next step (STATE): {s['next']}")


def cmd_next(a):
    reqs, _ = load_all("REQ")
    s = state()
    f = s.get("focus")
    if f and f in reqs and reqs[f][0].get("status") not in CLOSED:
        print(f"continue focus {f} [{reqs[f][0]['status']}] {reqs[f][0].get('title')}")
        if s.get("next"):
            print(f"  next step: {s['next']}")
        return
    active = [(i, m) for i, (m, _, _) in reqs.items() if m.get("status") in ORDER[1:5]]
    active.sort(key=lambda x: (-ORDER.index(x[1]["status"]), x[0]))
    if active:
        i, m = active[0]
        print(f"resume {i} [{m['status']}] {m.get('title')}   ->  {TOOL} focus {i}")
        return
    ready = [(i, m, b) for i, (m, b, _) in reqs.items() if m.get("status") == "TODO"]
    ok = [(i, m) for i, m, b in ready if not open_questions(b) and strip_comments(get_section(b, "Requirement"))]
    ok.sort(key=lambda x: (x[1].get("epic") or "ZZZ", x[0]))
    if ok:
        i, m = ok[0]
        print(f"start {i} [TODO] {m.get('title')}   ->  {TOOL} focus {i} && {TOOL} status {i} DESIGN")
        return
    waiting = [i for i, m, b in ready if open_questions(b)]
    if waiting:
        print("nothing ready; waiting on user answers for: " + ", ".join(waiting[:10]))
        return
    print("nothing open. All requirements closed (or none recorded).")


def cmd_list(a):
    reqs, _ = load_all("REQ")
    rows = []
    for i, (m, b, _) in reqs.items():
        st = m.get("status")
        if a.status and st not in a.status.upper().split(","):
            continue
        if a.active and st in CLOSED:
            continue
        if a.epic and m.get("epic") != norm_id(a.epic):
            continue
        if a.area and m.get("area") != a.area:
            continue
        ac = acceptance(b)
        rows.append(f"{i}  {st:12} {m.get('epic') or '-':9} AC {sum(c for c, _ in ac)}/{len(ac)}  {m.get('title')}")
    print("\n".join(rows[-a.limit:]) if rows else "(none)")


def cmd_show(a):
    p = path_of(a.id)
    if not a.section:
        print(p.read_text(encoding="utf-8"))
        return
    meta, body = parse(p)
    print(f"{meta['id']} [{meta.get('status', '')}] {meta.get('title')}")
    for s in a.section.split(","):
        print(f"## {s}\n{(get_section(body, s.strip()) or '(missing)').strip()}\n")


def cmd_search(a):
    terms = [fold(t) for t in a.terms if len(t) > 1]
    hits = []
    for prefix in ("REQ", "EPIC"):
        items, _ = load_all(prefix)
        for i, (m, b, _) in items.items():
            hay = fold(m.get("title", "") + " " + (get_section(b, "Requirement") or get_section(b, "Goal") or ""))
            score = sum(hay.count(t) for t in terms)
            if score:
                hits.append((score, i, m.get("status", ""), m.get("title")))
    for sc, i, st, t in sorted(hits, reverse=True)[:10]:
        print(f"{i}  {st:12} score={sc}  {t}")
    if not hits:
        print("(no similar items)")


def collect():
    reqs, e1 = load_all("REQ")
    epics, e2 = load_all("EPIC")
    raws, e3 = load_all("RAW")
    errors, warns = e1 + e2 + e3, []
    new_raw = [i for i, (m, _, _) in raws.items() if m.get("status") == "NEW"]
    if new_raw:
        errors.append(f"untriaged RAW: {', '.join(new_raw[:10])}{' ...' if len(new_raw) > 10 else ''}"
                      f" -> use skill req-intake (link to REQ/EPIC, create new, or ignore with reason)")
    for i, (m, b, _) in reqs.items():
        if m.get("status") not in ORDER + SIDE:
            errors.append(f"{i}: invalid status {m.get('status')!r}")
        if m.get("epic") and m["epic"] not in epics:
            errors.append(f"{i}: epic {m['epic']} does not exist")
    for eid, (m, b, _) in epics.items():
        for ref in re.findall(r"^\s*- (REQ-\d+)", get_section(b, "Decomposition") or "", re.M):
            if ref not in reqs:
                errors.append(f"{eid}: Decomposition references missing {ref}")
        tbd = re.findall(r"^\s*- \[ \]\s*TBD:?\s*(.*)$", b, re.M)
        if tbd:
            warns.append(f"{eid}: {len(tbd)} TBD item(s) not yet turned into REQs: " + " | ".join(t[:50] for t in tbd[:3]))
    waiting = [f"{i}({len(open_questions(b))})" for i, (m, b, _) in reqs.items()
               if m.get("status") not in CLOSED and open_questions(b)]
    if waiting:
        warns.append(f"questions waiting for user: {', '.join(waiting[:10])}")
    tg = config().get("task_glob")
    if tg:
        existing = {p.stem for p in ROOT.glob(tg)}
        for i, (m, _, _) in reqs.items():
            for t in as_list(m.get("tasks")):
                if t not in existing:
                    warns.append(f"{i}: linked task {t} not found by task_glob")
    s = state()
    active = [i for i, (m, _, _) in reqs.items() if m.get("status") in ORDER[1:5]]
    if active and not s.get("focus"):
        warns.append(f"work in progress ({', '.join(active[:5])}) but no focus set -> {TOOL} focus <id> --next '...'")
    return reqs, epics, raws, errors, warns


def cmd_check(a):
    reqs, epics, raws, errors, warns = collect()
    for e in errors:
        print(f"[GAP] {e}")
    for w in warns:
        print(f"[WARN] {w}")
    if not errors and not warns:
        print("[REQ] ledger OK")
    if a.gate and errors:
        sys.exit(1)


def brief_text(limit=6):
    if not DATA.exists():
        return ""
    reqs, epics, raws, errors, warns = collect()
    s = state()
    lines = []
    f = s.get("focus")
    if f and f in reqs:
        m = reqs[f][0]
        lines.append(f"[REQ] focus {f} [{m.get('status')}] {m.get('title')} | next: {s.get('next') or '-'}")
    else:
        lines.append("[REQ] no focus")
    counts = {st: 0 for st in ORDER}
    for m, _, _ in reqs.values():
        if m.get("status") in counts:
            counts[m["status"]] += 1
    lines.append("[REQ] " + " | ".join(f"{k} {v}" for k, v in counts.items()))
    active = [f"{i} {m['status']}" for i, (m, _, _) in reqs.items() if m.get("status") in ORDER[1:5] and i != f]
    if active:
        lines.append("[REQ] also active: " + ", ".join(active[:limit]) + (" ..." if len(active) > limit else ""))
    lines += [f"[GAP] {e}" for e in errors[:limit]] + [f"[WARN] {w}" for w in warns[:limit]]
    return "\n".join(lines)


def cmd_brief(a):
    print(brief_text())


def cmd_index(a, quiet=False):
    if not DATA.exists():
        return
    reqs, epics, raws, errors, warns = collect()
    out = ["<!-- generated by req.py index - do not edit -->", f"# Requirements index  (updated {now()})", ""]
    counts = {st: sum(m.get("status") == st for m, _, _ in reqs.values()) for st in ORDER + SIDE}
    out.append(" | ".join(f"**{k}** {v}" for k, v in counts.items()))
    out.append("")
    if errors or warns:
        out += ["## Attention", ""] + [f"- GAP: {e}" for e in errors] + [f"- WARN: {w}" for w in warns] + [""]

    def table(ids):
        rows = ["| ID | Status | AC | Title | Tasks |", "|---|---|---|---|---|"]
        for i in ids:
            m, b, _ = reqs[i]
            ac = acceptance(b)
            rows.append(f"| [{i}](items/{i}.md) | {m.get('status')} | {sum(c for c, _ in ac)}/{len(ac)} | "
                        f"{m.get('title', '').replace('|', '/')} | {', '.join(as_list(m.get('tasks')))} |")
        return rows

    for eid, (m, b, _) in epics.items():
        kids = [i for i, (rm, _, _) in reqs.items() if rm.get("epic") == eid]
        out += [f"## [{eid}](epics/{eid}.md) {m.get('title')} - {epic_status(eid, reqs)}", ""]
        out += table(kids) if kids else ["(no REQs yet)"]
        tbd = re.findall(r"^\s*- \[ \]\s*TBD:?\s*(.*)$", b, re.M)
        out += [f"- TBD: {t}" for t in tbd] + [""]
    orphans = [i for i, (m, _, _) in reqs.items() if not m.get("epic")]
    if orphans:
        out += ["## Without epic", ""] + table(orphans) + [""]
    INDEX_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    if not quiet:
        print(f"wrote {INDEX_FILE.relative_to(ROOT)}")


# ---------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(prog="req.py", description="Requirement ledger")
    sp = ap.add_subparsers(dest="cmd", required=True)

    sp.add_parser("init").set_defaults(fn=cmd_init)

    r = sp.add_parser("raw", help="verbatim captured prompts")
    r.add_argument("action", choices=["list", "show", "link", "ignore", "add"])
    r.add_argument("ids", nargs="*")
    r.add_argument("--new", action="store_true", help="only untriaged")
    r.add_argument("--to", dest="target", help="REQ/EPIC id(s), comma separated")
    r.add_argument("--reason")
    r.add_argument("--text")
    r.add_argument("--limit", type=int, default=30)
    r.add_argument("--ac", help="with link: append this text as the next ACn of the --to REQ (98.2)")
    r.add_argument("--note", nargs="?", const="active", default=None, metavar="TASK", help="with link: backlog.sh note TASK|active")
    r.set_defaults(fn=cmd_raw)

    for name, fn, help_ in (("new", cmd_new, "create REQ"), ("epic", cmd_epic, "create/list EPIC")):
        n = sp.add_parser(name, help=help_)
        if name == "epic":
            n.add_argument("action", choices=["new", "list"])
        n.add_argument("--title", required=(name == "new"))
        n.add_argument("--from", dest="frm", help="RAW ids, comma separated")
        n.add_argument("--text", help="normalized Requirement / Goal text")
        if name == "new":
            n.add_argument("--epic")
            n.add_argument("--area")
            n.add_argument("--supersedes")
        n.set_defaults(fn=fn, epic=None, area=None, supersedes=None) if name == "epic" else n.set_defaults(fn=fn)

    s = sp.add_parser("status", help="move REQ through lifecycle (gated)")
    s.add_argument("id")
    s.add_argument("new")
    s.add_argument("--evidence")
    s.add_argument("--reason")
    s.add_argument("--force", action="store_true")
    s.add_argument("--next", help="also focus this REQ with this next step (skipped when closing)")
    s.set_defaults(fn=cmd_status)

    ac = sp.add_parser("ac", help="tick Acceptance items with evidence (AC1,AC3 or all)")
    ac.add_argument("id")
    ac.add_argument("items", help="AC ids, comma separated, or all")
    ac.add_argument("--evidence", required=True)
    ac.set_defaults(fn=cmd_ac)

    l = sp.add_parser("log", help="append progress note")
    l.add_argument("id")
    l.add_argument("message")
    l.set_defaults(fn=cmd_log)

    t = sp.add_parser("task", help="link workflow TASK ids to REQ")
    t.add_argument("id")
    t.add_argument("tasks")
    t.set_defaults(fn=cmd_task)

    f = sp.add_parser("focus", help="set current REQ and next concrete step")
    f.add_argument("id", nargs="?")
    f.add_argument("--next")
    f.add_argument("--clear", action="store_true")
    f.set_defaults(fn=cmd_focus)

    g = sp.add_parser("gaps", help="what is still missing for a REQ (default: focus)")
    g.add_argument("id", nargs="?")
    g.set_defaults(fn=cmd_gaps)

    sp.add_parser("next", help="what to work on next").set_defaults(fn=cmd_next)

    ls = sp.add_parser("list")
    ls.add_argument("--status")
    ls.add_argument("--epic")
    ls.add_argument("--area")
    ls.add_argument("--active", action="store_true")
    ls.add_argument("--limit", type=int, default=200)
    ls.set_defaults(fn=cmd_list)

    sh = sp.add_parser("show")
    sh.add_argument("id")
    sh.add_argument("--section", help="e.g. Requirement,Acceptance")
    sh.set_defaults(fn=cmd_show)

    se = sp.add_parser("search", help="find similar REQ/EPIC (dedup)")
    se.add_argument("terms", nargs="+")
    se.set_defaults(fn=cmd_search)

    c = sp.add_parser("check")
    c.add_argument("--gate", action="store_true", help="exit 1 on GAP")
    c.set_defaults(fn=cmd_check)

    sp.add_parser("brief").set_defaults(fn=cmd_brief)
    sp.add_parser("index").set_defaults(fn=cmd_index)

    a = ap.parse_args()
    if a.cmd != "init" and not DATA.exists():
        die(f"{DATA} not initialized; run: {TOOL} init")
    a.fn(a)


if __name__ == "__main__":
    main()
