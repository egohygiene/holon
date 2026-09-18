"""Disposable Filament/scoped consumers exercising reviewed mutation and recovery."""

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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from materialization.common import MaterializationError, canonical_bytes, pretty_json_bytes, sha256_bytes
from materialization.gitignore import build_gitignore_plan
from materialization.gitignore_lifecycle import (
    apply_gitignore_plan, rollback_gitignore_target, verify_gitignore_target,
)
from materialization.gitignore_state import (
    FOREIGN_STATE_PATH, LOCK_PATH, STATE_PATH, file_image, seal_state, write_image,
)

FIXTURES = ROOT / "tests/fixtures/gitignore"
CLI = ROOT / "tools/holon_materialize.py"


def snapshot(root: Path) -> dict:
    return {path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mode)
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()}


class GitignoreLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / "consumer"
        self.target.mkdir()
        self.source = self.root / "empathy"
        shutil.copytree(FIXTURES / "empathy", self.source)
        self.fixture("filament")

    def fixture(self, name: str) -> None:
        self.request = json.loads((FIXTURES / name / "request.json").read_text())
        self.composition = json.loads((FIXTURES / name / "composition.json").read_text())

    def bind(self) -> None:
        self.request["composition_sha256"] = sha256_bytes(canonical_bytes(self.composition))

    def plan(self) -> dict:
        return build_gitignore_plan(self.request, self.composition, self.target, empathy_source=self.source)

    def apply(self, plan: dict | None = None) -> dict | None:
        plan = self.plan() if plan is None else plan
        return apply_gitignore_plan(plan, self.request, self.composition, self.target,
                                    empathy_source=self.source, reviewed_plan_id=plan["plan_id"])

    def rollback(self) -> None:
        rollback_gitignore_target(self.target, expected_state_sha256=self.verify()["state_sha256"])

    def verify(self) -> dict:
        return verify_gitignore_target(self.target)

    def local_update(self, text: str, index: int = 0) -> None:
        file = self.composition["files"][index]
        previous = self.request["scopes"][index]["local_additions"]
        file["content"] = file["content"].replace(
            "# Repository-owned local additions.\n" + previous + "\n# Universal baseline",
            "# Repository-owned local additions.\n" + text + "\n# Universal baseline", 1)
        self.request["scopes"][index]["local_additions"] = text
        next(layer for layer in file["layers"] if layer["kind"] == "local")["sha256"] = sha256_bytes(text.encode())
        file["content_sha256"] = sha256_bytes(file["content"].encode())
        self.bind()

    def cli(self, command: str, *extra: str) -> subprocess.CompletedProcess:
        arguments = [sys.executable, "-B", str(CLI), "gitignore", command, "--target", str(self.target)]
        if command not in {"verify", "rollback"}:
            request, composition = self.root / "request.json", self.root / "composition.json"
            request.write_text(json.dumps(self.request))
            composition.write_text(json.dumps(self.composition))
            arguments.extend(["--request", str(request), "--composition", str(composition),
                              "--empathy-source", str(self.source)])
        return subprocess.run([*arguments, *extra], text=True, capture_output=True)

    def test_public_cli_filament_create_noop_verify_and_rollback(self) -> None:
        (self.target / "README.md").write_bytes(b"authored prose\r\n")
        (self.target / ".git").mkdir()
        (self.target / ".git/config").write_bytes(b"[core]\n")
        untouched = snapshot(self.target)
        source_before = snapshot(self.source)
        output = self.root / "plan.json"
        result = self.cli("plan", "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(output.read_bytes())
        result = self.cli("apply", "--plan", str(output), "--reviewed-plan-id", plan["plan_id"])
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.target / STATE_PATH).read_bytes())
        self.assertEqual((self.target / ".gitignore").read_bytes(), self.composition["files"][0]["content"].encode())
        self.assertEqual(state["source"]["revision"], self.request["source_revision"])
        self.assertEqual(state["request"], self.request)
        self.assertEqual(state["files"][0]["layers"], self.composition["files"][0]["layers"])
        first = snapshot(self.target)
        noop_output = self.root / "noop.json"
        self.assertEqual(self.cli("plan", "--output", str(noop_output)).returncode, 0)
        noop = json.loads(noop_output.read_bytes())
        self.assertEqual(noop["summary"], {"noop": 1})
        self.assertEqual(self.cli("apply", "--plan", str(noop_output),
                                  "--reviewed-plan-id", noop["plan_id"]).returncode, 0)
        self.assertEqual(snapshot(self.target), first)
        self.assertEqual(self.cli("apply", "--plan", str(output),
                                  "--reviewed-plan-id", plan["plan_id"]).returncode, 1)
        result = self.cli("verify")
        self.assertEqual(result.returncode, 0, result.stderr)
        verified = json.loads(result.stdout)
        self.assertEqual(verified["tracked_files"], 1)
        result = self.cli("rollback", "--expected-state-sha256", verified["state_sha256"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.target / ".gitignore").exists())
        self.assertFalse((self.target / STATE_PATH).exists())
        self.assertTrue((self.target / state["rollback_manifest"]).is_file())
        for path, image in untouched.items():
            self.assertEqual(snapshot(self.target)[path], image)
        self.assertEqual(snapshot(self.source), source_before)

    def test_adoption_and_rollback_never_rewrite_existing_file(self) -> None:
        path = self.target / ".gitignore"
        path.write_bytes(self.composition["files"][0]["content"].encode())
        path.chmod(0o640)
        original = (file_image(self.target, ".gitignore"), path.stat())
        with self.assertRaisesRegex(MaterializationError, "conflicts"):
            self.apply()
        self.request["adopt"] = [{"path": ".gitignore", "before_sha256": original[0]["sha256"]}]
        output = self.root / "adoption-plan.json"
        result = self.cli("plan", "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli("apply", "--plan", str(output), "--reviewed-plan-id",
                          json.loads(output.read_bytes())["plan_id"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.plan()["summary"], {"noop": 1})
        self.apply()
        self.rollback()
        self.assertEqual(file_image(self.target, ".gitignore"), original[0])
        self.assertEqual((path.stat().st_ino, path.stat().st_mtime_ns),
                         (original[1].st_ino, original[1].st_mtime_ns))

    def test_mismatching_adoption_cannot_overwrite_authored_rules(self) -> None:
        path = self.target / ".gitignore"
        path.write_text("/authored-cache/\n")
        self.request["adopt"] = [{"path": ".gitignore", "before_sha256": sha256_bytes(path.read_bytes())}]
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "conflicts"):
            self.apply()
        self.assertEqual(snapshot(self.target), before)

    def test_explicit_local_updates_and_successive_rollbacks(self) -> None:
        self.apply()
        initial_file = file_image(self.target, ".gitignore")
        initial_state = (self.target / STATE_PATH).read_bytes()
        self.local_update("/first-cache/\n")
        self.assertEqual(self.plan()["summary"], {"update": 1})
        self.apply()
        middle_file = file_image(self.target, ".gitignore")
        middle_state = (self.target / STATE_PATH).read_bytes()
        self.local_update("/first-cache/\n/second-cache/\n")
        self.apply()
        self.rollback()
        self.assertEqual((self.target / STATE_PATH).read_bytes(), middle_state)
        self.assertEqual(file_image(self.target, ".gitignore"), middle_file)
        self.rollback()
        self.assertEqual((self.target / STATE_PATH).read_bytes(), initial_state)
        self.assertEqual(file_image(self.target, ".gitignore"), initial_file)
        self.rollback()
        self.assertFalse((self.target / ".gitignore").exists())

    def test_baseline_repin_preserves_local_exceptions_and_git_behavior(self) -> None:
        self.fixture("scoped-rust")
        self.apply()
        local = self.request["scopes"][1]["local_additions"]
        initial_state = (self.target / STATE_PATH).read_bytes()
        initial_files = [file_image(self.target, file["path"]) for file in self.composition["files"]]
        # A synthetic reviewed source-profile change, never a production pin or rule.
        profile = json.loads((ROOT / "catalog/gitignore-materialization.json").read_bytes())
        profile["revision"] = "a" * 40
        self.request["source_revision"] = profile["revision"]
        catalog_path = self.source / "foundation/catalog.json"
        catalog = json.loads(catalog_path.read_bytes())
        baseline = next(item for item in catalog["artifacts"] if item["id"] == "gitignore")["composition"]["baseline"]
        suffix = "\n# Synthetic upgrade fixture only.\n/fixture-cache/\n"
        source_path = self.source / baseline["path"]
        source_path.write_bytes(source_path.read_bytes() + suffix.encode())
        baseline["sha256"] = sha256_bytes(source_path.read_bytes())
        catalog_path.write_bytes(pretty_json_bytes(catalog))
        profile["catalog_sha256"] = sha256_bytes(canonical_bytes(catalog))
        self.composition["source"]["catalog_sha256"] = profile["catalog_sha256"]
        for file in self.composition["files"]:
            file["content"] += suffix
            file["content_sha256"] = sha256_bytes(file["content"].encode())
            file["layers"][-1]["sha256"] = baseline["sha256"]
        self.bind()
        profile_path = self.root / "synthetic-source-profile.json"
        profile_path.write_bytes(pretty_json_bytes(profile))
        with patch("materialization.gitignore.SOURCE_PROFILE", profile_path):
            self.assertEqual(self.plan()["summary"], {"update": 2})
            state = self.apply()
            self.assertEqual(state["files"][1]["selection"]["local_additions"], local)
            self.assertIn(local, (self.target / "crates/widget/.gitignore").read_text())
            self.verify()
            self.assertEqual(self.plan()["summary"], {"noop": 2})
            self.assert_git_behavior({"fixture-cache/output": True,
                                     "crates/widget/target/build.o": True,
                                     "crates/widget/target/keep.txt": False,
                                     "crates/widget/scratch/cache": True,
                                     "target/keep.txt": False, "crates/other/target/output": False,
                                     ".env": True, ".env.example": False, "Cargo.lock": False})
            self.rollback()
        self.assertEqual((self.target / STATE_PATH).read_bytes(), initial_state)
        self.assertEqual([file_image(self.target, file["path"]) for file in self.composition["files"]], initial_files)

    def assert_git_behavior(self, cases: dict[str, bool]) -> None:
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS="0")
        template = self.root / "empty-template"
        template.mkdir()
        subprocess.run(["git", "init", "--quiet", f"--template={template}", str(self.target)],
                       env=environment, check=True, capture_output=True)
        for path, ignored in cases.items():
            with self.subTest(path=path):
                destination = self.target / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text("fixture\n")
                result = subprocess.run(["git", "-c", f"core.excludesFile={os.devnull}",
                                         "-c", "core.ignoreCase=false", "check-ignore", "--quiet",
                                         "--no-index", "--", path], cwd=self.target, env=environment)
                self.assertEqual(result.returncode, 0 if ignored else 1)

    def test_wrong_review_id_and_rehashed_forgery_are_rejected(self) -> None:
        plan = self.plan()
        with self.assertRaisesRegex(MaterializationError, "reviewed plan ID"):
            apply_gitignore_plan(plan, self.request, self.composition, self.target,
                                 empathy_source=self.source, reviewed_plan_id="0" * 64)
        forged = copy.deepcopy(plan)
        forged["operations"][0]["proposed_content"] += "!/.env\n"
        forged["plan_id"] = sha256_bytes(canonical_bytes({key: value for key, value in forged.items() if key != "plan_id"}))
        with self.assertRaisesRegex(MaterializationError, "stale or changed"):
            self.apply(forged)
        plan["schema_version"] = "holon.gitignore-plan/v1"
        with self.assertRaisesRegex(MaterializationError, "regenerate a v2 plan"):
            self.apply(plan)
        self.assertEqual(snapshot(self.target), {})

    def test_input_and_target_drift_between_plan_and_apply_are_read_only(self) -> None:
        plan = self.plan()
        source = self.source / "foundation/ignore/universal.gitignore"
        original = source.read_bytes()
        source.write_bytes(original + b"/changed/\n")
        with self.assertRaisesRegex(MaterializationError, "digest mismatch"):
            self.apply(plan)
        source.write_bytes(original)
        (self.target / ".gitignore").write_text("/intervening-edit/\n")
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "stale or changed"):
            self.apply(plan)
        self.assertEqual(snapshot(self.target), before)

    def test_tracked_drift_is_never_overridden_by_adoption(self) -> None:
        self.apply()
        path = self.target / ".gitignore"
        original = file_image(self.target, ".gitignore")
        for mutation in ("content", "missing", "mode"):
            with self.subTest(mutation=mutation):
                write_image(self.target, ".gitignore", original)
                if mutation == "content":
                    path.write_bytes(path.read_bytes() + b"/manual/\n")
                elif mutation == "missing":
                    path.unlink()
                else:
                    path.chmod(0o600)
                self.request["adopt"] = [{"path": ".gitignore", "before_sha256": original["sha256"]}]
                before = snapshot(self.target)
                self.assertEqual(self.plan()["summary"], {"conflict": 1})
                with self.assertRaises(MaterializationError):
                    self.apply()
                with self.assertRaises(MaterializationError):
                    self.verify()
                with self.assertRaises(MaterializationError):
                    self.rollback()
                self.assertEqual(snapshot(self.target), before)

    def test_stale_state_digest_and_corrupt_recovery_prevent_rollback(self) -> None:
        state = self.apply()
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "stale"):
            rollback_gitignore_target(self.target, expected_state_sha256="0" * 64)
        self.assertEqual(snapshot(self.target), before)
        backup = self.target / state["rollback_manifest"]
        backup.write_bytes(backup.read_bytes() + b" ")
        before = snapshot(self.target)
        for action in (self.verify, self.plan, self.rollback):
            with self.assertRaisesRegex(MaterializationError, "missing or changed"):
                action()
        self.assertEqual(snapshot(self.target), before)

    def rewrite_recovery(self, change) -> None:
        state_path = self.target / STATE_PATH
        state = json.loads(state_path.read_bytes())
        backup = self.target / state["rollback_manifest"]
        recovery = json.loads(backup.read_bytes())
        change(recovery)
        backup.write_bytes(pretty_json_bytes(recovery))
        state["rollback_sha256"] = sha256_bytes(backup.read_bytes())
        state.pop("state_id")
        state_path.write_bytes(pretty_json_bytes(seal_state(state)))

    def test_rehashed_unsafe_recovery_path_cannot_touch_unrelated_files(self) -> None:
        self.apply()
        (self.target / "README.md").write_text("keep\n")
        self.rewrite_recovery(lambda recovery: recovery["operations"][0].update(path="README.md"))
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "exact .gitignore"):
            self.rollback()
        self.assertEqual(snapshot(self.target), before)

    def test_rehashed_wrong_preimage_does_not_restore_invented_bytes(self) -> None:
        self.apply()
        self.local_update("/updated/\n")
        self.apply()
        def change(recovery):
            image = recovery["operations"][0]["before"]
            image["content"] = "/invented/\n"
            image["sha256"] = sha256_bytes(image["content"].encode())
        self.rewrite_recovery(change)
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "preimage does not match"):
            self.rollback()
        self.assertEqual(snapshot(self.target), before)

    def test_previous_recovery_must_exist_before_restoring_previous_state(self) -> None:
        state = self.apply()
        self.local_update("/updated/\n")
        self.apply()
        (self.target / state["rollback_manifest"]).unlink()
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "missing or changed"):
            self.rollback()
        self.assertEqual(snapshot(self.target), before)

    def test_malformed_or_rehashed_state_cannot_change_the_path_boundary(self) -> None:
        self.apply()
        path = self.target / STATE_PATH
        original = path.read_bytes()
        mutations = {
            "checksum": lambda state: state.update(repository="changed/repository"),
            "path": lambda state: state["files"][0].update(path="../.gitignore"),
            "selection": lambda state: state["request"]["scopes"][0].update(root=123),
            "layers": lambda state: state["files"][0]["layers"][0].update(sha256="0" * 64),
            "recovery": lambda state: state.update(rollback_manifest=".git/config"),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                state = json.loads(original)
                mutate(state)
                if name != "checksum":
                    state.pop("state_id")
                    state = seal_state(state)
                path.write_bytes(pretty_json_bytes(state))
                before = snapshot(self.target)
                with self.assertRaises(MaterializationError):
                    self.verify()
                with self.assertRaises(MaterializationError):
                    self.apply()
                self.assertEqual(snapshot(self.target), before)

    def test_state_reformatting_invalidates_a_reviewed_plan(self) -> None:
        self.apply()
        self.local_update("/updated/\n")
        plan = self.plan()
        path = self.target / STATE_PATH
        path.write_text(json.dumps(json.loads(path.read_bytes())))
        self.verify()
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "stale"):
            self.apply(plan)
        self.assertEqual(snapshot(self.target), before)

    def test_case_only_scope_rename_is_not_an_implicit_move(self) -> None:
        self.fixture("scoped-rust")
        self.apply()
        self.request["scopes"][1]["root"] = "crates/Widget"
        self.composition["files"][1]["path"] = "crates/Widget/.gitignore"
        self.bind()
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "case-only"):
            self.apply()
        self.assertEqual(snapshot(self.target), before)

    def test_release_retains_files_and_rollback_checks_released_postimage(self) -> None:
        self.fixture("scoped-rust")
        self.apply()
        initial = (self.target / STATE_PATH).read_bytes()
        scoped = self.target / "crates/widget/.gitignore"
        original = scoped.read_bytes()
        self.request["scopes"].pop()
        self.composition["files"].pop()
        self.bind()
        self.assertEqual(self.plan()["summary"], {"noop": 1, "release": 1})
        self.apply()
        self.assertEqual(self.verify()["tracked_files"], 1)
        self.assertEqual(scoped.read_bytes(), original)
        scoped.write_bytes(original + b"/new-owner/\n")
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "file changed"):
            self.rollback()
        self.assertEqual(snapshot(self.target), before)
        scoped.write_bytes(original)
        self.rollback()
        self.assertEqual((self.target / STATE_PATH).read_bytes(), initial)

    def test_preserve_only_and_release_do_not_infer_readoption(self) -> None:
        self.composition["files"][0]["override"] = "preserve"
        self.bind()
        self.assertIsNone(self.apply())
        self.assertEqual(list(self.target.iterdir()), [])
        self.composition["files"][0]["override"] = None
        self.bind()
        self.apply()
        self.composition["files"][0]["override"] = "preserve"
        self.bind()
        self.request["adopt"] = [{"path": ".gitignore", "before_sha256": self.composition["files"][0]["content_sha256"]}]
        self.assertEqual(self.plan()["summary"], {"conflict": 1})
        self.request["adopt"] = []
        self.assertEqual(self.plan()["summary"], {"release": 1})
        self.apply()
        self.assertEqual(self.verify()["tracked_files"], 0)
        self.composition["files"][0]["override"] = None
        self.bind()
        self.assertEqual(self.plan()["summary"], {"conflict": 1})

    def test_reapply_after_rollback_retains_immutable_attempts(self) -> None:
        first = self.apply()
        first_raw = (self.target / first["rollback_manifest"]).read_bytes()
        self.rollback()
        second = self.apply()
        self.assertEqual(first["plan_id"], second["plan_id"])
        self.assertNotEqual(first["rollback_manifest"], second["rollback_manifest"])
        self.assertEqual((self.target / first["rollback_manifest"]).read_bytes(), first_raw)

    def foreign(self, paths: list[str]) -> None:
        path = self.target / FOREIGN_STATE_PATH
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(pretty_json_bytes({"schema_version": "holon.materialization-state/v1",
                                           "managed_files": [{"path": item} for item in paths]}))

    def test_generic_ownership_conflict_and_state_drift_fail_closed(self) -> None:
        plan = self.plan()
        self.foreign(["README.md"])
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "stale"):
            self.apply(plan)
        self.assertEqual(snapshot(self.target), before)
        self.apply()
        self.foreign([".GITIGNORE"])
        before = snapshot(self.target)
        self.assertEqual(self.plan()["summary"], {"conflict": 1})
        with self.assertRaisesRegex(MaterializationError, "overlap"):
            self.rollback()
        self.assertEqual(snapshot(self.target), before)

    def test_unsafe_internal_paths_fail_without_following_links(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "keep").write_text("keep\n")
        (self.target / ".holon").symlink_to(outside, target_is_directory=True)
        before = snapshot(outside)
        with self.assertRaisesRegex(MaterializationError, "symlink"):
            self.apply()
        self.assertEqual(snapshot(outside), before)
        (self.target / ".holon").unlink()
        state = self.apply()
        backup = self.target / state["rollback_manifest"]
        saved = backup.read_bytes()
        backup.unlink()
        (outside / "rollback").write_bytes(saved)
        backup.symlink_to(outside / "rollback")
        before = snapshot(outside)
        with self.assertRaisesRegex(MaterializationError, "symlink"):
            self.rollback()
        self.assertEqual(snapshot(outside), before)

    def test_target_replaced_by_symlink_after_planning_is_rejected(self) -> None:
        plan = self.plan()
        outside = self.root / "outside-file"
        outside.write_text("keep\n")
        (self.target / ".gitignore").symlink_to(outside)
        with self.assertRaises(MaterializationError):
            self.apply(plan)
        self.assertEqual(outside.read_text(), "keep\n")
        self.assertFalse((self.target / ".holon").exists())

    def test_initial_foreign_ownership_is_a_conflict_even_for_missing_file(self) -> None:
        self.foreign([".gitignore"])
        self.assertEqual(self.plan()["summary"], {"conflict": 1})
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "conflicts"):
            self.apply()
        self.assertEqual(snapshot(self.target), before)

    def test_busy_lock_blocks_apply_and_rollback_without_removal(self) -> None:
        plan = self.plan()
        lock = self.target / LOCK_PATH
        lock.mkdir(parents=True)
        with self.assertRaisesRegex(MaterializationError, "operation is active"):
            self.apply(plan)
        self.assertTrue(lock.is_dir())
        self.assertFalse((self.target / ".gitignore").exists())
        lock.rmdir()
        self.apply()
        lock.mkdir()
        before = snapshot(self.target)
        with self.assertRaisesRegex(MaterializationError, "operation is active"):
            self.rollback()
        self.assertTrue(lock.is_dir())
        self.assertEqual(snapshot(self.target), before)

    def test_mid_apply_failure_restores_preimages(self) -> None:
        self.fixture("scoped-rust")
        def fail_second(target, path, image):
            if path == "crates/widget/.gitignore" and image is not None:
                raise OSError("injected write failure")
            write_image(target, path, image)
        with patch("materialization.gitignore_lifecycle.write_image", side_effect=fail_second):
            with self.assertRaisesRegex(MaterializationError, "preimages restored"):
                self.apply()
        self.assertFalse((self.target / ".gitignore").exists())
        self.assertFalse((self.target / "crates/widget/.gitignore").exists())
        self.assertFalse((self.target / STATE_PATH).exists())
        self.assertFalse((self.target / LOCK_PATH).exists())

    def test_mid_rollback_failure_restores_postimages_and_state(self) -> None:
        self.fixture("scoped-rust")
        self.apply()
        before = snapshot(self.target)
        def fail_second(target, path, image):
            if path == ".gitignore" and image is None:
                raise OSError("injected delete failure")
            write_image(target, path, image)
        with patch("materialization.gitignore_lifecycle.write_image", side_effect=fail_second):
            with self.assertRaisesRegex(MaterializationError, "preimages restored"):
                self.rollback()
        self.assertEqual(snapshot(self.target), before)
        self.verify()

    def test_intervening_edit_survives_failed_write_restoration(self) -> None:
        self.fixture("scoped-rust")
        def edit_during_failure(target, path, image):
            if path == "crates/widget/.gitignore":
                (target / ".gitignore").write_text("/concurrent-local-edit/\n")
                raise OSError("injected competing writer")
            write_image(target, path, image)
        with patch("materialization.gitignore_lifecycle.write_image", side_effect=edit_during_failure):
            with self.assertRaisesRegex(MaterializationError, "recovery incomplete"):
                self.apply()
        self.assertEqual((self.target / ".gitignore").read_text(), "/concurrent-local-edit/\n")
        self.assertFalse((self.target / STATE_PATH).exists())
        self.assertTrue(list((self.target / ".holon/gitignore-backups").rglob("rollback.v1.json")))

    def test_rollback_removes_only_empty_created_scope_directories(self) -> None:
        self.fixture("scoped-rust")
        self.apply()
        (self.target / "crates/widget/README.md").write_text("new work\n")
        self.rollback()
        self.assertEqual((self.target / "crates/widget/README.md").read_text(), "new work\n")
        self.assertFalse((self.target / "crates/widget/.gitignore").exists())
        (self.target / "crates/widget/README.md").unlink()
        (self.target / "crates/widget").rmdir()
        (self.target / "crates").rmdir()
        self.apply()
        self.rollback()
        self.assertFalse((self.target / "crates").exists())


if __name__ == "__main__":
    unittest.main()
