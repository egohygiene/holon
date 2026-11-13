"""Disposable-fixture and golden-consumer tests for Holon materialization."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from materialization import (  # noqa: E402
    MaterializationError,
    STATE_RELATIVE_PATH,
    build_plan,
    render_plan,
    rollback_target,
    verify_target,
)
from materialization.common import atomic_write, validate_path_components, validate_target_root  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class MaterializationTests(unittest.TestCase):
    def assert_contract(self, name: str, value: object) -> None:
        schema = json.loads((ROOT / f"schemas/materialization-{name}.v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="holon-materialize-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "consumer"
        self.target.mkdir()
        self.source = self.root / "source"
        shutil.copytree(
            ROOT / "tests" / "fixtures" / "materialization" / "golden-source",
            self.source,
        )
        self.aether = self.root / "aether-dist"
        self._write_aether_fixture()
        self.resolved = {
            "schema_version": "1.0.0",
            "repository": "egohygiene/example-tool",
            "repository_class": "tool",
            "security_level": "hardened",
            "pins": {
                "architecture": "egohygiene/hygiene@architecture-v0.1.0",
                "foundation": "egohygiene/holon@foundation-v0.1.0",
                "aether": "egohygiene/aether@v0.1.0",
                "realm": "ghcr.io/egohygiene/realm@sha256:" + "0" * 64,
            },
            "capabilities": [
                "architecture-context",
                "aether-agents",
                "relay-ci",
            ],
            "sites": ["docs"],
            "preserve_paths": ["README.md", "LICENSE"],
            "parameters": {
                "language": "rust",
                "aether_providers": ["github-copilot"],
            },
            "ownership": {
                "generator": "egohygiene/holon",
                "preserve_paths": ["LICENSE", "README.md"],
            },
        }

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_aether_fixture(self, *, tag: str = "v0.1.0") -> None:
        agent = b"---\nname: Architect\n---\n\n# Architect\n"
        agent_path = (
            self.aether
            / "github"
            / "repository"
            / ".github"
            / "agents"
            / "architect.agent.md"
        )
        agent_path.parent.mkdir(parents=True, exist_ok=True)
        agent_path.write_bytes(agent)
        digest = sha(agent)
        write_json(
            self.aether / "projections" / "manifest.v1.json",
            {
                "schema_version": "aether.projection-manifest/v1",
                "interface_version": "1.0.0",
                "providers": [
                    {
                        "id": "github-copilot",
                        "status": "native",
                        "adapter": "github-agent-markdown",
                        "shares_output_with": None,
                        "unsupported_features": [],
                    },
                    {
                        "id": "zencoder",
                        "status": "manual-import",
                        "adapter": "manual-import-json",
                        "shares_output_with": None,
                        "unsupported_features": ["native-file"],
                    },
                ],
                "outputs": [
                    {
                        "path": "dist/github/repository/.github/agents/architect.agent.md",
                        "sha256": digest,
                    }
                ],
            },
        )
        write_json(
            self.aether / "release" / "release-manifest.v1.json",
            {"repository_release_tag": tag, "artifacts": []},
        )
        write_json(
            self.aether / "release" / "release-provenance.v1.json",
            {
                "repository_release_tag": tag,
                "commit_sha": "0123456789abcdef0123456789abcdef01234567",
                "output_files": [
                    {
                        "path": "github/repository/.github/agents/architect.agent.md",
                        "sha256": digest,
                    }
                ],
            },
        )

    def plan(self):
        return build_plan(
            self.resolved,
            self.target,
            render_source=self.source,
            aether_source=self.aether,
        )

    def render(self, plan):
        return render_plan(
            plan,
            self.target,
            render_source=self.source,
            aether_source=self.aether,
        )

    def snapshot(self) -> dict[str, tuple[str, object]]:
        """Capture disposable consumer and sibling sentinels without following links."""
        result = {}
        for path in sorted(self.root.rglob("*")):
            relative = path.relative_to(self.root).as_posix()
            if path.is_symlink():
                result[relative] = ("link", os.readlink(path))
            elif path.is_file():
                result[relative] = ("file", path.read_bytes())
            elif path.is_dir():
                result[relative] = ("directory", None)
            else:
                result[relative] = ("special", None)
        return result

    def assert_rejected_without_changes(self, operation) -> None:
        before = self.snapshot()
        with self.assertRaises(MaterializationError):
            operation()
        self.assertEqual(self.snapshot(), before)

    def updated_render(self):
        first, _ = self.plan()
        self.render(first)
        (self.source / "NOTICE.generated.md").write_text("updated={{repository}}\n", encoding="utf-8")
        (self.source / "ZZ.new.txt").write_text("new generated file\n", encoding="utf-8")
        second, _ = self.plan()
        state = self.render(second)
        return state, self.target / state["rollback_manifest"]

    def test_plan_rejects_generated_alias_to_git_unowned_or_preserved_files(self) -> None:
        git = self.target / ".git"
        git.mkdir()
        destinations = [git / "missing-sentinel", self.target / "unowned.txt", self.target / "README.md"]
        destinations[1].write_text("unowned sentinel\n", encoding="utf-8")
        destinations[2].write_text("preserved sentinel\n", encoding="utf-8")
        alias = self.target / "NOTICE.generated.md"
        for destination in destinations:
            with self.subTest(destination=destination.name):
                alias.symlink_to(destination)
                self.assert_rejected_without_changes(self.plan)
                alias.unlink()

    def test_plan_rejects_symlink_and_non_directory_ancestors(self) -> None:
        source_directory = self.source / "generated"
        source_directory.mkdir()
        (source_directory / "nested.txt").write_text("generated\n", encoding="utf-8")
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "nested.txt").write_text("outside sentinel\n", encoding="utf-8")
        destination = self.target / "generated"
        for parent in (outside, self.target / "missing-directory"):
            with self.subTest(parent=parent.name):
                destination.symlink_to(parent, target_is_directory=True)
                self.assert_rejected_without_changes(self.plan)
                destination.unlink()
        destination.write_text("non-directory sentinel\n", encoding="utf-8")
        self.assert_rejected_without_changes(self.plan)

    def test_nested_git_namespace_cannot_become_managed_content(self) -> None:
        protected = self.source / "nested/.git"
        protected.mkdir(parents=True)
        (protected / "config").write_text("nested Git sentinel\n", encoding="utf-8")
        self.assert_rejected_without_changes(self.plan)

    def test_dangling_state_or_internal_directory_alias_is_rejected(self) -> None:
        internal = self.target / ".holon"
        internal.symlink_to(self.root / "outside-missing", target_is_directory=True)
        self.assert_rejected_without_changes(self.plan)
        internal.unlink()
        internal.mkdir()
        state = self.target / STATE_RELATIVE_PATH
        state.symlink_to(self.root / "missing-state.json")
        self.assert_rejected_without_changes(self.plan)
        self.assert_rejected_without_changes(lambda: verify_target(self.target))
        self.assert_rejected_without_changes(lambda: rollback_target(self.target))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO checks require a POSIX filesystem")
    def test_special_state_file_is_rejected_without_reading(self) -> None:
        (self.target / ".holon").mkdir()
        os.mkfifo(self.target / STATE_RELATIVE_PATH)
        self.assert_rejected_without_changes(self.plan)

    def test_render_rejects_backup_alias_inserted_after_planning(self) -> None:
        plan, _ = self.plan()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("outside sentinel\n", encoding="utf-8")
        (self.target / ".holon").mkdir()
        (self.target / ".holon/backups").symlink_to(outside, target_is_directory=True)
        self.assert_rejected_without_changes(lambda: self.render(plan))

    def test_render_rejects_dangling_attempt_alias_before_allocating_backup(self) -> None:
        plan, _ = self.plan()
        parent = self.target / ".holon/backups" / plan["plan_id"]
        parent.mkdir(parents=True)
        (parent / "attempt-001").symlink_to(self.root / "missing-attempt", target_is_directory=True)
        self.assert_rejected_without_changes(lambda: self.render(plan))

    def test_verify_and_rollback_reject_generated_aliases(self) -> None:
        plan, _ = self.plan()
        self.render(plan)
        generated = self.target / "NOTICE.generated.md"
        outside = self.root / "same-content.txt"
        outside.write_bytes(generated.read_bytes())
        generated.unlink()
        generated.symlink_to(outside)
        self.assert_rejected_without_changes(lambda: verify_target(self.target))
        self.assert_rejected_without_changes(lambda: rollback_target(self.target))

    def test_rollback_checks_all_preimages_before_removing_created_files(self) -> None:
        state, rollback_path = self.updated_render()
        backup = rollback_path.parent / "files/NOTICE.generated.md"
        outside = self.root / "outside-preimage"
        outside.write_bytes(backup.read_bytes())
        backup.unlink()
        backup.symlink_to(outside)
        self.assertTrue((self.target / "ZZ.new.txt").is_file())
        self.assert_rejected_without_changes(lambda: rollback_target(self.target))
        self.assert_rejected_without_changes(lambda: verify_target(self.target))
        self.assertEqual(json.loads((self.target / STATE_RELATIVE_PATH).read_text())["plan_id"], state["plan_id"])

    def test_rollback_checks_prior_state_before_any_file_mutation(self) -> None:
        _state, rollback_path = self.updated_render()
        before = rollback_path.parent / "state-before.json"
        outside = self.root / "outside-state.json"
        outside.write_bytes(before.read_bytes())
        before.unlink()
        before.symlink_to(outside)
        self.assert_rejected_without_changes(lambda: rollback_target(self.target))

    def test_recovery_metadata_cannot_select_external_or_unowned_paths(self) -> None:
        _state, rollback_path = self.updated_render()
        rollback = json.loads(rollback_path.read_text())
        original = copy.deepcopy(rollback)
        operation = next(item for item in rollback["operations"] if item["path"] == "NOTICE.generated.md")
        operation["backup_path"] = "../../../../../outside-preimage"
        write_json(rollback_path, rollback)
        self.assert_rejected_without_changes(lambda: rollback_target(self.target))
        rollback = original
        unowned = self.target / "README.md"
        unowned.write_text("preserved owner content\n", encoding="utf-8")
        rollback["operations"].append({"action": "create", "path": "README.md",
            "expected_after_sha256": sha(unowned.read_bytes()), "previous_sha256": None, "backup_path": None})
        write_json(rollback_path, rollback)
        self.assert_rejected_without_changes(lambda: rollback_target(self.target))

    def test_explicit_directory_root_alias_retains_normal_lifecycle(self) -> None:
        alias = self.root / "consumer-alias"
        alias.symlink_to(self.target, target_is_directory=True)
        arguments = {"render_source": self.source, "aether_source": self.aether}
        plan, _ = build_plan(self.resolved, alias, **arguments)
        self.assertEqual(plan, self.plan()[0])
        render_plan(plan, alias, **arguments)
        self.assertEqual(verify_target(alias), [])
        self.assertEqual(build_plan(self.resolved, alias, **arguments)[0]["summary"], {"noop": 3})
        rollback_target(alias)
        self.assertFalse((self.target / STATE_RELATIVE_PATH).exists())

    def test_missing_ordinary_target_is_created_only_during_render(self) -> None:
        target = self.root / "not-created-yet"
        arguments = {"render_source": self.source, "aether_source": self.aether}
        plan, _ = build_plan(self.resolved, target, **arguments)
        self.assertFalse(target.exists())
        render_plan(plan, target, **arguments)
        self.assertEqual(verify_target(target), [])
        rollback_target(target)

    def test_dangling_root_alias_and_git_internal_root_are_not_consumers(self) -> None:
        target = self.root / "dangling-root"
        target.symlink_to(self.root / "missing-root", target_is_directory=True)
        arguments = {"render_source": self.source, "aether_source": self.aether}
        self.assert_rejected_without_changes(lambda: build_plan(self.resolved, target, **arguments))
        git = self.target / ".git"
        git.mkdir()
        self.assert_rejected_without_changes(lambda: build_plan(self.resolved, git, **arguments))
        git.rmdir()
        metadata = self.root / "metadata-store"
        metadata.mkdir()
        (metadata / "config").write_text("Git metadata sentinel\n", encoding="utf-8")
        git.symlink_to(metadata, target_is_directory=True)
        self.assert_rejected_without_changes(lambda: build_plan(self.resolved, git, **arguments))

    def test_windows_without_junction_aware_runtime_denies_before_path_use(self) -> None:
        before = self.snapshot()
        # This models the unsupported runtime boundary only. It neither creates
        # Windows junctions nor supplies Windows/native qualification evidence.
        with patch("materialization.common.os.name", "nt"), patch("materialization.common.Path", object):
            for operation in (validate_target_root, validate_path_components):
                with self.assertRaisesRegex(MaterializationError, "Windows.*Python 3.12"):
                    operation(self.target)
        self.assertEqual(self.snapshot(), before)

    def test_plan_is_deterministic_and_sorted(self) -> None:
        first, _ = self.plan()
        second, _ = self.plan()
        self.assertEqual(first, second)
        self.assertEqual(
            [operation["path"] for operation in first["operations"]],
            sorted(operation["path"] for operation in first["operations"]),
        )
        self.assertEqual(first["summary"]["create"], 3)

    def test_render_verify_and_idempotent_replan(self) -> None:
        plan, _ = self.plan()
        state = self.render(plan)
        self.assertEqual(verify_target(self.target), [])
        self.assertEqual(len(state["managed_files"]), 3)
        self.assertEqual(
            (self.target / "NOTICE.generated.md").read_text(encoding="utf-8"),
            "repository=egohygiene/example-tool\nname=example-tool\nclass=tool\n",
        )
        self.assertTrue((self.target / ".github/agents/architect.agent.md").is_file())
        next_plan, _ = self.plan()
        self.assertEqual(next_plan["summary"], {"noop": 3})

    def test_render_overlay_replaces_base_without_copying_the_pack(self) -> None:
        overlay = self.root / "overlay"
        overlay.mkdir()
        (overlay / "NOTICE.generated.md").write_text(
            "overlay={{parameter.overlay_content}}\n"
            "title={{parameter_json.overlay_title}}\n",
            encoding="utf-8",
        )
        resolved = copy.deepcopy(self.resolved)
        resolved["parameters"]["overlay_content"] = {"enabled": True, "items": [1, 2]}
        resolved["parameters"]["overlay_title"] = 'Quoted "title"'
        plan, _ = build_plan(
            resolved,
            self.target,
            render_source=self.source,
            render_overlays=[overlay],
            aether_source=self.aether,
        )
        state = render_plan(
            plan,
            self.target,
            render_source=self.source,
            render_overlays=[overlay],
            aether_source=self.aether,
        )
        self.assertEqual(
            (self.target / "NOTICE.generated.md").read_text(encoding="utf-8"),
            'overlay={"enabled":true,"items":[1,2]}\n'
            'title="Quoted \\"title\\""\n',
        )
        notice = next(item for item in state["managed_files"] if item["path"] == "NOTICE.generated.md")
        self.assertEqual(notice["source"], "render-overlay:0:NOTICE.generated.md")

    def test_emitted_zero_one_and_ordered_overlay_plans_state_and_recovery_match_schemas(self) -> None:
        overlays = []
        for index in range(2):
            overlay = self.root / f"overlay-{index}"
            overlay.mkdir()
            (overlay / "NOTICE.generated.md").write_text(f"overlay={index}\n", encoding="utf-8")
            overlays.append(overlay)
        plans = []
        for selected in ([], overlays[:1], overlays, list(reversed(overlays))):
            plan, _ = build_plan(self.resolved, self.target, render_source=self.source,
                                 render_overlays=selected, aether_source=self.aether)
            self.assert_contract("plan", plan)
            self.assertEqual(len(plan["inputs"]["render_overlays"]), len(selected))
            plans.append(plan)
        self.assertEqual(len({plan["plan_id"] for plan in plans}), 4)
        self.assertEqual(plans[2]["inputs"]["render_overlays"], list(reversed(plans[3]["inputs"]["render_overlays"])))
        before = plans[2]["plan_id"]
        (overlays[1] / "NOTICE.generated.md").write_text("changed overlay\n", encoding="utf-8")
        changed, _ = build_plan(self.resolved, self.target, render_source=self.source,
                                render_overlays=overlays, aether_source=self.aether)
        self.assertNotEqual(changed["plan_id"], before)
        self.assert_contract("plan", changed)
        state = render_plan(changed, self.target, render_source=self.source,
                            render_overlays=overlays, aether_source=self.aether)
        self.assert_contract("state", state)
        self.assertEqual(state["inputs"], changed["inputs"])
        recovery = json.loads((self.target / state["rollback_manifest"]).read_text())
        self.assert_contract("rollback", recovery)
        rollback_target(self.target)

    def test_overlay_schema_accepts_legacy_omission_but_rejects_invalid_descriptors(self) -> None:
        plan, _ = self.plan()
        legacy = copy.deepcopy(plan)
        del legacy["inputs"]["render_overlays"]
        self.assert_contract("plan", legacy)
        for malformed in (None, {}, ["digest"], [{"tree_sha256": "bad"}],
                          [{"tree_sha256": "0" * 64, "path": "ambient-source"}]):
            with self.subTest(malformed=malformed):
                candidate = copy.deepcopy(plan)
                candidate["inputs"]["render_overlays"] = malformed
                with self.assertRaises(ValidationError):
                    self.assert_contract("plan", candidate)

    def test_plan_cli_rejects_unknown_parameter_tokens_without_writing(self) -> None:
        plan_path = self.root / "plan.json"
        source_file = self.source / "NOTICE.generated.md"
        for token in ("{{parameter_json.missing}}", "{{parameter.missing}}"):
            with self.subTest(token=token):
                source_file.write_text(f"value={token}\n", encoding="utf-8")
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "tools" / "holon_materialize.py"),
                        "plan",
                        "--manifest",
                        str(ROOT / "examples" / "tool.manifest.json"),
                        "--target",
                        str(self.target),
                        "--render-source",
                        str(self.source),
                        "--aether-source",
                        str(self.aether),
                        "--output",
                        str(plan_path),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(
                    f"{source_file.name} contains unresolved Holon template tokens: {token}",
                    result.stderr,
                )
                self.assertFalse(plan_path.exists())
                self.assertEqual(list(self.target.iterdir()), [])

    def test_render_preserves_json_values_other_template_syntax_and_binary(self) -> None:
        values = {
            "scalar": 42,
            "object": {"enabled": True},
            "array": [1, None],
            "string": 'Quoted "text"\nnext line',
        }
        self.resolved["parameters"].update(values)
        (self.source / "parameters.json").write_text(
            "{\n"
            '  "scalar": {{parameter_json.scalar}},\n'
            '  "object": {{parameter_json.object}},\n'
            '  "array": {{parameter_json.array}},\n'
            '  "string": {{parameter_json.string}},\n'
            '  "literal": "{{another_engine.name}}"\n'
            "}\n",
            encoding="utf-8",
        )
        binary = b"\xff{{parameter_json.missing}}\r\n"
        (self.source / "asset.bin").write_bytes(binary)

        plan, _ = self.plan()
        self.render(plan)

        self.assertEqual(
            json.loads((self.target / "parameters.json").read_text(encoding="utf-8")),
            {**values, "literal": "{{another_engine.name}}"},
        )
        self.assertEqual((self.target / "asset.bin").read_bytes(), binary)

    def test_preserve_path_never_overwrites_user_content(self) -> None:
        (self.source / "README.md").write_text("generated\n", encoding="utf-8")
        (self.target / "README.md").write_text("user-owned\n", encoding="utf-8")
        plan, _ = self.plan()
        operation = next(
            item for item in plan["operations"] if item["path"] == "README.md"
        )
        self.assertEqual(operation["action"], "preserve")
        self.render(plan)
        self.assertEqual((self.target / "README.md").read_text(), "user-owned\n")

    def test_unowned_existing_file_is_a_conflict(self) -> None:
        (self.target / "NOTICE.generated.md").write_text(
            "user-owned\n", encoding="utf-8"
        )
        plan, _ = self.plan()
        operation = next(
            item
            for item in plan["operations"]
            if item["path"] == "NOTICE.generated.md"
        )
        self.assertEqual(operation["action"], "conflict")
        with self.assertRaises(MaterializationError):
            self.render(plan)

    def test_user_modified_owned_file_blocks_update(self) -> None:
        plan, _ = self.plan()
        self.render(plan)
        (self.target / "NOTICE.generated.md").write_text(
            "manual edit\n", encoding="utf-8"
        )
        (self.source / "NOTICE.generated.md").write_text(
            "changed={{repository}}\n", encoding="utf-8"
        )
        next_plan, _ = self.plan()
        operation = next(
            item
            for item in next_plan["operations"]
            if item["path"] == "NOTICE.generated.md"
        )
        self.assertEqual(operation["action"], "conflict")

    def test_rollback_restores_previous_generated_version(self) -> None:
        first, _ = self.plan()
        first_state = self.render(first)
        first_content = (self.target / "NOTICE.generated.md").read_bytes()
        (self.source / "NOTICE.generated.md").write_text(
            "v2={{repository}}\n", encoding="utf-8"
        )
        second, _ = self.plan()
        self.assertEqual(
            next(
                item
                for item in second["operations"]
                if item["path"] == "NOTICE.generated.md"
            )["action"],
            "update",
        )
        second_state = self.render(second)
        self.assertNotEqual(second_state["plan_id"], first_state["plan_id"])
        rollback_target(self.target)
        self.assertEqual(
            (self.target / "NOTICE.generated.md").read_bytes(), first_content
        )
        restored = json.loads((self.target / STATE_RELATIVE_PATH).read_text())
        self.assertEqual(restored["plan_id"], first_state["plan_id"])

    def test_rollback_of_first_render_removes_created_files(self) -> None:
        plan, _ = self.plan()
        self.render(plan)
        rollback_target(self.target)
        self.assertFalse((self.target / "NOTICE.generated.md").exists())
        self.assertFalse((self.target / ".github/agents/architect.agent.md").exists())
        self.assertFalse((self.target / STATE_RELATIVE_PATH).exists())
        repeated, _ = self.plan()
        self.assertEqual(repeated["plan_id"], plan["plan_id"])
        self.render(repeated)
        self.assertEqual(verify_target(self.target), [])

    def test_late_rollback_file_failure_restores_current_pair_then_allows_retry(self) -> None:
        first, _ = self.plan()
        self.render(first)
        (self.source / "NOTICE.generated.md").write_bytes(b"version two\n")
        (self.source / "extra.generated").write_bytes(b"new file\n")
        second, _ = self.plan()
        self.render(second)
        (self.target / "extra.generated").chmod(0o751)
        before = self.snapshot()
        calls = 0
        def fail_once(path: Path, content: bytes) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected later restoration failure")
            atomic_write(path, content)
        with patch("materialization.engine.atomic_write", side_effect=fail_once):
            with self.assertRaisesRegex(MaterializationError, "current rendered files and state were restored"):
                rollback_target(self.target)
        self.assertGreater(calls, 2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((self.target / "extra.generated").stat().st_mode & 0o777, 0o751)
        self.assertEqual(verify_target(self.target), [])
        rollback_target(self.target)
        self.assertFalse((self.target / "extra.generated").exists())
        self.assertEqual(verify_target(self.target), [])

    def test_prior_state_write_failure_restores_current_pair(self) -> None:
        first, _ = self.plan()
        self.render(first)
        (self.source / "NOTICE.generated.md").write_bytes(b"next version\n")
        second, _ = self.plan()
        self.render(second)
        before = self.snapshot()
        failed = False
        def fail_state_once(path: Path, content: bytes) -> None:
            nonlocal failed
            if path == self.target / STATE_RELATIVE_PATH and not failed:
                failed = True
                raise OSError("injected prior-state write failure")
            atomic_write(path, content)
        with patch("materialization.engine.atomic_write", side_effect=fail_state_once):
            with self.assertRaisesRegex(MaterializationError, "current rendered files and state were restored"):
                rollback_target(self.target)
        self.assertTrue(failed)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(verify_target(self.target), [])
        rollback_target(self.target)
        self.assertEqual(verify_target(self.target), [])

    def test_persistent_rollback_storage_failure_reports_incomplete_and_keeps_evidence(self) -> None:
        first, _ = self.plan()
        self.render(first)
        (self.source / "NOTICE.generated.md").write_bytes(b"next version\n")
        second, _ = self.plan()
        self.render(second)
        state_before = (self.target / STATE_RELATIVE_PATH).read_bytes()
        backups = {p.relative_to(self.target).as_posix(): p.read_bytes()
                   for p in (self.target / ".holon/backups").rglob("*") if p.is_file()}
        with patch("materialization.engine.atomic_write", side_effect=OSError("persistent storage failure")):
            with self.assertRaisesRegex(MaterializationError, "compensation is incomplete"):
                rollback_target(self.target)
        self.assertEqual((self.target / STATE_RELATIVE_PATH).read_bytes(), state_before)
        self.assertEqual({p.relative_to(self.target).as_posix(): p.read_bytes()
                          for p in (self.target / ".holon/backups").rglob("*") if p.is_file()}, backups)

    def test_rollback_refuses_to_destroy_post_render_edit(self) -> None:
        plan, _ = self.plan()
        self.render(plan)
        (self.target / "NOTICE.generated.md").write_text(
            "post render user edit\n", encoding="utf-8"
        )
        with self.assertRaises(MaterializationError):
            rollback_target(self.target)

    def test_aether_release_pin_mismatch_is_rejected(self) -> None:
        self._write_aether_fixture(tag="v0.2.0")
        with self.assertRaisesRegex(MaterializationError, "does not satisfy pin"):
            self.plan()

    def test_aether_projection_digest_mismatch_is_rejected(self) -> None:
        agent = self.aether / "github/repository/.github/agents/architect.agent.md"
        agent.write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(MaterializationError, "digest mismatch"):
            self.plan()

    def test_manual_import_provider_is_not_treated_as_native(self) -> None:
        resolved = copy.deepcopy(self.resolved)
        resolved["parameters"]["aether_providers"] = ["zencoder"]
        with self.assertRaisesRegex(MaterializationError, "manual-import"):
            build_plan(
                resolved,
                self.target,
                render_source=self.source,
                aether_source=self.aether,
            )


if __name__ == "__main__":
    unittest.main()
