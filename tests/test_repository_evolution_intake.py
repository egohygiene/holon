"""Consistency controls for the recorded manual evolution pilots."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples/repository-evolution"


class RepositoryEvolutionIntakeTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((FIXTURES / "pilots.v1.json").read_text())

    def test_two_distinct_existing_profiles_are_bound_to_real_frozen_bytes(self):
        self.assertEqual(self.record["kind"], "recorded-manual-assessments")
        self.assertFalse(self.record["external_writes"])
        self.assertEqual({p["profile"] for p in self.record["pilots"]},
                         {"offline-python-cli", "static-documentation"})
        for pilot in self.record["pilots"]:
            for phase in ("before", "after"):
                source = FIXTURES / pilot["id"] / phase
                inventory = [{"path": path.relative_to(source).as_posix(),
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                             for path in sorted(source.rglob("*")) if path.is_file()]
                bound = pilot["source_" + phase]
                self.assertEqual(inventory, bound["inventory"])
                digest = hashlib.sha256(json.dumps(inventory, sort_keys=True,
                                        separators=(",", ":")).encode()).hexdigest()
                self.assertEqual(digest, bound["sha256"])

    def test_unchanged_manual_rerun_has_stable_candidates_and_dispositions(self):
        for pilot in self.record["pilots"]:
            self.assertEqual(pilot["initial"], pilot["unchanged_rerun"])
            candidates = pilot["initial"]["proposed_issues"]
            self.assertEqual(len(candidates), len({c["id"] for c in candidates}))
            existing = {issue["capability"] for issue in pilot["existing_issues"]}
            self.assertFalse(existing & {c["capability"] for c in candidates})
            self.assertEqual(pilot["initial"]["reused_issues"], pilot["existing_issues"])

    def test_satisfied_inapplicable_and_unknown_capabilities_produce_no_tasks(self):
        for pilot in self.record["pilots"]:
            for phase in ("initial", "after"):
                assessment = pilot[phase]
                states = {c["id"]: c["state"] for c in assessment["capabilities"]}
                for candidate in assessment["proposed_issues"]:
                    self.assertEqual(states[candidate["capability"]], "gap")
                self.assertEqual(assessment["authority"], "proposal-only")
                self.assertEqual(assessment["current_maturity"]["kind"], "inference")
                self.assertEqual(assessment["desired_stage"]["kind"], "proposal")
        site = next(p for p in self.record["pilots"] if p["id"] == "site")
        self.assertTrue(site["initial"]["questions"])

    def test_reassessment_retires_only_simulated_resolved_candidates(self):
        for pilot in self.record["pilots"]:
            self.assertEqual(pilot["simulated_change"]["review"], "simulated-explicit")
            self.assertEqual(len(pilot["initial"]["proposed_issues"]), 1)
            self.assertEqual(pilot["after"]["proposed_issues"], [])
            self.assertEqual(pilot["initial"]["reused_issues"], pilot["after"]["reused_issues"])
            self.assertNotEqual(pilot["source_before"]["sha256"], pilot["source_after"]["sha256"])

    def test_cli_before_and_after_tests_run_without_mutating_frozen_snapshots(self):
        for phase in ("before", "after"):
            directory = FIXTURES / "cli" / phase
            result = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_app"],
                                    cwd=directory, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
        before, after = [{"__name__": "fixture"} for _ in range(2)]
        exec((FIXTURES / "cli/before/app.py").read_text(), before)
        exec((FIXTURES / "cli/after/app.py").read_text(), after)
        with self.assertRaisesRegex(ValueError, "invalid literal"):
            before["parse_count"]("invalid")
        with self.assertRaisesRegex(ValueError, "^count must be an integer$"):
            after["parse_count"]("invalid")

    def test_site_simulation_preserves_content_while_declaring_language(self):
        before = (FIXTURES / "site/before/index.html").read_text()
        after = (FIXTURES / "site/after/index.html").read_text()
        self.assertEqual(before.replace("<html>", '<html lang="en">'), after)

    def test_template_requires_evidence_applicability_existing_work_and_review(self):
        template = (ROOT / "templates/repository-evolution-intake.md").read_text()
        for requirement in ("inspected revision", "accepted decisions", "open PRs",
                            "not-applicable", "Unknowns", "stable candidate IDs",
                            "separate authorization", "does not prove capability"):
            self.assertIn(requirement, template)


if __name__ == "__main__":
    unittest.main()
