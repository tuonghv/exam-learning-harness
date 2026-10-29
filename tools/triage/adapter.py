#!/usr/bin/env python3
"""adapter.py - import Triage Records into ReqKit (phase 71, REQ-0029). Deterministic, stdlib only.

usage: adapter.py [--triage-dir DIR] [--targets-file FILE] [--dry-run] [record.json ...]

With no record arguments it handles every <triage-dir>/staging/trg-*.json. Per record:
  validate (schema triage-record.v1.json, KNOWN_TARGETS, id shapes, secret scan)
  -> needs_clarification: held in outbox/<id>.json, nothing submitted
  -> ledger hit (triage_id already imported): submitted/<id>.json keeps the existing RAW id
  -> else `req.py raw add --text <rendered>` -> submitted/<id>.json (+ reqkit_id), ledger row
  any failure -> invalid/<id>.json (+ reason)
The adapter never writes ReqKit data itself; ReqKit's own CLI does (file lock inside req.py).
Exit: 0 all handled, 1 at least one record invalid, 2 usage error.
Env: TRIAGE_REQ_CMD (default "python3 <repo>/.claude/req/req.py"); REQ_DIR is passed through.
"""
import argparse, datetime, json, os, re, shlex, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCHEMA = HERE / "schema" / "triage-record.v1.json"
CONTRACT = REPO / ".claude" / "skills" / "inbox-triage" / "references" / "reqkit-contract.md"
PRIORITY = {"urgent": "URGENT", "normal": "-", "low": "low"}
ID_RE = re.compile(r"^(REQ|RAW|EPIC)-\d+$")
RAW_RE = re.compile(r"^RAW-\d+$")
TRG_RE = re.compile(r"^trg-[A-Za-z0-9._-]+-[0-9]{2}$")  # a held request answered by this record
# Secret shapes: the value is never logged, only the rule name.
SECRETS = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("url_credentials", re.compile(r"[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@", re.I)),
    ("assignment", re.compile(r"\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\s*[:=]\s*\S{6,}", re.I)),
    ("bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}", re.I)),
]


# ------------------------------------------------------------ schema subset
def _type_ok(v, t):
    if isinstance(t, list):
        return any(_type_ok(v, x) for x in t)
    return {"object": isinstance(v, dict), "array": isinstance(v, list), "string": isinstance(v, str),
            "boolean": isinstance(v, bool), "null": v is None,
            "integer": isinstance(v, int) and not isinstance(v, bool),
            "number": isinstance(v, (int, float)) and not isinstance(v, bool)}.get(t, False)


def validate(v, s, path="$"):
    """Errors for the JSON-Schema constructs used by triage-record.v1.json (unknown keywords are
    ignored except those listed, so a schema change that adds one fails loudly in the tests)."""
    errs = []
    if "type" in s and not _type_ok(v, s["type"]):
        return [f"{path}: expected {s['type']}"]
    if "const" in s and v != s["const"]:
        errs.append(f"{path}: must be {s['const']!r}")
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: not one of {s['enum']}")
    if isinstance(v, str):
        if len(v) < s.get("minLength", 0):
            errs.append(f"{path}: shorter than {s['minLength']}")
        if "maxLength" in s and len(v) > s["maxLength"]:
            errs.append(f"{path}: longer than {s['maxLength']}")
        if "pattern" in s and not re.search(s["pattern"], v):
            errs.append(f"{path}: does not match {s['pattern']}")
        if s.get("format") == "date-time":
            try:
                datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                errs.append(f"{path}: not an ISO 8601 date-time")
    if isinstance(v, list):
        if len(v) < s.get("minItems", 0):
            errs.append(f"{path}: fewer than {s['minItems']} items")
        if "items" in s:
            for i, x in enumerate(v):
                errs += validate(x, s["items"], f"{path}[{i}]")
    if isinstance(v, dict):
        for k in s.get("required", []):
            if k not in v:
                errs.append(f"{path}: missing {k}")
        props = s.get("properties", {})
        for k, x in v.items():
            if k in props:
                errs += validate(x, props[k], f"{path}.{k}")
            elif s.get("additionalProperties") is False:
                errs.append(f"{path}: unexpected field {k}")
    for sub in s.get("allOf", []):
        errs += validate(v, sub, path)
    if "if" in s and not validate(v, s["if"], path):
        errs += validate(v, s.get("then", {}), path)
    return errs


# ------------------------------------------------------------ contract
def aliases():
    out = {}
    try:
        text = CONTRACT.read_text(encoding="utf-8")
    except OSError:
        return out
    m = re.search(r"## 5\. Target aliases\s*```(.*?)```", text, re.S)
    for line in (m.group(1).splitlines() if m else []):
        line = line.split("#", 1)[0].strip()
        if "->" in line:
            a, b = (x.strip() for x in line.split("->", 1))
            if a and b:
                out[a] = b
    return out


def known_targets(path):
    if path:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    else:
        r = subprocess.run(["bash", str(HERE / "known_targets.sh")], capture_output=True, text=True, cwd=REPO)
        lines = r.stdout.splitlines()
    return {x.strip() for x in lines if x.strip()}


# ------------------------------------------------------------ checks + render
def check(rec, schema, targets, alias):
    errs = validate(rec, schema)
    if errs:
        return "schema: " + "; ".join(errs[:6])
    t = rec["target"]
    if t is not None and alias.get(t, t) not in targets:
        return f"unknown_target: {t}"
    if rec["related_reqkit_id"] is not None and not ID_RE.match(rec["related_reqkit_id"]):
        return f"bad_reqkit_id: {rec['related_reqkit_id']}"
    for i in rec["possible_duplicate_of"]:
        if not (ID_RE.match(i) or TRG_RE.match(i)):
            return f"bad_reqkit_id: {i}"
    text = "\n".join([rec["title"], rec["task"]] + rec["acceptance"] + rec["questions"])
    for name, rx in SECRETS:
        if rx.search(text):
            return f"secret_detected: {name}"
    return ""


def render(rec, alias):
    t = rec["target"]
    t = alias.get(t, t) if t is not None else "-"
    out = [f"[inbox-triage {rec['triage_id']} · {rec['category']} · {PRIORITY[rec['priority']]} · target {t}]",
           rec["title"], "", rec["task"]]
    if rec["acceptance"]:
        out += ["", "Acceptance:"] + [f"- {a}" for a in rec["acceptance"]]
    if rec["context_refs"]:
        out += ["Context: " + ", ".join(c["file"] + (":" + c["lines"] if c.get("lines") else "") for c in rec["context_refs"])]
    if rec["related_reqkit_id"]:
        out += [f"Relates to: {rec['related_reqkit_id']} ({rec['intent']})"]
    elif rec["intent"] != "new":
        out += [f"Intent: {rec['intent']}"]
    dups = [i for i in rec["possible_duplicate_of"] if ID_RE.match(i)]
    held = [i for i in rec["possible_duplicate_of"] if TRG_RE.match(i)]
    if dups:
        out += ["Possible duplicate of: " + ", ".join(dups)]
    if held:
        out += ["Answers held request: " + ", ".join(held)]
    if rec["flags"]:
        out += ["Flags: " + ", ".join(rec["flags"])]
    out += [f"Source: {Path(rec['source_file']).name} · triaged {rec['triaged_at']} · confidence {rec['confidence']}"]
    return "\n".join(out)


# ------------------------------------------------------------ io
def ledger_get(ledger, tid):
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0] == tid:
                return parts[1]
    return ""


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def log(tdir, tid, outcome, detail=""):
    (tdir / "logs").mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    with open(tdir / "logs" / "adapter.log", "a", encoding="utf-8") as fh:
        fh.write(f"{ts}\t{tid}\t{outcome}\t{detail}\n")
    print(f"adapter: {tid} {outcome}{' ' + detail if detail else ''}")


def move_question(tdir, tid, dest):
    q = tdir / "outbox" / f"{tid}.question.md"
    if q.exists():
        dest.mkdir(parents=True, exist_ok=True)
        os.replace(q, dest / q.name)


def close_answered(tdir, rec):
    """A submitted record that answers a held clarification closes it (outbox/answered/)."""
    for hid in rec["possible_duplicate_of"]:
        held = tdir / "outbox" / f"{hid}.json"
        if TRG_RE.match(hid) and hid != rec["triage_id"] and held.exists():
            (tdir / "outbox" / "answered").mkdir(parents=True, exist_ok=True)
            os.replace(held, tdir / "outbox" / "answered" / held.name)
            move_question(tdir, hid, tdir / "outbox" / "answered")
            log(tdir, hid, "answered", f"by {rec['triage_id']}")


def submit(text):
    cmd = shlex.split(os.environ.get("TRIAGE_REQ_CMD") or f"python3 {shlex.quote(str(REPO / '.claude/req/req.py'))}")
    r = subprocess.run(cmd + ["raw", "add", "--text", text], capture_output=True, text=True, cwd=REPO)
    rid = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    if r.returncode != 0 or not RAW_RE.match(rid):
        tail = (r.stderr.strip().splitlines() or ["no output"])[-1][:200]
        return "", f"reqkit_error: rc={r.returncode} {tail}"
    return rid, ""


def handle(path, tdir, schema, targets, alias, dry):
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        rec, reason = None, f"unreadable: {e.__class__.__name__}"
    else:
        reason = check(rec, schema, targets, alias) if isinstance(rec, dict) else "schema: $: expected object"
        if not reason and rec["triage_id"] != path.stem:
            reason = f"file_name_mismatch: {path.name}"
    tid = rec["triage_id"] if not reason else path.stem
    if dry:
        log(tdir, tid, "dry-run", reason or "valid")
        return not reason
    if reason:
        write_json(tdir / "invalid" / f"{path.stem}.json",
                   {"reason": reason, "record": rec if rec is not None else path.read_text(encoding="utf-8", errors="replace")})
        path.unlink()
        move_question(tdir, tid, tdir / "invalid")  # no question for a record that was rejected
        log(tdir, tid, "invalid", reason)
        return False
    if rec["needs_clarification"]:
        write_json(tdir / "outbox" / f"{tid}.json", rec)
        path.unlink()
        log(tdir, tid, "held", "needs_clarification")
        close_answered(tdir, rec)  # a reply that asks again replaces the older held request
        return True
    ledger = tdir / "ledger.tsv"
    rid = ledger_get(ledger, tid)
    if rid:
        write_json(tdir / "submitted" / f"{tid}.json", dict(rec, reqkit_id=rid))
        path.unlink()
        log(tdir, tid, "duplicate", f"already {rid}")
        close_answered(tdir, rec)
        return True
    rid, err = submit(render(rec, alias))
    if err:
        write_json(tdir / "invalid" / f"{tid}.json", {"reason": err, "record": rec})
        path.unlink()
        move_question(tdir, tid, tdir / "invalid")
        log(tdir, tid, "invalid", err)
        return False
    with open(ledger, "a", encoding="utf-8") as fh:
        fh.write(f"{tid}\t{rid}\n")
    write_json(tdir / "submitted" / f"{tid}.json", dict(rec, reqkit_id=rid))
    path.unlink()
    log(tdir, tid, "submitted", rid)
    close_answered(tdir, rec)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--triage-dir", default=str(REPO / ".triage"))
    ap.add_argument("--targets-file", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("records", nargs="*")
    a = ap.parse_args()
    tdir = Path(a.triage_dir)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    targets, alias = known_targets(a.targets_file), aliases()
    files = [Path(p) for p in a.records] or sorted((tdir / "staging").glob("trg-*.json"))
    ok = True
    for p in files:
        ok = handle(p, tdir, schema, targets, alias, a.dry_run) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
