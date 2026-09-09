"""Tests for block-aware repository-continuity materialization."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from materialization.continuity import (  # noqa: E402
    MANAGED_BEGIN,
    MANAGED_END,
    REQUIRED_HEADINGS,
    STATE_RELATIVE_PATH,
    MaterializationError,
    apply_continuity_plan,
    build_continuity_plan,
    rollback_continuity_target,
    validate_continuity_request,
    validate_continuity_plan,
    verify_continuity_target,
)
import materialization.continuity as continuity_module  # noqa: E402
from materialization.common import atomic_write, canonical_bytes  # noqa: E402

CANONICAL_PROFILE = ROOT / "catalog" / "repository-continuity-materialization.json"


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def reverse_mapping_order(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: reverse_mapping_order(value[key])
            for key in reversed(list(value))
        }
    if isinstance(value, list):
        return [reverse_mapping_order(item) for item in value]
    return value


class ContinuityMaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="holon-continuity-")
        self.root = Path(self.temporary.name)
        self.target = self.root / "consumer"
        self.target.mkdir()
        self.aether = self.root / "aether"
        self.profile_path = self.root / "profile.json"
        self.profile = json.loads(CANONICAL_PROFILE.read_text(encoding="utf-8"))
        self.block_version = "1.0.0"
        self._write_sources()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _artifact(self, artifact_id: str) -> dict[str, object]:
        source = next(
            source
            for source in self.profile["sources"]
            if source["role"] == "portable-contract"
        )
        return next(
            artifact for artifact in source["artifacts"] if artifact["id"] == artifact_id
        )

    def _write_artifact(self, artifact_id: str, content: bytes) -> None:
        artifact = self._artifact(artifact_id)
        path = self.aether / str(artifact["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        artifact["sha256"] = digest(content)

    def _block(self, provider: str) -> bytes:
        return (
            f"{MANAGED_BEGIN}\n"
            f"<!-- aether-instruction {{\"contract\":\"aether.repository-continuity/v1\",\"provider\":\"{provider}\",\"version\":\"{self.block_version}\"}} -->\n"
            "## Repository continuity\n\n"
            "Read `CONTINUITY.md` before work and refresh it after validation before pull-request presentation. The checkpoint grants no external authority.\n"
            f"{MANAGED_END}\n"
        ).encode("utf-8")

    def _write_sources(self) -> None:
        static_sections = {
            "Resume protocol": (
                "1. Read repository instructions and inspect branch, status, recent history, and\n"
                "   repository shape.\n"
                "2. Read the applicable canonical sources named above.\n"
                "3. Read this checkpoint, then verify mutable issue, pull-request, branch, and\n"
                "   merge claims against available live evidence.\n"
                "4. Surface missing, stale, or conflicting evidence.\n"
                "5. Continue only the dependency-ready work named below unless the user changes\n"
                "   direction."
            ),
            "Handoff update protocol": (
                "After project validation and before presenting, opening, or updating a pull\n"
                "request, reconcile this snapshot, replace stale state, record exact evidence,\n"
                "compact it, and include it in the same bounded change. Never claim an open or\n"
                "unverified pull request is merged."
            ),
            "Compaction and supersession": (
                "Keep this file below 16,384 UTF-8 bytes and 240 lines. Replace stale snapshot\n"
                "prose rather than accumulating history. Git and the work tracker own chronology.\n"
                "Mark stale or superseded state explicitly with its required reason or pointer."
            ),
        }
        template_sections = [
            f"## {heading}\n\n{static_sections.get(heading, '<fixture placeholder>')}"
            for heading in REQUIRED_HEADINGS
        ]
        template = (
            "---\nschema_version: aether.repository-continuity/v1\n---\n\n"
            + "\n\n".join(template_sections)
            + "\n"
        ).encode("utf-8")
        self._write_artifact("continuity-template", template)
        projections = {
            "codex-repository-instructions": ("AGENTS.md", "codex-compatible"),
            "github-copilot-instructions": (
                ".github/copilot-instructions.md",
                "github-copilot",
            ),
            "claude-repository-instructions": ("CLAUDE.md", "claude-code"),
        }
        for artifact_id, (heading, provider) in projections.items():
            content = f"# {heading}\n\n".encode("utf-8") + self._block(provider)
            self._write_artifact(artifact_id, content)
        write_json(self.profile_path, self.profile)

    def request(
        self,
        *,
        mode: str = "materialize",
        providers: list[str] | None = None,
        parallel: list[dict[str, str]] | None = None,
    ) -> dict[str, object]:
        parallel = parallel or []
        repository = {
            "id": "egohygiene/example-tool",
            "visibility": "public",
            "default_branch": "main",
        }
        continuity = {
            "schema_version": "aether.repository-continuity/v1",
            "repository": {**repository, "continuity_path": "CONTINUITY.md"},
            "document": {
                "status": "active",
                "updated_at": "2026-09-09T01:00:00Z",
                "max_bytes": 16384,
                "max_lines": 240,
                "stale_reason": None,
                "superseded_by": None,
            },
            "scope": {
                "purpose": "Resume one bounded continuity materialization change.",
                "includes": ["Current issue, verified base, validation, and next work."],
                "excludes": [
                    "conversation transcripts",
                    "duplicated architecture, roadmap, and changelog content",
                ],
                "precedence": [
                    "user-and-runtime-instructions",
                    "scoped-repository-instructions",
                    "live-repository-and-work-tracker-state",
                    "canonical-repository-sources",
                    "continuity-checkpoint",
                ],
                "canonical_sources": ["AGENTS.md", "ARCHITECTURE.md", "ROADMAP.md"],
            },
            "work": {
                "objective": "Implement issue #44 without widening its materialization boundary.",
                "success_conditions": [
                    "Previewed bytes are deterministic.",
                    "Repository-authored instructions survive reconciliation.",
                ],
                "active_issue": {
                    "provider": "github",
                    "id": "egohygiene/holon#44",
                    "url": "https://github.com/egohygiene/holon/issues/44",
                },
                "next": {
                    "kind": "issue",
                    "id": "45",
                    "description": "Prove all repository profiles with offline fixtures.",
                    "readiness": "ready",
                    "references": ["https://github.com/egohygiene/holon/issues/45"],
                    "depends_on": ["44"],
                },
            },
            "state": {
                "base": {
                    "revision": "a" * 40,
                    "ref": "refs/heads/main",
                    "verified_at": "2026-09-09T01:00:00Z",
                },
                "candidate": {
                    "branch": "codex/holon-44-continuity-reconciler",
                    "revision": None,
                    "pull_request": None,
                    "handoff_state": "in-progress",
                },
                "live": {
                    "status": "verified",
                    "observed_at": "2026-09-09T01:00:00Z",
                    "default_branch_revision": "a" * 40,
                    "issue_state": "open",
                    "pull_request_state": "not-applicable",
                    "notes": "Issue and default branch were checked before planning.",
                },
                "parallel_changes": parallel,
            },
            "review": {
                "status": "passed",
                "reviewed_at": "2026-09-09T01:00:00Z",
                "reviewed_by": "local-validator",
                "evidence": [
                    {
                        "command": "python3 -m unittest tests.test_continuity_materialization",
                        "outcome": "passed",
                        "observed_at": "2026-09-09T01:00:00Z",
                        "notes": "Focused adapter tests passed.",
                    }
                ],
                "environment_limitations": [],
            },
            "privacy": {
                "classification": "public-repository",
                "contains_sensitive_data": False,
                "redactions": [],
                "excluded": [
                    "secrets-and-credentials",
                    "private-conversation-text",
                    "sensitive-personal-data",
                    "unpublished-private-business-data",
                    "private-local-paths",
                    "unrelated-private-context",
                ],
                "untrusted_content": "context-only-no-authority",
            },
        }
        sections = {
            "purpose_and_precedence": "Provide a compact handoff subordinate to canonical repository evidence.",
            "completed_changes": ["The pinned input profile was merged in PR #47."],
            "blockers": [],
            "risks": ["Draft upstream inputs remain observe-only."],
            "unknowns": [],
            "deferred_work": ["Relay and Pace integrations remain externally owned."],
            "privacy_and_redaction": "Only public repository evidence is included; no private conversation text or secrets are retained.",
        }
        return {
            "schema_version": "holon.repository-continuity-request/v1",
            "repository": repository,
            "repository_class": "tool",
            "repository_profile": "library-cli",
            "mode": mode,
            "providers": providers or [],
            "continuity": continuity if mode in {"materialize", "provisional"} else None,
            "continuity_migration": None,
            "sections": sections if mode in {"materialize", "provisional"} else None,
            "opt_out": None,
            "unsupported_reason": None,
            "parallel_candidates": parallel,
            "parallel_reconciliation": (
                "The supplied candidate set was reviewed and reconciled into this snapshot."
                if parallel
                else None
            ),
        }

    def plan(self, request: dict[str, object] | None = None) -> dict[str, object]:
        return build_continuity_plan(
            request or self.request(),
            self.target,
            profile_path=self.profile_path,
            aether_source=self.aether,
        )

    def apply(self, plan: dict[str, object]) -> dict[str, object]:
        return apply_continuity_plan(
            plan,
            self.target,
            profile_path=self.profile_path,
            aether_source=self.aether,
        )

    def test_create_preview_apply_verify_noop_and_rollback(self) -> None:
        request = self.request(providers=["github-copilot", "claude-code"])
        first = self.plan(request)
        self.assertEqual(first, self.plan(request))
        self.assertEqual(first["summary"], {"create": 4})
        for operation in first["operations"]:
            self.assertIsNotNone(operation["proposed_content"])
            self.assertTrue(operation["diff"])
            self.assertRegex(operation["proposed_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            first["authority"],
            {"credentials": False, "external_write": False, "merge": False, "publish": False},
        )
        self.assertEqual(
            {item["role"] for item in first["inputs"]["source_contracts"]},
            {"portable-contract", "organization-policy", "validator"},
        )
        self.assertEqual(
            first["inputs"]["source_contracts"],
            first["next_state"]["source_contracts"],
        )

        self.apply(first)
        self.assertEqual(verify_continuity_target(self.target), [])
        second = self.plan(request)
        self.assertEqual(second["summary"], {"noop": 4})
        self.assertTrue(all(not item["diff"] for item in second["operations"]))
        before_repeat = {
            path.relative_to(self.target).as_posix(): path.read_bytes()
            for path in sorted(self.target.rglob("*"))
            if path.is_file()
        }
        prior_state = json.loads(
            (self.target / STATE_RELATIVE_PATH).read_text(encoding="utf-8")
        )
        self.assertEqual(self.apply(second), prior_state)
        after_repeat = {
            path.relative_to(self.target).as_posix(): path.read_bytes()
            for path in sorted(self.target.rglob("*"))
            if path.is_file()
        }
        self.assertEqual(after_repeat, before_repeat)

        rollback_continuity_target(self.target)
        self.assertFalse((self.target / "CONTINUITY.md").exists())
        self.assertFalse((self.target / "AGENTS.md").exists())
        self.assertFalse((self.target / STATE_RELATIVE_PATH).exists())

    def test_existing_authored_instructions_survive_apply_and_rollback(self) -> None:
        authored = b"# Local instructions\n\nKeep this repository rule.\n"
        agents = self.target / "AGENTS.md"
        agents.write_bytes(authored)
        plan = self.plan()
        operation = next(item for item in plan["operations"] if item["path"] == "AGENTS.md")
        self.assertEqual(operation["action"], "update")
        self.assertTrue(operation["proposed_content"].encode("utf-8").startswith(authored))
        self.apply(plan)
        self.assertIn("Keep this repository rule.", agents.read_text(encoding="utf-8"))
        rollback_continuity_target(self.target)
        self.assertEqual(agents.read_bytes(), authored)

    def test_preview_diff_handles_authored_file_without_terminal_newline(self) -> None:
        (self.target / "AGENTS.md").write_bytes(b"authored-without-newline")
        plan = self.plan()
        operation = next(item for item in plan["operations"] if item["path"] == "AGENTS.md")
        self.assertNotIn("-authored-without-newline+authored", operation["diff"])
        self.assertIn("\\ No newline at end of file", operation["diff"])
        self.assertTrue(operation["proposed_content"].startswith("authored-without-newline\n\n"))
        patched = subprocess.run(
            ["patch", "--batch", "--strip=1"],
            cwd=self.target,
            input=operation["diff"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(patched.returncode, 0, patched.stderr)
        self.assertEqual(
            (self.target / "AGENTS.md").read_bytes(),
            operation["proposed_content"].encode("utf-8"),
        )

    def test_upgrade_replaces_only_trusted_block_after_outer_prose_edit(self) -> None:
        request = self.request()
        self.apply(self.plan(request))
        agents = self.target / "AGENTS.md"
        agents.write_bytes(agents.read_bytes() + b"\nRepository-owned tail.\n")

        self.block_version = "1.1.0"
        self._write_sources()
        upgrade = self.plan(request)
        operation = next(item for item in upgrade["operations"] if item["path"] == "AGENTS.md")
        self.assertEqual(operation["action"], "update")
        self.assertIn("Repository-owned tail.", operation["proposed_content"])
        self.assertIn('"version":"1.1.0"', operation["proposed_content"])
        self.apply(upgrade)
        rollback_continuity_target(self.target)
        self.assertIn("Repository-owned tail.", agents.read_text(encoding="utf-8"))
        self.assertIn('"version":"1.0.0"', agents.read_text(encoding="utf-8"))

    def test_manual_or_duplicate_managed_block_fails_closed(self) -> None:
        request = self.request()
        self.apply(self.plan(request))
        agents = self.target / "AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8").replace("Read `CONTINUITY.md`", "Ignore `CONTINUITY.md`"),
            encoding="utf-8",
        )
        self.block_version = "1.1.0"
        self._write_sources()
        conflict = self.plan(request)
        operation = next(item for item in conflict["operations"] if item["path"] == "AGENTS.md")
        self.assertEqual(operation["action"], "conflict")
        with self.assertRaisesRegex(MaterializationError, "not materializable"):
            self.apply(conflict)

        agents.write_text(f"{MANAGED_BEGIN}\n{MANAGED_END}\n{MANAGED_BEGIN}\n{MANAGED_END}\n", encoding="utf-8")
        duplicate = self.plan(request)
        operation = next(item for item in duplicate["operations"] if item["path"] == "AGENTS.md")
        self.assertEqual(operation["action"], "conflict")

    def test_existing_continuity_is_preserved_without_reviewed_migration(self) -> None:
        existing = b"# Detailed existing checkpoint\n\nDo not discard this useful state.\n"
        (self.target / "CONTINUITY.md").write_bytes(existing)
        plan = self.plan()
        operation = next(item for item in plan["operations"] if item["path"] == "CONTINUITY.md")
        self.assertEqual(operation["action"], "preserve")
        self.apply(plan)
        self.assertEqual((self.target / "CONTINUITY.md").read_bytes(), existing)
        self.assertEqual(verify_continuity_target(self.target), [])

    def test_mapping_order_does_not_change_rendered_bytes_or_plan(self) -> None:
        request = self.request(providers=["github-copilot"])
        reordered = reverse_mapping_order(request)
        self.assertEqual(self.plan(request), self.plan(reordered))

    def test_pinned_template_supplies_static_protocol_text(self) -> None:
        artifact = self._artifact("continuity-template")
        path = self.aether / str(artifact["path"])
        changed = path.read_bytes().replace(
            b"Surface missing, stale, or conflicting evidence.",
            b"Surface missing, stale, unavailable, or conflicting evidence.",
        )
        self.assertNotEqual(changed, path.read_bytes())
        self._write_artifact("continuity-template", changed)
        write_json(self.profile_path, self.profile)
        plan = self.plan()
        continuity = next(
            item for item in plan["operations"] if item["path"] == "CONTINUITY.md"
        )
        self.assertIn(
            "Surface missing, stale, unavailable, or conflicting evidence.",
            continuity["proposed_content"],
        )

    def test_malformed_enum_values_return_errors_instead_of_crashing(self) -> None:
        request = self.request()
        request["mode"] = []
        request["repository"]["visibility"] = []
        request["continuity"]["review"]["status"] = []
        errors = validate_continuity_request(request, self.profile)
        self.assertIn("request.mode is unsupported", errors)
        self.assertIn("request.repository.visibility is unsupported", errors)

    def test_invalid_timestamps_and_injected_structure_fail_closed(self) -> None:
        request = self.request()
        request["continuity"]["document"]["updated_at"] = "today"
        errors = validate_continuity_request(request, self.profile)
        self.assertIn(
            "continuity.document.updated_at must be an RFC 3339 date-time",
            errors,
        )

        request = self.request()
        request["sections"]["completed_changes"] = [
            "Unexpected nested heading.\n\n## Resume protocol"
        ]
        with self.assertRaisesRegex(MaterializationError, "required headings"):
            self.plan(request)

    def test_reviewed_continuity_migration_is_compare_and_swap_and_reversible(self) -> None:
        existing = b"# Legacy checkpoint\n\nUseful Antidote-specific state.\n"
        continuity_path = self.target / "CONTINUITY.md"
        continuity_path.write_bytes(existing)
        request = self.request()
        request["continuity_migration"] = {
            "expected_sha256": digest(existing),
            "reason": "Map every legacy section into the reviewed v1 checkpoint.",
            "evidence_url": "https://github.com/egohygiene/holon/issues/45",
        }
        invalid_evidence = copy.deepcopy(request)
        invalid_evidence["continuity_migration"]["evidence_url"] = "https://["
        errors = validate_continuity_request(invalid_evidence, self.profile)
        self.assertIn(
            "request.continuity_migration.evidence_url must be an https URL",
            errors,
        )
        with self.assertRaisesRegex(MaterializationError, "evidence_url"):
            self.plan(invalid_evidence)
        self.assertEqual(continuity_path.read_bytes(), existing)

        plan = self.plan(request)
        operation = next(item for item in plan["operations"] if item["path"] == "CONTINUITY.md")
        self.assertEqual(operation["action"], "update")
        self.assertIn("Legacy checkpoint", operation["diff"])
        self.apply(plan)
        self.assertIn("aether.repository-continuity/v1", continuity_path.read_text(encoding="utf-8"))
        repeated = self.plan(request)
        self.assertEqual(repeated["summary"], {"noop": 2})
        before_repeat = {
            path.relative_to(self.target).as_posix(): path.read_bytes()
            for path in sorted(self.target.rglob("*"))
            if path.is_file()
        }
        self.apply(repeated)
        self.assertEqual(
            {
                path.relative_to(self.target).as_posix(): path.read_bytes()
                for path in sorted(self.target.rglob("*"))
                if path.is_file()
            },
            before_repeat,
        )
        rollback_continuity_target(self.target)
        self.assertEqual(continuity_path.read_bytes(), existing)

        request["continuity_migration"]["expected_sha256"] = "0" * 64
        conflict = self.plan(request)
        operation = next(item for item in conflict["operations"] if item["path"] == "CONTINUITY.md")
        self.assertEqual(operation["action"], "conflict")

    def test_provisional_output_exposes_unknowns(self) -> None:
        request = self.request(mode="provisional")
        request["continuity"]["state"]["live"]["status"] = "unavailable"
        request["continuity"]["state"]["live"]["default_branch_revision"] = None
        request["continuity"]["state"]["live"]["notes"] = "Live provider access was unavailable."
        request["continuity"]["work"]["next"]["readiness"] = "unknown"
        request["sections"]["unknowns"] = ["Mutable pull-request state requires review."]
        plan = self.plan(request)
        continuity = next(item for item in plan["operations"] if item["path"] == "CONTINUITY.md")
        self.assertIn("Mutable pull-request state requires review.", continuity["proposed_content"])
        self.assertIn('status: "unavailable"', continuity["proposed_content"])

    def test_opt_out_unsupported_and_parallel_conflict_are_recorded_no_write(self) -> None:
        opt_out = self.request(mode="opt-out")
        opt_out["opt_out"] = {
            "enabled": True,
            "reason": "Maintainers retain a reviewed bespoke handoff.",
            "reference": "https://github.com/egohygiene/example-tool/issues/7",
        }
        opt_out_plan = self.plan(opt_out)
        self.assertEqual(opt_out_plan["summary"], {"opt-out": 2})
        self.assertIsNone(opt_out_plan["next_state"])
        self.assertTrue(all(not item["diff"] for item in opt_out_plan["operations"]))

        unsupported = self.request(mode="unsupported")
        unsupported["repository_profile"] = "generated-mirror"
        unsupported["repository_class"] = "generated"
        unsupported["unsupported_reason"] = "Generated mirrors are outside the v1 profile."
        unsupported_plan = self.plan(unsupported)
        self.assertEqual(unsupported_plan["summary"], {"unsupported": 2})

        candidates = [
            {
                "provider": "github",
                "id": "example/repo#11",
                "url": "https://github.com/example/repo/pull/11",
            },
            {
                "provider": "github",
                "id": "example/repo#12",
                "url": "https://github.com/example/repo/pull/12",
            },
        ]
        parallel = self.request(mode="parallel-conflict", parallel=candidates)
        parallel["parallel_reconciliation"] = None
        parallel_plan = self.plan(parallel)
        self.assertEqual(parallel_plan["summary"], {"conflict": 2})
        with self.assertRaisesRegex(MaterializationError, "not materializable"):
            self.apply(parallel_plan)

    def test_parallel_reconciliation_must_match_continuity_metadata(self) -> None:
        candidates = [
            {
                "provider": "github",
                "id": "example/repo#11",
                "url": "https://github.com/example/repo/pull/11",
            }
        ]
        request = self.request(parallel=candidates)
        request["continuity"]["state"]["parallel_changes"] = []
        errors = validate_continuity_request(request, self.profile)
        self.assertIn(
            "continuity.state.parallel_changes must exactly match parallel_candidates",
            errors,
        )

        request = self.request(parallel=candidates * 2)
        errors = validate_continuity_request(request, self.profile)
        self.assertIn("request.parallel_candidates must not contain duplicates", errors)

        request = self.request()
        request["continuity"]["work"]["active_issue"] = {
            "provider": "github",
            "id": "example/repo#44",
            "url": "https://github.com/another/repo/issues/44",
        }
        errors = validate_continuity_request(request, self.profile)
        self.assertIn(
            "continuity.work.active_issue.url must match its GitHub repository and number",
            errors,
        )

    def test_target_or_plan_changes_after_preview_are_rejected(self) -> None:
        plan = self.plan()
        plan["operations"][0]["proposed_content"] += "tampered"
        with self.assertRaisesRegex(MaterializationError, "digest|plan content"):
            self.apply(plan)

        plan = self.plan()
        (self.target / "AGENTS.md").write_text("late change\n", encoding="utf-8")
        with self.assertRaisesRegex(MaterializationError, "changed after preview"):
            self.apply(plan)

    def test_prior_state_bytes_are_bound_into_the_reviewed_plan(self) -> None:
        request = self.request()
        self.apply(self.plan(request))
        plan = self.plan(request)
        self.assertRegex(plan["prior_state_sha256"], r"^[0-9a-f]{64}$")
        state_path = self.target / STATE_RELATIVE_PATH
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["profile_version"] = state["profile_version"] + "-format-change"
        write_json(state_path, state)
        with self.assertRaisesRegex(MaterializationError, "changed after preview"):
            self.apply(plan)

    def test_symlink_destination_is_a_no_write_conflict(self) -> None:
        outside = self.root / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        (self.target / "AGENTS.md").symlink_to(outside)
        plan = self.plan()
        operation = next(item for item in plan["operations"] if item["path"] == "AGENTS.md")
        self.assertEqual(operation["action"], "conflict")
        self.assertIsNone(plan["next_state"])
        self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")

    def test_symlinked_destination_parent_is_a_no_write_conflict(self) -> None:
        outside = self.root / "outside-provider"
        outside.mkdir()
        (self.target / ".github").symlink_to(outside, target_is_directory=True)
        plan = self.plan(self.request(providers=["github-copilot"]))
        operation = next(
            item
            for item in plan["operations"]
            if item["path"] == ".github/copilot-instructions.md"
        )
        self.assertEqual(operation["action"], "conflict")
        self.assertEqual(list(outside.iterdir()), [])

    def test_non_directory_destination_parent_is_a_no_write_conflict(self) -> None:
        (self.target / ".github").write_text("repository-owned file\n", encoding="utf-8")
        plan = self.plan(self.request(providers=["github-copilot"]))
        operation = next(
            item
            for item in plan["operations"]
            if item["path"] == ".github/copilot-instructions.md"
        )
        self.assertEqual(operation["action"], "conflict")
        self.assertIsNone(plan["next_state"])
        self.assertEqual(
            (self.target / ".github").read_text(encoding="utf-8"),
            "repository-owned file\n",
        )

    def test_symlinked_internal_state_directory_is_rejected(self) -> None:
        outside = self.root / "outside-state"
        outside.mkdir()
        (self.target / ".holon").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(MaterializationError, "unsupported symlink"):
            self.plan()
        self.assertEqual(list(outside.iterdir()), [])

    def test_rejected_apply_leaves_no_lock_or_internal_directory(self) -> None:
        outside = self.root / "outside-lock-test.md"
        outside.write_text("outside\n", encoding="utf-8")
        (self.target / "AGENTS.md").symlink_to(outside)
        plan = self.plan()
        with self.assertRaisesRegex(MaterializationError, "not materializable"):
            self.apply(plan)
        self.assertFalse((self.target / ".holon").exists())
        self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")

    def test_failed_apply_preserves_concurrent_state_edit(self) -> None:
        plan = self.plan()
        concurrent_state = b'{"concurrent":"repository edit"}\n'
        original_atomic_write = continuity_module.atomic_write

        def fail_at_first_surface(path: Path, content: bytes) -> None:
            if path == self.target / "AGENTS.md":
                original_atomic_write(
                    self.target / STATE_RELATIVE_PATH,
                    concurrent_state,
                )
                raise OSError("injected apply failure")
            original_atomic_write(path, content)

        with mock.patch.object(
            continuity_module,
            "atomic_write",
            side_effect=fail_at_first_surface,
        ):
            with self.assertRaisesRegex(MaterializationError, "refused concurrent edits"):
                self.apply(plan)
        self.assertEqual(
            (self.target / STATE_RELATIVE_PATH).read_bytes(),
            concurrent_state,
        )

    def test_fenced_or_inline_markers_are_not_adopted(self) -> None:
        block = self._block("codex-compatible").decode("utf-8")
        agents = self.target / "AGENTS.md"
        for content in (
            f"# Documentation\n\n```markdown\n{block}```\n",
            f"# Documentation\n\n```markdown\n````not-a-closing-fence\n{block}```\n",
            "prefix " + block,
        ):
            agents.write_text(content, encoding="utf-8")
            plan = self.plan()
            operation = next(
                item for item in plan["operations"] if item["path"] == "AGENTS.md"
            )
            self.assertEqual(operation["action"], "conflict")
            self.assertIsNone(plan["next_state"])

    def test_non_utf8_markdown_is_an_exact_no_write_conflict(self) -> None:
        agents = self.target / "AGENTS.md"
        agents.write_bytes(b"\xff\xfe")
        plan = self.plan()
        operation = next(item for item in plan["operations"] if item["path"] == "AGENTS.md")
        self.assertEqual(operation["action"], "conflict")
        self.assertEqual(operation["previous_sha256"], digest(b"\xff\xfe"))
        self.assertIsNone(operation["proposed_content"])
        self.assertEqual(operation["diff"], "")
        self.assertEqual(agents.read_bytes(), b"\xff\xfe")

    def test_mixed_line_endings_have_byte_exact_preview_diffs(self) -> None:
        agents = self.target / "AGENTS.md"
        for content in (
            b"# Authored\r\rText\r",
            b"# Authored\r\nText\rTail",
            "# Authored\u2028Tail".encode("utf-8"),
        ):
            agents.write_bytes(content)
            plan = self.plan()
            operation = next(
                item for item in plan["operations"] if item["path"] == "AGENTS.md"
            )
            self.assertEqual(operation["action"], "update")
            self.assertEqual(operation["previous_sha256"], digest(content))
            patched = subprocess.run(
                ["patch", "--batch", "--strip=1"],
                cwd=self.target,
                input=operation["diff"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(patched.returncode, 0, patched.stderr)
            self.assertEqual(
                agents.read_bytes(),
                operation["proposed_content"].encode("utf-8"),
            )

    def test_rollback_refuses_to_destroy_post_apply_edits(self) -> None:
        self.apply(self.plan())
        continuity = self.target / "CONTINUITY.md"
        continuity.write_bytes(continuity.read_bytes() + b"\nPost-apply repository edit.\n")
        with self.assertRaisesRegex(MaterializationError, "changed after apply"):
            rollback_continuity_target(self.target)

    def test_rollback_prevalidates_every_backup_before_mutating(self) -> None:
        (self.target / "AGENTS.md").write_text("# Authored\n", encoding="utf-8")
        state = self.apply(self.plan())
        rollback_path = self.target / state["rollback_manifest"]
        (rollback_path.parent / "files" / "AGENTS.md").unlink()
        with self.assertRaisesRegex(MaterializationError, "backup is missing"):
            rollback_continuity_target(self.target)
        self.assertTrue((self.target / "CONTINUITY.md").is_file())

    def test_rollback_approval_is_state_bound_and_checked_before_mutation(self) -> None:
        self.apply(self.plan())
        state_path = self.target / STATE_RELATIVE_PATH
        before = {
            path.relative_to(self.target).as_posix(): path.read_bytes()
            for path in sorted(self.target.rglob("*"))
            if path.is_file()
        }
        for expected in ("invalid", "0" * 64):
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(
                    MaterializationError,
                    "expected continuity state SHA-256|changed after rollback approval",
                ):
                    rollback_continuity_target(
                        self.target,
                        expected_state_sha256=expected,
                    )
                after = {
                    path.relative_to(self.target).as_posix(): path.read_bytes()
                    for path in sorted(self.target.rglob("*"))
                    if path.is_file()
                }
                self.assertEqual(after, before)

        rollback_continuity_target(
            self.target,
            expected_state_sha256=digest(state_path.read_bytes()),
        )
        self.assertFalse((self.target / "CONTINUITY.md").exists())
        self.assertFalse((self.target / "AGENTS.md").exists())
        self.assertFalse(state_path.exists())

    def test_failed_rollback_restores_applied_surfaces_and_remains_retryable(self) -> None:
        authored = b"# Authored instructions\n"
        agents = self.target / "AGENTS.md"
        agents.write_bytes(authored)
        self.apply(self.plan())
        continuity = self.target / "CONTINUITY.md"
        state_path = self.target / STATE_RELATIVE_PATH
        applied = {
            "AGENTS.md": agents.read_bytes(),
            "CONTINUITY.md": continuity.read_bytes(),
            STATE_RELATIVE_PATH: state_path.read_bytes(),
        }
        original_atomic_write = continuity_module.atomic_write
        failure_injected = False

        def fail_during_surface_restore(path: Path, content: bytes) -> None:
            nonlocal failure_injected
            if path == agents and content == authored and not failure_injected:
                failure_injected = True
                raise OSError("injected rollback failure")
            original_atomic_write(path, content)

        with mock.patch.object(
            continuity_module,
            "atomic_write",
            side_effect=fail_during_surface_restore,
        ):
            with self.assertRaisesRegex(
                MaterializationError,
                "restored the applied state so rollback can be retried",
            ):
                rollback_continuity_target(self.target)

        self.assertTrue(failure_injected)
        self.assertEqual(agents.read_bytes(), applied["AGENTS.md"])
        self.assertEqual(continuity.read_bytes(), applied["CONTINUITY.md"])
        self.assertEqual(state_path.read_bytes(), applied[STATE_RELATIVE_PATH])
        self.assertEqual(verify_continuity_target(self.target), [])

        rollback_continuity_target(self.target)
        self.assertEqual(agents.read_bytes(), authored)
        self.assertFalse(continuity.exists())
        self.assertFalse(state_path.exists())

    def test_failed_state_restore_reinstates_applied_snapshot_for_retry(self) -> None:
        request = self.request()
        self.apply(self.plan(request))
        state_path = self.target / STATE_RELATIVE_PATH
        prior_state_bytes = state_path.read_bytes()
        continuity = self.target / "CONTINUITY.md"

        updated_request = copy.deepcopy(request)
        updated_request["continuity"]["work"]["objective"] = (
            "Exercise failure-atomic rollback of an updated continuity checkpoint."
        )
        self.apply(self.plan(updated_request))
        applied_state_bytes = state_path.read_bytes()
        applied_continuity_bytes = continuity.read_bytes()
        original_atomic_write = continuity_module.atomic_write
        failure_injected = False

        def fail_after_state_restore(path: Path, content: bytes) -> None:
            nonlocal failure_injected
            original_atomic_write(path, content)
            if (
                path == state_path
                and content == prior_state_bytes
                and not failure_injected
            ):
                failure_injected = True
                raise OSError("injected post-write rollback failure")

        with mock.patch.object(
            continuity_module,
            "atomic_write",
            side_effect=fail_after_state_restore,
        ):
            with self.assertRaisesRegex(
                MaterializationError,
                "restored the applied state so rollback can be retried",
            ):
                rollback_continuity_target(self.target)

        self.assertTrue(failure_injected)
        self.assertEqual(continuity.read_bytes(), applied_continuity_bytes)
        self.assertEqual(state_path.read_bytes(), applied_state_bytes)
        self.assertEqual(verify_continuity_target(self.target), [])

        rollback_continuity_target(self.target)
        self.assertEqual(state_path.read_bytes(), prior_state_bytes)

    def test_malformed_state_and_rollback_are_reported_without_raw_exceptions(self) -> None:
        state = self.apply(self.plan())
        state_path = self.target / STATE_RELATIVE_PATH
        malformed_state = copy.deepcopy(state)
        malformed_state["surfaces"] = [None]
        write_json(state_path, malformed_state)
        self.assertIn("two to four surfaces", verify_continuity_target(self.target)[0])

        write_json(state_path, state)
        rollback_path = self.target / state["rollback_manifest"]
        write_json(rollback_path, [])
        with self.assertRaisesRegex(MaterializationError, "digest does not match state"):
            rollback_continuity_target(self.target)

        malformed_bytes = b"[]\n"
        state["rollback_sha256"] = digest(malformed_bytes)
        write_json(state_path, state)
        with self.assertRaisesRegex(MaterializationError, "metadata is malformed"):
            rollback_continuity_target(self.target)

        state_path.write_bytes(b"\xff")
        self.assertIn("unable to read continuity state", verify_continuity_target(self.target)[0])

    def test_state_verification_rejects_unapproved_source_artifact_kind(self) -> None:
        state = self.apply(self.plan())
        state["source_contracts"][0]["artifacts"][0]["kind"] = "nonsense"
        write_json(self.target / STATE_RELATIVE_PATH, state)
        errors = verify_continuity_target(self.target)
        self.assertTrue(errors)
        self.assertIn("invalid source artifact provenance", errors[0])

    def test_reversed_projection_markers_and_package_import_fail_cleanly(self) -> None:
        reversed_projection = (
            b"# AGENTS.md\n\n"
            + MANAGED_END.encode("utf-8")
            + b"\n"
            + MANAGED_BEGIN.encode("utf-8")
            + b"\n"
        )
        self._write_artifact("codex-repository-instructions", reversed_projection)
        write_json(self.profile_path, self.profile)
        with self.assertRaisesRegex(MaterializationError, "reversed, inline, or fenced"):
            self.plan()

        result = subprocess.run(
            [sys.executable, "-c", "import tools.materialization"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_atomic_write_does_not_follow_a_predictable_temporary_symlink(self) -> None:
        destination = self.target / "atomic.txt"
        outside = self.root / "outside-atomic.txt"
        outside.write_bytes(b"outside\n")
        predictable = destination.with_name(
            f".{destination.name}.holon-tmp-{os.getpid()}"
        )
        predictable.symlink_to(outside)
        atomic_write(destination, b"inside\n")
        self.assertEqual(destination.read_bytes(), b"inside\n")
        self.assertEqual(outside.read_bytes(), b"outside\n")

    def test_atomic_write_honors_new_file_umask(self) -> None:
        for mask, expected in ((0o022, 0o644), (0o077, 0o600)):
            with self.subTest(mask=oct(mask)):
                destination = self.target / f"state-{mask:o}.json"
                previous_umask = os.umask(mask)
                try:
                    atomic_write(destination, b"{}\n")
                finally:
                    os.umask(previous_umask)
                self.assertEqual(destination.stat().st_mode & 0o777, expected)

    def test_plan_validator_rejects_self_hashed_partial_contract(self) -> None:
        malformed = {
            "schema_version": "holon.repository-continuity-plan/v1",
            "authority": {
                "credentials": False,
                "external_write": False,
                "merge": False,
                "publish": False,
            },
            "request": {},
            "operations": [],
        }
        malformed["plan_id"] = digest(canonical_bytes(malformed))
        with self.assertRaisesRegex(MaterializationError, "missing fields"):
            validate_continuity_plan(malformed)

    def test_plan_validator_wraps_unhashable_malformed_values(self) -> None:
        mutations = (
            lambda value: value.__setitem__("mode", []),
            lambda value: value["inputs"].__setitem__("rollout_stage", []),
            lambda value: value["inputs"]["source_contracts"][0].__setitem__(
                "role", []
            ),
            lambda value: value["inputs"]["source_contracts"][0]["artifacts"][
                0
            ].__setitem__("id", []),
            lambda value: value["operations"][0].__setitem__("path", []),
            lambda value: value["operations"][0].__setitem__("action", []),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                malformed = copy.deepcopy(self.plan())
                mutate(malformed)
                payload = {
                    key: value for key, value in malformed.items() if key != "plan_id"
                }
                malformed["plan_id"] = digest(canonical_bytes(payload))
                with self.assertRaises(MaterializationError):
                    validate_continuity_plan(malformed)

    def test_public_schemas_track_runtime_artifact_shapes(self) -> None:
        schemas = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in (ROOT / "schemas").glob("repository-continuity-*.schema.json")
        }
        expected_ids = {
            "repository-continuity-request.v1.schema.json": (
                "https://egohygiene.io/schemas/holon/repository-continuity-request.v1.schema.json"
            ),
            "repository-continuity-plan.v1.schema.json": (
                "https://egohygiene.io/schemas/holon/repository-continuity-plan.v1.schema.json"
            ),
            "repository-continuity-state.v1.schema.json": (
                "https://egohygiene.io/schemas/holon/repository-continuity-state.v1.schema.json"
            ),
            "repository-continuity-rollback.v1.schema.json": (
                "https://egohygiene.io/schemas/holon/repository-continuity-rollback.v1.schema.json"
            ),
        }
        for name, schema_id in expected_ids.items():
            self.assertEqual(schemas[name]["$id"], schema_id)

        request = self.request(providers=["github-copilot", "claude-code"])
        plan = self.plan(request)
        plan_schema = schemas["repository-continuity-plan.v1.schema.json"]
        self.assertEqual(set(plan), set(plan_schema["required"]))
        self.assertEqual(
            set(plan["inputs"]),
            set(plan_schema["$defs"]["inputs"]["required"]),
        )
        operation_required = set(plan_schema["$defs"]["operation"]["required"])
        self.assertTrue(
            all(set(operation) == operation_required for operation in plan["operations"])
        )

        state_schema = schemas["repository-continuity-state.v1.schema.json"]
        self.assertEqual(
            set(plan["next_state"]),
            set(state_schema["$defs"]["stateWithoutApply"]["required"]),
        )
        state = self.apply(plan)
        self.assertEqual(
            set(state),
            set(state_schema["$defs"]["stateWithApply"]["required"]),
        )
        rollback = json.loads(
            (self.target / state["rollback_manifest"]).read_text(encoding="utf-8")
        )
        rollback_schema = schemas["repository-continuity-rollback.v1.schema.json"]
        self.assertEqual(set(rollback), set(rollback_schema["required"]))
        rollback_required = set(rollback_schema["$defs"]["operation"]["required"])
        self.assertTrue(
            all(set(operation) == rollback_required for operation in rollback["operations"])
        )


if __name__ == "__main__":
    unittest.main()
