"""Contract and clean-materialization tests for the generic React/Vite blueprint."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from check_react_vite_fixture import materialize_example, write_aether_fixture  # noqa: E402
from react_vite_blueprint import load_strict_json, validate_blueprint  # noqa: E402
from materialization import verify_target  # noqa: E402


class ReactViteBlueprintTests(unittest.TestCase):
    """Keep the foundation generic, versioned, reproducible, and executable."""

    def test_canonical_blueprint_contract_is_valid(self) -> None:
        """The committed profile, inventory, example, and template stay aligned."""
        self.assertEqual(validate_blueprint(ROOT), [])
        profile = load_strict_json(ROOT / "blueprints/react-vite/blueprint.json")
        self.assertEqual(profile["capability"], "site-react-vite")
        self.assertEqual(profile["extends"], None)
        self.assertGreaterEqual(len(profile["files"]), 20)

    def test_baseline_excludes_specialized_and_rejected_dependencies(self) -> None:
        """LaunchKit, Storybook, publint, and rejected utilities stay opt-in or absent."""
        profile = load_strict_json(ROOT / "blueprints/react-vite/blueprint.json")
        package = load_strict_json(ROOT / "blueprints/react-vite/files/package.json")
        dependencies = set(package["dependencies"]) | set(package["devDependencies"])
        self.assertTrue(set(profile["dependencies"]["forbidden_baseline"]).isdisjoint(dependencies))
        self.assertFalse(any("storybook" in name.casefold() for name in dependencies))
        self.assertNotIn("publint", dependencies)
        self.assertEqual(profile["optional_capabilities"]["launchkit"]["status"], "separate-blueprint")

    def test_clean_example_materializes_and_replans_as_noop(self) -> None:
        """A clean directory becomes a verified application without manual repair."""
        with tempfile.TemporaryDirectory(prefix="holon-react-vite-unit-") as temporary:
            root = Path(temporary)
            target = root / "consumer"
            target.mkdir()
            aether = root / "aether-dist"
            write_aether_fixture(aether)
            state = materialize_example(ROOT, target, aether)
            self.assertEqual(verify_target(target), [])
            self.assertEqual(state["resolved_manifest"]["repository_class"], "product")
            self.assertIn("site-react-vite", state["resolved_manifest"]["capabilities"])
            package = json.loads((target / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(package["name"], "@egohygiene/example-react-vite-site")
            self.assertTrue((target / "pnpm-lock.yaml").is_file())
            self.assertTrue((target / "src/app.test.tsx").is_file())


if __name__ == "__main__":
    unittest.main()
