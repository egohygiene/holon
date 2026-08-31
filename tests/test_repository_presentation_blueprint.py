"""Tests for the non-destructive repository-presentation blueprint."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from repository_presentation_blueprint import (  # noqa: E402
    BLUEPRINT_PATH,
    FIXTURES_PATH,
    apply_plan,
    build_plan,
    digest_text,
    load_json,
    render_region,
    rollback,
    validate_fixture_contract,
    validate_fixtures,
    validate_source,
)


class RepositoryPresentationBlueprintTests(unittest.TestCase):
    """Protect exact plans, authored prose, profile coverage, and rollback."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.blueprint = load_json(BLUEPRINT_PATH)
        cls.fixture_document = load_json(FIXTURES_PATH)
        cls.mantle = next(
            fixture for fixture in cls.fixture_document["fixtures"] if fixture["name"] == "mantle"
        )

    def test_all_profiles_and_mantle_pass_local_and_egolint_contracts(self) -> None:
        self.assertEqual(validate_fixtures(self.blueprint, self.fixture_document), [])
        profile_names = {
            fixture["source"]["profile"]
            for fixture in self.fixture_document["fixtures"]
            if fixture["name"] != "mantle"
        }
        self.assertEqual(profile_names, set(self.blueprint["profiles"]))
        for fixture in self.fixture_document["fixtures"]:
            region = render_region(fixture["source"], self.blueprint)
            self.assertEqual(
                validate_fixture_contract(fixture["source"], region, self.blueprint),
                [],
                fixture["name"],
            )

    def test_initialization_is_exact_and_preserves_authored_readme(self) -> None:
        source = self.mantle["source"]
        authored = self.mantle["readme"]
        plan = build_plan(source, authored, None, self.blueprint)
        self.assertEqual(plan["action"], "initialize")
        self.assertTrue(plan["proposedReadme"].endswith(authored))
        self.assertIn("--- a/README.md", plan["diff"])
        self.assertIn("+++ b/README.md", plan["diff"])
        self.assertEqual(plan, build_plan(source, authored, None, self.blueprint))

    def test_upgrade_replaces_only_a_verified_managed_region(self) -> None:
        source = self.mantle["source"]
        authored = self.mantle["readme"]
        initial = build_plan(source, authored, None, self.blueprint)
        state = initial["nextState"]
        upgraded_source = copy.deepcopy(source)
        upgraded_source["slots"]["purpose"] = "Mantle now projects a revised repository-owned purpose."
        upgrade = build_plan(upgraded_source, initial["proposedReadme"], state, self.blueprint)
        self.assertEqual(upgrade["action"], "upgrade")
        self.assertTrue(upgrade["proposedReadme"].endswith(authored))
        self.assertIn(upgraded_source["slots"]["purpose"], upgrade["proposedReadme"])

    def test_manual_managed_region_edit_fails_closed(self) -> None:
        source = self.mantle["source"]
        initial = build_plan(source, self.mantle["readme"], None, self.blueprint)
        edited = initial["proposedReadme"].replace(
            source["slots"]["purpose"],
            "An untracked manual edit inside the generated region.",
        )
        conflict = build_plan(source, edited, initial["nextState"], self.blueprint)
        self.assertEqual(conflict["action"], "conflict")
        self.assertEqual(conflict["proposedReadme"], edited)
        self.assertTrue(
            any(item["code"] == "HOLON-PRESENT-CONFLICT-004" for item in conflict["diagnostics"])
        )

    def test_missing_required_facts_are_visible_blockers(self) -> None:
        source = copy.deepcopy(self.mantle["source"])
        del source["banner"]
        del source["slots"]["purpose"]
        diagnostics = validate_source(source, self.blueprint)
        self.assertTrue(any("TODO(blocker)" in item["message"] for item in diagnostics))
        plan = build_plan(source, self.mantle["readme"], None, self.blueprint)
        self.assertEqual(plan["action"], "blocked")
        self.assertIn("TODO(blocker): add a repository-authored purpose", plan["proposedReadme"])

    def test_documented_opt_out_never_mutates_readme(self) -> None:
        source = copy.deepcopy(self.mantle["source"])
        source["optOut"] = {
            "enabled": True,
            "reason": "Repository maintainers retain a reviewed bespoke presentation.",
        }
        plan = build_plan(source, self.mantle["readme"], None, self.blueprint)
        self.assertEqual(plan["action"], "opt-out")
        self.assertEqual(plan["diff"], "")
        self.assertEqual(plan["proposedReadme"], self.mantle["readme"])

    def test_apply_rechecks_inputs_and_rollback_is_checksum_bound(self) -> None:
        source = self.mantle["source"]
        with tempfile.TemporaryDirectory(prefix="holon-presentation-") as temporary:
            root = Path(temporary)
            readme_path = root / "README.md"
            state_path = root / ".holon/repository-presentation.state.json"
            readme_path.write_text(self.mantle["readme"], encoding="utf-8")
            plan = build_plan(source, self.mantle["readme"], None, self.blueprint)
            apply_plan(plan, source, readme_path, state_path)
            self.assertEqual(
                digest_text(readme_path.read_text(encoding="utf-8")),
                plan["proposedReadmeDigest"],
            )
            self.assertTrue(state_path.exists())
            previous = rollback(readme_path, state_path)
            self.assertEqual(previous, self.mantle["readme"])
            self.assertEqual(readme_path.read_text(encoding="utf-8"), self.mantle["readme"])
            self.assertFalse(state_path.exists())

    def test_tampered_preview_is_rejected(self) -> None:
        source = self.mantle["source"]
        with tempfile.TemporaryDirectory(prefix="holon-presentation-tamper-") as temporary:
            root = Path(temporary)
            readme_path = root / "README.md"
            state_path = root / "state.json"
            readme_path.write_text(self.mantle["readme"], encoding="utf-8")
            plan = build_plan(source, self.mantle["readme"], None, self.blueprint)
            plan["proposedReadme"] += "tampered"
            with self.assertRaisesRegex(ValueError, "checksum"):
                apply_plan(plan, source, readme_path, state_path)


if __name__ == "__main__":
    unittest.main()
