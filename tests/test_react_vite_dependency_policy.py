"""Tests for the React/Vite dependency-policy contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from react_vite_dependency_policy import load_policy, validate_policy  # noqa: E402

POLICY_PATH = ROOT / "catalog" / "react-vite-dependencies.json"
SCHEMA_PATH = ROOT / "schemas" / "react-vite-dependency-policy.v1.schema.json"


class ReactViteDependencyPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy(POLICY_PATH)
        cls.candidates = {
            candidate["id"]: candidate for candidate in cls.policy["candidates"]
        }

    def test_policy_is_valid(self) -> None:
        self.assertEqual(validate_policy(self.policy), [])

    def test_schema_identity_is_versioned(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["$id"],
            "https://egohygiene.io/schemas/holon/"
            "react-vite-dependency-policy.v1.schema.json",
        )
        self.assertEqual(
            self.policy["schema"],
            "egohygiene.holon.react-vite-dependency-policy/v1",
        )

    def test_candidate_set_is_explicit(self) -> None:
        self.assertEqual(
            set(self.candidates),
            {"chalk", "source-map-support", "visibilityjs"},
        )

    def test_candidate_packages_are_not_dead_baseline_weight(self) -> None:
        baseline = self.policy["baseline"]
        dependencies = set(
            baseline["browser_runtime_dependencies"]
            + baseline["node_runtime_dependencies"]
            + baseline["node_development_dependencies"]
        )
        self.assertTrue(
            dependencies.isdisjoint(
                {candidate["package"] for candidate in self.candidates.values()}
            )
        )

    def test_each_candidate_records_complete_decision_evidence(self) -> None:
        required_strings = {
            "current_version",
            "license",
            "module_format",
            "maintenance",
            "runtime_footprint",
            "testability",
            "outcome",
            "adoption_guard",
            "replacement_or_removal",
        }
        for candidate_id, candidate in self.candidates.items():
            with self.subTest(candidate=candidate_id):
                for key in required_strings:
                    self.assertIsInstance(candidate[key], str)
                    self.assertTrue(candidate[key].strip())
                self.assertIsInstance(candidate["security_notes"], list)
                self.assertTrue(candidate["native_alternatives"])
                self.assertTrue(candidate["evidence"])

    def test_chalk_is_node_only_and_capability_gated(self) -> None:
        chalk = self.candidates["chalk"]
        self.assertEqual(chalk["decision"], "optional")
        self.assertEqual(chalk["environment"], "node-cli")
        self.assertEqual(chalk["current_version"], "6.0.0")
        self.assertEqual(chalk["runtime_dependencies"], 0)
        self.assertEqual(chalk["compatibility"]["node"], ">=22")
        self.assertFalse(chalk["compatibility"]["browser_runtime"])
        self.assertIn(
            "node-cli-rich-output",
            self.policy["baseline"]["optional_capabilities"],
        )

    def test_source_map_support_prefers_modern_node(self) -> None:
        candidate = self.candidates["source-map-support"]
        self.assertEqual(candidate["decision"], "reject")
        alternatives = " ".join(candidate["native_alternatives"])
        self.assertIn("--enable-source-maps", alternatives)
        self.assertIn("module.setSourceMapsSupport()", alternatives)

    def test_visibilityjs_prefers_the_web_platform(self) -> None:
        candidate = self.candidates["visibilityjs"]
        self.assertEqual(candidate["decision"], "reject")
        alternatives = " ".join(candidate["native_alternatives"])
        self.assertIn("document.visibilityState", alternatives)
        self.assertIn("visibilitychange", alternatives)

    def test_supply_chain_policy_requires_reviewed_exact_versions(self) -> None:
        supply_chain = self.policy["supply_chain"]
        self.assertEqual(supply_chain["version_policy"], "exact-reviewed-version")
        self.assertEqual(supply_chain["lockfile_policy"], "frozen")
        self.assertTrue(supply_chain["transitive_dependency_review"])
        self.assertTrue(supply_chain["revalidate_on_major_upgrade"])

    def test_rejected_dependency_cannot_enter_the_baseline(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["baseline"]["node_runtime_dependencies"].append("source-map-support")
        errors = validate_policy(policy)
        self.assertTrue(
            any("source-map-support is reject" in error for error in errors),
            errors,
        )

    def test_optional_dependency_cannot_become_implicit_baseline_weight(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["baseline"]["node_development_dependencies"].append("chalk")
        errors = validate_policy(policy)
        self.assertTrue(any("chalk is optional" in error for error in errors), errors)

    def test_missing_decision_evidence_fails_validation(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["candidates"][0]["maintenance"] = ""
        errors = validate_policy(policy)
        self.assertTrue(
            any("maintenance must be a non-empty string" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
