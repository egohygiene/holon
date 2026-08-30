"""Contract tests for Zensical and composed public site surfaces."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from holon_contract import load_json, resolve_manifest  # noqa: E402
from materialization import build_plan, render_plan, verify_target  # noqa: E402
from site_suite_blueprint import EXAMPLES, validate_blueprints, validate_site_content  # noqa: E402


class SiteSuiteBlueprintTests(unittest.TestCase):
    """Protect source ownership, variants, and consumer-driven content."""

    def test_canonical_profiles_are_valid(self) -> None:
        self.assertEqual(validate_blueprints(ROOT), [])

    def test_variants_resolve_distinct_landing_capabilities(self) -> None:
        catalog = load_json(ROOT / "catalog/foundation.json")
        observed: dict[str, set[str]] = {}
        for name, path in EXAMPLES.items():
            resolved, errors = resolve_manifest(catalog, load_json(ROOT / path))
            self.assertEqual(errors, [])
            assert resolved is not None
            observed[name] = set(resolved["capabilities"])
            self.assertIn("site-react-vite", observed[name])
            self.assertIn("docs-zensical", observed[name])
        self.assertNotIn("landing-launchkit", observed["generic"])
        self.assertIn("landing-launchkit", observed["launchkit"])

    def test_ordered_composition_preserves_every_source_boundary(self) -> None:
        catalog = load_json(ROOT / "catalog/foundation.json")
        profile = load_json(ROOT / "blueprints/site-suite/blueprint.json")
        manifest = load_json(ROOT / EXAMPLES["launchkit"])
        resolved, errors = resolve_manifest(catalog, manifest)
        self.assertEqual(errors, [])
        assert resolved is not None
        resolved = copy.deepcopy(resolved)
        resolved["capabilities"] = [
            capability for capability in resolved["capabilities"] if capability != "aether-agents"
        ]
        variant = profile["variants"]["launchkit"]
        with tempfile.TemporaryDirectory(prefix="holon-site-suite-unit-") as temporary:
            target = Path(temporary) / "consumer"
            target.mkdir()
            overlays = [ROOT / path for path in variant["render_overlays"]]
            plan, _ = build_plan(
                resolved,
                target,
                render_source=ROOT / variant["render_source"],
                render_overlays=overlays,
            )
            state = render_plan(
                plan,
                target,
                render_source=ROOT / variant["render_source"],
                render_overlays=overlays,
            )
            self.assertEqual(verify_target(target), [])
            sources = {record["source"] for record in state["managed_files"]}
            self.assertTrue(any(source.startswith("render-source:") for source in sources))
            for index in range(3):
                self.assertTrue(
                    any(source.startswith(f"render-overlay:{index}:") for source in sources)
                )
            settings = json_load(target / "site-docs/settings.json")
            self.assertEqual(settings["site_title"], "OptiFlow")
            content = json_load(target / "site-docs/content.json")
            self.assertEqual(content["schema"], "holon.site-suite-content/v1")

    def test_placeholder_content_is_rejected(self) -> None:
        content = copy.deepcopy(
            load_json(ROOT / EXAMPLES["generic"])["parameters"]["site_suite_content"]
        )
        content["documentation"]["introduction"] = "Lorem ipsum"
        errors = validate_site_content(content, "fixture")
        self.assertTrue(any("placeholder copy" in error for error in errors))

    def test_composed_verifier_rejects_unsafe_reference_schemes(self) -> None:
        source = ROOT / "blueprints/site-suite/files/site_suite.py"
        namespace = {"__name__": "holon_generated_site_suite", "__file__": str(source)}
        exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), namespace)
        with self.assertRaisesRegex(RuntimeError, "unsupported URL scheme"):
            namespace["reference_target"](source, "javascript:alert(1)")
        with self.assertRaisesRegex(RuntimeError, "protocol-relative URL"):
            namespace["reference_target"](source, "//unsafe.example/path")


def json_load(path: Path) -> dict[str, object]:
    """Load one rendered JSON object for an assertion."""
    value = load_json(path)
    return value


if __name__ == "__main__":
    unittest.main()
