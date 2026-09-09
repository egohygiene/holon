"""Fast contract tests for the publish-safe repository-continuity fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from check_repository_continuity_fixtures import (  # noqa: E402
    CASES_PATH,
    EXPECTED_COVERAGE,
    EXPECTED_FIXTURE_IDS,
    FixtureError,
    MIGRATION_MAP_PATH,
    SNAPSHOTS_PATH,
    require_regular_binary,
    validate_fixture_contract,
)


def load(path: Path) -> dict[str, object]:
    """Load one fixture JSON object."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} is not a JSON object")
    return value


class RepositoryContinuityFixtureTests(unittest.TestCase):
    """Protect fixture coverage, provenance, and publication safety."""

    def setUp(self) -> None:
        self.cases = load(ROOT / CASES_PATH)
        self.mapping = load(ROOT / MIGRATION_MAP_PATH)

    def test_case_catalog_is_closed_and_covers_issue_45(self) -> None:
        validate_fixture_contract(self.cases)
        fixtures = self.cases["fixtures"]
        self.assertEqual({item["id"] for item in fixtures}, EXPECTED_FIXTURE_IDS)
        self.assertEqual(
            {requirement for item in fixtures for requirement in item["requirements"]},
            EXPECTED_COVERAGE,
        )

    def test_source_pins_match_the_materialization_profile(self) -> None:
        profile = load(ROOT / "catalog/repository-continuity-materialization.json")
        by_repository = {
            source["repository"]: source["revision"] for source in profile["sources"]
        }
        pins = self.cases["source_pins"]
        for name in ("aether", "hygiene", "egolint"):
            pin = pins[name]
            self.assertEqual(by_repository[pin["repository"]], pin["revision"])
        self.assertEqual(
            pins["antidote"]["revision"],
            self.mapping["source"]["revision"],
        )

    def test_private_case_contains_only_synthetic_minimum_information(self) -> None:
        private = next(
            item for item in self.cases["fixtures"] if item["id"] == "private-creative"
        )
        self.assertEqual(private["visibility"], "private")
        self.assertEqual(private["repository"], "fixture-org/private-creative")
        serialized = json.dumps(private, sort_keys=True).lower()
        for prohibited in (
            "conversation transcript",
            "participant name",
            "journal entry",
            "api key",
            "access token",
            "/users/",
            "/home/",
        ):
            self.assertNotIn(prohibited, serialized)

    def test_antidote_map_covers_every_legacy_section_and_both_files(self) -> None:
        source = self.mapping["source"]
        self.assertEqual(
            source["merge_evidence"],
            {
                "url": (
                    "https://github.com/egohygiene/antidote/commit/"
                    "f9e23128a660066b3f64c73c4dd2d36554b6040a"
                ),
                "subject": (
                    "Merge pull request #90 from "
                    "egohygiene/codex/issue-47-synthesis"
                ),
                "parents": [
                    "f4dc9326e07ad99d08557d0695e2bee8918657ec",
                    "bb8ab5e0d0f4a69d894dab41cee8ede7a1fb7fd0",
                ],
            },
        )
        self.assertEqual(
            {item["path"] for item in source["files"]},
            {"CONTINUITY.md", "AGENTS.md"},
        )
        mappings = self.mapping["mappings"]
        self.assertEqual(len({item["id"] for item in mappings}), len(mappings))
        self.assertEqual(
            {item["source"]["heading"] for item in mappings},
            {
                "Preamble",
                "Resume protocol",
                "Current checkpoint",
                "Publication state in this revision",
                "Issue #47 material changes",
                "Verified evidence for this revision",
                "Dependency-ordered publication path",
                "Boundaries and unresolved work",
                "Required update at every issue handoff",
                "Whole file",
            },
        )
        for file_record in source["files"]:
            self.assertRegex(file_record["sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(file_record["git_blob"], r"^[0-9a-f]{40}$")
        for mapping in mappings:
            self.assertRegex(
                mapping["source"]["normalized_sha256"], r"^[0-9a-f]{64}$"
            )
            self.assertTrue(mapping["targets"])
        superseded = next(item for item in mappings if item["id"] == "current-checkpoint")
        self.assertEqual(superseded["disposition"], "superseded-with-evidence")
        self.assertEqual(superseded["evidence_url"], source["merge_evidence"]["url"])

    def test_checker_has_no_network_or_mutable_provider_command(self) -> None:
        source = (ROOT / "tools/check_repository_continuity_fixtures.py").read_text(
            encoding="utf-8"
        )
        for prohibited_import in (
            "import requests",
            "import socket",
            "from urllib",
            "import urllib",
        ):
            self.assertNotIn(prohibited_import, source)
        self.assertIsNone(re.search(r'\[\s*["\']git["\']\s*,\s*["\'](?:fetch|pull)', source))
        self.assertNotIn("gh api", source)

    def test_binary_path_rejects_leaf_and_ancestor_symlinks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="holon-egolint-path-") as temporary:
            root = Path(temporary)
            real = root / "real"
            real.mkdir()
            binary = real / "egolint"
            binary.write_bytes(b"fixture")
            leaf = root / "egolint-link"
            leaf.symlink_to(binary)
            with self.assertRaisesRegex(FixtureError, "contains a symlink"):
                require_regular_binary(leaf)
            parent = root / "linked-parent"
            parent.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(FixtureError, "contains a symlink"):
                require_regular_binary(parent / "egolint")

    def test_reviewed_artifact_contract_has_exact_fixture_set(self) -> None:
        snapshots = load(ROOT / SNAPSHOTS_PATH)
        self.assertEqual(
            set(snapshots),
            {
                "schema_version",
                "profile_sha256",
                "verified_profile_artifacts",
                "egolint",
                "fixtures",
            },
        )
        self.assertEqual(set(snapshots["fixtures"]), EXPECTED_FIXTURE_IDS)
        self.assertRegex(snapshots["profile_sha256"], r"^[0-9a-f]{64}$")
        snapshot_bytes = (ROOT / SNAPSHOTS_PATH).read_bytes()
        self.assertEqual(snapshot_bytes[-1:], b"\n")
        self.assertNotEqual(hashlib.sha256(snapshot_bytes).hexdigest(), "0" * 64)
        self.assertEqual(
            snapshots["fixtures"]["private-creative"]["private_safety"],
            {
                "bytes": 6771,
                "lines": 182,
                "classification": "private-repository",
                "contains_sensitive_data": False,
            },
        )
        site = snapshots["fixtures"]["site-application"]
        self.assertEqual(site["summary"], {"preserve": 1, "update": 3})
        self.assertEqual(
            set(site["prior_managed_block_sha256"]),
            {"AGENTS.md", ".github/copilot-instructions.md", "CLAUDE.md"},
        )
        self.assertNotEqual(
            site["prior_state_contract_sha256"], site["state_contract_sha256"]
        )
        self.assertNotEqual(
            site["prior_profile_sha256"], site["state_profile_sha256"]
        )


if __name__ == "__main__":
    unittest.main()
