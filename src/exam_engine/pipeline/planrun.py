"""Plan run: every raw LLM call of a solve, written as it happens (REQ-0062, phase 58).

plans/<exam-id>/<plan-run-id>/ holds plan.json, config.json, input/exam.md, calls/index.jsonl +
calls/NNN-{prompt,reply}.txt, and (written by the engine) result.json + run.log. Capture never fails a
run: a write error prints one WARN and turns capture off. Replies go through claude.mask (token
pattern); the sha256 in index.jsonl is of the unmasked text.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import time
import unicodedata

from exam_engine.adapters import claude
from exam_engine.pipeline import metrics, prompts, reporter

SCHEMA_VERSION = 1


def exam_id_of(exam_path):
    """Exam id derived from the file stem, sanitized (diacritics folded, other chars -> '-'); never rejected."""
    stem = os.path.splitext(os.path.basename(exam_path))[0]
    stem = unicodedata.normalize("NFKD", stem.replace("\u0111", "d").replace("\u0110", "D"))
    stem = "".join(c for c in stem if not unicodedata.combining(c))
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem)
    stem = re.sub(r"-{2,}", "-", re.sub(r"\.{2,}", ".", stem)).lstrip(".-")
    return stem or "exam"


_ID_RE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9._-]*$")
TRACE_MAX_BYTES = 20 * 1024 * 1024


def safe_id(value, what="id"):
    """The one check for any id that becomes a path component; returns value or raises ValueError.
    Only [A-Za-z0-9._-], no leading dot, no '..', so it can never leave plans/ or reports/."""
    if not isinstance(value, str) or not _ID_RE.match(value) or ".." in value:
        raise ValueError("invalid %s %r (allowed: letters, digits, . _ -; no leading dot, no '..')"
                         % (what, value if isinstance(value, str) else ""))
    return value


def claim_run_dir(root, exam_id):
    """plans/<exam-id>/<UTC stamp>[-N], created with makedirs(exist_ok=False) so two runs never share one."""
    base = os.path.join(root, safe_id(exam_id, "exam id"))
    os.makedirs(base, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    n = 1
    while True:
        out = os.path.join(base, stamp if n == 1 else "%s-%d" % (stamp, n))
        try:
            os.makedirs(out)
            return out
        except FileExistsError:
            n += 1


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dump(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


class PlanWriter(object):
    def __init__(self, plan_dir, exam_path, cfg, repo_root=None):
        self.dir, self.exam_path, self.cfg, self.repo_root = plan_dir, exam_path, cfg, repo_root
        self.meta = None
        self.ok = True
        self.calls = 0
        self.t0 = time.time()

    def _warn(self, exc):
        if self.ok:
            print("WARN: capture off: %s" % exc, file=sys.stderr)
        self.ok = False

    def _config(self):
        cfg = dict(self.cfg)
        key = cfg.get("key")
        cfg["key"] = {"path": key, "sha256": metrics.file_sha256(key)} if key else None
        return cfg

    def start(self):
        try:
            os.makedirs(os.path.join(self.dir, "calls"), exist_ok=True)
            os.makedirs(os.path.join(self.dir, "input"), exist_ok=True)
            cfg = self._config()
            _dump(os.path.join(self.dir, "config.json"), cfg)
            shutil.copyfile(self.exam_path, os.path.join(self.dir, "input", "exam.md"))
            canon = json.dumps(cfg, sort_keys=True, ensure_ascii=False)
            self.meta = {
                "schema_version": SCHEMA_VERSION, "exam_id": exam_id_of(self.exam_path),
                "plan_run_id": os.path.basename(os.path.abspath(self.dir)), "source": "solve",
                "status": "running", "exit_code": None,
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "finished_utc": None, "wall_s": None,
                "git": reporter.git_info(self.repo_root) if self.repo_root else None,
                "prompt": prompts.prompt_info(), "model": self.cfg.get("model"),
                "llm": self.cfg.get("llm_name"), "config_sha256": _sha(canon),
                "exam": {"path": self.exam_path, "sha256": metrics.file_sha256(self.exam_path)},
                "calls": 0, "cost_usd": 0.0, "calls_captured": True, "imported_from": None}
            _dump(os.path.join(self.dir, "plan.json"), self.meta)
        except OSError as exc:
            self._warn(exc)

    def record(self, n, tag, prompt, call):
        """Sink for Runner.call: one prompt file, one reply file, one flushed index line."""
        if not self.ok:
            return
        self.calls = n
        text = call.text or ""
        try:
            cdir = os.path.join(self.dir, "calls")
            for name, body in (("prompt", prompt), ("reply", claude.mask(text))):
                with open(os.path.join(cdir, "%03d-%s.txt" % (n, name)), "w", encoding="utf-8") as fh:
                    fh.write(body)
            line = {"n": n, "tag": tag, "ok": bool(call.ok), "cls": call.cls or "",
                    "reason": claude.mask(call.reason or "")[:200], "duration_s": call.duration_s or 0.0,
                    "cost_usd": call.cost_usd or 0.0, "prompt_bytes": len(prompt.encode("utf-8")),
                    "reply_bytes": len(text.encode("utf-8")), "prompt_sha256": _sha(prompt),
                    "reply_sha256": _sha(text)}
            with open(os.path.join(cdir, "index.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
                fh.flush()
        except OSError as exc:
            self._warn(exc)

    def finish(self, result, code, wall_s=None):
        """Final plan.json. result None = crash or invalid input (status failed); code 3 = stopped."""
        if self.meta is None:
            return
        if result is None and self.calls == 0 and code == 2:
            shutil.rmtree(self.dir, ignore_errors=True)  # invalid input: nothing worth keeping
            return
        run = (result or {}).get("run") or {}
        self.meta.update({
            "status": "failed" if result is None else "stopped" if code == 3 else "done",
            "exit_code": code, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "wall_s": round(wall_s if wall_s is not None else time.time() - self.t0, 1),
            "calls": run.get("calls", self.calls), "cost_usd": run.get("cost_usd", 0.0),
            "calls_captured": self.ok})
        try:
            _dump(os.path.join(self.dir, "plan.json"), self.meta)
        except OSError as exc:
            self._warn(exc)


def load(plan_dir):
    """{plan, result, log, exam_text}; a missing part is None."""
    def rd(name, parse):
        try:
            with open(os.path.join(plan_dir, name), encoding="utf-8") as fh:
                return parse(fh)
        except (OSError, ValueError):
            return None
    return {"plan": rd("plan.json", json.load), "result": rd("result.json", json.load),
            "log": rd("run.log", lambda f: f.read().splitlines()),
            "exam_text": rd(os.path.join("input", "exam.md"), lambda f: f.read())}


_CALL_RE = re.compile(r"^call (\d+) ok=(\S+) cls=(\S+) dur=([\d.]+)s cost=([\d.]+) "
                      r"prompt_bytes=(\d+) answer_bytes=(\d+)")


def _already_imported(base, src, rsha):
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return None
    for name in names:
        try:
            with open(os.path.join(base, name, "plan.json"), encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            continue
        if meta.get("imported_from") == src and meta.get("result_sha256") == rsha:
            return os.path.join(base, name)
    return None


def _log_index(lines):
    """index.jsonl rows from run.log lines; the raw replies of old runs were never stored."""
    rows = []
    for ln in lines or ():
        m = _CALL_RE.match(ln)
        if m:
            rows.append({"n": int(m.group(1)), "ok": m.group(2) == "True",
                         "cls": "" if m.group(3) == "-" else m.group(3), "duration_s": float(m.group(4)),
                         "cost_usd": float(m.group(5)), "prompt_bytes": int(m.group(6)),
                         "reply_bytes": int(m.group(7)), "captured": False, "reply": "not captured"})
    return rows


def _ingest_sources(src, ingest_cache):
    """(trace files, cache dirs) of the same exam: *.trace.json in the run dir; the ingest cache dir
    <src>/../work/ingest/<hash> when it is the only one (a hash does not name its exam)."""
    traces = sorted(os.path.join(src, n) for n in os.listdir(src)
                    if n.endswith(".trace.json") and not os.path.islink(os.path.join(src, n)))
    if ingest_cache:
        return traces, [ingest_cache]
    root = os.path.join(os.path.dirname(src), "work", "ingest")
    try:
        subs = [os.path.join(root, n) for n in sorted(os.listdir(root))
                if os.path.isdir(os.path.join(root, n))]
    except OSError:
        subs = []
    return traces, subs if len(subs) == 1 else []


def _plain_file_quiet(path):
    return os.path.isfile(path) and not os.path.islink(path)


def _plain_file(path, max_bytes=None):
    """True for a regular non-symlink file (within max_bytes); else one WARN and False."""
    if os.path.islink(path) or not os.path.isfile(path):
        print("WARN: skipped %s (symlink or not a regular file)" % path, file=sys.stderr)
        return False
    if max_bytes is not None and os.path.getsize(path) > max_bytes:
        print("WARN: skipped %s (over %d bytes)" % (path, max_bytes), file=sys.stderr)
        return False
    return True


def import_dir(src, root, exam_path=None, exam_id=None, ingest_cache=None, traces_extra=()):
    """Old run dir (result.json [+ run.log, *.trace.json]) -> <root>/<exam-id>/<run>/; (plan_dir, status).
    status "skipped" when the same dir with the same result.json was imported before.
    ValueError when src has no readable result.json or an id is invalid. traces_extra: more
    *.trace.json files (any place) to copy into ingest/. result.json exam.path is read only when
    it lies inside src; otherwise pass exam_path."""
    src = os.path.abspath(src)
    rpath = os.path.join(src, "result.json")
    if exam_id is not None:
        safe_id(exam_id, "exam id")
    if os.path.islink(rpath):
        raise ValueError("%s: result.json is a symlink" % src)
    try:
        with open(rpath, encoding="utf-8") as fh:
            result = json.load(fh)
        rsha = metrics.file_sha256(rpath)
    except (OSError, ValueError):
        raise ValueError("%s: not a result dir (no readable result.json)" % src)
    declared = ((result.get("exam") or {}).get("path")) or ""
    if exam_path is None and declared:
        real_src = os.path.realpath(src)
        cand = os.path.realpath(declared if os.path.isabs(declared) else os.path.join(src, declared))
        if os.path.commonpath([cand, real_src]) == real_src and os.path.isfile(cand):
            exam_path = cand
        else:
            print("WARN: exam not imported (result exam.path %s is outside the run dir; pass --exam)"
                  % declared, file=sys.stderr)
    exam_id = safe_id(exam_id or exam_id_of(declared or exam_path or src), "exam id")
    hit = _already_imported(os.path.join(root, exam_id), src, rsha)
    if hit:
        return hit, "skipped"
    out = claim_run_dir(root, exam_id)
    shutil.copyfile(rpath, os.path.join(out, "result.json"))
    log = None
    if _plain_file_quiet(os.path.join(src, "run.log")):
        shutil.copyfile(os.path.join(src, "run.log"), os.path.join(out, "run.log"))
        log = metrics.load_log(os.path.join(out, "run.log"))
    os.makedirs(os.path.join(out, "calls"))
    with open(os.path.join(out, "calls", "index.jsonl"), "w", encoding="utf-8") as fh:
        for row in _log_index(log):
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    exam = None
    if exam_path and _plain_file(exam_path):
        os.makedirs(os.path.join(out, "input"))
        shutil.copyfile(exam_path, os.path.join(out, "input", "exam.md"))
        exam = {"path": exam_path, "sha256": metrics.file_sha256(exam_path)}
    ingest = 0
    traces, caches = _ingest_sources(src, ingest_cache)
    for tr in traces + list(traces_extra):
        if not _plain_file(tr, TRACE_MAX_BYTES):
            continue
        os.makedirs(os.path.join(out, "ingest"), exist_ok=True)
        shutil.copyfile(tr, os.path.join(out, "ingest", os.path.basename(tr)))
        ingest += 1
    for cdir in caches:
        dest = os.path.join(out, "ingest", "cache", os.path.basename(cdir.rstrip("/")))
        for base, _, names in os.walk(cdir):
            for n in names:
                if os.path.islink(os.path.join(base, n)):
                    continue
                tgt = os.path.join(dest, os.path.relpath(os.path.join(base, n), cdir))
                os.makedirs(os.path.dirname(tgt), exist_ok=True)
                shutil.copyfile(os.path.join(base, n), tgt)
                ingest += 1
    run = result.get("run") or {}
    _dump(os.path.join(out, "plan.json"), {
        "schema_version": SCHEMA_VERSION, "exam_id": exam_id, "plan_run_id": os.path.basename(out),
        "source": "import", "status": "done", "exit_code": None, "started_utc": None,
        "finished_utc": None, "imported_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_s": None, "git": None, "prompt": run.get("prompt"), "model": run.get("model"),
        "llm": run.get("llm"), "config_sha256": None, "exam": exam, "calls": run.get("calls", 0),
        "cost_usd": run.get("cost_usd", 0.0), "calls_captured": False, "imported_from": src,
        "result_sha256": rsha, "ingest_files": ingest})
    return out, "imported"
