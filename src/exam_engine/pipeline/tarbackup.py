"""Shared tar.gz backup helpers (plans-migrate backup, exam backup): refuse a dest inside the root, free-space check,
write + re-read verify, sha256 of a file. Stdlib only."""
import hashlib
import os
import shutil
import tarfile

MIN_FREE = 64 * 1024 * 1024


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def refuse_inside(dest, root):
    """realpath of dest; ValueError if it is root or under root."""
    bd = os.path.realpath(dest)
    rr = os.path.realpath(root)
    if bd == rr or bd.startswith(rr + os.sep):
        raise ValueError("backup dir %s is inside %s" % (dest, root))
    return bd


def ensure_free(directory, need_bytes):
    """Create directory; ValueError unless need_bytes + MIN_FREE fit."""
    need = need_bytes + MIN_FREE
    os.makedirs(directory, exist_ok=True)
    free = shutil.disk_usage(directory).free
    if free < need:
        raise ValueError("not enough free space in %s: need %d bytes, have %d" % (directory, need, free))


def write_verified(path, items, want_members=None, want_bytes=None):
    """tar.gz of items [(abs path, arcname)] (a dir is added recursively) at path via path.part; the listing is re-read
    and must match want_members/want_bytes (default: items are all regular files). Returns {"members", "bytes"};
    ValueError on mismatch."""
    if want_members is None:
        want_members = len(items)
    if want_bytes is None:
        want_bytes = sum(os.path.getsize(p) for p, _a in items)
    part = path + ".part"
    try:
        with tarfile.open(part, "w:gz") as tf:
            for p, a in items:
                tf.add(p, arcname=a)
        with tarfile.open(part, "r:gz") as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
        got_b = sum(m.size for m in members)
        if len(members) != want_members or got_b != want_bytes:
            raise ValueError("backup listing mismatch: %d files / %d bytes, expected %d / %d" % (
                len(members), got_b, want_members, want_bytes))
        os.replace(part, path)
    except BaseException:
        if os.path.exists(part):
            os.remove(part)
        raise
    return {"members": len(members), "bytes": got_b}
