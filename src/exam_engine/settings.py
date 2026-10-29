"""One place for repo paths and config loading (found from __file__, never from cwd).

EXAM_ENGINE_CONFIG_DIR overrides CONFIG_DIR (tests, extra subjects without code change).
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROMPTS_DIR = os.path.join(ROOT, "prompts")
SCHEMAS_DIR = os.path.join(ROOT, "schemas")
CONFIG_DIR = os.path.join(ROOT, "config")
WORKSPACE = os.path.join(ROOT, "workspace")


def config_dir():
    return os.environ.get("EXAM_ENGINE_CONFIG_DIR") or CONFIG_DIR


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_config(name, config_dir_=None):
    """config/<name>.json as a dict."""
    return load_json(os.path.join(config_dir_ or config_dir(), name + ".json"))


def load_schema(name):
    """schemas/<name>.schema.json as a dict."""
    return load_json(os.path.join(SCHEMAS_DIR, name + ".schema.json"))


# Chosen prompt source; None = default from config/engine.json (prompt_channel, prompt_release).
PROMPT_SOURCE = {"channel": None, "version": None}
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
CODE_RE = re.compile(r"^[a-z]{2}$")  # prompt variant code; the exam header Language: is untrusted


def use_prompts(channel=None, version=None):
    """Select the prompt channel ("release" or "dev") and release version; None = config default."""
    if channel not in (None, "release", "dev"):
        raise ValueError("prompt channel must be release or dev, got %r" % (channel,))
    if version is not None and not VERSION_RE.match(version):
        raise ValueError("prompt version must look like v1.2.3, got %r" % (version,))
    if version is not None and channel == "dev":
        raise ValueError("--prompt-version applies to the release channel only")
    PROMPT_SOURCE["channel"], PROMPT_SOURCE["version"] = channel, version


def prompt_source():
    """(channel, version) in effect; version is None for dev."""
    cfg = load_config("engine")
    channel = PROMPT_SOURCE["channel"] or cfg.get("prompt_channel", "release")
    if channel == "dev":
        return "dev", None
    return "release", PROMPT_SOURCE["version"] or cfg.get("prompt_release", "v1.0.0")


def prompt_root():
    """Directory the engine reads prompts from."""
    channel, version = prompt_source()
    if channel == "dev":
        return os.path.join(PROMPTS_DIR, "dev")
    return os.path.join(PROMPTS_DIR, "releases", version)


def read_prompt(rel, lang=None):
    """Text of <prompt_root>/lang/<lang>/<rel> if it exists, else <prompt_root>/<rel> (default variant)."""
    root = prompt_root()
    path = os.path.join(root, rel)
    if lang and CODE_RE.match(lang):
        cand = os.path.join(root, "lang", lang, rel)
        if os.path.isfile(cand):
            path = cand
    with open(path, encoding="utf-8") as fh:
        return fh.read()
