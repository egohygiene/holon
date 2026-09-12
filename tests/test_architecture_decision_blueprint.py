"""Contract and migration-safety tests for ADR scaffolding."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from architecture_decision_blueprint import (  # noqa: E402
    BlueprintError,
    POLICY_PIN,
    build_pack,
    decision_records,
    load_strict_json,
    render_pack,
    validate_blueprint,
)
from holon_contract import load_json, resolve_manifest  # noqa: E402
from materialization import MaterializationError, build_plan, render_plan, verify_target  # noqa: E402


def write_adr(path: Path, identifier: str, title: str, status: str, recorded: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "schema: egohygiene.architecture-decision/v1",
                f"id: {identifier}",
                f"title: {title}",
                f"status: {status}",
                f"date: {recorded}",
                "---",
                "",
                f"# {identifier}: {title}",
                "",
            ]
        ),
        encoding="utf-8",
    )


class ArchitectureDecisionBlueprintTests(unittest.TestCase):
    """Keep ADR initialization deterministic and existing decisions human-owned."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_json(ROOT / "catalog/foundation.json")
        cls.manifest = load_json(ROOT / "examples/library.manifest.json")
        cls.resolved, errors = resolve_manifest(cls.catalog, cls.manifest)
        if errors:
            raise AssertionError(errors)

    def test_canonical_blueprint_contract_is_valid(self) -> None:
        self.assertEqual(validate_blueprint(ROOT), [])
        profile = load_strict_json(ROOT / "blueprints/architecture-decisions/blueprint.json")
        self.assertEqual(profile["policy"]["source"]["revision"], POLICY_PIN.rsplit("@", 1)[1])
        self.assertEqual(
            profile["ownership"]["repository"],
            ["docs/decisions/ADR-NNN-short-slug.md"],
        )

    def test_empty_repository_renders_standard_scaffold(self) -> None:
        with tempfile.TemporaryDirectory(prefix="holon-adr-empty-") as temporary:
            root = Path(temporary)
            target = root / "consumer"
            target.mkdir()
            pack = root / "pack"
            desired = render_pack(
                ROOT,
                ROOT / "examples/library.manifest.json",
                target,
                pack,
            )
            self.assertEqual(
                set(desired),
                {
                    "docs/decisions/ADR-TEMPLATE.md",
                    "docs/decisions/README.md",
                    "docs/decisions/policy-reference.json",
                },
            )
            reference = json.loads(
                (pack / "docs/decisions/policy-reference.json").read_text(encoding="utf-8")
            )
            self.assertEqual(reference["repository"], "egohygiene/example-library")
            self.assertEqual(reference["policy"]["source"]["revision"], POLICY_PIN.rsplit("@", 1)[1])
            self.assertEqual(reference["extensions"], [])
            self.assertEqual(reference["exceptions"], [])
            index = (pack / "docs/decisions/README.md").read_text(encoding="utf-8")
            self.assertIn("No architecture decisions have been recorded yet.", index)

    def test_index_is_numeric_deterministic_and_preserves_legacy_width(self) -> None:
        with tempfile.TemporaryDirectory(prefix="holon-adr-index-") as temporary:
            target = Path(temporary) / "consumer"
            target.mkdir()
            write_adr(
                target / "docs/decisions/ADR-010-later.md",
                "ADR-010",
                "Later decision",
                "accepted",
                "2026-09-02",
            )
            write_adr(
                target / "docs/decisions/ADR-002-first.md",
                "ADR-002",
                "First | decision",
                "rejected",
                "2026-08-20",
            )
            write_adr(
                target / "docs/decisions/ADR-0001-legacy.md",
                "ADR-0001",
                "Legacy decision",
                "superseded",
                "2026-08-18",
            )
            write_adr(
                target / "docs/decisions/OFD-005-established-prefix.md",
                "OFD-005",
                "Established prefix",
                "proposed",
                "2026-08-25",
            )
            records = decision_records(target)
            self.assertEqual(
                [record["id"] for record in records],
                ["ADR-0001", "ADR-002", "OFD-005", "ADR-010"],
            )
            first = build_pack(ROOT, self.resolved, target)
            second = build_pack(ROOT, self.resolved, target)
            self.assertEqual(first, second)
            index = first["docs/decisions/README.md"].decode("utf-8")
            self.assertLess(index.index("ADR-0001"), index.index("ADR-002"))
            self.assertLess(index.index("ADR-002"), index.index("OFD-005"))
            self.assertLess(index.index("OFD-005"), index.index("ADR-010"))
            self.assertIn("First \\| decision", index)

    def test_existing_adrs_are_indexed_but_never_materialized_or_modified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="holon-adr-adopt-") as temporary:
            root = Path(temporary)
            target = root / "consumer"
            target.mkdir()
            adr = target / "docs/decisions/ADR-003-existing.md"
            write_adr(adr, "ADR-003", "Existing decision", "proposed", "2026-09-01")
            before = adr.read_bytes()
            pack = root / "pack"
            render_pack(ROOT, ROOT / "examples/library.manifest.json", target, pack)
            resolved = copy.deepcopy(self.resolved)
            resolved["capabilities"] = ["architecture-decisions"]
            plan, _ = build_plan(resolved, target, render_source=pack)
            paths = {operation["path"] for operation in plan["operations"]}
            self.assertNotIn("docs/decisions/ADR-003-existing.md", paths)
            render_plan(plan, target, render_source=pack)
            self.assertEqual(verify_target(target), [])
            self.assertEqual(adr.read_bytes(), before)
            self.assertIn(
                "[ADR-003](ADR-003-existing.md)",
                (target / "docs/decisions/README.md").read_text(encoding="utf-8"),
            )

    def test_existing_generated_path_conflicts_without_any_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="holon-adr-conflict-") as temporary:
            root = Path(temporary)
            target = root / "consumer"
            target.mkdir()
            existing = target / "docs/decisions/policy-reference.json"
            existing.parent.mkdir(parents=True)
            existing.write_text('{"local":"authored"}\n', encoding="utf-8")
            before = existing.read_bytes()
            pack = root / "pack"
            render_pack(ROOT, ROOT / "examples/library.manifest.json", target, pack)
            resolved = copy.deepcopy(self.resolved)
            resolved["capabilities"] = ["architecture-decisions"]
            plan, _ = build_plan(resolved, target, render_source=pack)
            self.assertEqual(plan["summary"]["conflict"], 1)
            with self.assertRaises(MaterializationError):
                render_plan(plan, target, render_source=pack)
            self.assertEqual(existing.read_bytes(), before)
            self.assertFalse((target / ".holon").exists())

    def test_local_extensions_and_exceptions_cannot_change_policy_source(self) -> None:
        resolved = copy.deepcopy(self.resolved)
        resolved["parameters"] = {
            "adr_extensions": [
                {
                    "id": "egohygiene.example.decision-impact/v1",
                    "kind": "metadata",
                    "schema": "schemas/example-decision-impact.v1.schema.json",
                    "required": False,
                }
            ],
            "adr_exceptions": [
                {
                    "rule": "legacy filename width",
                    "reason": "Historic IDs remain stable during migration.",
                    "status": "proposed",
                    "owner": "egohygiene/example-library",
                    "approval_evidence": None,
                    "expires": None,
                }
            ],
        }
        with tempfile.TemporaryDirectory(prefix="holon-adr-extension-") as temporary:
            target = Path(temporary)
            pack = build_pack(ROOT, resolved, target)
        reference = json.loads(pack["docs/decisions/policy-reference.json"])
        self.assertEqual(reference["extensions"], resolved["parameters"]["adr_extensions"])
        self.assertEqual(reference["exceptions"], resolved["parameters"]["adr_exceptions"])
        self.assertEqual(reference["policy"]["source"]["repository"], "egohygiene/hygiene")

        invalid = copy.deepcopy(resolved)
        invalid["parameters"]["adr_extensions"][0]["contract"] = "local-policy-override"
        with tempfile.TemporaryDirectory(prefix="holon-adr-invalid-") as temporary:
            with self.assertRaisesRegex(BlueprintError, "only id, kind, schema, and required"):
                build_pack(ROOT, invalid, Path(temporary))

    def test_manifest_requires_the_immutable_policy_pin(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        del manifest["pins"]["adr_policy"]
        resolved, errors = resolve_manifest(self.catalog, manifest)
        self.assertIsNone(resolved)
        self.assertTrue(any("pin adr_policy" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
