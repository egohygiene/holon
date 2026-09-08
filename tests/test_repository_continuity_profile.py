"""Tests for the pinned repository-continuity materialization profile."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from repository_continuity_profile import (  # noqa: E402
    MANAGED_BEGIN,
    MANAGED_END,
    ProfileError,
    load_json,
    validate_profile,
    verify_sources,
)

PROFILE_PATH = ROOT / "catalog" / "repository-continuity-materialization.json"
SCHEMA_PATH = ROOT / "schemas" / "repository-continuity-materialization-profile.v1.schema.json"


class RepositoryContinuityProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_json(PROFILE_PATH)

    def test_canonical_profile_is_valid(self) -> None:
        self.assertEqual(validate_profile(self.profile), [])

    def test_schema_identity_is_versioned_and_closed(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["$id"],
            "https://egohygiene.io/schemas/holon/"
            "repository-continuity-materialization-profile.v1.schema.json",
        )
        self.assertFalse(schema["additionalProperties"])

    def test_source_roles_are_exact_and_revisions_are_immutable(self) -> None:
        sources = {source["role"]: source for source in self.profile["sources"]}
        self.assertEqual(
            set(sources),
            {"portable-contract", "organization-policy", "validator"},
        )
        for source in sources.values():
            self.assertRegex(source["revision"], r"^[0-9a-f]{40}$")
            self.assertFalse(source["release_included"])

    def test_destinations_and_markers_are_exact(self) -> None:
        surfaces = {surface["path"]: surface for surface in self.profile["surfaces"]}
        self.assertEqual(
            set(surfaces),
            {
                "CONTINUITY.md",
                "AGENTS.md",
                ".github/copilot-instructions.md",
                "CLAUDE.md",
            },
        )
        self.assertTrue(surfaces["CONTINUITY.md"]["required"])
        self.assertTrue(surfaces["AGENTS.md"]["required"])
        for path in ("AGENTS.md", ".github/copilot-instructions.md", "CLAUDE.md"):
            self.assertEqual(surfaces[path]["begin_marker"], MANAGED_BEGIN)
            self.assertEqual(surfaces[path]["end_marker"], MANAGED_END)

    def test_all_five_proof_profiles_are_declared(self) -> None:
        self.assertEqual(
            {profile["id"] for profile in self.profile["repository_profiles"]},
            {
                "research-publication",
                "library-cli",
                "site-application",
                "organization-meta",
                "private-creative",
            },
        )

    def test_unknown_fields_fail_closed(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["unexpected"] = True
        errors = validate_profile(profile)
        self.assertIn("profile has unknown fields: unexpected", errors)

    def test_mutable_or_short_revision_is_rejected(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["sources"][0]["revision"] = "main"
        errors = validate_profile(profile)
        self.assertTrue(any("full lowercase commit SHA" in error for error in errors), errors)

    def test_pinned_url_must_match_revision_and_path(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["sources"][0]["artifacts"][0]["url"] = (
            "https://github.com/egohygiene/aether/blob/main/schema.json"
        )
        errors = validate_profile(profile)
        self.assertTrue(any("url must pin" in error for error in errors), errors)

    def test_source_inventory_cannot_silently_drop_an_input(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["sources"][0]["artifacts"].pop()
        errors = validate_profile(profile)
        self.assertTrue(any("exact approved portable-contract inputs" in error for error in errors), errors)

    def test_surface_cannot_select_an_unapproved_source_artifact(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["surfaces"][1]["source_artifact"] = "continuity-template"
        errors = validate_profile(profile)
        self.assertIn("surface AGENTS.md does not match its approved contract", errors)

    def test_unreleased_inputs_cannot_advance_beyond_observe(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["rollout"]["stage"] = "enforce"
        profile["status"] = "active"
        errors = validate_profile(profile)
        self.assertIn("unreleased sources require rollout.stage observe", errors)
        self.assertIn("unreleased sources require profile status proposed", errors)

    def test_unsafe_artifact_path_is_rejected(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["sources"][0]["artifacts"][0]["path"] = "../secret"
        errors = validate_profile(profile)
        self.assertTrue(any("safe repository-relative path" in error for error in errors), errors)

    def test_noncanonical_managed_marker_is_rejected(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["surfaces"][1]["begin_marker"] = "<!-- duplicate -->"
        errors = validate_profile(profile)
        self.assertTrue(any("canonical Aether managed-block markers" in error for error in errors), errors)

    def test_errors_are_deterministic(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["unexpected"] = True
        profile["owner"] = "mutable-owner"
        first = validate_profile(profile)
        second = validate_profile(profile)
        self.assertEqual(first, second)
        self.assertEqual(first, sorted(first))

    def test_malformed_nested_types_return_errors_instead_of_crashing(self) -> None:
        mutations = (
            ("status", ["proposed"]),
            ("rollout-stage", ["observe"]),
            ("source-role", ["portable-contract"]),
            ("profile-id", ["library-cli"]),
            ("profile-requirement", ["required"]),
        )
        for mutation, value in mutations:
            with self.subTest(mutation=mutation):
                profile = copy.deepcopy(self.profile)
                if mutation == "status":
                    profile["status"] = value
                elif mutation == "rollout-stage":
                    profile["rollout"]["stage"] = value
                elif mutation == "source-role":
                    profile["sources"][0]["role"] = value
                elif mutation == "profile-id":
                    profile["repository_profiles"][0]["id"] = value
                else:
                    profile["repository_profiles"][0]["requirement"] = value
                self.assertTrue(validate_profile(profile))

    def test_source_verification_is_byte_exact(self) -> None:
        profile = copy.deepcopy(self.profile)
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            roots: dict[str, Path] = {}
            for source in profile["sources"]:
                source_root = temporary_root / source["role"]
                roots[source["role"]] = source_root
                for artifact in source["artifacts"]:
                    content = f"{source['role']}:{artifact['id']}\n".encode()
                    artifact_path = source_root / artifact["path"]
                    artifact_path.parent.mkdir(parents=True, exist_ok=True)
                    artifact_path.write_bytes(content)
                    artifact["sha256"] = hashlib.sha256(content).hexdigest()

            expected = sum(len(source["artifacts"]) for source in profile["sources"])
            self.assertEqual(verify_sources(profile, roots), expected)

            changed = roots["validator"] / profile["sources"][2]["artifacts"][0]["path"]
            changed.write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ProfileError, "digest mismatch"):
                verify_sources(profile, roots)

    def test_cli_validates_without_network_access(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/repository_continuity_profile.py", "validate"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("continuity profile valid", result.stdout)


if __name__ == "__main__":
    unittest.main()
