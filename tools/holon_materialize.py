#!/usr/bin/env python3
"""Plan, render, verify, and roll back Holon repository materializations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from holon_contract import load_json, resolve_manifest
from materialization import (
    CONTINUITY_STATE_RELATIVE_PATH,
    MaterializationError,
    apply_continuity_plan,
    build_plan,
    build_continuity_plan,
    render_plan,
    rollback_continuity_target,
    rollback_target,
    validate_continuity_plan,
    verify_continuity_target,
    verify_target,
)
from materialization.common import (
    atomic_write,
    canonical_bytes,
    load_state,
    pretty_json_bytes,
    sha256_bytes,
    validate_target_root,
)


ROOT = Path(__file__).resolve().parents[1]
CONTINUITY_PROFILE = ROOT / "catalog" / "repository-continuity-materialization.json"
CONTINUITY_PREVIEW_SCHEMA = "holon.repository-continuity-preview/v1"
CONTINUITY_CLI_RESULT_SCHEMA = "holon.repository-continuity-cli-result/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NON_MATERIALIZABLE_ACTIONS = {"conflict", "opt-out", "unsupported"}


class CliUsageError(ValueError):
    """Raised when argparse rejects a command without writing prose first."""

    def __init__(self, parser: argparse.ArgumentParser, message: str) -> None:
        super().__init__(message)
        self.parser = parser


class ContinuityCliError(MaterializationError):
    """Carry a stable CLI error code and an actionable recovery instruction."""

    def __init__(self, code: str, message: str, corrective_action: str) -> None:
        super().__init__(message)
        self.code = code
        self.corrective_action = corrective_action


class HolonArgumentParser(argparse.ArgumentParser):
    """Defer usage failures so continuity commands can emit JSON-only errors."""

    def error(self, message: str) -> None:
        raise CliUsageError(self, message)


def resolve_foundation_manifest(catalog_path: Path, manifest_path: Path) -> dict[str, Any]:
    """Resolve one foundation manifest through the existing HOL-01 contract."""
    try:
        catalog = load_json(catalog_path)
        manifest = load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise MaterializationError(f"unable to load foundation inputs: {error}") from error
    resolved, errors = resolve_manifest(catalog, manifest)
    if errors:
        raise MaterializationError("foundation manifest is invalid: " + "; ".join(errors))
    assert resolved is not None
    return resolved


def _sha256_argument(value: str) -> str:
    """Require one complete lowercase SHA-256 CLI acknowledgement."""
    if SHA256_RE.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(
            "must be a complete 64-character lowercase SHA-256 digest"
        )
    return value


def _requested_top_level_command(argv: list[str]) -> str | None:
    """Return the top-level command without mistaking --catalog's value for it."""
    skip_next = False
    for argument in argv:
        if skip_next:
            skip_next = False
            continue
        if argument == "--catalog":
            skip_next = True
            continue
        if argument.startswith("--catalog="):
            continue
        if not argument.startswith("-"):
            return argument
    return None


def _absolute_lexical_path(path: Path) -> Path:
    """Normalize an absolute path without silently accepting symlink components."""
    return Path(os.path.abspath(os.fspath(path)))


def _reject_symlink_components(path: Path, label: str) -> None:
    """Reject symlinks at the named artifact or any existing ancestor."""
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise ContinuityCliError(
                "unsafe-artifact-path",
                f"{label} uses a symlink path component: {candidate}",
                f"Choose a regular {label} path outside the target repository and rerun the command.",
            )


def _external_artifact_path(
    path: Path,
    target: Path,
    label: str,
    *,
    must_exist: bool,
) -> Path:
    """Validate a plan or preview artifact path outside the consumer target."""
    target_root = validate_target_root(target)
    artifact = _absolute_lexical_path(path)
    _reject_symlink_components(artifact, label)
    if artifact == target_root or target_root in artifact.parents:
        raise ContinuityCliError(
            "unsafe-artifact-path",
            f"{label} must be outside the target repository",
            f"Choose a regular {label} path outside {target_root} and rerun the command.",
        )
    if must_exist:
        if not artifact.is_file():
            raise ContinuityCliError(
                "invalid-input",
                f"{label} is missing or is not a regular file: {artifact}",
                f"Create the {label} with the preceding continuity command, then rerun this command.",
            )
    elif artifact.exists() and not artifact.is_file():
        raise ContinuityCliError(
            "unsafe-artifact-path",
            f"{label} output exists but is not a regular file: {artifact}",
            f"Choose a new regular {label} path outside the target repository and rerun the command.",
        )
    return artifact


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one required JSON object with a bounded, actionable error."""
    try:
        value = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ContinuityCliError(
            "invalid-input",
            f"unable to load {label}: {error}",
            f"Correct the {label} JSON and rerun the command.",
        ) from error
    if not isinstance(value, dict):
        raise ContinuityCliError(
            "invalid-input",
            f"{label} must contain one JSON object",
            f"Correct the {label} JSON and rerun the command.",
        )
    return value


def _write_review_artifact(path: Path, value: dict[str, Any], label: str) -> None:
    """Write a deterministic artifact without replacing different reviewed bytes."""
    content = pretty_json_bytes(value)
    if path.exists():
        try:
            current = path.read_bytes()
        except OSError as error:
            raise ContinuityCliError(
                "io-failed",
                f"unable to read existing {label}: {error}",
                f"Choose a writable {label} path and rerun the command.",
            ) from error
        if current != content:
            raise ContinuityCliError(
                "artifact-exists",
                f"{label} already exists with different bytes: {path}",
                f"Choose a new {label} path or remove the old artifact after review, then rerun the command.",
            )
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _reject_symlink_components(path, label)
        atomic_write(path, content)
    except ContinuityCliError:
        raise
    except OSError as error:
        raise ContinuityCliError(
            "io-failed",
            f"unable to write {label}: {error}",
            f"Choose a writable {label} path and rerun the command.",
        ) from error


def _continuity_plan_is_materializable(plan: dict[str, Any]) -> bool:
    """Return whether a validated plan contains an applicable next state."""
    return plan.get("next_state") is not None and all(
        operation.get("action") not in NON_MATERIALIZABLE_ACTIONS
        for operation in plan.get("operations", [])
    )


def build_continuity_preview_receipt(plan: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic, content-addressed receipt for exact plan review."""
    validate_continuity_plan(plan)
    payload = {
        "schema_version": CONTINUITY_PREVIEW_SCHEMA,
        "plan_schema_version": plan["schema_version"],
        "plan_id": plan["plan_id"],
        "repository": plan["repository"],
        "mode": plan["mode"],
        "summary": plan["summary"],
        "materializable": _continuity_plan_is_materializable(plan),
        "authority": plan["authority"],
        "operations": [
            {
                "action": operation["action"],
                "path": operation["path"],
                "reason": operation["reason"],
                "previous_sha256": operation["previous_sha256"],
                "proposed_sha256": operation["proposed_sha256"],
                "managed_block_sha256": operation["managed_block_sha256"],
                "diff": operation["diff"],
            }
            for operation in plan["operations"]
        ],
    }
    receipt = dict(payload)
    receipt["preview_id"] = sha256_bytes(canonical_bytes(payload))
    return receipt


def validate_continuity_preview_receipt(
    receipt: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    """Require a receipt produced from the exact validated plan."""
    expected = build_continuity_preview_receipt(plan)
    if receipt != expected:
        raise ContinuityCliError(
            "review-required",
            "preview receipt does not match the exact continuity plan",
            "Run continuity preview for this plan, inspect every operation, and retry apply with its exact plan ID.",
        )


def _no_write_corrective_action(plan: dict[str, Any]) -> str:
    """Describe the exact next step for a non-materializable disposition."""
    actions = {operation["action"] for operation in plan["operations"]}
    if "conflict" in actions:
        return "Reconcile every reported conflict, create a new plan, and run continuity preview again."
    if "opt-out" in actions:
        return "Do not run apply; retain the reviewed repository opt-out and its evidence."
    return "Do not run apply; select a supported repository profile, create a new plan, and run continuity preview again."


def _result(
    *,
    command: str,
    status: str,
    code: str,
    ok: bool,
    corrective_action: str,
    plan_id: str | None = None,
    preview_id: str | None = None,
    state_sha256: str | None = None,
    reviewed_state_sha256: str | None = None,
    materializable: bool | None = None,
    summary: dict[str, int] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    """Build one closed machine-readable continuity CLI result."""
    return {
        "schema_version": CONTINUITY_CLI_RESULT_SCHEMA,
        "command": command,
        "status": status,
        "code": code,
        "ok": ok,
        "plan_id": plan_id,
        "preview_id": preview_id,
        "state_sha256": state_sha256,
        "reviewed_state_sha256": reviewed_state_sha256,
        "materializable": materializable,
        "summary": summary,
        "errors": errors or [],
        "corrective_action": corrective_action,
    }


def _emit_json(value: dict[str, Any], *, error: bool = False) -> None:
    """Emit exactly one deterministic JSON document."""
    stream = sys.stderr if error else sys.stdout
    stream.write(pretty_json_bytes(value).decode("utf-8"))


def build_parser() -> argparse.ArgumentParser:
    """Build the Holon materialization command-line interface."""
    parser = HolonArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("catalog/foundation.json"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Resolve inputs and write a dry-run change plan.")
    plan.add_argument("--manifest", type=Path, required=True)
    plan.add_argument("--target", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--render-source", type=Path)
    plan.add_argument("--render-overlay", type=Path, action="append", default=[])
    plan.add_argument("--aether-source", type=Path)

    render = subparsers.add_parser("render", help="Apply one previously reviewed plan.")
    render.add_argument("--plan", type=Path, required=True)
    render.add_argument("--target", type=Path, required=True)
    render.add_argument("--render-source", type=Path)
    render.add_argument("--render-overlay", type=Path, action="append", default=[])
    render.add_argument("--aether-source", type=Path)

    verify = subparsers.add_parser("verify", help="Verify the current generated ownership state.")
    verify.add_argument("--target", type=Path, required=True)

    rollback = subparsers.add_parser("rollback", help="Revert the latest safe materialization.")
    rollback.add_argument("--target", type=Path, required=True)

    continuity = subparsers.add_parser(
        "continuity",
        help="Plan, explicitly preview, apply, verify, or roll back repository continuity.",
    )
    continuity_commands = continuity.add_subparsers(
        dest="continuity_command",
        required=True,
    )

    continuity_plan = continuity_commands.add_parser(
        "plan",
        help="Build a dry-run plan; next run continuity preview.",
    )
    continuity_plan.add_argument(
        "--request",
        type=Path,
        required=True,
        help="Closed v1 request JSON populated from inspected repository evidence.",
    )
    continuity_plan.add_argument("--target", type=Path, required=True)
    continuity_plan.add_argument(
        "--profile",
        type=Path,
        default=CONTINUITY_PROFILE,
        help="Pinned continuity materialization profile (defaults to Holon's canonical profile).",
    )
    continuity_plan.add_argument(
        "--aether-source",
        type=Path,
        required=True,
        help="Local Aether checkout at the exact portable-contract revision; no fetch occurs.",
    )
    continuity_plan.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Plan artifact path outside the target repository.",
    )

    continuity_preview = continuity_commands.add_parser(
        "preview",
        help="Validate a plan and create the exact receipt required by continuity apply.",
    )
    continuity_preview.add_argument("--plan", type=Path, required=True)
    continuity_preview.add_argument("--target", type=Path, required=True)
    continuity_preview.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Preview receipt path outside the target repository.",
    )

    continuity_apply = continuity_commands.add_parser(
        "apply",
        help="Apply only an exact plan with its preview receipt and reviewed plan ID.",
    )
    continuity_apply.add_argument("--plan", type=Path, required=True)
    continuity_apply.add_argument("--preview-receipt", type=Path, required=True)
    continuity_apply.add_argument(
        "--reviewed-plan-id",
        type=_sha256_argument,
        required=True,
        help="Exact plan_id copied only after inspecting the preview receipt.",
    )
    continuity_apply.add_argument("--target", type=Path, required=True)
    continuity_apply.add_argument(
        "--profile",
        type=Path,
        default=CONTINUITY_PROFILE,
    )
    continuity_apply.add_argument("--aether-source", type=Path, required=True)

    continuity_verify = continuity_commands.add_parser(
        "verify",
        help="Read and verify current continuity state and owned regions without writing.",
    )
    continuity_verify.add_argument("--target", type=Path, required=True)

    continuity_rollback = continuity_commands.add_parser(
        "rollback",
        help="Roll back only the state whose current digest was explicitly reviewed.",
    )
    continuity_rollback.add_argument("--target", type=Path, required=True)
    continuity_rollback.add_argument(
        "--expected-state-sha256",
        type=_sha256_argument,
        required=True,
        help=f"Exact current SHA-256 of {CONTINUITY_STATE_RELATIVE_PATH}.",
    )
    return parser


def _current_continuity_state_sha256(target: Path) -> str | None:
    """Read the current state digest, or return None when rollback removed it."""
    target_root = validate_target_root(target)
    state_path = target_root / CONTINUITY_STATE_RELATIVE_PATH
    _reject_symlink_components(state_path, "continuity state")
    if not state_path.exists():
        return None
    if not state_path.is_file():
        raise ContinuityCliError(
            "invalid-state",
            f"continuity state is not a regular file: {CONTINUITY_STATE_RELATIVE_PATH}",
            "Restore a regular continuity state file from reviewed evidence before continuing.",
        )
    try:
        return sha256_bytes(state_path.read_bytes())
    except OSError as error:
        raise ContinuityCliError(
            "io-failed",
            f"unable to read continuity state: {error}",
            "Restore read access to the continuity state and rerun the command.",
        ) from error


def _continuity_state_sha256(target: Path) -> str:
    """Require and return the current continuity state digest."""
    digest = _current_continuity_state_sha256(target)
    if digest is None:
        raise ContinuityCliError(
            "state-missing",
            f"continuity state is missing: {CONTINUITY_STATE_RELATIVE_PATH}",
            "Run continuity apply successfully before verify or rollback.",
        )
    return digest


def _run_continuity(arguments: argparse.Namespace) -> int:
    """Run one continuity command and emit its versioned JSON result."""
    command = arguments.continuity_command
    if command == "plan":
        target = validate_target_root(arguments.target)
        output = _external_artifact_path(
            arguments.output,
            target,
            "continuity plan",
            must_exist=False,
        )
        request = _load_json_object(arguments.request, "continuity request")
        plan = build_continuity_plan(
            request,
            target,
            profile_path=arguments.profile,
            aether_source=arguments.aether_source,
        )
        validate_continuity_plan(plan)
        _write_review_artifact(output, plan, "continuity plan")
        materializable = _continuity_plan_is_materializable(plan)
        corrective_action = (
            "Run continuity preview for this plan, inspect every operation, and retain its receipt before apply."
            if materializable
            else _no_write_corrective_action(plan)
        )
        _emit_json(
            _result(
                command=command,
                status="planned",
                code="plan-created",
                ok=True,
                plan_id=plan["plan_id"],
                materializable=materializable,
                summary=plan["summary"],
                corrective_action=corrective_action,
            )
        )
        return 0

    if command == "preview":
        target = validate_target_root(arguments.target)
        plan_path = _external_artifact_path(
            arguments.plan,
            target,
            "continuity plan",
            must_exist=True,
        )
        output = _external_artifact_path(
            arguments.output,
            target,
            "continuity preview receipt",
            must_exist=False,
        )
        plan = _load_json_object(plan_path, "continuity plan")
        receipt = build_continuity_preview_receipt(plan)
        _write_review_artifact(output, receipt, "continuity preview receipt")
        corrective_action = (
            "Inspect every receipt operation, then run continuity apply with this receipt and the exact reviewed plan_id."
            if receipt["materializable"]
            else _no_write_corrective_action(plan)
        )
        _emit_json(
            _result(
                command=command,
                status="previewed",
                code="preview-created",
                ok=True,
                plan_id=plan["plan_id"],
                preview_id=receipt["preview_id"],
                materializable=receipt["materializable"],
                summary=plan["summary"],
                corrective_action=corrective_action,
            )
        )
        return 0

    if command == "apply":
        target = validate_target_root(arguments.target)
        plan_path = _external_artifact_path(
            arguments.plan,
            target,
            "continuity plan",
            must_exist=True,
        )
        receipt_path = _external_artifact_path(
            arguments.preview_receipt,
            target,
            "continuity preview receipt",
            must_exist=True,
        )
        plan = _load_json_object(plan_path, "continuity plan")
        receipt = _load_json_object(
            receipt_path,
            "continuity preview receipt",
        )
        validate_continuity_preview_receipt(receipt, plan)
        if arguments.reviewed_plan_id != plan["plan_id"]:
            raise ContinuityCliError(
                "review-required",
                "reviewed plan ID does not match the exact continuity plan",
                "Inspect this plan's preview receipt and retry apply with its exact plan_id.",
            )
        if not receipt["materializable"]:
            raise ContinuityCliError(
                "plan-not-materializable",
                "reviewed continuity plan has a no-write disposition",
                _no_write_corrective_action(plan),
            )
        apply_continuity_plan(
            plan,
            target,
            profile_path=arguments.profile,
            aether_source=arguments.aether_source,
        )
        state_sha256 = _continuity_state_sha256(target)
        _emit_json(
            _result(
                command=command,
                status="applied",
                code="plan-applied",
                ok=True,
                plan_id=plan["plan_id"],
                preview_id=receipt["preview_id"],
                state_sha256=state_sha256,
                materializable=True,
                summary=plan["summary"],
                corrective_action="Run continuity verify before presenting or relying on the materialized handoff.",
            )
        )
        return 0

    if command == "verify":
        errors = verify_continuity_target(arguments.target)
        if errors:
            raise ContinuityCliError(
                "verification-failed",
                "continuity verification failed: " + "; ".join(errors),
                "Reconcile the reported state or surface drift through a new plan and preview; do not force managed bytes.",
            )
        state_sha256 = _continuity_state_sha256(arguments.target)
        _emit_json(
            _result(
                command=command,
                status="verified",
                code="target-verified",
                ok=True,
                state_sha256=state_sha256,
                corrective_action="No corrective action is required; use this state_sha256 for an explicitly reviewed rollback only.",
            )
        )
        return 0

    rollback_continuity_target(
        arguments.target,
        expected_state_sha256=arguments.expected_state_sha256,
    )
    state_sha256 = _current_continuity_state_sha256(arguments.target)
    _emit_json(
        _result(
            command=command,
            status="rolled-back",
            code="rollback-complete",
            ok=True,
            state_sha256=state_sha256,
            reviewed_state_sha256=arguments.expected_state_sha256,
            corrective_action="Create and preview a new continuity plan before any later apply.",
        )
    )
    return 0


def _continuity_error_result(
    command: str,
    error: Exception,
) -> dict[str, Any]:
    """Translate a continuity failure into a stable, actionable JSON result."""
    if isinstance(error, ContinuityCliError):
        code = error.code
        corrective_action = error.corrective_action
    elif command == "plan":
        code = "plan-failed"
        corrective_action = (
            "Correct the request, target, pinned profile, or local Aether source named by the error, then rerun continuity plan."
        )
    elif command == "preview":
        code = "preview-failed"
        corrective_action = (
            "Discard the invalid artifact, create a new continuity plan, and run continuity preview again."
        )
    elif command == "apply":
        code = "apply-refused"
        corrective_action = (
            "Rerun continuity plan and preview against the current target and pinned inputs, review the new receipt, then retry apply."
        )
    elif command == "verify":
        code = "verification-failed"
        corrective_action = (
            "Reconcile the reported state or surface drift through a new plan and preview; do not force managed bytes."
        )
    else:
        code = "rollback-refused"
        corrective_action = (
            "Verify the current state digest and rollback evidence, reconcile any post-apply edits, then retry without forcing changes."
        )
    return _result(
        command=command,
        status="error",
        code=code,
        ok=False,
        corrective_action=corrective_action,
        errors=[str(error)],
    )


def main(argv: list[str] | None = None) -> int:
    """Run the Holon materialization CLI."""
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    requested_command = _requested_top_level_command(raw_arguments)
    parser = build_parser()
    try:
        arguments = parser.parse_args(raw_arguments)
    except CliUsageError as error:
        if requested_command == "continuity":
            continuity_command = "continuity"
            try:
                continuity_index = raw_arguments.index("continuity")
            except ValueError:
                continuity_index = -1
            if continuity_index >= 0 and len(raw_arguments) > continuity_index + 1:
                candidate = raw_arguments[continuity_index + 1]
                if candidate in {"plan", "preview", "apply", "verify", "rollback"}:
                    continuity_command = candidate
            help_command = (
                "continuity"
                if continuity_command == "continuity"
                else f"continuity {continuity_command}"
            )
            _emit_json(
                _result(
                    command=continuity_command,
                    status="error",
                    code="invalid-arguments",
                    ok=False,
                    errors=[str(error)],
                    corrective_action=(
                        f"Run python3 tools/holon_materialize.py {help_command} --help, add the required arguments, and rerun the command."
                    ),
                ),
                error=True,
            )
            return 2
        error.parser.print_usage(file=sys.stderr)
        print(f"{error.parser.prog}: error: {error}", file=sys.stderr)
        return 2

    if arguments.command == "continuity":
        try:
            return _run_continuity(arguments)
        except (MaterializationError, OSError, ValueError, json.JSONDecodeError) as error:
            _emit_json(
                _continuity_error_result(arguments.continuity_command, error),
                error=True,
            )
            return 1

    try:
        if arguments.command == "plan":
            resolved = resolve_foundation_manifest(arguments.catalog, arguments.manifest)
            plan, _ = build_plan(
                resolved,
                arguments.target,
                render_source=arguments.render_source,
                render_overlays=arguments.render_overlay,
                aether_source=arguments.aether_source,
            )
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_bytes(pretty_json_bytes(plan))
            conflicts = plan["summary"].get("conflict", 0)
            print(
                f"wrote plan {arguments.output} ({plan['plan_id'][:12]}): "
                f"{len(plan['operations'])} operations, {conflicts} conflict(s)"
            )
            return 1 if conflicts else 0

        if arguments.command == "render":
            plan = load_json(arguments.plan)
            state = render_plan(
                plan,
                arguments.target,
                render_source=arguments.render_source,
                render_overlays=arguments.render_overlay,
                aether_source=arguments.aether_source,
            )
            print(
                f"rendered plan {state['plan_id'][:12]}: "
                f"{len(state['managed_files'])} managed file(s)"
            )
            return 0

        if arguments.command == "verify":
            errors = verify_target(arguments.target)
            if errors:
                for error in errors:
                    print(f"verify failed: {error}", file=sys.stderr)
                return 1
            state = load_state(validate_target_root(arguments.target))
            assert state is not None
            print(f"verified {len(state['managed_files'])} managed file(s)")
            return 0

        rollback_target(arguments.target)
        print("rolled back the latest Holon materialization")
        return 0
    except (MaterializationError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"holon materialization failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
