"""Stateful plan/render/verify/rollback engine for Holon."""

from __future__ import annotations

import json
from pathlib import Path
import re
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
    read_regular_file,
    render_source_bytes,
    safe_relative_path,
    sha256_bytes,
    state_files,
    target_path,
    tree_digest,
    validate_target_root,
    validate_state,
)


def _managed_path(target: Path, path: str, *, kind: str | None = None) -> Path:
    """Only the resolved manifest is a generic managed file inside .holon."""
    normalized = safe_relative_path(path, allow_internal=path == RESOLVED_MANIFEST_RELATIVE_PATH)
    return target_path(target, normalized, kind=kind)


def _file_digest(path: Path) -> str:
    return sha256_bytes(read_regular_file(path))


def _rollback_path(target: Path, state: dict[str, Any]) -> Path:
    relative = state.get("rollback_manifest")
    plan_id = state.get("plan_id")
    if not isinstance(plan_id, str) or re.fullmatch(r"[0-9a-f]{64}", plan_id) is None:
        raise MaterializationError("Holon state does not identify a valid recovery plan")
    prefix = f"{BACKUPS_RELATIVE_PATH}/{plan_id}/"
    if not isinstance(relative, str) or not relative.startswith(prefix):
        raise MaterializationError("Holon state does not reference its own backup namespace")
    suffix = relative[len(prefix):]
    attempt = re.fullmatch(r"attempt-([0-9]{3,})/rollback\.v1\.json", suffix)
    if attempt is None or int(attempt[1]) < 1 or suffix != f"attempt-{int(attempt[1]):03d}/rollback.v1.json":
        raise MaterializationError("Holon state has an unsupported recovery path")
    return target_path(target, relative, kind="file")


def _read_recovery(target: Path, state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bytes], bytes | None]:
    """Preflight every selected recovery input/destination before any mutation.

    Recovery metadata cannot turn an arbitrary relative path into an owned file
    or select another attempt's preimage. Original valid v1 layouts are retained.
    """
    rollback_path = _rollback_path(target, state)
    try:
        rollback = json.loads(read_regular_file(rollback_path).decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise MaterializationError("invalid generic rollback metadata") from error
    fields = {"schema_version", "plan_id", "repository", "prior_state_present", "operations"}
    if (not isinstance(rollback, dict) or set(rollback) != fields
            or rollback.get("schema_version") != ROLLBACK_SCHEMA
            or rollback.get("plan_id") != state.get("plan_id")
            or rollback.get("repository") != state.get("repository")
            or type(rollback.get("prior_state_present")) is not bool
            or not isinstance(rollback.get("operations"), list)):
        raise MaterializationError("rollback metadata does not match current Holon state")
    current = state_files(state)
    manifest = state.get("resolved_manifest")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("preserve_paths", []), list):
        raise MaterializationError("Holon state does not identify its preserve boundaries")
    preserved = manifest.get("preserve_paths", [])
    if any(not isinstance(path, str) for path in preserved):
        raise MaterializationError("Holon state has invalid preserve boundaries")
    # Validate reserved preserve namespaces even when there are no mutations.
    is_preserved("", preserved)
    for path, record in current.items():
        _managed_path(target, path)
        if (is_preserved(path, preserved) or not isinstance(record.get("sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None):
            raise MaterializationError("Holon state has invalid managed-file evidence")

    backup_root = rollback_path.parent
    state_before = target_path(backup_root, "state-before.json", kind="file")
    state_before_bytes: bytes | None = None
    prior: dict[str, dict[str, Any]] = {}
    if rollback["prior_state_present"]:
        state_before_bytes = read_regular_file(state_before)
        try:
            prior_state = validate_state(json.loads(state_before_bytes.decode("utf-8")))
        except (ValueError, UnicodeError) as error:
            raise MaterializationError("rollback prior state is invalid") from error
        if prior_state.get("repository") != state.get("repository"):
            raise MaterializationError("rollback prior state belongs to another repository")
        # Restoring prior state must not publish an alias to its next recovery
        # record or claim a managed path through a filesystem link.
        if not _rollback_path(target, prior_state).is_file():
            raise MaterializationError("rollback prior state no longer has its recovery record")
        prior = state_files(prior_state)
        prior_manifest = prior_state.get("resolved_manifest")
        if not isinstance(prior_manifest, dict) or not isinstance(prior_manifest.get("preserve_paths", []), list):
            raise MaterializationError("rollback prior state has invalid preserve boundaries")
        prior_preserved = prior_manifest.get("preserve_paths", [])
        if any(not isinstance(path, str) for path in prior_preserved):
            raise MaterializationError("rollback prior state has invalid preserve boundaries")
        is_preserved("", prior_preserved)
        for path, record in prior.items():
            _managed_path(target, path)
            if (is_preserved(path, prior_preserved) or not isinstance(record.get("sha256"), str)
                    or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None):
                raise MaterializationError("rollback prior state has invalid managed-file evidence")

    preimages: dict[str, bytes] = {}
    paths: list[str] = []
    for operation in rollback["operations"]:
        keys = {"action", "path", "expected_after_sha256", "previous_sha256", "backup_path"}
        if (not isinstance(operation, dict) or set(operation) != keys or not isinstance(operation.get("path"), str)
                or not isinstance(operation.get("action"), str)):
            raise MaterializationError("malformed generic rollback operation")
        path, action = operation["path"], operation["action"]
        _managed_path(target, path, kind="file")
        if path in paths or is_preserved(path, preserved) or action not in {"create", "update", "delete"}:
            raise MaterializationError("rollback cannot target duplicate, preserved or unsupported paths")
        paths.append(path)
        after, before = operation["expected_after_sha256"], operation["previous_sha256"]
        if action in {"create", "update"}:
            if (not isinstance(after, str) or re.fullmatch(r"[0-9a-f]{64}", after) is None
                    or current.get(path, {}).get("sha256") != after):
                raise MaterializationError("rollback cannot mutate a path outside current generated ownership")
        elif after is not None or path in current:
            raise MaterializationError("deleted rollback path has incompatible ownership evidence")
        if action == "create":
            if before is not None or operation["backup_path"] is not None or path in prior:
                raise MaterializationError("created rollback path has incompatible prior evidence")
            continue
        if (not isinstance(before, str) or re.fullmatch(r"[0-9a-f]{64}", before) is None
                or prior.get(path, {}).get("sha256") != before
                or operation["backup_path"] != f"files/{path}"):
            raise MaterializationError("rollback preimage is outside prior generated ownership")
        backup = target_path(backup_root, operation["backup_path"], kind="file")
        content = read_regular_file(backup)
        if sha256_bytes(content) != before:
            raise MaterializationError(f"rollback backup is missing or invalid for {path}")
        preimages[path] = content
    return rollback, preimages, state_before_bytes


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
    for path in desired:
        if any(parent.as_posix() in desired for parent in Path(path).parents if parent.as_posix() != "."):
            raise MaterializationError("generated file paths cannot be ancestors of other generated files")

    for path, desired_record in sorted(desired.items()):
        destination = _managed_path(target, path)
        previous_record = previous.get(path)
        preserved = is_preserved(path, preserve_paths)
        current_sha: str | None = None
        exists = destination.exists()
        if exists and not destination.is_file():
            action = "conflict"
            reason = "target path exists but is not a regular file"
        elif exists:
            current_sha = _file_digest(destination)
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
        destination = _managed_path(target, path)
        if is_preserved(path, preserve_paths):
            operations.append(
                {
                    "action": "preserve",
                    "path": path,
                    "owner": previous_record.get("owner", "egohygiene/holon"),
                    "source": previous_record.get("source", "previous-state"),
                    "desired_sha256": None,
                    "previous_sha256": _file_digest(destination)
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
            current_sha = _file_digest(destination)
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
    # Dry-run checks the same state/recovery namespaces that render will use.
    # Nothing is allocated by this preflight, including for a missing target.
    target_path(target, BACKUPS_RELATIVE_PATH, kind="directory")
    state = load_state(target)
    if state is not None:
        _read_recovery(target, state)
    operations = _build_operations(target, desired, resolved_manifest, state)
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
    parent = target_path(target, parent_relative, kind="directory")
    attempt = 1
    while target_path(target, f"{parent_relative}/attempt-{attempt:03d}", kind="directory").exists():
        attempt += 1
    relative = f"{parent_relative}/attempt-{attempt:03d}"
    root = target_path(target, relative, kind="directory")
    # All existing ancestors and attempt aliases are checked before mkdir.
    parent.mkdir(parents=True, exist_ok=True)
    target_path(target, relative, kind="directory")
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
        atomic_write(target_path(backup_root, "state-before.json", kind="file"), pretty_json_bytes(prior_state))

    rollback_operations = []
    for operation in plan["operations"]:
        action = operation["action"]
        if action not in {"create", "update", "delete"}:
            continue
        path = operation["path"]
        destination = _managed_path(target, path, kind="file")
        backup_path: str | None = None
        if action in {"update", "delete"}:
            backup_path = f"files/{path}"
            backup_destination = target_path(backup_root, backup_path, kind="file")
            atomic_write(backup_destination, read_regular_file(destination))
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
        target_path(backup_root, "rollback.v1.json", kind="file"),
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
            destination = _managed_path(target, path, kind="file")
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
        atomic_write(target_path(target, STATE_RELATIVE_PATH, kind="file"), pretty_json_bytes(state))
        return state
    except Exception:
        for operation in reversed(applied):
            path = operation["path"]
            destination = _managed_path(target, path, kind="file")
            if operation["action"] == "create":
                if destination.is_file() and _file_digest(destination) == operation.get(
                    "desired_sha256"
                ):
                    destination.unlink()
                continue
            backup = target_path(backup_root, f"files/{path}", kind="file")
            if backup.is_file():
                atomic_write(destination, read_regular_file(backup))
        raise


def verify_target(target: Path) -> list[str]:
    """Verify every Holon-managed file against the current ownership state."""
    target = validate_target_root(target)
    state = load_state(target)
    if state is None:
        return ["no Holon materialization state exists"]
    target_path(target, BACKUPS_RELATIVE_PATH, kind="directory")
    _read_recovery(target, state)
    errors: list[str] = []
    for path, record in state_files(state).items():
        destination = _managed_path(target, path)
        if not destination.is_file():
            errors.append(f"missing managed file: {record['path']}")
        elif _file_digest(destination) != record.get("sha256"):
            errors.append(f"managed file drift: {record['path']}")
    return errors


def rollback_target(target: Path) -> None:
    """Roll back the latest render only when post-render generated files are unchanged."""
    target = validate_target_root(target)
    state = load_state(target)
    if state is None:
        raise MaterializationError("no Holon materialization state exists to roll back")
    rollback, preimages, state_before_bytes = _read_recovery(target, state)
    state_path = target_path(target, STATE_RELATIVE_PATH, kind="file")
    for operation in rollback["operations"]:
        destination = _managed_path(target, operation["path"], kind="file")
        if operation["action"] in {"create", "update"}:
            if not destination.is_file():
                raise MaterializationError(
                    f"rollback blocked because generated file is missing: {operation['path']}"
                )
            if _file_digest(destination) != operation.get("expected_after_sha256"):
                raise MaterializationError(
                    "rollback blocked because generated file changed after render: "
                    + operation["path"]
                )
        elif operation["action"] == "delete" and destination.exists():
            raise MaterializationError(
                f"rollback blocked because deleted path was recreated after render: {operation['path']}"
            )

    # Only checked in-memory preimages are used after the first mutation. A
    # later bad backup, prior-state file or protected destination cannot cause a
    # partially applied rollback before its path is discovered.
    for operation in reversed(rollback["operations"]):
        destination = _managed_path(target, operation["path"], kind="file")
        if operation["action"] == "create":
            destination.unlink()
            continue
        atomic_write(destination, preimages[operation["path"]])

    if state_before_bytes is not None:
        atomic_write(state_path, state_before_bytes)
    else:
        state_path.unlink(missing_ok=True)
