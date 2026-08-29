"""Stateful plan/render/verify/rollback engine for Holon."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
from typing import Any

from .aether import load_aether_projection_files
from .common import (
    BACKUPS_RELATIVE_PATH,
    ENGINE_VERSION,
    PLAN_SCHEMA,
    RESOLVED_MANIFEST_RELATIVE_PATH,
    ROLLBACK_SCHEMA,
    STATE_RELATIVE_PATH,
    STATE_SCHEMA,
    MaterializationError,
    add_desired,
    atomic_write,
    canonical_bytes,
    is_preserved,
    load_state,
    pretty_json_bytes,
    render_source_bytes,
    safe_relative_path,
    sha256_bytes,
    sha256_file,
    state_files,
    target_path,
    tree_digest,
    validate_target_root,
)


def build_desired_files(
    resolved_manifest: dict[str, Any],
    *,
    render_source: Path | None = None,
    render_overlays: list[Path] | None = None,
    aether_source: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Build desired file bytes and path-independent input provenance."""
    desired: dict[str, dict[str, Any]] = {}
    add_desired(
        desired,
        RESOLVED_MANIFEST_RELATIVE_PATH,
        pretty_json_bytes(resolved_manifest),
        owner="egohygiene/holon",
        source="holon:resolved-manifest",
        allow_internal=True,
    )

    inputs: dict[str, Any] = {"render_source": None, "render_overlays": [], "aether": None}

    def add_render_pack(source: Path, *, label: str, replace: bool) -> None:
        if not source.is_dir():
            raise MaterializationError(f"{label} is not a directory: {source}")
        for source_path in sorted(source.rglob("*")):
            if source_path.is_symlink():
                raise MaterializationError(
                    f"{label} contains unsupported symlink: {source_path}"
                )
            if not source_path.is_file():
                continue
            relative = safe_relative_path(source_path.relative_to(source).as_posix())
            add_desired(
                desired,
                relative,
                render_source_bytes(source_path.read_bytes(), resolved_manifest, relative),
                owner="egohygiene/holon",
                source=f"{label}:{relative}",
                replace=replace,
            )

    if render_source is not None:
        inputs["render_source"] = {"tree_sha256": tree_digest(render_source)}
        add_render_pack(render_source, label="render-source", replace=False)

    for index, overlay in enumerate(render_overlays or []):
        inputs["render_overlays"].append({"tree_sha256": tree_digest(overlay)})
        add_render_pack(overlay, label=f"render-overlay:{index}", replace=True)

    if "aether-agents" in set(resolved_manifest.get("capabilities", [])):
        if aether_source is None:
            raise MaterializationError(
                "resolved manifest selects aether-agents; provide a pinned Aether distribution "
                "with --aether-source"
            )
        aether_files, aether_metadata = load_aether_projection_files(
            resolved_manifest, aether_source
        )
        inputs["aether"] = aether_metadata
        for destination, (content, source) in sorted(aether_files.items()):
            add_desired(
                desired,
                destination,
                content,
                owner="egohygiene/aether",
                source=source,
            )
    return desired, inputs


def _build_operations(
    target: Path,
    desired: dict[str, dict[str, Any]],
    resolved_manifest: dict[str, Any],
    state: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    preserve_paths = [str(path) for path in resolved_manifest.get("preserve_paths", [])]
    previous = state_files(state)
    operations: list[dict[str, Any]] = []

    for path, desired_record in sorted(desired.items()):
        destination = target_path(target, path)
        previous_record = previous.get(path)
        preserved = is_preserved(path, preserve_paths)
        current_sha: str | None = None
        exists = destination.exists()
        if exists and not destination.is_file():
            action = "conflict"
            reason = "target path exists but is not a regular file"
        elif exists:
            current_sha = sha256_file(destination)
            if preserved:
                action = "preserve"
                reason = "manifest preserve_paths protects this path"
            elif previous_record is None:
                action = "conflict"
                reason = "existing file is not owned by the current Holon materialization state"
            elif current_sha != previous_record.get("sha256"):
                action = "conflict"
                reason = "Holon-owned file changed since the previous render"
            elif current_sha == desired_record["sha256"]:
                action = "noop"
                reason = "current file already matches desired generated content"
            else:
                action = "update"
                reason = "Holon owns the unmodified current file and desired content changed"
        else:
            if preserved:
                action = "preserve"
                reason = "manifest preserve_paths reserves this path"
            elif previous_record is not None:
                action = "conflict"
                reason = "previously Holon-owned file is missing from the target"
            else:
                action = "create"
                reason = "target file does not exist"
        operations.append(
            {
                "action": action,
                "path": path,
                "owner": desired_record["owner"],
                "source": desired_record["source"],
                "desired_sha256": desired_record["sha256"],
                "previous_sha256": current_sha,
                "reason": reason,
            }
        )

    for path, previous_record in sorted(previous.items()):
        if path in desired:
            continue
        destination = target_path(target, path)
        if is_preserved(path, preserve_paths):
            operations.append(
                {
                    "action": "preserve",
                    "path": path,
                    "owner": previous_record.get("owner", "egohygiene/holon"),
                    "source": previous_record.get("source", "previous-state"),
                    "desired_sha256": None,
                    "previous_sha256": sha256_file(destination)
                    if destination.is_file()
                    else None,
                    "reason": "manifest preserve_paths relinquishes generated ownership without deleting the path",
                }
            )
            continue
        if not destination.exists():
            action = "conflict"
            current_sha = None
            reason = "previously Holon-owned file is missing; verify or restore before changing ownership"
        elif not destination.is_file():
            action = "conflict"
            current_sha = None
            reason = "previously Holon-owned path is no longer a regular file"
        else:
            current_sha = sha256_file(destination)
            if current_sha != previous_record.get("sha256"):
                action = "conflict"
                reason = "stale Holon-owned file changed since the previous render"
            else:
                action = "delete"
                reason = "file is no longer emitted and remains unchanged since the previous render"
        operations.append(
            {
                "action": action,
                "path": path,
                "owner": previous_record.get("owner", "egohygiene/holon"),
                "source": previous_record.get("source", "previous-state"),
                "desired_sha256": None,
                "previous_sha256": current_sha,
                "reason": reason,
            }
        )
    return sorted(operations, key=lambda record: record["path"])


def build_plan(
    resolved_manifest: dict[str, Any],
    target: Path,
    *,
    render_source: Path | None = None,
    render_overlays: list[Path] | None = None,
    aether_source: Path | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Build a deterministic, path-independent materialization plan."""
    target = validate_target_root(target)
    desired, inputs = build_desired_files(
        resolved_manifest,
        render_source=render_source,
        render_overlays=render_overlays,
        aether_source=aether_source,
    )
    operations = _build_operations(target, desired, resolved_manifest, load_state(target))
    summary: dict[str, int] = {}
    for operation in operations:
        action = str(operation["action"])
        summary[action] = summary.get(action, 0) + 1
    payload = {
        "schema_version": PLAN_SCHEMA,
        "engine_version": ENGINE_VERSION,
        "repository": resolved_manifest["repository"],
        "resolved_manifest_sha256": sha256_bytes(canonical_bytes(resolved_manifest)),
        "resolved_manifest": resolved_manifest,
        "inputs": inputs,
        "capability_adapters": [
            {
                "id": capability,
                "adapter": "aether-release-projection"
                if capability == "aether-agents"
                else "render-source-or-specialized-pack",
            }
            for capability in resolved_manifest.get("capabilities", [])
        ],
        "operations": operations,
        "summary": {key: summary[key] for key in sorted(summary)},
    }
    plan = dict(payload)
    plan["plan_id"] = sha256_bytes(canonical_bytes(payload))
    return plan, desired


def validate_plan(plan: dict[str, Any]) -> None:
    """Validate the deterministic plan identity and minimum v1 shape."""
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise MaterializationError("unsupported materialization plan schema")
    plan_id = plan.get("plan_id")
    if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
        raise MaterializationError("materialization plan is missing a valid plan_id")
    payload = {key: value for key, value in plan.items() if key != "plan_id"}
    if sha256_bytes(canonical_bytes(payload)) != plan_id:
        raise MaterializationError("materialization plan content does not match its plan_id")
    if not isinstance(plan.get("operations"), list) or not isinstance(
        plan.get("resolved_manifest"), dict
    ):
        raise MaterializationError("materialization plan is missing required v1 fields")


def _next_backup(target: Path, plan_id: str) -> tuple[str, Path]:
    parent_relative = f"{BACKUPS_RELATIVE_PATH}/{plan_id}"
    parent = target / parent_relative
    parent.mkdir(parents=True, exist_ok=True)
    attempt = 1
    while (parent / f"attempt-{attempt:03d}").exists():
        attempt += 1
    relative = f"{parent_relative}/attempt-{attempt:03d}"
    root = target / relative
    root.mkdir(parents=True, exist_ok=False)
    return relative, root


def render_plan(
    plan: dict[str, Any],
    target: Path,
    *,
    render_source: Path | None = None,
    render_overlays: list[Path] | None = None,
    aether_source: Path | None = None,
) -> dict[str, Any]:
    """Recompute and apply an approved plan, preserving a reversible backup."""
    validate_plan(plan)
    target = validate_target_root(target)
    resolved_manifest = plan["resolved_manifest"]
    current_plan, desired = build_plan(
        resolved_manifest,
        target,
        render_source=render_source,
        render_overlays=render_overlays,
        aether_source=aether_source,
    )
    if current_plan["plan_id"] != plan["plan_id"]:
        raise MaterializationError(
            "target or materialization inputs changed after planning; generate and review a new plan"
        )
    conflicts = [item for item in plan["operations"] if item["action"] == "conflict"]
    if conflicts:
        raise MaterializationError(
            "materialization plan contains conflicts: "
            + ", ".join(item["path"] for item in conflicts)
        )

    prior_state = load_state(target)
    backup_relative, backup_root = _next_backup(target, plan["plan_id"])
    if prior_state is not None:
        atomic_write(backup_root / "state-before.json", pretty_json_bytes(prior_state))

    rollback_operations = []
    for operation in plan["operations"]:
        action = operation["action"]
        if action not in {"create", "update", "delete"}:
            continue
        path = operation["path"]
        destination = target_path(target, path)
        backup_path: str | None = None
        if action in {"update", "delete"}:
            backup_path = f"files/{path}"
            backup_destination = backup_root / backup_path
            backup_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(destination, backup_destination)
        rollback_operations.append(
            {
                "action": action,
                "path": path,
                "expected_after_sha256": operation.get("desired_sha256")
                if action in {"create", "update"}
                else None,
                "previous_sha256": operation.get("previous_sha256"),
                "backup_path": backup_path,
            }
        )
    atomic_write(
        backup_root / "rollback.v1.json",
        pretty_json_bytes(
            {
                "schema_version": ROLLBACK_SCHEMA,
                "plan_id": plan["plan_id"],
                "repository": plan["repository"],
                "prior_state_present": prior_state is not None,
                "operations": rollback_operations,
            }
        ),
    )

    applied: list[dict[str, Any]] = []
    try:
        for operation in plan["operations"]:
            action = operation["action"]
            path = operation["path"]
            if action in {"noop", "preserve"}:
                continue
            destination = target_path(target, path)
            if action in {"create", "update"}:
                record = desired.get(path)
                if record is None or record["sha256"] != operation["desired_sha256"]:
                    raise MaterializationError(f"desired materialization content changed for {path}")
                atomic_write(destination, record["content"])
            elif action == "delete":
                destination.unlink()
            else:
                raise MaterializationError(f"unsupported plan action during render: {action}")
            applied.append(operation)

        managed_files = []
        by_path = {item["path"]: item for item in plan["operations"]}
        for path, record in sorted(desired.items()):
            if by_path[path]["action"] != "preserve":
                managed_files.append(
                    {
                        "path": path,
                        "sha256": record["sha256"],
                        "owner": record["owner"],
                        "source": record["source"],
                    }
                )
        state = {
            "schema_version": STATE_SCHEMA,
            "engine_version": ENGINE_VERSION,
            "repository": plan["repository"],
            "plan_id": plan["plan_id"],
            "resolved_manifest_sha256": plan["resolved_manifest_sha256"],
            "resolved_manifest": resolved_manifest,
            "inputs": plan["inputs"],
            "managed_files": managed_files,
            "rollback_manifest": f"{backup_relative}/rollback.v1.json",
        }
        atomic_write(target / STATE_RELATIVE_PATH, pretty_json_bytes(state))
        return state
    except Exception:
        for operation in reversed(applied):
            path = operation["path"]
            destination = target_path(target, path)
            if operation["action"] == "create":
                if destination.is_file() and sha256_file(destination) == operation.get(
                    "desired_sha256"
                ):
                    destination.unlink()
                continue
            backup = backup_root / "files" / path
            if backup.is_file():
                atomic_write(destination, backup.read_bytes())
        raise


def verify_target(target: Path) -> list[str]:
    """Verify every Holon-managed file against the current ownership state."""
    target = validate_target_root(target)
    state = load_state(target)
    if state is None:
        return ["no Holon materialization state exists"]
    errors: list[str] = []
    for record in state["managed_files"]:
        destination = target_path(target, record["path"])
        if not destination.is_file():
            errors.append(f"missing managed file: {record['path']}")
        elif sha256_file(destination) != record.get("sha256"):
            errors.append(f"managed file drift: {record['path']}")
    return errors


def rollback_target(target: Path) -> None:
    """Roll back the latest render only when post-render generated files are unchanged."""
    target = validate_target_root(target)
    state = load_state(target)
    if state is None:
        raise MaterializationError("no Holon materialization state exists to roll back")
    rollback_relative = state.get("rollback_manifest")
    if not isinstance(rollback_relative, str):
        raise MaterializationError("Holon state does not reference rollback metadata")
    rollback_path = target_path(target, rollback_relative)
    if not rollback_path.is_file():
        raise MaterializationError(f"rollback metadata is missing: {rollback_relative}")
    try:
        rollback = json.loads(rollback_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MaterializationError(f"invalid rollback metadata: {error}") from error
    if rollback.get("schema_version") != ROLLBACK_SCHEMA or rollback.get("plan_id") != state.get(
        "plan_id"
    ):
        raise MaterializationError("rollback metadata does not match current Holon state")

    backup_root = rollback_path.parent
    for operation in rollback.get("operations", []):
        destination = target_path(target, operation["path"])
        if operation["action"] in {"create", "update"}:
            if not destination.is_file():
                raise MaterializationError(
                    f"rollback blocked because generated file is missing: {operation['path']}"
                )
            if sha256_file(destination) != operation.get("expected_after_sha256"):
                raise MaterializationError(
                    "rollback blocked because generated file changed after render: "
                    + operation["path"]
                )
        elif operation["action"] == "delete" and destination.exists():
            raise MaterializationError(
                f"rollback blocked because deleted path was recreated after render: {operation['path']}"
            )

    for operation in reversed(rollback.get("operations", [])):
        destination = target_path(target, operation["path"])
        if operation["action"] == "create":
            destination.unlink()
            continue
        backup_path = operation.get("backup_path")
        if not isinstance(backup_path, str):
            raise MaterializationError(f"rollback backup is missing for {operation['path']}")
        backup = backup_root / backup_path
        if not backup.is_file() or sha256_file(backup) != operation.get("previous_sha256"):
            raise MaterializationError(
                f"rollback backup is missing or invalid for {operation['path']}"
            )
        atomic_write(destination, backup.read_bytes())

    state_before = backup_root / "state-before.json"
    current_state_path = target / STATE_RELATIVE_PATH
    if rollback.get("prior_state_present"):
        if not state_before.is_file():
            raise MaterializationError("rollback expected prior state but state-before.json is missing")
        atomic_write(current_state_path, state_before.read_bytes())
    else:
        current_state_path.unlink(missing_ok=True)
