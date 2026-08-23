"""Deterministic filesystem and provenance primitives for Holon materialization."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any

ENGINE_VERSION = "1.0.0"
PLAN_SCHEMA = "holon.materialization-plan/v1"
STATE_SCHEMA = "holon.materialization-state/v1"
ROLLBACK_SCHEMA = "holon.materialization-rollback/v1"
STATE_RELATIVE_PATH = ".holon/materialization-state.v1.json"
RESOLVED_MANIFEST_RELATIVE_PATH = ".holon/resolved-manifest.v1.json"
BACKUPS_RELATIVE_PATH = ".holon/backups"
TEMPLATE_TOKEN_RE = re.compile(
    r"\{\{(?:repository|repository_name|repository_class|security_level|parameter\.[A-Za-z0-9_.-]+)\}\}"
)


class MaterializationError(RuntimeError):
    """Raised when a materialization cannot proceed safely."""


def canonical_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically for hashing and plan comparison."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def pretty_json_bytes(value: Any) -> bytes:
    """Serialize reviewable JSON with deterministic key ordering."""
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(content: bytes) -> str:
    """Return a lowercase SHA-256 digest for bytes."""
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    """Return a lowercase SHA-256 digest for one file."""
    return sha256_bytes(path.read_bytes())


def safe_relative_path(value: str, *, allow_internal: bool = False) -> str:
    """Normalize one repository-relative path and reject traversal/reserved roots."""
    candidate = value.replace("\\", "/").strip()
    pure = PurePosixPath(candidate)
    if not candidate or pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise MaterializationError(f"unsafe repository-relative path: {value!r}")
    normalized = pure.as_posix()
    if normalized == ".git" or normalized.startswith(".git/"):
        raise MaterializationError(f"materialization cannot target Git internals: {normalized}")
    if not allow_internal and (normalized == ".holon" or normalized.startswith(".holon/")):
        raise MaterializationError(f"render sources cannot target Holon state paths: {normalized}")
    return normalized


def target_path(target: Path, relative_path: str) -> Path:
    """Resolve a validated relative path beneath the materialization target."""
    normalized = safe_relative_path(relative_path, allow_internal=True)
    resolved_target = target.resolve()
    resolved_path = (target / normalized).resolve()
    if resolved_path != resolved_target and resolved_target not in resolved_path.parents:
        raise MaterializationError(f"path escapes materialization target: {relative_path}")
    return resolved_path


def validate_target_root(target: Path) -> Path:
    """Reject dangerously broad target roots before any stateful operation."""
    resolved = target.resolve()
    if resolved == Path(resolved.anchor):
        raise MaterializationError("refusing to materialize into a filesystem root")
    try:
        home = Path.home().resolve()
    except RuntimeError:
        home = None
    if home is not None and resolved == home:
        raise MaterializationError("refusing to materialize directly into the home directory")
    return resolved


def is_preserved(path: str, preserve_paths: list[str]) -> bool:
    """Return whether a path is equal to or nested beneath a preserved path."""
    for preserved in preserve_paths:
        normalized = safe_relative_path(preserved, allow_internal=True)
        if normalized == ".holon" or normalized.startswith(".holon/"):
            raise MaterializationError("manifest preserve_paths cannot reserve Holon's .holon state")
        if path == normalized or path.startswith(normalized.rstrip("/") + "/"):
            return True
    return False


def tree_digest(root: Path) -> str:
    """Digest a source tree using only relative paths and file bytes."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise MaterializationError(f"source tree contains unsupported symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def template_values(resolved_manifest: dict[str, Any]) -> dict[str, str]:
    """Build the bounded text-template substitution map."""
    repository = str(resolved_manifest["repository"])
    values = {
        "{{repository}}": repository,
        "{{repository_name}}": repository.split("/", 1)[-1],
        "{{repository_class}}": str(resolved_manifest["repository_class"]),
        "{{security_level}}": str(resolved_manifest["security_level"]),
    }
    parameters = resolved_manifest.get("parameters", {})
    if isinstance(parameters, dict):
        for key, value in sorted(parameters.items()):
            if isinstance(value, (str, int, float, bool)) or value is None:
                if value is None:
                    rendered = "null"
                elif isinstance(value, bool):
                    rendered = str(value).lower()
                else:
                    rendered = str(value)
                values[f"{{{{parameter.{key}}}}}"] = rendered
    return values


def render_source_bytes(content: bytes, resolved_manifest: dict[str, Any], path: str) -> bytes:
    """Render bounded Holon tokens in UTF-8 text and copy binary content verbatim."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    for token, value in template_values(resolved_manifest).items():
        text = text.replace(token, value)
    unresolved = sorted(set(TEMPLATE_TOKEN_RE.findall(text)))
    if unresolved:
        raise MaterializationError(
            f"render source {path} contains unresolved Holon template tokens: {', '.join(unresolved)}"
        )
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def add_desired(
    desired: dict[str, dict[str, Any]],
    path: str,
    content: bytes,
    *,
    owner: str,
    source: str,
    allow_internal: bool = False,
) -> None:
    """Add one desired file, rejecting ambiguous collisions."""
    normalized = safe_relative_path(path, allow_internal=allow_internal)
    candidate = {
        "path": normalized,
        "sha256": sha256_bytes(content),
        "owner": owner,
        "source": source,
        "content": content,
    }
    existing = desired.get(normalized)
    if existing is None:
        desired[normalized] = candidate
        return
    if existing["sha256"] != candidate["sha256"]:
        raise MaterializationError(
            f"multiple materialization inputs produce different content for {normalized}"
        )


def load_state(target: Path) -> dict[str, Any] | None:
    """Load the current Holon ownership state if present."""
    state_path = target / STATE_RELATIVE_PATH
    if not state_path.exists():
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MaterializationError(f"unable to read Holon materialization state: {error}") from error
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA:
        raise MaterializationError("unsupported or malformed Holon materialization state")
    if not isinstance(state.get("managed_files"), list):
        raise MaterializationError("Holon materialization state managed_files must be an array")
    return state


def state_files(state: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index prior managed-file records by path."""
    if state is None:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for record in state["managed_files"]:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise MaterializationError("malformed managed-file record in Holon state")
        path = safe_relative_path(record["path"], allow_internal=True)
        result[path] = record
    return result


def atomic_write(path: Path, content: bytes) -> None:
    """Replace one file atomically within its destination directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.holon-tmp-{os.getpid()}")
    temporary.write_bytes(content)
    os.replace(temporary, path)
