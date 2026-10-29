"""One model call through the Claude CLI, its error classes and JSON extraction.

The ONLY module that runs `claude`.

Python 3.8 stdlib only. The real runner is only the default of `runner`; tests and
--mock inject a fake. Nothing here reads a key file.
"""
import base64
import collections
import json
import re
import subprocess
import time

Call = collections.namedtuple("Call", "ok text cost_usd cls reason duration_s")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TOKEN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|Bearer\s+\S+|[A-Za-z0-9_-]{32,})")
_FENCE = re.compile(r"```[A-Za-z]*[ \t]*\n?(.*?)```", re.S)


def mask(s):
    s = _EMAIL.sub("<email>", str(s))
    return _TOKEN.sub("<token>", s)


def _classify(blob):
    low = blob.casefold()
    if any(w in low for w in ("401", "authenticat", "login", "api key", "unauthorized",
                              "credential")):
        return "auth"
    if any(w in low for w in ("429", "rate limit", "rate_limit", "session limit",
                              "usage limit", "overloaded")):
        return "rate_limit"
    if any(w in low for w in ("500", "502", "503", "504", "service", "unavailable",
                              "connection", "network")):
        return "service"
    return "other"


def _bad(cls, reason, dur, cost=0.0):
    return Call(False, "", cost, cls, mask(reason)[:200], dur)


IMAGE_TYPES = ("image/png", "image/jpeg", "image/webp")
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def run_claude(prompt, *, model, timeout_s, runner=subprocess.run, cwd=None):
    return _run(prompt, [], model, timeout_s, runner, cwd)


def run_claude_images(text, images, *, model, timeout_s, runner=subprocess.run, cwd=None):
    """Like run_claude with images: `images` = [(media_type, bytes)], sent base64 on stdin.

    Validated before any call (type, non-empty, size); no file path is ever sent.
    """
    blocks = []
    for i, (mtype, data) in enumerate(images or (), 1):
        if mtype not in IMAGE_TYPES:
            return _bad("other", "image %d: unsupported media type %r" % (i, mtype), 0.0)
        if not isinstance(data, (bytes, bytearray)) or not data:
            return _bad("other", "image %d: empty or not bytes" % i, 0.0)
        if len(data) > MAX_IMAGE_BYTES:
            return _bad("other", "image %d: %d bytes > %d" % (i, len(data), MAX_IMAGE_BYTES), 0.0)
        blocks.append({"type": "image", "source": {
            "type": "base64", "media_type": mtype,
            "data": base64.b64encode(bytes(data)).decode("ascii")}})
    if not blocks:
        return _bad("other", "no images given", 0.0)
    blocks.append({"type": "text", "text": text})
    line = json.dumps({"type": "user", "message": {"role": "user", "content": blocks}})
    return _run(line + "\n", ["--input-format", "stream-json", "--verbose"], model, timeout_s,
                runner, cwd, stream=True)


def _envelope(out, stream):
    """The result envelope: whole stdout as JSON, or (stream-json) the last `result` line."""
    if not out.strip():
        return None
    if not stream:
        try:
            return json.loads(out)
        except ValueError:
            return None
    env = None
    for ln in out.splitlines():
        try:
            obj = json.loads(ln)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("type") == "result":
            env = obj
    return env


def _run(prompt, extra, model, timeout_s, runner, cwd, stream=False):
    argv = ["claude", "-p", "--output-format", "stream-json" if stream else "json", "--model", model,
            "--tools", "", "--disable-slash-commands", "--no-session-persistence",
            "--strict-mcp-config"] + extra
    t0 = time.time()
    try:
        p = runner(argv, input=prompt, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   universal_newlines=True, timeout=timeout_s, shell=False, cwd=cwd)
    except subprocess.TimeoutExpired:
        return _bad("timeout", "timeout after %ss" % timeout_s, time.time() - t0)
    except OSError as exc:
        return _bad("other", "cannot start claude: %s" % exc, time.time() - t0)
    dur = time.time() - t0
    out, err = p.stdout or "", p.stderr or ""
    env = _envelope(out, stream)
    cost = 0.0
    if isinstance(env, dict):
        c = env.get("total_cost_usd", env.get("cost_usd", 0.0))
        cost = float(c) if isinstance(c, (int, float)) else 0.0
    res = env.get("result") if isinstance(env, dict) else None
    if p.returncode != 0 or (isinstance(env, dict) and env.get("is_error")):
        blob = err + " " + (res if isinstance(res, str) else out)
        return _bad(_classify(blob), blob.strip() or "exit %s" % p.returncode, dur, cost)
    if not isinstance(res, str) or not res.strip():
        return _bad("empty", "empty result", dur, cost)
    return Call(True, res, cost, "", "", dur)


def _load(s):
    try:
        obj = json.loads(s)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def extract_json(text):
    """(obj, None) for a JSON object, else (None, reason)."""
    if not isinstance(text, str) or not text.strip():
        return None, "empty text"
    obj = _load(text.strip())
    if obj is not None:
        return obj, None
    fences = _FENCE.findall(text)
    if len(fences) > 1:
        return None, "more than one code fence"
    if fences:
        obj = _load(fences[0].strip())
        if obj is not None:
            return obj, None
    i, j = text.find("{"), text.rfind("}")
    if 0 <= i < j:
        obj = _load(text[i:j + 1])
        if obj is not None:
            return obj, None
    return None, "no valid JSON object found"
