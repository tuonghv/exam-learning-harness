"""Reply cache shared by the AI helpers of ingest (boundary hints; page refine in TASK-047).

Interface (keep it this small): `ReplyCache(dir=None)`, `.get(namespace, key)` -> object or None,
`.put(namespace, key, obj)`. `key` is any string the caller hashes together (text + prompt hash +
model); `namespace` ("boundary", "page") keeps callers apart. Memory always; disk only when `dir`
is given (one JSON file per entry, written whole). A corrupt or unreadable file is a miss.
"""
import hashlib
import json
import os


class ReplyCache:
    def __init__(self, dir=None):
        self.dir = dir
        self.mem = {}

    def _path(self, namespace, key):
        digest = hashlib.sha256(("%s\0%s" % (namespace, key)).encode("utf-8")).hexdigest()
        return os.path.join(self.dir, "%s-%s.json" % (namespace, digest))

    def get(self, namespace, key):
        slot = (namespace, key)
        if slot in self.mem:
            return self.mem[slot]
        if self.dir:
            try:
                with open(self._path(namespace, key), encoding="utf-8") as fh:
                    obj = json.load(fh)
            except (OSError, ValueError):
                return None
            self.mem[slot] = obj
            return obj
        return None

    def put(self, namespace, key, obj):
        self.mem[(namespace, key)] = obj
        if self.dir:
            try:
                os.makedirs(self.dir, exist_ok=True)
                with open(self._path(namespace, key), "w", encoding="utf-8") as fh:
                    json.dump(obj, fh, ensure_ascii=False)
            except OSError:
                pass  # the cache is an optimisation, never a failure
