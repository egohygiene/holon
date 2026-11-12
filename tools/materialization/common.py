"""Deterministic filesystem and provenance primitives for Holon materialization."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
from typing import Any

ENGINE_VERSION = "1.0.0"
PLAN_SCHEMA = "holon.materialization-plan/v1"
STATE_SCHEMA = "holon.materialization-state/v1"
ROLLBACK_SCHEMA = "holon.materialization-rollback/v1"
STATE_RELATIVE_PATH = ".holon/materialization-state.v1.json"
RESOLVED_MANIFEST_RELATIVE_PATH = ".holon/resolved-manifest.v1.json"
BACKUPS_RELATIVE_PATH = ".holon/backups"
TEMPLATE_TOKEN_RE = re.compile(
    r"\{\{(?:repository|repository_name|repository_class|security_level|"
    r"parameter(?:_json)?\.[A-Za-z0-9_.-]+)\}\}"
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
    if normalized == ".":
        raise MaterializationError(f"unsafe repository-relative path: {value!r}")
    if any(part.casefold() == ".git" for part in pure.parts):
        raise MaterializationError(f"materialization cannot target Git internals: {normalized}")
    if not allow_internal and pure.parts and pure.parts[0].casefold() == ".holon":
        raise MaterializationError(f"render sources cannot target Holon state paths: {normalized}")
    return normalized


def _require_boundary_runtime() -> None:
    if os.name == "nt" and not callable(getattr(Path, "is_junction", None)):
        raise MaterializationError(
            "Windows materialization boundaries require Python 3.12 or newer with junction-aware pathlib"
        )


def validate_path_components(path: Path, *, kind: str | None = None) -> Path:
    """Reject aliases and unsupported ancestors without erasing them via resolve.

    Missing ordinary paths are allowed for planned creation. Existing components
    must be directories, with an optional regular-file leaf. A dangling link is
    still a link; exists() alone is not a boundary check. This does not serialize
    concurrent filesystem changes by another process.
    """
    _require_boundary_runtime()
    absolute = path.absolute()
    if ".." in absolute.parts:
        raise MaterializationError(f"path contains parent traversal: {path}")
    components = (*reversed(absolute.parents), absolute)
    for component in components:
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise MaterializationError(f"unable to inspect filesystem path: {component}") from error
        reparse_point = getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(metadata.st_mode) or reparse_point or getattr(component, "is_junction", lambda: False)():
            raise MaterializationError(f"filesystem path contains an unsupported symlink: {component}")
        leaf = component == absolute
        if not leaf or kind == "directory":
            if not stat.S_ISDIR(metadata.st_mode):
                raise MaterializationError(f"filesystem path requires a directory: {component}")
        elif not stat.S_ISREG(metadata.st_mode) and not (kind is None and stat.S_ISDIR(metadata.st_mode)):
            raise MaterializationError(f"filesystem path requires a regular file: {component}")
    return absolute


def read_regular_file(path: Path) -> bytes:
    """Read a checked regular file without following a final link or opening a FIFO."""
    path = validate_path_components(path, kind="file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise MaterializationError(f"filesystem path requires a regular file: {path}")
            return handle.read()
    except OSError as error:
        raise MaterializationError(f"unable to read regular filesystem file: {path}") from error


def target_path(target: Path, relative_path: str, *, kind: str | None = None) -> Path:
    """Check one path beneath an already canonicalized consumer/recovery root."""
    normalized = safe_relative_path(relative_path, allow_internal=True)
    root = validate_path_components(target, kind="directory")
    candidate = validate_path_components(root / normalized, kind=kind)
    resolved_target = root.resolve()
    resolved_path = candidate.resolve()
    if resolved_path != resolved_target and resolved_target not in resolved_path.parents:
        raise MaterializationError(f"path escapes materialization target: {relative_path}")
    # Reapply namespace validation to the actual destination as well as the
    # caller spelling. Checked components must not turn an ordinary file into
    # Git metadata through an alias or platform-specific path interpretation.
    actual = resolved_path.relative_to(resolved_target).as_posix()
    safe_relative_path(actual, allow_internal=True)
    return candidate


def validate_target_root(target: Path) -> Path:
    """Reject dangerously broad target roots before any stateful operation."""
    _require_boundary_runtime()
    # Preserve explicit existing directory-root aliases: the chosen consumer
    # root is canonicalized once, before relative managed paths are checked.
    # Dangling root/ancestor aliases and non-directory roots are not targets.
    absolute = target.absolute()
    if any(part.casefold() == ".git" for part in absolute.parts):
        raise MaterializationError("refusing to materialize inside Git internals")
    for component in (*reversed(absolute.parents), absolute):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        reparse_point = getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (stat.S_ISLNK(metadata.st_mode) or reparse_point) and not component.exists():
            raise MaterializationError(f"materialization target uses a dangling symlink: {component}")
        if component.exists() and not component.is_dir():
            raise MaterializationError(f"materialization target requires a directory: {component}")
    resolved = target.resolve()
    if resolved == Path(resolved.anchor):
        raise MaterializationError("refusing to materialize into a filesystem root")
    try:
        home = Path.home().resolve()
    except RuntimeError:
        home = None
    if home is not None and resolved == home:
        raise MaterializationError("refusing to materialize directly into the home directory")
    if any(part.casefold() == ".git" for part in resolved.parts):
        raise MaterializationError("refusing to materialize inside Git internals")
    return resolved


def is_preserved(path: str, preserve_paths: list[str]) -> bool:
    """Return whether a path is equal to or nested beneath a preserved path."""
    for preserved in preserve_paths:
        normalized = safe_relative_path(preserved, allow_internal=True)
        if normalized.split("/", 1)[0].casefold() == ".holon":
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
            values[f"{{{{parameter_json.{key}}}}}"] = canonical_bytes(value).decode("utf-8")
            if isinstance(value, (dict, list)):
                rendered = canonical_bytes(value).decode("utf-8")
            elif isinstance(value, (str, int, float, bool)) or value is None:
                if value is None:
                    rendered = "null"
                elif isinstance(value, bool):
                    rendered = str(value).lower()
                else:
                    rendered = str(value)
            else:
                continue
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
    replace: bool = False,
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
    if existing is None or replace:
        desired[normalized] = candidate
        return
    if existing["sha256"] != candidate["sha256"]:
        raise MaterializationError(
            f"multiple materialization inputs produce different content for {normalized}"
        )


def load_state(target: Path) -> dict[str, Any] | None:
    """Load the current Holon ownership state if present."""
    state_path = target_path(target, STATE_RELATIVE_PATH, kind="file")
    if not state_path.exists():
        return None
    try:
        state = json.loads(read_regular_file(state_path).decode("utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MaterializationError(f"unable to read Holon materialization state: {error}") from error
    return validate_state(state)


def validate_state(state: Any) -> dict[str, Any]:
    """Validate the generic ownership boundary, including recovered state."""
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA:
        raise MaterializationError("unsupported or malformed Holon materialization state")
    if not isinstance(state.get("managed_files"), list):
        raise MaterializationError("Holon materialization state managed_files must be an array")
    state_files(state)
    return state


def state_files(state: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index prior managed-file records by path."""
    if state is None:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for record in state["managed_files"]:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise MaterializationError("malformed managed-file record in Holon state")
        path = safe_relative_path(record["path"], allow_internal=record["path"] == RESOLVED_MANIFEST_RELATIVE_PATH)
        if path in result:
            raise MaterializationError(f"duplicate managed path in Holon state: {path}")
        result[path] = record
    return result


def atomic_write(path: Path, content: bytes) -> None:
    """Replace one file atomically within its destination directory."""
    path = validate_path_components(path, kind="file")
    path.parent.mkdir(parents=True, exist_ok=True)
    validate_path_components(path, kind="file")
    descriptor = -1
    temporary: Path | None = None
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    for _ in range(128):
        candidate = path.with_name(
            f".{path.name}.holon-tmp-{secrets.token_hex(16)}"
        )
        try:
            descriptor = os.open(candidate, flags, 0o666)
        except FileExistsError:
            continue
        temporary = candidate
        break
    if temporary is None:
        raise MaterializationError(
            f"unable to allocate a unique atomic-write path for {path.name}"
        )
    try:
        if path.is_file():
            os.fchmod(descriptor, path.lstat().st_mode & 0o777)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        validate_path_components(path, kind="file")
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
