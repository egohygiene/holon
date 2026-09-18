"""Exercise root dogfood after a legitimate repository-owned handoff refresh."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_repository_continuity_dogfood as dogfood  # noqa: E402
import test_continuity_materialization as fixture_module  # noqa: E402


class ContinuityDogfoodTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = fixture_module.ContinuityMaterializationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.apply(self.fixture.plan())
        self.target = self.fixture.target
        (self.target / ".git").mkdir()
        (self.target / ".git/HEAD").write_text("ref: refs/heads/main\n")
        self.original = dogfood.managed_artifacts(self.target)
        self.request = self.fixture.root / "request.json"
        self.request.write_text(json.dumps(self.fixture.request()))
        self.review = self.fixture.root / "review"
        self.review.mkdir()
        self.environment, _ = dogfood.prepare_environment(self.fixture.root)

    def check(self) -> dict:
        before = dogfood.path_contract(self.target)
        try:
            return dogfood.assert_root_parity(
                root=self.target, request=self.request, profile=self.fixture.profile_path,
                aether_source=self.fixture.aether, disposable_artifacts=self.original,
                review=self.review, environment=self.environment,
            )
        finally:
            self.assertEqual(dogfood.path_contract(self.target), before)

    def refresh(self) -> None:
        path = self.target / "CONTINUITY.md"
        path.write_bytes(path.read_bytes() + b"\nA later evidence-grounded repository checkpoint.\n")

    def test_unchanged_scaffold_still_proves_exact_noop(self) -> None:
        self.assertEqual(self.check()["checkpoint"], "template-identical")

    def test_authored_refresh_preserves_historical_state_and_recovery(self) -> None:
        self.refresh()
        self.assertEqual(self.check()["checkpoint"], "repository-owned-preserved")
        current = dogfood.managed_artifacts(self.target)
        self.assertNotEqual(current["CONTINUITY.md"], self.original["CONTINUITY.md"])
        for path in self.original:
            if path != "CONTINUITY.md":
                self.assertEqual(current[path], self.original[path])

    def test_malformed_refresh_still_fails(self) -> None:
        (self.target / "CONTINUITY.md").write_text("# Missing the required structure\n")
        with self.assertRaises(dogfood.DogfoodError):
            self.check()

    def test_managed_block_edit_still_fails(self) -> None:
        self.refresh()
        path = self.target / "AGENTS.md"
        path.write_text(path.read_text().replace("Read `CONTINUITY.md`", "Skip `CONTINUITY.md`"))
        with self.assertRaises(dogfood.DogfoodError):
            self.check()

    def test_recovery_evidence_edit_still_fails(self) -> None:
        self.refresh()
        state = json.loads(self.original[dogfood.STATE_RELATIVE_PATH])
        path = self.target / state["rollback_manifest"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(dogfood.DogfoodError):
            self.check()


if __name__ == "__main__":
    unittest.main()
