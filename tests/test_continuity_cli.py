"""Focused contract tests for the repository-continuity CLI boundary."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import holon_materialize as cli  # noqa: E402


class ContinuityCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preview_schema = json.loads(
            (
                ROOT / "schemas" / "repository-continuity-preview.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        cls.result_schema = json.loads(
            (
                ROOT
                / "schemas"
                / "repository-continuity-cli-result.v1.schema.json"
            ).read_text(encoding="utf-8")
        )

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = self.root / "target"
        self.target.mkdir()
        self.artifacts = self.root / "review-artifacts"
        self.artifacts.mkdir()
        self.plan = self._plan()

    def _plan(self) -> dict[str, object]:
        operations = [
            {
                "action": "create",
                "path": "AGENTS.md",
                "reason": "required agent handoff pointer is missing",
                "previous_sha256": None,
                "proposed_sha256": "1" * 64,
                "managed_block_sha256": "2" * 64,
                "diff": "--- a/AGENTS.md\n+++ b/AGENTS.md\n",
            },
            {
                "action": "create",
                "path": "CONTINUITY.md",
                "reason": "required continuity checkpoint is missing",
                "previous_sha256": None,
                "proposed_sha256": "3" * 64,
                "managed_block_sha256": None,
                "diff": "--- a/CONTINUITY.md\n+++ b/CONTINUITY.md\n",
            },
        ]
        return {
            "schema_version": "holon.repository-continuity-plan/v1",
            "plan_id": "a" * 64,
            "repository": "egohygiene/holon",
            "mode": "provisional",
            "summary": {"create": 2},
            "authority": {
                "credentials": False,
                "external_write": False,
                "merge": False,
                "publish": False,
            },
            "operations": operations,
            "next_state": {"planned": True},
        }

    def _write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def _run(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = cli.main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def assert_digest_or_none(self, value: object) -> None:
        if value is not None:
            self.assertIsInstance(value, str)
            self.assertRegex(value, r"^[0-9a-f]{64}$")

    def assert_result_contract(self, value: dict[str, object]) -> None:
        schema = self.result_schema
        self.assertEqual(set(value), set(schema["required"]))
        self.assertEqual(
            value["schema_version"],
            schema["properties"]["schema_version"]["const"],
        )
        self.assertIn(value["command"], schema["properties"]["command"]["enum"])
        self.assertIn(value["status"], schema["properties"]["status"]["enum"])
        self.assertIsInstance(value["code"], str)
        self.assertRegex(value["code"], schema["properties"]["code"]["pattern"])
        self.assertIs(type(value["ok"]), bool)
        for key in (
            "plan_id",
            "preview_id",
            "state_sha256",
            "reviewed_state_sha256",
        ):
            self.assert_digest_or_none(value[key])
        self.assertTrue(
            value["materializable"] is None
            or type(value["materializable"]) is bool
        )
        summary = value["summary"]
        if summary is not None:
            self.assertIsInstance(summary, dict)
            allowed = set(
                schema["properties"]["summary"]["oneOf"][0]["propertyNames"][
                    "enum"
                ]
            )
            self.assertLessEqual(set(summary), allowed)
            self.assertTrue(
                all(type(count) is int and count >= 0 for count in summary.values())
            )
        self.assertIsInstance(value["errors"], list)
        self.assertTrue(
            all(isinstance(error, str) and error for error in value["errors"])
        )
        self.assertIsInstance(value["corrective_action"], str)
        self.assertTrue(value["corrective_action"])

    def assert_preview_contract(self, value: dict[str, object]) -> None:
        schema = self.preview_schema
        self.assertEqual(set(value), set(schema["required"]))
        self.assertEqual(
            value["schema_version"],
            schema["properties"]["schema_version"]["const"],
        )
        self.assertEqual(
            value["plan_schema_version"],
            schema["properties"]["plan_schema_version"]["const"],
        )
        self.assert_digest_or_none(value["plan_id"])
        self.assert_digest_or_none(value["preview_id"])
        self.assertIsInstance(value["repository"], str)
        self.assertRegex(
            value["repository"],
            schema["properties"]["repository"]["pattern"],
        )
        self.assertIn(value["mode"], schema["properties"]["mode"]["enum"])
        self.assertIs(type(value["materializable"]), bool)
        self.assertEqual(
            value["authority"],
            {
                "credentials": False,
                "external_write": False,
                "merge": False,
                "publish": False,
            },
        )
        self.assertIsInstance(value["summary"], dict)
        self.assertTrue(
            all(type(count) is int and count >= 0 for count in value["summary"].values())
        )
        operations = value["operations"]
        self.assertIsInstance(operations, list)
        self.assertGreaterEqual(len(operations), 2)
        self.assertLessEqual(len(operations), 4)
        operation_schema = schema["$defs"]["operation"]
        for operation in operations:
            self.assertEqual(set(operation), set(operation_schema["required"]))
            self.assertIn(
                operation["action"],
                operation_schema["properties"]["action"]["enum"],
            )
            self.assertIn(
                operation["path"],
                operation_schema["properties"]["path"]["enum"],
            )
            self.assertIsInstance(operation["reason"], str)
            self.assertTrue(operation["reason"])
            for key in (
                "previous_sha256",
                "proposed_sha256",
                "managed_block_sha256",
            ):
                self.assert_digest_or_none(operation[key])
            self.assertIsInstance(operation["diff"], str)

    def test_preview_receipt_is_deterministic_and_exact(self) -> None:
        with mock.patch.object(cli, "validate_continuity_plan"):
            first = cli.build_continuity_preview_receipt(self.plan)
            second = cli.build_continuity_preview_receipt(self.plan)
            self.assertEqual(first, second)
            self.assert_preview_contract(first)
            self.assertEqual(
                first["schema_version"],
                "holon.repository-continuity-preview/v1",
            )
            self.assertRegex(first["preview_id"], r"^[0-9a-f]{64}$")
            self.assertTrue(first["materializable"])
            self.assertEqual(
                set(first["operations"][0]),
                {
                    "action",
                    "path",
                    "reason",
                    "previous_sha256",
                    "proposed_sha256",
                    "managed_block_sha256",
                    "diff",
                },
            )

            changed = json.loads(json.dumps(first))
            changed["operations"][0]["diff"] += "tampered"
            with self.assertRaisesRegex(
                cli.ContinuityCliError,
                "does not match the exact continuity plan",
            ):
                cli.validate_continuity_preview_receipt(changed, self.plan)

    def test_apply_requires_receipt_and_exact_reviewed_plan_id_before_writes(self) -> None:
        plan_path = self.artifacts / "plan.json"
        receipt_path = self.artifacts / "preview.json"
        self._write_json(plan_path, self.plan)
        with mock.patch.object(cli, "validate_continuity_plan"):
            receipt = cli.build_continuity_preview_receipt(self.plan)
        self._write_json(receipt_path, receipt)

        with mock.patch.object(cli, "apply_continuity_plan") as apply:
            exit_code, stdout, stderr = self._run(
                [
                    "continuity",
                    "apply",
                    "--plan",
                    str(plan_path),
                    "--target",
                    str(self.target),
                    "--aether-source",
                    str(self.root / "aether"),
                ]
            )
        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        error = json.loads(stderr)
        self.assert_result_contract(error)
        self.assertEqual(error["code"], "invalid-arguments")
        self.assertIn("continuity apply --help", error["corrective_action"])
        apply.assert_not_called()

        with (
            mock.patch.object(cli, "validate_continuity_plan"),
            mock.patch.object(cli, "apply_continuity_plan") as apply,
        ):
            exit_code, stdout, stderr = self._run(
                [
                    "continuity",
                    "apply",
                    "--plan",
                    str(plan_path),
                    "--preview-receipt",
                    str(receipt_path),
                    "--reviewed-plan-id",
                    "b" * 64,
                    "--target",
                    str(self.target),
                    "--aether-source",
                    str(self.root / "aether"),
                ]
            )
        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "")
        error = json.loads(stderr)
        self.assert_result_contract(error)
        self.assertEqual(error["code"], "review-required")
        self.assertIn("exact plan_id", error["corrective_action"])
        apply.assert_not_called()
        self.assertEqual(list(self.target.iterdir()), [])

    def test_successful_apply_reports_current_state_digest(self) -> None:
        plan_path = self.artifacts / "plan.json"
        receipt_path = self.artifacts / "preview.json"
        self._write_json(plan_path, self.plan)
        with mock.patch.object(cli, "validate_continuity_plan"):
            receipt = cli.build_continuity_preview_receipt(self.plan)
        self._write_json(receipt_path, receipt)
        state_bytes = b'{"state":"applied"}\n'

        def apply_plan(*_args: object, **_kwargs: object) -> None:
            state_path = self.target / cli.CONTINUITY_STATE_RELATIVE_PATH
            state_path.parent.mkdir(parents=True)
            state_path.write_bytes(state_bytes)

        with (
            mock.patch.object(cli, "validate_continuity_plan"),
            mock.patch.object(cli, "apply_continuity_plan", side_effect=apply_plan),
        ):
            exit_code, stdout, stderr = self._run(
                [
                    "continuity",
                    "apply",
                    "--plan",
                    str(plan_path),
                    "--preview-receipt",
                    str(receipt_path),
                    "--reviewed-plan-id",
                    "a" * 64,
                    "--target",
                    str(self.target),
                    "--aether-source",
                    str(self.root / "aether"),
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        result = json.loads(stdout)
        self.assert_result_contract(result)
        self.assertEqual(result["code"], "plan-applied")
        self.assertEqual(result["state_sha256"], cli.sha256_bytes(state_bytes))
        self.assertIsNone(result["reviewed_state_sha256"])

    def test_plan_and_preview_artifacts_cannot_live_inside_target_or_use_symlinks(self) -> None:
        request = self.target / "request.json"
        self._write_json(request, {})
        with mock.patch.object(cli, "build_continuity_plan") as build:
            exit_code, stdout, stderr = self._run(
                [
                    "continuity",
                    "plan",
                    "--request",
                    str(request),
                    "--target",
                    str(self.target),
                    "--aether-source",
                    str(self.root / "aether"),
                    "--output",
                    str(self.target / "plan.json"),
                ]
            )
        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(json.loads(stderr)["code"], "unsafe-artifact-path")
        build.assert_not_called()

        outside = self.root / "outside.json"
        outside.write_text("{}\n", encoding="utf-8")
        symlink = self.artifacts / "preview.json"
        try:
            symlink.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks are unavailable")
        plan_path = self.artifacts / "plan.json"
        self._write_json(plan_path, self.plan)
        exit_code, stdout, stderr = self._run(
            [
                "continuity",
                "preview",
                "--plan",
                str(plan_path),
                "--target",
                str(self.target),
                "--output",
                str(symlink),
            ]
        )
        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(json.loads(stderr)["code"], "unsafe-artifact-path")
        self.assertEqual(outside.read_text(encoding="utf-8"), "{}\n")

    def test_rollback_reports_post_command_state_separately_from_approval(self) -> None:
        state_path = self.target / cli.CONTINUITY_STATE_RELATIVE_PATH
        state_path.parent.mkdir(parents=True)
        state_bytes = b'{"state":"current"}\n'
        state_path.write_bytes(state_bytes)
        expected = cli.sha256_bytes(state_bytes)

        def rollback(
            target: Path,
            *,
            expected_state_sha256: str | None = None,
        ) -> None:
            self.assertEqual(Path(target), self.target)
            self.assertEqual(expected_state_sha256, expected)
            state_path.unlink()

        with mock.patch.object(
            cli,
            "rollback_continuity_target",
            side_effect=rollback,
        ):
            exit_code, stdout, stderr = self._run(
                [
                    "continuity",
                    "rollback",
                    "--target",
                    str(self.target),
                    "--expected-state-sha256",
                    expected,
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        result = json.loads(stdout)
        self.assert_result_contract(result)
        self.assertIsNone(result["state_sha256"])
        self.assertEqual(result["reviewed_state_sha256"], expected)

    def test_preview_and_cli_result_schemas_are_closed_and_versioned(self) -> None:
        preview = self.preview_schema
        result = self.result_schema
        self.assertFalse(preview["additionalProperties"])
        self.assertFalse(result["additionalProperties"])
        self.assertEqual(
            preview["$id"],
            "https://egohygiene.io/schemas/holon/repository-continuity-preview.v1.schema.json",
        )
        self.assertEqual(
            result["$id"],
            "https://egohygiene.io/schemas/holon/repository-continuity-cli-result.v1.schema.json",
        )
        self.assertIn("reviewed_state_sha256", result["required"])

    def test_generic_plan_success_output_remains_compatible(self) -> None:
        output = self.root / "generic-plan.json"
        generic_plan = {
            "plan_id": "c" * 64,
            "operations": [{"action": "noop"}],
            "summary": {"noop": 1},
        }
        with (
            mock.patch.object(cli, "resolve_foundation_manifest", return_value={}),
            mock.patch.object(cli, "build_plan", return_value=(generic_plan, {})),
        ):
            exit_code, stdout, stderr = self._run(
                [
                    "plan",
                    "--manifest",
                    str(self.root / "manifest.json"),
                    "--target",
                    str(self.target),
                    "--output",
                    str(output),
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout,
            f"wrote plan {output} (cccccccccccc): 1 operations, 0 conflict(s)\n",
        )
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), generic_plan)

    def test_generic_parser_and_runtime_errors_remain_prose_compatible(self) -> None:
        exit_code, stdout, stderr = self._run(["verify"])
        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn(" verify [-h] --target TARGET", stderr)
        self.assertIn(
            "error: the following arguments are required: --target",
            stderr,
        )
        with mock.patch.object(cli, "verify_target", return_value=["legacy drift"]):
            exit_code, stdout, stderr = self._run(
                ["verify", "--target", str(self.target)]
            )
        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "verify failed: legacy drift\n")
        with self.assertRaises(json.JSONDecodeError):
            json.loads(stderr)


if __name__ == "__main__":
    unittest.main()
