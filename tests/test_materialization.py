"""Disposable-fixture and golden-consumer tests for Holon materialization."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

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


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class MaterializationTests(unittest.TestCase):
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
            "overlay={{parameter.overlay_content}}\n", encoding="utf-8"
        )
        resolved = copy.deepcopy(self.resolved)
        resolved["parameters"]["overlay_content"] = {"enabled": True, "items": [1, 2]}
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
            'overlay={"enabled":true,"items":[1,2]}\n',
        )
        notice = next(item for item in state["managed_files"] if item["path"] == "NOTICE.generated.md")
        self.assertEqual(notice["source"], "render-overlay:0:NOTICE.generated.md")

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
