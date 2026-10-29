"""Prompt releases: freeze prompts/dev into prompts/releases/<version> and verify it.

release() is the only writer of a release path and never overwrites one.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

from exam_engine import settings

MANIFEST = "MANIFEST.json"
VERSION_RE = settings.VERSION_RE


def _dev_dir():
    return os.path.join(settings.PROMPTS_DIR, "dev")


def _release_dir(version):
    return os.path.join(settings.PROMPTS_DIR, "releases", version)


def _hash_tree(root):
    """{relative path with /: sha256} of every file under root except the manifest."""
    out = {}
    for d, _, names in os.walk(root):
        for n in names:
            p = os.path.join(d, n)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if rel == MANIFEST:
                continue
            with open(p, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def release(version):
    """Copy dev to releases/<version> and write the manifest; ValueError if invalid or existing."""
    if not VERSION_RE.match(version or ""):
        raise ValueError("version must look like v1.2.3, got %r" % (version,))
    dest = _release_dir(version)
    if os.path.exists(dest):
        raise ValueError("release %s already exists (releases are never overwritten)" % version)
    shutil.copytree(_dev_dir(), dest)
    manifest = {"version": version,
                "created": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "files": _hash_tree(dest)}
    with open(os.path.join(dest, MANIFEST), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return manifest


def verify_release(version=None):
    """List of problems (empty = release intact); version defaults to the one in effect."""
    version = version or settings.prompt_source()[1] or settings.load_config("engine")["prompt_release"]
    root = _release_dir(version)
    try:
        manifest = settings.load_json(os.path.join(root, MANIFEST))
    except (OSError, ValueError) as exc:
        return ["%s: cannot read manifest: %s" % (version, exc)]
    want, have = manifest.get("files", {}), _hash_tree(root)
    errs = ["%s: missing file %s" % (version, f) for f in sorted(set(want) - set(have))]
    errs += ["%s: extra file %s" % (version, f) for f in sorted(set(have) - set(want))]
    errs += ["%s: changed file %s" % (version, f)
             for f in sorted(set(want) & set(have)) if want[f] != have[f]]
    return errs


def prompt_info():
    """{channel, version} of the prompts in effect (version None for dev)."""
    channel, version = settings.prompt_source()
    return {"channel": channel, "version": version}


def prompts_main(argv):
    """prompts release V | prompts verify [V]"""
    usage = "usage: exam.py prompts release V | verify [V]"
    if argv[:1] == ["release"] and len(argv) == 2:
        try:
            m = release(argv[1])
        except (OSError, ValueError) as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 1
        print("released %s (%d files)" % (argv[1], len(m["files"])))
        return 0
    if argv[:1] == ["verify"] and len(argv) in (1, 2):
        errs = verify_release(argv[1] if len(argv) == 2 else None)
        for e in errs:
            print("ERROR: %s" % e, file=sys.stderr)
        if not errs:
            print("ok")
        return 1 if errs else 0
    print(usage, file=sys.stderr)
    return 2
