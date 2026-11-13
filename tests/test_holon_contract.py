"""Conformance tests for the Holon foundation contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from holon_contract import load_json, resolve_manifest, validate_catalog  # noqa: E402
from foundation_manifest_grammar import validate_manifest  # noqa: E402


def grammar_cases(valid: dict[str, object]):
    """Source-independent malformed inputs shared by CLI and schema checks."""
    yield "valid", copy.deepcopy(valid), True
    for value in (None, [], "not-an-object", True):
        yield f"root-{value!r}", value, False
    for field in valid:
        value = copy.deepcopy(valid)
        del value[field]
        yield f"missing-{field}", value, False
    for field, required in (("pins", ("architecture", "foundation")),
                            ("capabilities", ("include", "exclude"))):
        for key in required:
            value = copy.deepcopy(valid)
            del value[field][key]
            yield f"missing-{field}-{key}", value, False
    for label, path, replacement in (
        ("unknown-field", (), {**valid, "extra": True}),
        ("identity-type", ("repository",), 17),
        ("identity-syntax", ("repository",), "owner/repository/extra"),
        ("identity-newline", ("repository",), "owner/repository\n"),
        ("class-type", ("repository_class",), []),
        ("empty-class", ("repository_class",), ""),
        ("security-type", ("security_level",), []),
        ("pins-type", ("pins",), []),
        ("extra-pin-type", ("pins", "other"), False),
        ("empty-pin", ("pins", "foundation"), ""),
        ("capabilities-type", ("capabilities",), []),
        ("capabilities-extra", ("capabilities", "extra"), []),
        ("include-type", ("capabilities", "include"), "relay-ci"),
        ("include-item", ("capabilities", "include"), [{}]),
        ("exclude-duplicates", ("capabilities", "exclude"), ["relay-ci", "relay-ci"]),
        ("sites-type", ("sites",), "docs"),
        ("sites-item", ("sites",), [None]),
        ("sites-duplicates", ("sites",), ["docs", "docs"]),
        ("preserve-type", ("preserve_paths",), "README.md"),
        ("preserve-item", ("preserve_paths",), [1]),
        ("parameters-type", ("parameters",), []),
    ):
        value = copy.deepcopy(valid)
        if not path:
            value = replacement
        else:
            parent = value
            for component in path[:-1]:
                parent = parent[component]
            parent[path[-1]] = replacement
        yield label, value, False
    for path in (
        "", ".", "..", "../README.md", "docs/../README.md", "docs/./README.md",
        "/README.md", "docs//README.md", "docs///", "docs\\README.md",
        "C:/README.md", ".git", ".git/config", ".holon", ".holon/state.json",
        " README.md", "README.md ", "docs/\x00name", "docs/\nname",
    ):
        value = copy.deepcopy(valid)
        value["preserve_paths"] = [path]
        yield f"unsafe-preserve-{path!r}", value, False
    for path in ("README.md", "apps/", ".github/workflows", "docs/My file.md", "données/✓.md"):
        value = copy.deepcopy(valid)
        value["preserve_paths"] = [path]
        yield f"literal-preserve-{path}", value, True


class FoundationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_json(ROOT / "catalog" / "foundation.json")

    def example(self, name: str) -> dict[str, object]:
        return load_json(ROOT / "examples" / f"{name}.manifest.json")

    def test_catalog_is_valid(self) -> None:
        self.assertEqual(validate_catalog(self.catalog), [])

    def test_complete_manifest_grammar_precedes_semantic_resolution(self) -> None:
        for label, manifest, valid in grammar_cases(self.example("tool")):
            with self.subTest(case=label):
                errors = validate_manifest(manifest)
                self.assertEqual(not errors, valid)
                if not valid:
                    resolved, resolution_errors = resolve_manifest(self.catalog, manifest)
                    self.assertIsNone(resolved)
                    self.assertEqual(resolution_errors, errors)

    @unittest.skipUnless(Draft202012Validator, "optional independent JSON Schema qualification")
    def test_manifest_grammar_matches_draft202012_schema(self) -> None:
        schema = load_json(ROOT / "schemas/foundation-manifest.v1.schema.json")
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        for label, manifest, valid in grammar_cases(self.example("tool")):
            with self.subTest(case=label):
                self.assertEqual(validator.is_valid(manifest), valid)
                self.assertEqual(not validate_manifest(manifest), valid)

    @unittest.skipUnless(Draft202012Validator, "optional independent CLI/schema qualification")
    def test_public_cli_matches_schema_without_mutating_consumer_or_invalid_output(self) -> None:
        validator = Draft202012Validator(load_json(ROOT / "schemas/foundation-manifest.v1.schema.json"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            output = root / "resolved.json"
            target = root / "consumer"
            target.mkdir()
            sentinel = target / "README.md"
            sentinel.write_bytes(b"repository-owned\r\n")
            for label, manifest, _ in grammar_cases(self.example("tool")):
                with self.subTest(case=label):
                    valid = validator.is_valid(manifest)
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                    output.write_bytes(b"existing output\n")
                    results = []
                    for arguments in (
                        ["validate", "--manifest", str(manifest_path)],
                        ["resolve", "--manifest", str(manifest_path), "--output", str(output)],
                    ):
                        result = subprocess.run(
                            [sys.executable, str(ROOT / "tools/holon_contract.py"), *arguments],
                            cwd=ROOT, capture_output=True, text=True, check=False,
                        )
                        self.assertEqual(result.returncode == 0, valid, result.stderr)
                        results.append(result)
                    if not valid:
                        self.assertTrue(results[0].stderr)
                        self.assertEqual(results[0].returncode, results[1].returncode)
                        self.assertEqual(results[0].stderr, results[1].stderr)
                        self.assertEqual(output.read_bytes(), b"existing output\n")
                    self.assertEqual(sentinel.read_bytes(), b"repository-owned\r\n")
                    self.assertEqual(sorted(path.name for path in target.iterdir()), ["README.md"])

    def test_all_committed_manifests_keep_the_public_grammar(self) -> None:
        for path in sorted((ROOT / "examples").glob("*.manifest.json")):
            with self.subTest(path=path.name):
                manifest = load_json(path)
                self.assertEqual(validate_manifest(manifest), [])
                resolved, errors = resolve_manifest(self.catalog, manifest)
                self.assertEqual(errors, [])
                self.assertIsNotNone(resolved)

    def test_unknown_schema_keyword_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schema.json"
            schema = load_json(ROOT / "schemas/foundation-manifest.v1.schema.json")
            schema["not"] = {}
            path.write_text(json.dumps(schema), encoding="utf-8")
            with patch("foundation_manifest_grammar.SCHEMA_PATH", path):
                self.assertEqual(validate_manifest(self.example("tool")), [
                    "foundation-manifest schema is unavailable or unsupported"
                ])

    def test_malformed_safety_fields_leave_cli_output_and_target_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            manifest = self.example("tool")
            del manifest["repository"]
            manifest["preserve_paths"] = "README.md"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "resolved.json"
            output.write_bytes(b"existing output\n")
            target = root / "consumer"
            target.mkdir()
            readme = target / "README.md"
            readme.write_bytes(b"repository-owned\r\n")
            for arguments in (
                ["validate", "--manifest", str(manifest_path)],
                ["resolve", "--manifest", str(manifest_path), "--output", str(output)],
            ):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools/holon_contract.py"), *arguments],
                    cwd=ROOT, capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("manifest.repository is required", result.stderr)
                self.assertIn("manifest.preserve_paths must be an array", result.stderr)
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools/holon_materialize.py"), "plan",
                 "--manifest", str(manifest_path), "--target", str(target),
                 "--output", str(root / "plan.json")],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "plan.json").exists())
            self.assertEqual(output.read_bytes(), b"existing output\n")
            self.assertEqual(readme.read_bytes(), b"repository-owned\r\n")
            self.assertEqual(sorted(path.name for path in target.iterdir()), ["README.md"])

    def test_every_repository_class_has_a_resolvable_example(self) -> None:
        classes = set(self.catalog["repository_classes"])
        self.assertEqual(classes, {"library", "tool", "product", "publication"})
        for name in sorted(classes):
            with self.subTest(repository_class=name):
                resolved, errors = resolve_manifest(self.catalog, self.example(name))
                self.assertEqual(errors, [])
                self.assertIsNotNone(resolved)
                self.assertEqual(resolved["repository_class"], name)
                self.assertIn("architecture-decisions", resolved["capabilities"])
                self.assertEqual(
                    resolved["pins"]["adr_policy"],
                    "egohygiene/hygiene@a05b14f8b9e2772124f879f818e09a911e996ad8",
                )

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

    def test_unknown_capability_is_a_diagnostic_before_graph_traversal(self) -> None:
        manifest = self.example("tool")
        manifest["capabilities"]["include"] = ["does-not-exist"]
        resolved, errors = resolve_manifest(self.catalog, manifest)
        self.assertIsNone(resolved)
        self.assertTrue(any("unknown capabilities" in error for error in errors))

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

    def test_missing_architecture_decision_policy_pin_is_rejected(self) -> None:
        manifest = self.example("library")
        del manifest["pins"]["adr_policy"]
        resolved, errors = resolve_manifest(self.catalog, manifest)
        self.assertIsNone(resolved)
        self.assertTrue(any("pin adr_policy" in error for error in errors))

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
