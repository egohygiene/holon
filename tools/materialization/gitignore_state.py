"""Bounded filesystem, ownership, and recovery records for layered ignore files."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterator

from .common import (
    MaterializationError, atomic_write, canonical_bytes, safe_relative_path,
    sha256_bytes, state_files, validate_target_root,
)

STATE_SCHEMA = "holon.gitignore-state/v1"
RECOVERY_SCHEMA = "holon.gitignore-rollback/v1"
STATE_PATH = ".holon/gitignore-state.v1.json"
BACKUPS_PATH = ".holon/gitignore-backups"
LOCK_PATH = ".holon/gitignore.lock"
FOREIGN_STATE_PATH = ".holon/materialization-state.v1.json"
SEMANTIC_FIELDS = {"schema_version", "repository", "request", "source", "composition_source", "files"}
DIGEST = re.compile(r"[0-9a-f]{64}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MaterializationError(message)


def object_fields(value: Any, fields: set[str], label: str) -> None:
    require(isinstance(value, dict) and set(value) == fields, f"invalid {label} fields")


def digest_value(value: Any, label: str) -> None:
    require(isinstance(value, str) and DIGEST.fullmatch(value) is not None,
            f"{label} must be a lowercase SHA-256 digest")


def string_list(value: Any, label: str) -> None:
    require(isinstance(value, list) and all(isinstance(item, str) and item for item in value),
            f"{label} must be an array of nonempty strings")
    require(len(value) == len(set(value)), f"duplicate {label}")


def relative_path(value: Any) -> str:
    require(isinstance(value, str) and bool(value), "path must be a nonempty string")
    require(all(char.isprintable() and char not in '\\:*?[]<>|"!' for char in value),
            f"unsafe path: {value!r}")
    normalized = safe_relative_path(value)
    require(normalized == value and all(
        part == part.strip() and part.casefold() not in {".git", ".holon"}
        for part in value.split("/")
    ), f"path must be normalized and outside Git/Holon metadata: {value!r}")
    return normalized


def ignore_path(value: Any) -> str:
    path = relative_path(value)
    require(path.split("/")[-1] == ".gitignore"
            and ".gitignore" not in {part.casefold() for part in path.split("/")[:-1]},
            "tracked paths must be exact .gitignore files in safe scopes")
    return path


def no_symlinks(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    for component in (*reversed(absolute.parents), absolute):
        require(not component.is_symlink(), f"symlink path is unsupported: {component.name}")
        if component != absolute and component.exists():
            require(component.is_dir(), f"path ancestor is not a directory: {component.name}")
    return absolute


def target_root(target: Path) -> Path:
    target = no_symlinks(target)
    validate_target_root(target)
    require(not target.exists() or target.is_dir(), "target must be a directory")
    return target


def internal_bytes(target: Path, relative: str) -> bytes | None:
    path = no_symlinks(target / relative)
    if not path.exists():
        return None
    require(path.is_file(), f"expected a regular internal file: {relative}")
    return path.read_bytes()


def file_image(target: Path, relative: str) -> dict[str, Any] | None:
    path = no_symlinks(target / ignore_path(relative))
    if not path.exists():
        return None
    metadata = path.stat()
    require(stat.S_ISREG(metadata.st_mode), f"target is not a regular file: {relative}")
    raw = path.read_bytes()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = None
    return {"content": content, "sha256": sha256_bytes(raw), "mode": stat.S_IMODE(metadata.st_mode)}


def validate_image(image: Any) -> None:
    object_fields(image, {"content", "sha256", "mode"}, "file image")
    require(isinstance(image["content"], str), "tracked content must be UTF-8 text")
    digest_value(image["sha256"], "file image digest")
    require(sha256_bytes(image["content"].encode("utf-8")) == image["sha256"],
            "file image digest mismatch")
    require(type(image["mode"]) is int and 0 <= image["mode"] <= 0o7777,
            "file image mode must be Unix permission bits")


def semantic_state(state: dict[str, Any]) -> dict[str, Any]:
    return {key: state[key] for key in SEMANTIC_FIELDS}


def seal_state(payload: dict[str, Any]) -> dict[str, Any]:
    return {**payload, "state_id": sha256_bytes(canonical_bytes(payload))}


def parse_state(raw: bytes) -> dict[str, Any]:
    state = json.loads(raw)
    object_fields(state, SEMANTIC_FIELDS | {"plan_id", "rollback_manifest", "rollback_sha256", "state_id"},
                  "gitignore state")
    require(state["schema_version"] == STATE_SCHEMA, "unsupported gitignore state schema")
    digest_value(state["state_id"], "state_id")
    payload = {key: value for key, value in state.items() if key != "state_id"}
    require(seal_state(payload) == state, "gitignore state checksum mismatch")
    digest_value(state["plan_id"], "state plan_id")
    digest_value(state["rollback_sha256"], "rollback_sha256")
    require(isinstance(state["rollback_manifest"], str) and re.fullmatch(
        re.escape(BACKUPS_PATH) + "/" + state["plan_id"] + r"/attempt-[0-9]{3,}/rollback.v1.json",
        state["rollback_manifest"],
    ) is not None, "unsafe or unrelated gitignore rollback reference")
    require(isinstance(state["repository"], str) and re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", state["repository"]
    ) is not None, "invalid state repository")
    request = state["request"]
    object_fields(request, {"schema_version", "repository", "source_revision", "profiles",
                           "scopes", "composition_sha256", "adopt"}, "saved request")
    require(request["schema_version"] == "holon.gitignore-request/v1"
            and request["repository"] == state["repository"], "state/request identity mismatch")
    digest_value(request["composition_sha256"], "saved composition digest")
    source = state["source"]
    object_fields(source, {"schema_version", "repository", "revision", "foundation", "format",
                          "catalog_path", "catalog_sha256"}, "saved source")
    require(source["schema_version"] == "holon.gitignore-source/v1"
            and source["repository"] == "egohygiene/empathy"
            and source["format"] == "empathy.gitignore/v1"
            and source["revision"] == request["source_revision"]
            and isinstance(source["revision"], str)
            and re.fullmatch(r"[0-9a-f]{40}", source["revision"]) is not None,
            "state/source identity mismatch")
    require(isinstance(source["foundation"], str) and bool(source["foundation"]), "invalid saved foundation")
    relative_path(source["catalog_path"])
    digest_value(source["catalog_sha256"], "saved catalog digest")
    composition_source = state["composition_source"]
    object_fields(composition_source, {"owner", "catalog_sha256", "resolved_manifest_sha256"},
                  "saved composition source")
    require(composition_source["owner"] == source["repository"]
            and composition_source["catalog_sha256"] == source["catalog_sha256"],
            "saved composition provenance mismatch")
    digest_value(composition_source["resolved_manifest_sha256"], "saved resolved manifest digest")
    string_list(request["profiles"], "saved profiles")
    require("universal" in request["profiles"], "saved profiles must include universal")
    require(isinstance(request["scopes"], list) and bool(request["scopes"]), "saved scopes must be a nonempty array")
    scopes = {}
    for scope in request["scopes"]:
        object_fields(scope, {"root", "overlays", "local_additions"}, "saved scope")
        require(isinstance(scope["root"], str), "saved scope root must be a string")
        string_list(scope["overlays"], "saved overlays")
        local = scope["local_additions"]
        require(isinstance(local, str) and "\r" not in local and "\0" not in local
                and (not local or local.endswith("\n")), "invalid saved local additions")
        path = ".gitignore" if scope["root"] == "." else ignore_path(f"{scope['root']}/.gitignore")
        require(path.casefold() not in scopes, "duplicate saved scope")
        scopes[path.casefold()] = scope
    require(".gitignore" in scopes, "saved scopes must include root")
    require(isinstance(request["adopt"], list), "saved adoption must be an array")
    adopted = set()
    for approval in request["adopt"]:
        object_fields(approval, {"path", "before_sha256"}, "saved adoption")
        path = ignore_path(approval["path"])
        require(path.casefold() in scopes and path.casefold() not in adopted, "invalid saved adoption path")
        adopted.add(path.casefold())
        digest_value(approval["before_sha256"], "saved adoption digest")
    require(isinstance(state["files"], list), "saved files must be an array")
    paths = set()
    for record in state["files"]:
        object_fields(record, {"path", "image", "selection", "layers"}, "tracked file")
        path = ignore_path(record["path"])
        require(path.casefold() not in paths and path.casefold() in scopes, "duplicate or unselected tracked path")
        paths.add(path.casefold())
        validate_image(record["image"])
        require(record["selection"] == scopes[path.casefold()], "tracked selection mismatch")
        layers = record["layers"]
        selection = record["selection"]
        require(isinstance(layers, list) and len(layers) == len(selection["overlays"]) + 2,
                "invalid tracked layers")
        for index, layer in enumerate(layers):
            require(isinstance(layer, dict), "invalid tracked layer")
            kind = "overlay" if index < len(layers) - 2 else "local" if index == len(layers) - 2 else "baseline"
            fields = {"kind", "owner", "sha256"}
            if kind != "local":
                fields |= {"id", "path"}
            if kind == "overlay":
                fields.add("profile")
            object_fields(layer, fields, "tracked layer")
            require(layer["kind"] == kind, "invalid tracked layer ordering")
            digest_value(layer["sha256"], "tracked layer digest")
            require(layer["owner"] == (state["repository"] if kind == "local" else source["repository"]),
                    "tracked layer owner mismatch")
            if kind == "local":
                require(layer["sha256"] == sha256_bytes(selection["local_additions"].encode("utf-8")),
                        "saved local additions digest mismatch")
            else:
                relative_path(layer["path"])
                require(isinstance(layer["id"], str) and bool(layer["id"]), "invalid tracked layer ID")
            if kind == "overlay":
                require(layer["id"] == selection["overlays"][index]
                        and layer["profile"] in request["profiles"], "tracked overlay selection mismatch")
    return state


def load_state(target: Path) -> tuple[dict[str, Any] | None, bytes | None]:
    raw = internal_bytes(target, STATE_PATH)
    if raw is None:
        return None, None
    return parse_state(raw), raw


def foreign_state(target: Path) -> tuple[set[str], str | None]:
    raw = internal_bytes(target, FOREIGN_STATE_PATH)
    if raw is None:
        return set(), None
    state = json.loads(raw)
    require(isinstance(state, dict) and state.get("schema_version") == "holon.materialization-state/v1"
            and isinstance(state.get("managed_files"), list), "invalid generic materialization state")
    return {path.casefold() for path in state_files(state)}, sha256_bytes(raw)


def load_recovery(target: Path, state: dict[str, Any]) -> dict[str, Any]:
    raw = internal_bytes(target, state["rollback_manifest"])
    require(raw is not None and sha256_bytes(raw) == state["rollback_sha256"],
            "gitignore recovery evidence is missing or changed")
    recovery = json.loads(raw)
    object_fields(recovery, {"schema_version", "repository", "plan_id", "after_semantic_sha256",
                            "before_state", "before_state_sha256", "operations", "created_directories"},
                  "gitignore recovery")
    require(recovery["schema_version"] == RECOVERY_SCHEMA
            and recovery["repository"] == state["repository"]
            and recovery["plan_id"] == state["plan_id"]
            and recovery["after_semantic_sha256"] == sha256_bytes(canonical_bytes(semantic_state(state))),
            "recovery/state identity mismatch")
    prior = None
    if recovery["before_state"] is not None:
        require(isinstance(recovery["before_state"], str), "invalid prior state bytes")
        prior_raw = recovery["before_state"].encode("utf-8")
        require(sha256_bytes(prior_raw) == recovery["before_state_sha256"], "prior state digest mismatch")
        prior = parse_state(prior_raw)
        require(prior["repository"] == state["repository"], "prior state repository mismatch")
    else:
        require(recovery["before_state_sha256"] is None, "unexpected prior state digest")
    before_files = {record["path"]: record["image"] for record in prior["files"]} if prior else {}
    after_files = {record["path"]: record["image"] for record in state["files"]}
    require(isinstance(recovery["operations"], list), "recovery operations must be an array")
    seen = set()
    for operation in recovery["operations"]:
        object_fields(operation, {"path", "action", "before", "after"}, "recovery operation")
        path = ignore_path(operation["path"])
        require(path.casefold() not in seen, "duplicate recovery path")
        seen.add(path.casefold())
        action = operation["action"]
        require(action in {"create", "adopt", "update", "noop", "release"}, "invalid recovery action")
        validate_image(operation["after"])
        if operation["before"] is not None:
            validate_image(operation["before"])
        require((operation["before"] is None) == (action == "create"), "invalid recovery preimage")
        if action in {"adopt", "noop", "release"}:
            require(operation["before"] == operation["after"], "non-writing action changes bytes")
        if action in {"create", "adopt"}:
            require(path not in before_files, "creation/adoption overlaps prior ownership")
        else:
            require(path in before_files and before_files[path] == operation["before"],
                    "recovery preimage does not match prior ownership")
        if action == "release":
            require(path not in after_files, "released path is still owned")
        else:
            require(after_files.get(path) == operation["after"], "recovery postimage/state mismatch")
    require(seen == {path.casefold() for path in set(before_files) | set(after_files)},
            "recovery inventory does not match ownership transition")
    require(isinstance(recovery["created_directories"], list), "invalid created directories")
    directories = recovery["created_directories"]
    for directory in directories:
        relative_path(directory)
        require(any(path.startswith(directory + "/") for path in after_files),
                "recovery directory is unrelated to tracked files")
    require(len(directories) == len(set(directories)), "duplicate recovery directory")
    return recovery


@contextmanager
def operation_lock(target: Path) -> Iterator[None]:
    internal = no_symlinks(target / ".holon")
    existed = internal.exists()
    internal.mkdir(parents=True, exist_ok=True)
    lock = no_symlinks(target / LOCK_PATH)
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise MaterializationError(
            "another gitignore operation is active; remove a stale gitignore.lock only after inspection"
        ) from error
    identity = lock.stat()
    try:
        yield
    finally:
        current = lock.lstat()
        require(not lock.is_symlink() and (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino),
                "gitignore operation lock changed; inspect recovery evidence")
        lock.rmdir()
        if not existed:
            try:
                internal.rmdir()
            except OSError:
                pass


def assert_image(target: Path, path: str, expected: dict[str, Any] | None) -> None:
    require(file_image(target, path) == expected,
            f"file changed or mode drift at {path}; preserve edits and re-plan")


def write_image(target: Path, path: str, image: dict[str, Any] | None) -> None:
    destination = no_symlinks(target / ignore_path(path))
    if image is None:
        destination.unlink()
    else:
        atomic_write(destination, image["content"].encode("utf-8"))
        no_symlinks(destination).chmod(image["mode"])


def write_internal(target: Path, relative: str, raw: bytes | None) -> None:
    destination = no_symlinks(target / relative)
    if raw is None:
        destination.unlink()
    else:
        atomic_write(destination, raw)
