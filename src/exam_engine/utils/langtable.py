"""Extra-language word table (config/lang.json). vi+en stay code literals; this only adds words.

Words, never regex fragments (an exam clone is untrusted): every word is re.escape()d.
"""
import json
import os
import re

SLOTS = ("question", "group", "range", "intro", "part", "page", "true", "false", "paragraph", "figure",
         "needs_text", "scripts")


def load(config_dir=None):
    """-> {"extra": {code: {slot: [words]}}}; missing file = empty table; malformed = ValueError."""
    if config_dir is None:
        from exam_engine import settings
        config_dir = settings.config_dir()
    path = os.path.join(config_dir, "lang.json")
    if not os.path.exists(path):
        return {"extra": {}}
    try:
        with open(path, encoding="utf-8") as fh:
            table = json.load(fh)
    except ValueError as e:
        raise ValueError("%s: %s" % (path, e))
    extra = table.get("extra") if isinstance(table, dict) else None
    ok = isinstance(extra, dict) and all(
        isinstance(langs, dict) and all(
            k in SLOTS and isinstance(ws, list) and all(isinstance(w, str) and w.strip() for w in ws)
            for k, ws in langs.items())
        for langs in extra.values())
    if not ok:
        raise ValueError("%s: expected {\"extra\": {code: {slot: [words]}}}" % path)
    return table


def raw(slot, table):
    """Plain words of all extra languages for `slot`, sorted, unique."""
    out = set()
    for langs in (table or {}).get("extra", {}).values():
        out.update(w.strip() for w in langs.get(slot, ()))
    return sorted(out)


def words(slot, table):
    """Escaped words (regex-safe); longest first so a longer word wins over its prefix."""
    return sorted((re.escape(w) for w in raw(slot, table)), key=lambda w: (-len(w), w))


def alt(base, slot, table):
    """`base` unchanged when no extra words, else a group of base or the extra words."""
    ws = words(slot, table)
    return "(?:" + base + "|" + "|".join(ws) + ")" if ws else base
