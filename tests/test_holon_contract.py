"""Conformance tests for the Holon foundation contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from holon_contract import load_json, resolve_manifest, validate_catalog  # noqa: E402


class FoundationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_json(ROOT / "catalog" / "foundation.json")

    def example(self, name: str) -> dict[str, object]:
        return load_json(ROOT / "examples" / f"{name}.manifest.json")

    def test_catalog_is_valid(self) -> None:
        self.assertEqual(validate_catalog(self.catalog), [])

    def test_every_repository_class_has_a_resolvable_example(self) -> None:
        classes = set(self.catalog["repository_classes"])
        self.assertEqual(classes, {"library", "tool", "product", "publication"})
        for name in sorted(classes):
            with self.subTest(repository_class=name):
                resolved, errors = resolve_manifest(self.catalog, self.example(name))
                self.assertEqual(errors, [])
                self.assertIsNotNone(resolved)
                self.assertEqual(resolved["repository_class"], name)

    def test_resolution_is_deterministic_and_dependency_ordered(self) -> None:
        manifest = self.example("tool")
        first, first_errors = resolve_manifest(self.catalog, manifest)
        second, second_errors = resolve_manifest(self.catalog, manifest)
        self.assertEqual(first_errors, second_errors)
        self.assertEqual(
            json.dumps(first, sort_keys=True, separators=(",", ":")),
            json.dumps(second, sort_keys=True, separators=(",", ":")),
        )
        self.assertLess(
            first["capabilities"].index("relay-ci"),
            first["capabilities"].index("binary-release"),
        )

    def test_required_capability_cannot_be_excluded(self) -> None:
        manifest = self.example("tool")
        manifest["capabilities"]["exclude"] = ["relay-ci"]
        resolved, errors = resolve_manifest(self.catalog, manifest)
        self.assertIsNone(resolved)
        self.assertTrue(any("cannot be excluded" in error for error in errors))

    def test_security_floor_cannot_be_weakened(self) -> None:
        manifest = self.example("product")
        manifest["security_level"] = "baseline"
        resolved, errors = resolve_manifest(self.catalog, manifest)
        self.assertIsNone(resolved)
        self.assertTrue(any("weakens" in error for error in errors))

    def test_mutable_pin_is_rejected(self) -> None:
        manifest = self.example("library")
        manifest["pins"]["aether"] = "egohygiene/aether@main"
        resolved, errors = resolve_manifest(self.catalog, manifest)
        self.assertIsNone(resolved)
        self.assertTrue(any("pin aether" in error for error in errors))

    def test_missing_transitive_pin_is_rejected(self) -> None:
        manifest = self.example("tool")
        del manifest["pins"]["realm"]
        resolved, errors = resolve_manifest(self.catalog, manifest)
        self.assertIsNone(resolved)
        self.assertTrue(any("pin realm" in error for error in errors))

    def test_catalog_cycle_is_rejected(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["capabilities"]["community-health"]["requires"] = ["aether-agents"]
        catalog["capabilities"]["architecture-context"]["requires"] = ["community-health"]
        errors = validate_catalog(catalog)
        self.assertTrue(any("cycle" in error for error in errors))

    def test_conflicting_capabilities_are_rejected(self) -> None:
        manifest = self.example("product")
        manifest["capabilities"]["include"] = ["private-no-pages"]
        resolved, errors = resolve_manifest(self.catalog, manifest)
        self.assertIsNone(resolved)
        self.assertTrue(any("conflicts" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
