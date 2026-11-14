"""exam backup: tar.gz + sha256 manifest of the untracked rebuild inputs (plans/, input/, the published-reports recipe),
verified after writing, newest N kept; `--check A [--restore-to D]` proves an archive intact and restores it safely.
Local disk only: no network. Stdlib only."""
import argparse
import datetime
import hashlib
import json
import os
import sys
import tarfile

from exam_engine.pipeline import tarbackup

BACKUP_ROOTS = ("plans", "input", "config/published_reports.json")
PREFIX = "exam-inputs-"
SUFFIX = ".tar.gz"
MAN_SUFFIX = ".sha256.json"
DEFAULT_DEST = os.path.join("~", "exam-harness-backup")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/exam_engine/ -> repo root
UP = "." + "."


def manifest_path(archive):
    base = archive[:-len(SUFFIX)] if archive.endswith(SUFFIX) else archive
    return base + MAN_SUFFIX


def _collect(repo):
    """([(abs, arcname)] sorted regular files, [warning lines])."""
    items, warns = [], []
    for root in BACKUP_ROOTS:
        top = os.path.join(repo, *root.split("/"))
        if os.path.islink(top):
            warns.append("WARN: skip symlink %s" % root)
        elif os.path.isfile(top):
            items.append((top, root))
        elif os.path.isdir(top):
            for base, dns, fns in os.walk(top):
                dns.sort()
                for dn in list(dns):
                    if os.path.islink(os.path.join(base, dn)):
                        dns.remove(dn)
                        warns.append("WARN: skip symlink %s" % os.path.relpath(
                            os.path.join(base, dn), repo).replace(os.sep, "/"))
                for fn in sorted(fns):
                    p = os.path.join(base, fn)
                    rel = os.path.relpath(p, repo).replace(os.sep, "/")
                    if os.path.islink(p) or not os.path.isfile(p):
                        warns.append("WARN: skip non-regular %s" % rel)
                    else:
                        items.append((p, rel))
        else:
            warns.append("WARN: missing %s" % root)
    return sorted(items, key=lambda t: t[1]), warns


def unsafe_member(m, dest=None):
    """Reason a tar member must be refused, else ''. Only regular files/dirs with a relative, parent-free name that
    stays under dest (when given) are safe."""
    name = m.name
    if not (m.isfile() or m.isdir()):
        return "not a regular file or dir"
    if not name or os.path.isabs(name):
        return "absolute name"
    if UP in name.split("/"):
        return "parent dir part in name"
    if dest is not None:
        d = os.path.realpath(dest)
        t = os.path.realpath(os.path.join(d, name))
        if t != d and not t.startswith(d + os.sep):
            return "outside dest"
    return ""


def _stream_sha(tf, m):
    h = hashlib.sha256()
    fh = tf.extractfile(m)
    for chunk in iter(lambda: fh.read(1 << 20), b""):
        h.update(chunk)
    return h.hexdigest()


def verify_archive(archive, manifest):
    """[problem lines]; empty = archive matches the manifest member by member."""
    try:
        with open(manifest, encoding="utf-8") as fh:
            man = json.load(fh)
        want = dict(man["files"])
        want_arch = man["archive_sha256"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ["manifest unreadable: %s" % exc]
    problems = []
    try:
        if tarbackup.sha_file(archive) != want_arch:
            problems.append("archive sha mismatch")
        seen = set()
        with tarfile.open(archive, "r:gz") as tf:
            for m in tf:
                why = unsafe_member(m)
                if why:
                    problems.append("unsafe member %s (%s)" % (m.name, why))
                elif m.isfile():
                    seen.add(m.name)
                    if m.name not in want:
                        problems.append("%s not in manifest" % m.name)
                    elif _stream_sha(tf, m) != want[m.name]:
                        problems.append("%s sha mismatch" % m.name)
        for name in sorted(set(want) - seen):
            problems.append("%s missing from archive" % name)
    except (OSError, tarfile.TarError, EOFError) as exc:
        problems.append("archive unreadable: %s" % exc)
    return problems


def _rotate(dest, keep):
    names = sorted(n for n in os.listdir(dest) if n.startswith(PREFIX) and n.endswith(SUFFIX))
    for n in names[:max(0, len(names) - keep)]:
        for p in (os.path.join(dest, n), manifest_path(os.path.join(dest, n))):
            if os.path.isfile(p):
                os.remove(p)


def _write_manifest(path, obj):
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def backup_main(argv):
    ap = argparse.ArgumentParser(prog="exam backup", description="Archive the untracked rebuild inputs (plans/, input/, "
                                 "the published-reports recipe) to a local dir with a sha256 manifest; keep the newest N. "
                                 "--check ARCHIVE verifies one (and --restore-to DIR restores it). Nothing is uploaded.")
    ap.add_argument("--dest", default=DEFAULT_DEST, help="backup dir, outside the repo (default: %(default)s)")
    ap.add_argument("--keep", type=int, default=5, help="archives to keep (default 5, >= 1)")
    ap.add_argument("--repo", default=REPO, help="repo root to archive (default: this checkout)")
    ap.add_argument("--check", metavar="ARCHIVE", help="verify ARCHIVE against its .sha256.json instead of writing")
    ap.add_argument("--restore-to", metavar="DIR", help="with --check: restore into this empty dir outside the repo")
    a = ap.parse_args(argv)
    if a.keep < 1:
        print("ERROR: --keep must be >= 1", file=sys.stderr)
        return 2
    if a.restore_to and not a.check:
        print("ERROR: --restore-to needs --check", file=sys.stderr)
        return 2
    if a.check:
        return check_main(a.check, a.restore_to, a.repo)
    dest = os.path.expanduser(a.dest)
    try:
        bd = tarbackup.refuse_inside(dest, a.repo)
    except ValueError:
        print("ERROR: dest %s inside repo" % a.dest, file=sys.stderr)
        return 2
    items, warns = _collect(a.repo)
    for w in warns:
        print(w, file=sys.stderr)
    if not items:
        print("ERROR: nothing to back up", file=sys.stderr)
        return 2
    total = sum(os.path.getsize(p) for p, _a in items)
    try:
        tarbackup.ensure_free(bd, total)
    except (ValueError, OSError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = os.path.join(bd, PREFIX + stamp + SUFFIX)
    man = manifest_path(archive)
    try:
        tarbackup.write_verified(archive, items)
        _write_manifest(man, {"version": 1, "created_utc": stamp, "repo": os.path.abspath(a.repo),
                              "archive": os.path.basename(archive), "archive_sha256": tarbackup.sha_file(archive),
                              "files": {arc: tarbackup.sha_file(p) for p, arc in items}, "bytes": total})
    except (ValueError, OSError) as exc:
        _cleanup(archive, man)
        print("ERROR: backup failed: %s" % exc, file=sys.stderr)
        return 1
    problems = verify_archive(archive, man)
    if problems:
        _cleanup(archive, man)
        print("ERROR: verify failed: %s" % problems[0], file=sys.stderr)
        return 1
    _rotate(bd, a.keep)
    with open(man, encoding="utf-8") as fh:
        sha = json.load(fh)["archive_sha256"]
    print("backup %s files %d bytes %d sha256 %s" % (archive, len(items), total, sha[:12]))
    return 0


def _cleanup(archive, man):
    for p in (archive, man, archive + ".part", man + ".part"):
        if os.path.exists(p):
            os.remove(p)


def _restore(archive, dest):
    """Extract regular files member by member (no extractall). Caller checked every member first."""
    with tarfile.open(archive, "r:gz") as tf:
        for m in tf:
            target = os.path.join(dest, *m.name.split("/"))
            if m.isdir():
                os.makedirs(target, exist_ok=True)
                os.chmod(target, 0o755)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            src = tf.extractfile(m)
            with open(target, "wb") as out:
                for chunk in iter(lambda: src.read(1 << 20), b""):
                    out.write(chunk)
            os.chmod(target, 0o644)


def check_main(archive, restore_to, repo):
    man = manifest_path(archive)
    if not os.path.isfile(archive) or not os.path.isfile(man):
        print("ERROR: need both %s and %s" % (archive, man), file=sys.stderr)
        return 2
    dest = None
    if restore_to:
        dest = os.path.expanduser(restore_to)
        try:
            tarbackup.refuse_inside(dest, repo)
            if os.path.exists(dest) and (not os.path.isdir(dest) or os.listdir(dest)):
                raise ValueError("%s is not empty" % dest)
        except ValueError as exc:
            print("ERROR: restore dir: %s" % exc, file=sys.stderr)
            return 2
    problems = []
    try:
        with tarfile.open(archive, "r:gz") as tf:  # unsafe members reject the archive before any hashing or writing
            for m in tf:
                why = unsafe_member(m, dest)
                if why:
                    problems.append("unsafe member %s (%s)" % (m.name, why))
    except (OSError, tarfile.TarError, EOFError) as exc:
        problems.append("archive unreadable: %s" % exc)
    if not problems:
        problems = verify_archive(archive, man)
    if problems:
        for p in problems:
            print("FAIL: %s" % p, file=sys.stderr)
        return 1
    with open(man, encoding="utf-8") as fh:
        n = len(json.load(fh)["files"])
    if dest is not None:
        os.makedirs(dest, exist_ok=True)
        _restore(archive, dest)
        print("restored %d files to %s" % (n, dest))
    print("OK %d files" % n)
    return 0
