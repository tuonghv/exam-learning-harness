"""exam backup (TASK-106): write, verify, rotate, check/restore. Tmp trees only; never the real plans/."""
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from exam_engine import backup  # noqa: E402
from exam_engine.pipeline import tarbackup  # noqa: E402

MAN = ".sha256.json"
GZ = ".tar.gz"


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = backup.backup_main(argv)
    return code, out.getvalue(), err.getvalue()


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class BackupBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = os.path.join(self.tmp, "repo")
        self.dest = os.path.join(self.tmp, "bk")
        for rel, data in (("plans/x1/run1/solve.json", b"{}"), ("plans/x1/run-history.jsonl", b"a\n"),
                          ("input/k.answer.txt", b"1 A\n"), ("config/published_reports.json", b"{}\n"),
                          ("other/skip.txt", b"no")):
            p = os.path.join(self.repo, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(data)

    def write(self, *extra):
        return _run(["--dest", self.dest, "--repo", self.repo] + list(extra))

    def archives(self):
        return sorted(n for n in os.listdir(self.dest) if n.endswith(GZ))

    def make(self):
        self.assertEqual(self.write()[0], 0)
        return os.path.join(self.dest, self.archives()[0])


class TestWrite(BackupBase):
    def test_write_manifest_matches_tree(self):
        code, out, err = self.write()
        self.assertEqual(code, 0, err)
        (name,) = self.archives()
        man = _load(os.path.join(self.dest, name[:-len(GZ)] + MAN))
        self.assertEqual(sorted(man["files"]), ["config/published_reports.json", "input/k.answer.txt",
                                                "plans/x1/run-history.jsonl", "plans/x1/run1/solve.json"])
        for arc, sha in man["files"].items():
            self.assertEqual(_sha(os.path.join(self.repo, *arc.split("/"))), sha)
        self.assertIn("files 4", out)

    def test_dest_inside_repo_exit2_nothing_created(self):
        inside = os.path.join(self.repo, "tmpb")
        code, _o, err = _run(["--dest", inside, "--repo", self.repo])
        self.assertEqual(code, 2)
        self.assertIn("inside repo", err)
        self.assertFalse(os.path.exists(inside))

    def test_keep_zero_exit2(self):
        self.assertEqual(self.write("--keep", "0")[0], 2)

    def test_nothing_to_back_up_exit2(self):
        shutil.rmtree(os.path.join(self.repo, "plans"))
        shutil.rmtree(os.path.join(self.repo, "input"))
        os.remove(os.path.join(self.repo, "config", "published_reports.json"))
        self.assertEqual(self.write()[0], 2)

    def test_symlink_skipped_with_warning(self):
        os.symlink(os.path.join(self.repo, "input", "k.answer.txt"), os.path.join(self.repo, "input", "ln.txt"))
        code, _o, err = self.write()
        self.assertEqual(code, 0)
        self.assertIn("WARN: skip", err)

    def test_verify_failure_removes_archive_and_manifest(self):
        with mock.patch.object(backup, "verify_archive", return_value=["x sha mismatch"]):
            code, _o, err = self.write()
        self.assertEqual(code, 1)
        self.assertIn("verify failed", err)
        self.assertEqual(os.listdir(self.dest), [])

    def test_low_space_exit2(self):
        with mock.patch.object(tarbackup, "MIN_FREE", 1 << 60):
            self.assertEqual(self.write()[0], 2)
        self.assertFalse(os.path.exists(self.dest) and os.listdir(self.dest))


class TestRotate(BackupBase):
    def test_keep_five_newest_other_files_untouched(self):
        os.makedirs(self.dest)
        for d in range(1, 8):
            stem = os.path.join(self.dest, "exam-inputs-2020010%dT000000Z" % d)
            for suf in (GZ, MAN):
                open(stem + suf, "w").close()
        open(os.path.join(self.dest, "other.txt"), "w").close()
        backup._rotate(self.dest, 5)
        left = sorted(os.listdir(self.dest))
        self.assertEqual(len([n for n in left if n.endswith(GZ)]), 5)
        self.assertEqual(len([n for n in left if n.endswith(MAN)]), 5)
        self.assertIn("other.txt", left)
        self.assertNotIn("exam-inputs-20200101T000000Z.tar.gz", left)

    def test_leftover_part_ignored_by_rotation(self):
        # crash mid-write leaves only .part; rotation must neither count nor delete it
        os.makedirs(self.dest)
        part = os.path.join(self.dest, "exam-inputs-20200101T000000Z.tar.gz.part")
        open(part, "w").close()
        for d in (2, 3):
            open(os.path.join(self.dest, "exam-inputs-2020010%dT000000Z%s" % (d, GZ)), "w").close()
        backup._rotate(self.dest, 1)
        self.assertTrue(os.path.exists(part))
        self.assertEqual(len(self.archives()), 1)


class TestCheck(BackupBase):
    def test_check_ok_and_restore_matches(self):
        arc = self.make()
        self.assertEqual(_run(["--check", arc, "--repo", self.repo])[0], 0)
        out_dir = os.path.join(self.tmp, "er")
        code, _o, err = _run(["--check", arc, "--restore-to", out_dir, "--repo", self.repo])
        self.assertEqual(code, 0, err)
        for arcname, sha in _load(arc[:-len(GZ)] + MAN)["files"].items():
            self.assertEqual(_sha(os.path.join(out_dir, *arcname.split("/"))), sha)

    def test_tampered_archive_exit1(self):
        arc = self.make()
        with open(arc, "rb") as fh:
            raw = bytearray(fh.read())
        raw[len(raw) // 2] ^= 0xFF
        with open(arc, "wb") as fh:
            fh.write(bytes(raw))
        code, _o, err = _run(["--check", arc, "--repo", self.repo])
        self.assertEqual(code, 1)
        self.assertIn("FAIL", err)

    def test_valid_gzip_with_altered_member_exit1(self):
        # repacked (still readable) archive: only the sha check can catch it
        arc = self.make()
        with tarfile.open(arc, "r:gz") as tf:
            items = [(m, tf.extractfile(m).read() if m.isfile() else None) for m in tf]
        with tarfile.open(arc, "w:gz") as tf:
            for m, data in items:
                if data is not None and m.name == "input/k.answer.txt":
                    data = b"9 Z\n"
                    m.size = len(data)
                tf.addfile(m, io.BytesIO(data) if data is not None else None)
        code, _o, err = _run(["--check", arc, "--repo", self.repo])
        self.assertEqual(code, 1)
        self.assertIn("FAIL", err)

    def test_manifest_sha_mismatch_names_member(self):
        arc = self.make()
        mp = arc[:-len(GZ)] + MAN
        man = _load(mp)
        man["files"]["input/k.answer.txt"] = "0" * 64
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump(man, fh)
        code, _o, err = _run(["--check", arc, "--repo", self.repo])
        self.assertEqual(code, 1)
        self.assertIn("input/k.answer.txt sha mismatch", err)

    def test_missing_manifest_exit2(self):
        arc = self.make()
        os.remove(arc[:-len(GZ)] + MAN)
        self.assertEqual(_run(["--check", arc, "--repo", self.repo])[0], 2)

    def test_restore_dir_not_empty_or_inside_repo_exit2(self):
        arc = self.make()
        full = os.path.join(self.tmp, "full")
        os.makedirs(full)
        open(os.path.join(full, "f"), "w").close()
        self.assertEqual(_run(["--check", arc, "--restore-to", full, "--repo", self.repo])[0], 2)
        self.assertEqual(_run(["--check", arc, "--restore-to", os.path.join(self.repo, "r"),
                               "--repo", self.repo])[0], 2)

    def _evil(self, kind):
        arc = os.path.join(self.tmp, "evil" + GZ)
        names = {"parent": "../evil", "abs": "/abs-evil", "link": "plans/ln", "dev": "plans/dev"}
        with tarfile.open(arc, "w:gz") as tf:
            good = tarfile.TarInfo("plans/good")
            good.size = 1
            tf.addfile(good, io.BytesIO(b"g"))
            ti = tarfile.TarInfo(names[kind])
            if kind in ("parent", "abs"):
                ti.size = 1
                tf.addfile(ti, io.BytesIO(b"x"))
            else:
                ti.type = tarfile.SYMTYPE if kind == "link" else tarfile.CHRTYPE
                ti.linkname = "target"
                tf.addfile(ti)
        man = {"version": 1, "archive_sha256": _sha(arc), "files": {"plans/good": hashlib.sha256(b"g").hexdigest()}}
        with open(arc[:-len(GZ)] + MAN, "w", encoding="utf-8") as fh:
            json.dump(man, fh)
        return arc

    def test_unsafe_members_reject_whole_archive_nothing_extracted(self):
        for kind in ("parent", "abs", "link", "dev"):
            arc = self._evil(kind)
            out_dir = os.path.join(self.tmp, "r-" + kind)
            code, _o, err = _run(["--check", arc, "--restore-to", out_dir, "--repo", self.repo])
            self.assertEqual(code, 1, kind)
            self.assertIn("unsafe member", err)
            self.assertFalse(os.path.exists(out_dir) and os.listdir(out_dir), kind)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "evil")))

    def test_restore_does_not_use_extractall(self):
        arc = self.make()
        with mock.patch.object(tarfile.TarFile, "extractall", side_effect=AssertionError("extractall")):
            self.assertEqual(_run(["--check", arc, "--restore-to", os.path.join(self.tmp, "r2"),
                                   "--repo", self.repo])[0], 0)


class TestTarbackup(unittest.TestCase):
    def test_refuse_inside_and_write_verified(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                tarbackup.refuse_inside(os.path.join(d, "a"), d)
            f = os.path.join(d, "f")
            with open(f, "w", encoding="utf-8") as fh:
                fh.write("hi")
            path = os.path.join(d, "o" + GZ)
            self.assertEqual(tarbackup.write_verified(path, [(f, "f")]), {"members": 1, "bytes": 2})
            self.assertFalse(os.path.exists(path + ".part"))
            with self.assertRaises(ValueError):
                tarbackup.write_verified(path + "2", [(f, "f")], want_members=2)
            self.assertFalse(os.path.exists(path + "2.part"))


if __name__ == "__main__":
    unittest.main()
