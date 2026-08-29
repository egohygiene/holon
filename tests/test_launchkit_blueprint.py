"""Contract tests for the derived LaunchKit landing-page blueprint."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from holon_contract import load_json, resolve_manifest  # noqa: E402
from launchkit_blueprint import EXAMPLE_PATHS, validate_blueprint, validate_content  # noqa: E402
from materialization import build_plan, render_plan, verify_target  # noqa: E402


class LaunchKitBlueprintTests(unittest.TestCase):
    """Protect composition, provenance, and manifest-driven customization."""

    def test_canonical_launchkit_contract_is_valid(self) -> None:
        self.assertEqual(validate_blueprint(ROOT), [])

    def test_pilots_resolve_base_and_derived_capabilities(self) -> None:
        catalog = load_json(ROOT / "catalog/foundation.json")
        section_sets: list[set[str]] = []
        for path in EXAMPLE_PATHS:
            manifest = load_json(ROOT / path)
            resolved, errors = resolve_manifest(catalog, manifest)
            self.assertEqual(errors, [])
            assert resolved is not None
            self.assertIn("site-react-vite", resolved["capabilities"])
            self.assertIn("landing-launchkit", resolved["capabilities"])
            section_sets.append(set(resolved["parameters"]["launchkit_content"]))
        self.assertNotEqual(section_sets[0], section_sets[1])

    def test_ordered_overlay_records_base_and_launchkit_provenance(self) -> None:
        catalog = load_json(ROOT / "catalog/foundation.json")
        manifest = load_json(ROOT / EXAMPLE_PATHS[0])
        resolved, errors = resolve_manifest(catalog, manifest)
        self.assertEqual(errors, [])
        assert resolved is not None

        with tempfile.TemporaryDirectory(prefix="holon-launchkit-unit-") as temporary:
            target = Path(temporary) / "consumer"
            target.mkdir()
            resolved_without_agents = copy.deepcopy(resolved)
            resolved_without_agents["capabilities"] = [
                capability
                for capability in resolved["capabilities"]
                if capability != "aether-agents"
            ]
            plan, _ = build_plan(
                resolved_without_agents,
                target,
                render_source=ROOT / "blueprints/react-vite/files",
                render_overlays=[ROOT / "blueprints/launchkit/files"],
            )
            state = render_plan(
                plan,
                target,
                render_source=ROOT / "blueprints/react-vite/files",
                render_overlays=[ROOT / "blueprints/launchkit/files"],
            )
            self.assertEqual(verify_target(target), [])
            sources = {record["source"] for record in state["managed_files"]}
            self.assertTrue(any(source.startswith("render-source:") for source in sources))
            self.assertTrue(any(source.startswith("render-overlay:0:") for source in sources))
            content = (target / "src/launchkit/content.ts").read_text(encoding="utf-8")
            self.assertIn("Transform large media", content)

    def test_placeholder_copy_is_rejected(self) -> None:
        manifest = load_json(ROOT / EXAMPLE_PATHS[0])
        content = copy.deepcopy(manifest["parameters"]["launchkit_content"])
        content["hero"]["title"] = "Lorem ipsum developer tool"
        errors = validate_content(content, "fixture")
        self.assertTrue(any("placeholder copy" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
