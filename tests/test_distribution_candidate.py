"""Real archive/Git-boundary controls for finite candidate preparation."""

from __future__ import annotations

import gzip
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import tarfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("holon_distribution_candidate", ROOT / "tools/distribution_candidate.py")
candidate = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(candidate)


class DistributionCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "producer"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Candidate Fixture")
        self.git("config", "user.email", "candidate@example.test")
        (self.repo / "tools").mkdir()
        (self.repo / "catalog").mkdir()
        (self.repo / "LICENSE").write_text("Synthetic archive license fixture.\n")
        (self.repo / "tools/distribution_candidate.py").write_bytes((ROOT / "tools/distribution_candidate.py").read_bytes())
        profile = {"repository": "egohygiene/holon", "status": "candidate-only", "version": "1.0.0-rc.0",
                   "included_paths": ["LICENSE", "catalog/distribution-candidate.json", "tools/distribution_candidate.py"],
                   "interfaces": ["synthetic archive fixture"], "supported_environments": [], "exclusions": ["publication"]}
        (self.repo / candidate.PROFILE).write_bytes(candidate.canonical(profile))
        self.commit()

    def git(self, *arguments):
        return subprocess.check_output(["git", "-C", str(self.repo), *arguments], stderr=subprocess.PIPE)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "Synthetic candidate fixture")
        self.source = self.git("rev-parse", "HEAD").decode().strip()

    def prepare(self, name="candidate"):
        with patch.object(candidate, "ROOT", self.repo):
            receipt = candidate.prepare(self.source, self.root / name)
        return receipt, self.root / name / receipt["archive"]

    def rewrite(self, archive, change):
        raw = gzip.decompress(archive.read_bytes())
        entries = []
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as source:
            for member in source:
                data = source.extractfile(member).read() if member.isfile() else b""
                entries.append((member, data))
        change(entries)
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w") as target:
            for member, data in entries:
                target.addfile(member, io.BytesIO(data) if member.isfile() else None)
        path = self.root / "changed.tar.gz"
        path.write_bytes(gzip.compress(output.getvalue(), mtime=0))
        return path, candidate.digest(path.read_bytes())

    def test_actual_archive_is_complete_reproducible_and_path_independent(self):
        first, archive = self.prepare("one-name")
        second, other = self.prepare("a-different-name")
        self.assertEqual(first, second)
        self.assertEqual(archive.read_bytes(), other.read_bytes())
        checked = candidate.verify(archive, first["archive_sha256"], self.root / "consumer")
        self.assertEqual(checked["source_commit"], self.source)
        self.assertEqual(checked["files"], 3)
        self.assertEqual((self.root / "consumer/holon/LICENSE").read_bytes(), (self.repo / "LICENSE").read_bytes())
        self.assertNotIn(str(self.repo).encode(), gzip.decompress(archive.read_bytes()))

    def test_dirty_source_is_never_packaged(self):
        original = (self.repo / "LICENSE").read_bytes()
        (self.repo / "LICENSE").write_text("Uncommitted source must not enter an immutable candidate.\n")
        receipt, archive = self.prepare()
        candidate.verify(archive, receipt["archive_sha256"], self.root / "consumer")
        self.assertEqual((self.root / "consumer/holon/LICENSE").read_bytes(), original)

    def test_moving_ref_and_different_preparer_are_rejected(self):
        with patch.object(candidate, "ROOT", self.repo):
            with self.assertRaises(candidate.CandidateError):
                candidate.prepare("HEAD", self.root / "moving")
        (self.repo / "tools/distribution_candidate.py").write_text("# different builder\n")
        self.commit()
        with self.assertRaisesRegex(candidate.CandidateError, "running preparer differs"):
            self.prepare()

    def test_symlink_source_is_not_distributed(self):
        (self.repo / "LICENSE").unlink()
        (self.repo / "LICENSE").symlink_to("tools/distribution_candidate.py")
        self.commit()
        with self.assertRaisesRegex(candidate.CandidateError, "symlink"):
            self.prepare()
        self.assertFalse((self.root / "candidate").exists())

    def test_existing_or_in_source_output_is_never_overwritten(self):
        self.prepare()
        before = {path.name: path.read_bytes() for path in (self.root / "candidate").iterdir()}
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(before, {path.name: path.read_bytes() for path in (self.root / "candidate").iterdir()})
        with patch.object(candidate, "ROOT", self.repo):
            with self.assertRaisesRegex(candidate.CandidateError, "outside"):
                candidate.prepare(self.source, self.repo / "output")

    def test_wrong_digest_refuses_before_extraction(self):
        _, archive = self.prepare()
        with self.assertRaisesRegex(candidate.CandidateError, "digest mismatch"):
            candidate.verify(archive, "0" * 64, self.root / "untouched")
        self.assertFalse((self.root / "untouched").exists())

    def test_trailing_payload_is_not_hidden_after_the_tar_end_marker(self):
        _, archive = self.prepare()
        altered = self.root / "trailing.tar.gz"
        altered.write_bytes(gzip.compress(gzip.decompress(archive.read_bytes()) + b"undeclared payload", mtime=0))
        with self.assertRaisesRegex(candidate.CandidateError, "trailing payload"):
            candidate.verify(altered, candidate.digest(altered.read_bytes()), self.root / "untouched")
        self.assertFalse((self.root / "untouched").exists())

    def test_traversal_link_and_duplicate_members_refuse_before_writes(self):
        _, archive = self.prepare()
        for kind in ("traversal", "link", "duplicate"):
            with self.subTest(kind=kind):
                def mutate(entries):
                    info = tarfile.TarInfo("holon/../outside" if kind == "traversal" else "holon/extra")
                    if kind == "link":
                        info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
                    elif kind == "duplicate":
                        info.name = entries[0][0].name
                    info.mode = 0o644
                    entries.append((info, b""))
                path, sha = self.rewrite(archive, mutate)
                with self.assertRaises(candidate.CandidateError):
                    candidate.verify(path, sha, self.root / ("refused-" + kind))
                self.assertFalse((self.root / ("refused-" + kind)).exists())

    def test_rehashed_archive_cannot_hide_payload_or_scope_changes(self):
        _, archive = self.prepare()
        for member in ("holon/LICENSE", "holon/DISTRIBUTION.json"):
            with self.subTest(member=member):
                def mutate(entries):
                    for index, (info, data) in enumerate(entries):
                        if info.name == member:
                            if member.endswith("DISTRIBUTION.json"):
                                value = json.loads(data); value["exclusions"] = []
                                data = candidate.canonical(value)
                            else:
                                data = b"Different payload\n"
                            info.size = len(data)
                            entries[index] = (info, data)
                path, sha = self.rewrite(archive, mutate)
                with self.assertRaises(candidate.CandidateError):
                    candidate.verify(path, sha, self.root / "refused-payload")
                self.assertFalse((self.root / "refused-payload").exists())

    def test_rehashed_manifest_cannot_change_the_supported_environment(self):
        _, archive = self.prepare()
        def mutate(entries):
            for index, (info, data) in enumerate(entries):
                if info.name == candidate.MANIFEST:
                    value = json.loads(data)
                    value["supported_environments"] = [{"os": "Windows", "architecture": "arm64", "python": "any"}]
                    data = candidate.canonical(value)
                    info.size = len(data)
                    entries[index] = (info, data)
        path, sha = self.rewrite(archive, mutate)
        with self.assertRaisesRegex(candidate.CandidateError, "scope differs"):
            candidate.verify(path, sha, self.root / "refused-environment")
        self.assertFalse((self.root / "refused-environment").exists())

    def test_rehashed_profile_cannot_promote_itself_to_a_release(self):
        _, archive = self.prepare()
        for field, changed in (("status", "released"), ("version", "1.0.0"), ("repository", "other/owner")):
            with self.subTest(field=field):
                def mutate(entries):
                    profile_name = "holon/" + candidate.PROFILE
                    for index, (info, data) in enumerate(entries):
                        if info.name == profile_name:
                            value = json.loads(data); value[field] = changed
                            updated = candidate.canonical(value)
                            info.size = len(updated)
                            entries[index] = (info, updated)
                    for index, (info, data) in enumerate(entries):
                        if info.name == candidate.MANIFEST:
                            value = json.loads(data)
                            value["files"][candidate.PROFILE] = {"sha256": candidate.digest(updated),
                                                                "bytes": len(updated), "mode": "0644"}
                            value["profile_sha256"] = candidate.digest(updated)
                            if field == "version": value["version"] = changed
                            data = candidate.canonical(value)
                            info.size = len(data)
                            entries[index] = (info, data)
                path, sha = self.rewrite(archive, mutate)
                with self.assertRaises(candidate.CandidateError):
                    candidate.verify(path, sha, self.root / "refused-release")
                self.assertFalse((self.root / "refused-release").exists())


if __name__ == "__main__":
    unittest.main()
