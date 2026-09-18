"""Disposable consumer proof for the pinned, read-only ignore adapter."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from materialization.common import MaterializationError, canonical_bytes, sha256_bytes
from materialization.gitignore import build_gitignore_plan, check_gitignore_plan

FIXTURES = ROOT / "tests/fixtures/gitignore"
CLI = ROOT / "tools/holon_materialize.py"


def snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()}


class GitignoreMaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = self.root / "consumer"
        self.target.mkdir()
        self.source = self.root / "empathy"
        shutil.copytree(FIXTURES / "empathy", self.source)
        self.load_fixture("filament")

    def load_fixture(self, name: str) -> None:
        self.request = json.loads((FIXTURES / name / "request.json").read_text())
        self.composition = json.loads((FIXTURES / name / "composition.json").read_text())

    def bind(self) -> None:
        self.request["composition_sha256"] = sha256_bytes(canonical_bytes(self.composition))

    def plan(self) -> dict:
        return build_gitignore_plan(self.request, self.composition, self.target,
                                   empathy_source=self.source)

    def install(self) -> None:
        # Test setup only: Holon itself has no apply command in this slice.
        for file in self.composition["files"]:
            path = self.target / file["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(file["content"].encode("utf-8"))

    def adopt(self) -> None:
        self.request["adopt"] = [{"path": file["path"], "before_sha256": file["content_sha256"]}
                                 for file in self.composition["files"]]

    def test_greenfield_is_exact_deterministic_and_read_only(self) -> None:
        (self.target / "README.md").write_bytes(b"Unrelated repository prose\r\n")
        (self.target / ".git").mkdir()
        (self.target / ".git/config").write_bytes(b"[core]\n")
        before, source_before = snapshot(self.target), snapshot(self.source)
        plan = self.plan()
        self.assertEqual(plan, self.plan())
        self.assertEqual(plan["summary"], {"create": 1})
        operation = plan["operations"][0]
        self.assertEqual(operation["proposed_sha256"],
                         "3637ea33004215037e745cf898f59e7c2a3195f8b66df5bae0921186ec731373")
        self.assertEqual(operation["proposed_content"], self.composition["files"][0]["content"])
        self.assertTrue(operation["diff"].startswith("--- /dev/null\n+++ b/.gitignore\n"))
        self.assertIsNone(operation["before_sha256"])
        self.assertNotIn(str(self.root), json.dumps(plan))
        self.assertEqual(snapshot(self.target), before)
        self.assertEqual(snapshot(self.source), source_before)

    def test_exact_match_needs_explicit_adoption(self) -> None:
        self.install()
        self.assertEqual(self.plan()["summary"], {"conflict": 1})
        self.adopt()
        before = snapshot(self.target)
        plan = self.plan()
        self.assertEqual(plan["summary"], {"adopt": 1})
        self.assertEqual(plan["operations"][0]["diff"], "")
        check_gitignore_plan(plan, self.request, self.composition, self.target,
                             empathy_source=self.source)
        self.assertEqual(snapshot(self.target), before)
        self.assertFalse((self.target / ".holon").exists())

    def test_missing_target_stays_absent_and_plan_is_path_independent(self) -> None:
        plan = self.plan()
        self.target = self.root / "different location" / "missing-consumer"
        self.assertEqual(self.plan(), plan)
        self.assertFalse(self.target.parent.exists())

    def test_adoption_binds_present_exact_bytes(self) -> None:
        self.adopt()
        self.assertEqual(self.plan()["summary"], {"conflict": 1})
        self.install()
        self.request["adopt"][0]["before_sha256"] = "0" * 64
        self.assertEqual(self.plan()["summary"], {"conflict": 1})
        path = self.target / ".gitignore"
        path.write_bytes(path.read_bytes() + b"/my-local-output/\n")
        self.request["adopt"][0]["before_sha256"] = sha256_bytes(path.read_bytes())
        self.assertEqual(self.plan()["summary"], {"conflict": 1})

    def test_unknown_bytes_are_preserved_with_useful_diff(self) -> None:
        path = self.target / ".gitignore"
        path.write_bytes(b"# Authored locally\r\n/private-cache/")
        before = path.read_bytes()
        operation = self.plan()["operations"][0]
        self.assertEqual(operation["action"], "conflict")
        self.assertIn("explicitly reconcile", operation["reason"])
        self.assertIn("No newline at end of file", operation["diff"])
        self.assertEqual(operation["before_content"].encode(), before)
        self.assertEqual(path.read_bytes(), before)

    def test_binary_unknown_file_is_not_decoded_or_overwritten(self) -> None:
        (self.target / ".gitignore").write_bytes(b"\xff\x00")
        operation = self.plan()["operations"][0]
        self.assertEqual(operation["action"], "conflict")
        self.assertIsNone(operation["diff"])
        self.assertEqual(operation["before_sha256"], sha256_bytes(b"\xff\x00"))

    def test_scoped_selection_and_local_text_are_preserved(self) -> None:
        self.load_fixture("scoped-rust")
        plan = self.plan()
        self.assertEqual(plan["summary"], {"create": 2})
        root, scoped = plan["operations"]
        self.assertEqual(root["path"], ".gitignore")
        self.assertNotIn("/target/", root["proposed_content"].split("# Language/build outputs")[0])
        self.assertEqual(scoped["path"], "crates/widget/.gitignore")
        self.assertEqual([layer["kind"] for layer in scoped["layers"]], ["overlay", "local", "baseline"])
        local = self.request["scopes"][1]["local_additions"]
        self.assertEqual(scoped["selection"]["local_additions"], local)
        self.assertIn("\n" + local + "\n# Universal baseline", scoped["proposed_content"])

    def test_git_behavior_uses_actual_scoped_composition(self) -> None:
        git = shutil.which("git")
        self.assertIsNotNone(git, "Git is required for the consumer behavior proof")
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_ATTR_NOSYSTEM="1", GIT_OPTIONAL_LOCKS="0")
        template = self.root / "empty-template"
        template.mkdir()
        subprocess.run([git, "init", "--quiet", f"--template={template}", str(self.target)],
                       env=environment, check=True)
        self.load_fixture("scoped-rust")
        self.install()
        self.adopt()
        cases = {".env": True, ".env.example": False, "Cargo.lock": False,
                 "target/keep.txt": False, "src/main.rs": False,
                 "crates/widget/target/build.o": True, "crates/widget/target/keep.txt": False,
                 "crates/widget/scratch/cache": True, "crates/widget/.env.dev": True,
                 "crates/widget/.env.dev.template": False, "crates/widget/src/lib.rs": False,
                 "crates/other/target/output": False}
        for path in cases:
            destination = self.target / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("fixture\n")
        before = snapshot(self.target)
        self.assertEqual(self.plan()["summary"], {"adopt": 2})
        for path, ignored in cases.items():
            with self.subTest(path=path):
                result = subprocess.run([git, "-c", f"core.excludesFile={os.devnull}",
                                         "-c", "core.ignoreCase=false", "check-ignore", "--quiet",
                                         "--no-index", "--", path], cwd=self.target, env=environment)
                self.assertEqual(result.returncode, 0 if ignored else 1)
        self.assertEqual(snapshot(self.target), before)

    def test_stale_and_tampered_plans_fail(self) -> None:
        plan = self.plan()
        (self.target / "README.md").write_text("unrelated change\n")
        check_gitignore_plan(plan, self.request, self.composition, self.target,
                             empathy_source=self.source)
        forged = copy.deepcopy(plan)
        forged["operations"][0]["action"] = "adopt"
        with self.assertRaisesRegex(MaterializationError, "stale or changed"):
            check_gitignore_plan(forged, self.request, self.composition, self.target,
                                 empathy_source=self.source)
        self.install()
        with self.assertRaisesRegex(MaterializationError, "stale or changed"):
            check_gitignore_plan(plan, self.request, self.composition, self.target,
                                 empathy_source=self.source)

    def test_conflicted_plan_cannot_pass_check(self) -> None:
        self.install()
        with self.assertRaisesRegex(MaterializationError, "has conflicts"):
            check_gitignore_plan(self.plan(), self.request, self.composition, self.target,
                                 empathy_source=self.source)

    def test_source_drift_including_unselected_fragment_fails(self) -> None:
        for relative in ("foundation/catalog.json", "foundation/ignore/universal.gitignore",
                         "foundation/ignore/rust.gitignore"):
            with self.subTest(relative=relative):
                path = self.source / relative
                original = path.read_bytes()
                path.write_bytes(original.replace(b"universal", b"modified", 1)
                                 if relative.endswith(".json") else original + b"/extra/\n")
                with self.assertRaisesRegex(MaterializationError, "digest mismatch"):
                    self.plan()
                path.write_bytes(original)

    def test_source_symlink_fails_even_with_matching_bytes(self) -> None:
        path = self.source / "foundation/ignore/universal.gitignore"
        outside = self.root / "baseline"
        path.rename(outside)
        path.symlink_to(outside)
        with self.assertRaisesRegex(MaterializationError, "symlink"):
            self.plan()

    def test_unsupported_and_malformed_requests_fail(self) -> None:
        valid = copy.deepcopy(self.request)
        for field, value in (("schema_version", "v2"), ("source_revision", "main"),
                             ("repository", []), ("profiles", ["unknown"]), ("scopes", []),
                             ("adopt", [{"path": "README.md", "before_sha256": "0" * 64}]),
                             ("composition_sha256", "0" * 64), ("unexpected", True)):
            with self.subTest(field=field):
                self.request = {**valid, field: value}
                with self.assertRaises(MaterializationError):
                    self.plan()

    def test_invalid_scope_paths_fail(self) -> None:
        for root in ("../escape", "/tmp/escape", "a/../b", "a//b", "./a", "a\\b",
                     ".git", ".GIT/config", ".holon", "a/.gitignore", "a/*", "a\n", " a"):
            with self.subTest(root=root):
                self.request["scopes"][0]["root"] = root
                with self.assertRaises(MaterializationError):
                    self.plan()

    def test_duplicate_scopes_and_invalid_local_text_fail(self) -> None:
        self.load_fixture("scoped-rust")
        for root in (".", "CRATES/widget"):
            # Add a duplicate output; case-insensitive collisions also fail.
            request = copy.deepcopy(self.request)
            composition = copy.deepcopy(self.composition)
            scope = copy.deepcopy(request["scopes"][0 if root == "." else 1])
            scope["root"] = root
            self.request["scopes"].append(scope)
            self.composition["files"].append(copy.deepcopy(composition["files"][0 if root == "." else 1]))
            self.bind()
            with self.assertRaisesRegex(MaterializationError, "unique"):
                self.plan()
            self.request, self.composition = request, composition
        for local in ("unterminated", "\r\n", "\0\n"):
            self.request["scopes"][0]["local_additions"] = local
            with self.assertRaisesRegex(MaterializationError, "local_additions"):
                self.plan()

    def test_consistent_hashes_cannot_hide_wrong_rules_or_layers(self) -> None:
        valid = copy.deepcopy(self.composition)
        for mutation in ("content", "layers", "content_sha256", "path", "format", "source", "profiles"):
            with self.subTest(mutation=mutation):
                self.composition = copy.deepcopy(valid)
                file = self.composition["files"][0]
                if mutation == "content":
                    file["content"] += "!/.env\n"
                    file["content_sha256"] = sha256_bytes(file["content"].encode())
                elif mutation == "layers":
                    file["layers"].reverse()
                elif mutation == "content_sha256":
                    file["content_sha256"] = "0" * 64
                elif mutation == "path":
                    file["path"] = "../.gitignore"
                elif mutation == "source":
                    self.composition["source"]["catalog_sha256"] = "0" * 64
                elif mutation == "profiles":
                    self.composition["profiles"] = []
                else:
                    self.composition["format"] = "empathy.gitignore/v2"
                self.bind()
                with self.assertRaises(MaterializationError):
                    self.plan()

    def test_overlay_requires_resolved_profile(self) -> None:
        self.load_fixture("scoped-rust")
        self.request["profiles"] = self.composition["profiles"] = ["universal"]
        self.bind()
        with self.assertRaisesRegex(MaterializationError, "requires profile"):
            self.plan()

    def test_symlink_and_directory_targets_are_conflicts(self) -> None:
        path = self.target / ".gitignore"
        path.mkdir()
        self.assertEqual(self.plan()["summary"], {"conflict": 1})
        path.rmdir()
        for destination in (self.root / "missing", self.target / "README.md"):
            path.symlink_to(destination)
            self.assertEqual(self.plan()["summary"], {"conflict": 1})
            path.unlink()
        self.load_fixture("scoped-rust")
        (self.target / "crates").symlink_to(self.root, target_is_directory=True)
        self.assertEqual(self.plan()["summary"], {"create": 1, "conflict": 1})

    def test_target_root_symlink_and_non_directory_fail(self) -> None:
        self.target.rmdir()
        self.target.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(MaterializationError, "symlink"):
            self.plan()
        self.target.unlink()
        self.target.write_text("file")
        with self.assertRaisesRegex(MaterializationError, "directory"):
            self.plan()

    def test_preserve_is_explicit_and_never_adopts(self) -> None:
        self.composition["files"][0]["override"] = "preserve"
        self.bind()
        (self.target / ".gitignore").write_text("/custom/\n")
        before = snapshot(self.target)
        self.assertEqual(self.plan()["summary"], {"preserve": 1})
        self.adopt()
        self.assertEqual(self.plan()["summary"], {"conflict": 1})
        self.assertEqual(snapshot(self.target), before)

    def cli(self, command: str, *extra: str) -> subprocess.CompletedProcess:
        request = self.root / "request.json"
        composition = self.root / "composition.json"
        request.write_text(json.dumps(self.request))
        composition.write_text(json.dumps(self.composition))
        return subprocess.run([sys.executable, str(CLI), "gitignore", command,
                               "--request", str(request), "--composition", str(composition),
                               "--empathy-source", str(self.source), "--target", str(self.target),
                               *extra], text=True, capture_output=True)

    def test_cli_plan_check_and_conflict_exit_codes(self) -> None:
        output = self.root / "plan.json"
        result = self.cli("plan", "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        before = output.read_bytes()
        self.assertEqual(self.cli("plan", "--output", str(output)).returncode, 0)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(self.cli("check-plan", "--plan", str(output)).returncode, 0)
        self.install()
        self.assertEqual(self.cli("check-plan", "--plan", str(output)).returncode, 1)
        self.assertEqual(self.cli("plan", "--output", str(output)).returncode, 1)
        self.assertEqual(output.read_bytes(), before)
        conflicts = self.root / "conflicts.json"
        self.assertEqual(self.cli("plan", "--output", str(conflicts)).returncode, 1)
        self.assertEqual(json.loads(conflicts.read_text())["summary"], {"conflict": 1})

    def test_cli_rejects_unsafe_outputs_and_has_no_apply(self) -> None:
        for output in (self.target / "plan.json", self.source / "plan.json"):
            result = self.cli("plan", "--output", str(output))
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(output.exists())
        link = self.root / "output-link"
        link.symlink_to(self.target, target_is_directory=True)
        self.assertEqual(self.cli("plan", "--output", str(link / "plan.json")).returncode, 1)
        self.assertEqual(self.cli("apply").returncode, 2)


if __name__ == "__main__":
    unittest.main()
