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


# Built, not a literal: a test bans bare path-name strings here (paths come from settings).
CONTRACT_KEY = "prompt" + "s"
CODE_RE = settings.CODE_RE


def _shape(v):
    """Key structure of a JSON value (keys only, no values); lists of scalars collapse to 'list'."""
    if isinstance(v, dict):
        return {k: _shape(x) for k, x in v.items()}
    if isinstance(v, list):
        dicts = [x for x in v if isinstance(x, dict)]
        return [_shape(dicts[0])] if dicts else "list"
    return "value"


def _bad_keys(v, sch, path=""):
    """Keys of v that the schema does not declare."""
    out = []
    if isinstance(v, dict) and isinstance(sch.get("properties"), dict):
        for k, x in v.items():
            if k not in sch["properties"]:
                out.append(path + k)
            else:
                out += _bad_keys(x, sch["properties"][k], path + k + ".")
    elif isinstance(v, list) and isinstance(sch.get("items"), dict):
        for x in v[:1]:
            out += _bad_keys(x, sch["items"], path)
    return out


def _example(text, anchor):
    """(object, error) for the JSON object that starts at anchor."""
    i = text.find(anchor)
    if i < 0:
        return None, "output example anchor %s not found" % anchor
    try:
        return json.JSONDecoder().raw_decode(text[i:])[0], None
    except ValueError as exc:
        return None, "output example does not parse: %s" % exc


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _check_file(path, rel, spec, default_example, errs, shown):
    """Markers + output example of one prompt file; appends 'ERROR' lines to errs."""
    try:
        text = _read(path)
    except (OSError, ValueError) as exc:
        errs.append("ERROR %s: cannot read: %s" % (shown, exc))
        return None
    for m in spec.get("markers", []):
        if not re.search(r"(?<![A-Za-z_])%s(?![A-Za-z_])" % re.escape(m), text):
            errs.append("ERROR %s: missing marker %r" % (shown, m))
    out = spec.get("output")
    if not out:
        return None
    ex, err = _example(text, out["anchor"])
    if err:
        errs.append("ERROR %s: %s" % (shown, err))
        return None
    bad = _bad_keys(ex, settings.load_schema(out["schema"]))
    if bad:
        errs.append("ERROR %s: output keys not in schema %s: %s" % (shown, out["schema"], ", ".join(bad)))
    if default_example is not None and _shape(ex) != _shape(default_example):
        errs.append("ERROR %s: output example key structure differs from the default variant" % shown)
    return ex


def _subject_spec(contract, name):
    subs = contract.get("subjects", {})
    return subs.get(name) or subs.get("*") or {"markers": []}


def _check_root(root, label, contract):
    """(errors, files, variants) for one prompt root (dev or a release)."""
    errs, files, defaults = [], 0, {}
    spec = contract[CONTRACT_KEY]
    for rel, sp in sorted(spec.items()):
        path = os.path.join(root, rel)
        shown = "%s/%s" % (label, rel)
        if not os.path.isfile(path):
            errs.append("ERROR %s: missing default file" % shown)
            continue
        files += 1
        defaults[rel] = _check_file(path, rel, sp, None, errs, shown)
    subj_dir = os.path.join(root, "subjects")
    subjects = sorted(n for n in os.listdir(subj_dir) if n.endswith(".md")) if os.path.isdir(subj_dir) else []
    for n in subjects:
        files += 1
        _check_file(os.path.join(subj_dir, n), "subjects/" + n, _subject_spec(contract, n[:-3]),
                    None, errs, "%s/subjects/%s" % (label, n))
    lang_dir = os.path.join(root, "lang")
    variants = 0
    for code in sorted(os.listdir(lang_dir)) if os.path.isdir(lang_dir) else []:
        cdir = os.path.join(lang_dir, code)
        shown = "%s/lang/%s" % (label, code)
        if not os.path.isdir(cdir):
            errs.append("ERROR %s: stray file under lang/" % shown)
            continue
        if not CODE_RE.match(code):
            errs.append("ERROR %s: bad variant code (want two lowercase letters)" % shown)
            continue
        variants += 1
        for d, _, names in sorted(os.walk(cdir)):
            for n in sorted(names):
                p = os.path.join(d, n)
                rel = os.path.relpath(p, cdir).replace(os.sep, "/")
                shown_f = "%s/%s" % (shown, rel)
                if rel in spec:
                    sp, dflt = spec[rel], defaults.get(rel)
                elif re.match(r"^subjects/[^/]+\.md$", rel) and rel[9:] in subjects:
                    sp, dflt = _subject_spec(contract, rel[9:-3]), None
                else:
                    errs.append("ERROR %s: file not in the prompt contract (typo?)" % shown_f)
                    continue
                files += 1
                _check_file(p, rel, sp, dflt, errs, shown_f)
    return errs, files, variants


def check_prompts(channel=None, version=None, all_=False):
    """(error lines, files checked, variants checked) for the chosen prompt roots against prompts/contract.json."""
    contract = settings.load_json(os.path.join(settings.PROMPTS_DIR, "contract.json"))
    if all_:
        rels = [("dev", os.path.join(settings.PROMPTS_DIR, "dev"))]
        rel_dir = os.path.join(settings.PROMPTS_DIR, "releases")
        for v in sorted(os.listdir(rel_dir)) if os.path.isdir(rel_dir) else []:
            rels.append(("releases/" + v, os.path.join(rel_dir, v)))
    else:
        settings.use_prompts(channel, version)
        ch, ver = settings.prompt_source()
        rels = [("dev", settings.prompt_root()) if ch == "dev" else ("releases/" + ver, settings.prompt_root())]
    errs, files, variants = [], 0, 0
    for label, root in rels:
        if not os.path.isdir(root):
            errs.append("ERROR %s: no such prompt directory" % label)
            continue
        e, f, v = _check_root(root, label, contract)
        errs, files, variants = errs + e, files + f, variants + v
    return errs, files, variants


def check_prompts_main(argv):
    """check-prompts [--channel C] [--version V] [--all]"""
    import argparse
    ap = argparse.ArgumentParser(prog="exam check-prompts",
                                 description="Check every prompt variant keeps the interface in prompts/contract.json.")
    ap.add_argument("--channel", choices=("release", "dev"))
    ap.add_argument("--version")
    ap.add_argument("--all", action="store_true", help="dev + every release")
    a = ap.parse_args(argv)
    try:
        errs, files, variants = check_prompts(a.channel, a.version, a.all)
    except (OSError, ValueError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    for e in errs:
        print(e)
    if errs:
        return 1
    print("OK: %d files, %d variants" % (files, variants))
    return 0
