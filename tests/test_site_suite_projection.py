"""Real scoped lifecycle and unchanged full-foundation admission controls."""

from __future__ import annotations

import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from check_react_vite_fixture import write_aether_fixture  # noqa: E402
from holon_contract import load_json, resolve_manifest  # noqa: E402
from materialization import build_plan, render_plan  # noqa: E402
from materialization.common import MaterializationError, canonical_bytes, sha256_bytes  # noqa: E402
from materialization.site_suite import (  # noqa: E402
    build_site_suite_plan,
    render_site_suite_plan,
    rollback_site_suite_target,
    verify_site_suite_target,
)
from site_suite_blueprint import EXAMPLES  # noqa: E402


class SiteSuiteProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = self.root / "consumer"
        self.manifest = load_json(ROOT / EXAMPLES["generic"])

    def test_both_real_variants_plan_render_noop_verify_and_rollback_without_aether(self) -> None:
        for variant in ("generic", "launchkit"):
            with self.subTest(variant=variant):
                target = self.root / variant
                manifest = load_json(ROOT / EXAMPLES[variant])
                plan = build_site_suite_plan(manifest, variant, target, project=ROOT)
                self.assertFalse(target.exists(), "planning must remain read-only")
                scoped = plan["resolved_manifest"]
                scope = scoped["site_suite_projection"]
                Draft202012Validator(load_json(ROOT / "schemas/site-suite-projection.v1.schema.json")).validate(scope)
                full, errors = resolve_manifest(load_json(ROOT / "catalog/foundation.json"), manifest)
                self.assertEqual(errors, [])
                self.assertEqual(scope["foundation_resolved_sha256"], sha256_bytes(canonical_bytes(full)))
                self.assertEqual(scope["foundation_qualification"], "unqualified")
                self.assertIn("aether-agents", scope["unqualified_capabilities"])
                self.assertIn("architecture-decisions", scope["unqualified_capabilities"])
                self.assertEqual(scope["foundation_manifest"], manifest)
                self.assertIsNone(plan["inputs"]["aether"])
                state = render_site_suite_plan(plan, target, project=ROOT)
                self.assertEqual(verify_site_suite_target(target, project=ROOT), [])
                self.assertTrue((target / "site_suite.py").is_file())
                self.assertFalse((target / ".github/agents").exists())
                self.assertEqual(len(state["managed_files"]), len(plan["operations"]))
                repeated = build_site_suite_plan(manifest, variant, target, project=ROOT)
                self.assertEqual(set(repeated["summary"]), {"noop"})
                rollback_site_suite_target(target, project=ROOT)
                self.assertFalse((target / "site_suite.py").exists())

    def test_default_foundation_still_requires_real_aether_distribution(self) -> None:
        resolved, errors = resolve_manifest(load_json(ROOT / "catalog/foundation.json"), self.manifest)
        self.assertEqual(errors, [])
        assert resolved is not None
        self.assertIn("aether-agents", resolved["capabilities"])
        with self.assertRaisesRegex(MaterializationError, "provide a pinned Aether distribution"):
            build_plan(resolved, self.target, render_source=ROOT / "blueprints/react-vite/files")
        self.assertFalse(self.target.exists())

    def test_scope_cannot_downgrade_an_existing_complete_foundation(self) -> None:
        # Existing owner unit fixture isolates lifecycle behavior; it is never a
        # released Aether artifact or consumer qualification receipt.
        aether = self.root / "synthetic-owner-unit-aether"
        write_aether_fixture(aether)
        resolved, errors = resolve_manifest(load_json(ROOT / "catalog/foundation.json"), self.manifest)
        self.assertEqual(errors, [])
        assert resolved is not None
        source = ROOT / "blueprints/react-vite/files"
        plan, _ = build_plan(resolved, self.target, render_source=source, aether_source=aether)
        render_plan(plan, self.target, render_source=source, aether_source=aether)
        before = {p: p.read_bytes() for p in self.target.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(MaterializationError, "not an explicit site-suite projection"):
            build_site_suite_plan(self.manifest, "generic", self.target, project=ROOT)
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_required_capabilities_security_and_immutable_pins_are_not_relaxed(self) -> None:
        for change in ("capability", "security", "pin"):
            with self.subTest(change=change):
                manifest = copy.deepcopy(self.manifest)
                if change == "capability":
                    manifest["capabilities"]["exclude"] = ["architecture-decisions"]
                elif change == "security":
                    manifest["security_level"] = "baseline"
                else:
                    manifest["pins"]["aether"] = "egohygiene/aether@main"
                with self.assertRaisesRegex(MaterializationError, "foundation manifest is invalid"):
                    build_site_suite_plan(manifest, "generic", self.target, project=ROOT)
                self.assertFalse(self.target.exists())

    def test_invalid_content_and_wrong_variant_are_rejected_before_writes(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["parameters"]["site_suite_content"]["legal"]["pages"][0]["slug"] = "index"
        with self.assertRaisesRegex(MaterializationError, "content is invalid"):
            build_site_suite_plan(invalid, "generic", self.target, project=ROOT)
        with self.assertRaisesRegex(MaterializationError, "cannot silently omit"):
            build_site_suite_plan(load_json(ROOT / EXAMPLES["launchkit"]), "generic", self.target, project=ROOT)
        self.assertFalse(self.target.exists())

    def test_rehashed_plan_cannot_falsify_qualification_or_omitted_capabilities(self) -> None:
        for field, value in (("foundation_qualification", "qualified"), ("unqualified_capabilities", [])):
            with self.subTest(field=field):
                plan = build_site_suite_plan(self.manifest, "generic", self.target, project=ROOT)
                plan["resolved_manifest"]["site_suite_projection"][field] = value
                plan["plan_id"] = sha256_bytes(canonical_bytes({k: v for k, v in plan.items() if k != "plan_id"}))
                with self.assertRaisesRegex(MaterializationError, "scope differs"):
                    render_site_suite_plan(plan, self.target, project=ROOT)
                self.assertFalse(self.target.exists())

    def test_guarded_rollback_preserves_a_later_human_edit(self) -> None:
        plan = build_site_suite_plan(self.manifest, "generic", self.target, project=ROOT)
        render_site_suite_plan(plan, self.target, project=ROOT)
        path = self.target / "src/app.tsx"
        path.write_text(path.read_text(encoding="utf-8") + "\n// local consumer edit\n", encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(MaterializationError):
            rollback_site_suite_target(self.target, project=ROOT)
        self.assertEqual(path.read_bytes(), before)

    def test_actual_cli_keeps_scope_explicit_and_refuses_inside_target_plan(self) -> None:
        cli = [sys.executable, str(ROOT / "tools/holon_materialize.py"), "site-suite"]
        plan = self.root / "plan.json"
        result = subprocess.run(cli + ["plan", "--manifest", str(ROOT / EXAMPLES["generic"]),
                                     "--variant", "generic", "--target", str(self.target),
                                     "--output", str(plan)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("foundation unqualified", result.stdout)
        for command, arguments in (("render", ["--plan", str(plan)]), ("verify", []), ("rollback", [])):
            result = subprocess.run(cli + [command, "--target", str(self.target), *arguments],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
        bad = subprocess.run(cli + ["plan", "--manifest", str(ROOT / EXAMPLES["generic"]),
                                  "--variant", "generic", "--target", str(self.root / "other"),
                                  "--output", str(self.root / "other/plan.json")],
                             capture_output=True, text=True, check=False)
        self.assertEqual(bad.returncode, 1)
        self.assertFalse((self.root / "other").exists())


if __name__ == "__main__":
    unittest.main()
