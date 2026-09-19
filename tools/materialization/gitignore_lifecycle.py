"""Reviewed local application and guarded recovery of layered ignore plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import MaterializationError, canonical_bytes, pretty_json_bytes, sha256_bytes
from .gitignore import check_gitignore_plan
from .gitignore_state import (
    BACKUPS_PATH, RECOVERY_SCHEMA, STATE_PATH, STATE_SCHEMA,
    assert_image, digest_value, file_image, foreign_state, internal_bytes,
    load_recovery, load_state, no_symlinks, operation_lock, require,
    seal_state, semantic_state, target_root, write_image, write_internal,
)


def _image(operation: dict[str, Any], prefix: str) -> dict[str, Any] | None:
    if prefix == "before" and operation["before_kind"] == "missing":
        return None
    return {"content": operation[f"{prefix}_content"], "sha256": operation[f"{prefix}_sha256"],
            "mode": operation[f"{prefix}_mode"]}


def _semantic(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA, "repository": plan["repository"],
        "request": plan["request"], "source": plan["source"],
        "composition_source": plan["composition_source"],
        "files": [{"path": item["path"], "image": _image(item, "proposed"),
                   "selection": item["selection"], "layers": item["layers"]}
                  for item in plan["operations"] if item["action"] not in {"preserve", "release"}],
    }


def _backup_path(target: Path, plan_id: str) -> str:
    parent = no_symlinks(target / BACKUPS_PATH / plan_id)
    parent.mkdir(parents=True, exist_ok=True)
    attempt = 1
    while True:
        candidate = no_symlinks(parent / f"attempt-{attempt:03d}")
        try:
            candidate.mkdir()
            return candidate.relative_to(target).as_posix() + "/rollback.v1.json"
        except FileExistsError:
            attempt += 1


def _assert_state(target: Path, expected: bytes | None) -> None:
    require(internal_bytes(target, STATE_PATH) == expected,
            "gitignore state changed during the operation; inspect recovery evidence")


def _transition(
    target: Path, operations: list[dict[str, Any]], *, before_state: bytes | None,
    after_state: bytes | None, foreign_sha: str | None, recovery_path: str,
) -> None:
    """Preflight all paths, compare again per write, and restore only known bytes."""
    _assert_state(target, before_state)
    for item in operations:
        assert_image(target, item["path"], item["before"])
    attempted = []
    try:
        for item in operations:
            assert_image(target, item["path"], item["before"])
            if item["before"] == item["after"]:
                continue
            attempted.append(item)
            write_image(target, item["path"], item["after"])
            assert_image(target, item["path"], item["after"])
        for item in operations:
            assert_image(target, item["path"], item["after"])
        _assert_state(target, before_state)
        require(foreign_state(target)[1] == foreign_sha, "generic ownership state changed during operation")
        write_internal(target, STATE_PATH, after_state)
    except Exception as error:
        failures = []
        for item in reversed(attempted):
            try:
                current = file_image(target, item["path"])
                if current == item["before"]:
                    continue
                require(current == item["after"], "intervening edit prevents automatic restoration")
                write_image(target, item["path"], item["before"])
            except (OSError, ValueError, MaterializationError):
                failures.append(item["path"])
        try:
            current_state = internal_bytes(target, STATE_PATH)
            if current_state != before_state:
                require(not failures and current_state == after_state, "state cannot be restored safely")
                write_internal(target, STATE_PATH, before_state)
        except (OSError, ValueError, MaterializationError):
            failures.append(STATE_PATH)
        message = ("preimages restored" if not failures else
                   "automatic recovery incomplete; preserved changed paths: " + ", ".join(failures))
        raise MaterializationError(
            f"gitignore operation failed ({error}); {message}; recovery evidence: {recovery_path}"
        ) from error


def apply_gitignore_plan(
    plan: dict[str, Any], request: dict[str, Any], composition: dict[str, Any], target: Path,
    *, empathy_source: Path, reviewed_plan_id: str,
) -> dict[str, Any] | None:
    """Apply only an exact reviewed v2 plan; never infer an overwrite or adoption."""
    digest_value(reviewed_plan_id, "reviewed_plan_id")
    require(isinstance(plan, dict) and plan.get("plan_id") == reviewed_plan_id,
            "reviewed plan ID does not match the supplied plan")
    target = target_root(target)
    check_gitignore_plan(plan, request, composition, target, empathy_source=empathy_source)
    proposed = _semantic(plan)
    if plan["prior_state_sha256"] is None and not proposed["files"]:
        return None  # A preserve-only request has no ownership or filesystem effect.
    with operation_lock(target):
        check_gitignore_plan(plan, request, composition, target, empathy_source=empathy_source)
        prior, prior_raw = load_state(target)
        if prior is not None and semantic_state(prior) == proposed:
            return prior  # Do not rotate state or create another recovery record.
        changes = [{"path": item["path"], "action": item["action"],
                    "before": _image(item, "before"), "after": _image(item, "proposed")}
                   for item in plan["operations"] if item["action"] != "preserve"]
        created = set()
        for item in changes:
            for directory in (target / item["path"]).parents:
                if directory == target:
                    break
                no_symlinks(directory)
                if not directory.exists():
                    created.add(directory.relative_to(target).as_posix())
        recovery = {
            "schema_version": RECOVERY_SCHEMA, "repository": plan["repository"], "plan_id": plan["plan_id"],
            "after_semantic_sha256": sha256_bytes(canonical_bytes(proposed)),
            "before_state": prior_raw.decode("utf-8") if prior_raw is not None else None,
            "before_state_sha256": sha256_bytes(prior_raw) if prior_raw is not None else None,
            "operations": changes, "created_directories": sorted(created),
        }
        recovery_raw = pretty_json_bytes(recovery)
        recovery_path = _backup_path(target, plan["plan_id"])
        write_internal(target, recovery_path, recovery_raw)
        state = seal_state({**proposed, "plan_id": plan["plan_id"], "rollback_manifest": recovery_path,
                            "rollback_sha256": sha256_bytes(recovery_raw)})
        # Validate the complete persisted transition before touching consumer files.
        load_recovery(target, state)
        _transition(target, changes, before_state=prior_raw, after_state=pretty_json_bytes(state),
                    foreign_sha=plan["foreign_state_sha256"], recovery_path=recovery_path)
        return state


def verify_gitignore_target(target: Path) -> dict[str, Any]:
    """Verify current bytes/modes, source evidence, ownership, and recovery integrity."""
    target = target_root(target)
    state, raw = load_state(target)
    require(state is not None, "no gitignore state exists; plan and explicitly apply or adopt first")
    load_recovery(target, state)
    foreign, _ = foreign_state(target)
    for record in state["files"]:
        require(record["path"].casefold() not in foreign, "gitignore and generic ownership overlap")
        assert_image(target, record["path"], record["image"])
    return {"schema_version": "holon.gitignore-verification/v1", "status": "verified",
            "repository": state["repository"], "state_sha256": sha256_bytes(raw),
            "plan_id": state["plan_id"], "tracked_files": len(state["files"])}


def rollback_gitignore_target(target: Path, *, expected_state_sha256: str) -> None:
    """Restore the latest preimages only if all postimages and recovery bytes agree."""
    digest_value(expected_state_sha256, "expected_state_sha256")
    target = target_root(target)
    # A missing/corrupt state must not create a lock or filesystem metadata.
    verification = verify_gitignore_target(target)
    require(verification["state_sha256"] == expected_state_sha256, "reviewed rollback state is stale")
    with operation_lock(target):
        verification = verify_gitignore_target(target)
        require(verification["state_sha256"] == expected_state_sha256, "reviewed rollback state is stale")
        state, state_raw = load_state(target)
        recovery = load_recovery(target, state)
        prior_raw = recovery["before_state"].encode("utf-8") if recovery["before_state"] is not None else None
        # Verify the preceding recovery anchor too, before restoring its state.
        if prior_raw is not None:
            from .gitignore_state import parse_state
            load_recovery(target, parse_state(prior_raw))
        foreign, foreign_sha = foreign_state(target)
        changes = []
        for item in reversed(recovery["operations"]):
            require(item["path"].casefold() not in foreign,
                    "rollback path is owned by generic Holon state; reconcile ownership first")
            changes.append({"path": item["path"], "before": item["after"], "after": item["before"]})
        _transition(target, changes, before_state=state_raw, after_state=prior_raw,
                    foreign_sha=foreign_sha, recovery_path=state["rollback_manifest"])
        for relative in sorted(recovery["created_directories"], key=lambda path: len(path.split("/")), reverse=True):
            try:
                no_symlinks(target / relative).rmdir()
            except (OSError, MaterializationError):
                # Retain nonempty/changed paths; unrelated work never becomes cleanup.
                pass
