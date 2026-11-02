"""Plan run: every raw LLM call of a solve, written as it happens (REQ-0062, phase 58).

plans/<exam-id>/<plan-run-id>/ holds plan.json, config.json, input/exam.md, calls/index.jsonl +
calls/NNN-{prompt,reply}.txt, and (written by the engine) result.json + run.log. Capture never fails a
run: a write error prints one WARN and turns capture off. Replies go through claude.mask (token
pattern); the sha256 in index.jsonl is of the unmasked text.
"""
import hashlib
import json
import os
import shutil
import sys
import time

from exam_engine.adapters import claude
from exam_engine.pipeline import metrics, prompts, reporter

SCHEMA_VERSION = 1


def exam_id_of(exam_path):
    return os.path.splitext(os.path.basename(exam_path))[0]


def claim_run_dir(root, exam_id):
    """plans/<exam-id>/<UTC stamp>[-N], created with makedirs(exist_ok=False) so two runs never share one."""
    base = os.path.join(root, exam_id)
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
