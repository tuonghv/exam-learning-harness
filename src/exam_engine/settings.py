"""One place for repo paths and config loading (found from __file__, never from cwd).

EXAM_ENGINE_CONFIG_DIR overrides CONFIG_DIR (tests, extra subjects without code change).
"""
import json
import os

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


def read_prompt(rel):
    """Text of prompts/<rel>."""
    with open(os.path.join(PROMPTS_DIR, rel), encoding="utf-8") as fh:
        return fh.read()
