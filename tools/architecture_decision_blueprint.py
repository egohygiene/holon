#!/usr/bin/env python3
"""Validate and render Holon's inherited architecture-decision scaffold."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from holon_contract import load_json, resolve_manifest
from materialization.common import atomic_write, pretty_json_bytes


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = Path("blueprints/architecture-decisions/blueprint.json")
SOURCE_PATH = Path("blueprints/architecture-decisions/files")
CATALOG_PATH = Path("catalog/foundation.json")
EXPECTED_SCHEMA = "holon.architecture-decision-blueprint/v1"
EXPECTED_VERSION = "1.0.0"
EXPECTED_CAPABILITY = "architecture-decisions"
POLICY_CONTRACT = "egohygiene.architecture-decision/v1"
POLICY_VERSION = "1.1.0"
POLICY_REPOSITORY = "egohygiene/hygiene"
POLICY_REVISION = "f598ed659a43dd759d4ede41c27f9e5daf991aa7"
POLICY_PATH = "docs/decisions/POLICY.md"
POLICY_PIN = f"{POLICY_REPOSITORY}@{POLICY_REVISION}"
DECISION_DIRECTORY = Path("docs/decisions")
INDEX_PATH = DECISION_DIRECTORY / "README.md"
POLICY_REFERENCE_PATH = DECISION_DIRECTORY / "policy-reference.json"
TEMPLATE_PATH = DECISION_DIRECTORY / "ADR-TEMPLATE.md"
ADR_FILENAME_RE = re.compile(
    r"^([A-Z][A-Z0-9]*)-([0-9]{3,})-[a-z0-9][a-z0-9-]*\.md$"
)
EXTENSION_ID_RE = re.compile(r"^egohygiene\.[a-z0-9][a-z0-9.-]*/v[0-9]+$")
EXTENSION_SCHEMA_RE = re.compile(r"^schemas/[A-Za-z0-9._/-]+\.json$")
URL_RE = re.compile(r"^https?://[^\s]+$")
DECISION_STATUSES = {"proposed", "accepted", "rejected", "superseded", "deprecated"}
REQUIRED_SECTIONS = [
    "Context",
    "Decision",
    "Alternatives considered and rejected",
    "Consequences and tradeoffs",
    "Implementation and evidence links",
    "Replacement or exit strategy",
    "Follow-up work",
]


class BlueprintError(ValueError):
    """Raised when the scaffold cannot be validated or rendered safely."""


class DuplicateKeyError(ValueError):
    """Raised when JSON silently repeats an object key."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_strict_json(path: Path) -> dict[str, Any]:
    """Load one JSON object while rejecting repeated keys."""
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise BlueprintError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_inventory(project: Path) -> list[dict[str, str]]:
    """Return the deterministic inventory of static scaffold sources."""
    source = project / SOURCE_PATH
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise BlueprintError(f"blueprint source must not contain a symlink: {path}")
    return [
        {"path": path.relative_to(source).as_posix(), "sha256": _sha256(path)}
        for path in sorted(source.rglob("*"))
        if path.is_file()
    ]


def _safe_local_schema(value: object) -> bool:
    if not isinstance(value, str) or EXTENSION_SCHEMA_RE.fullmatch(value) is None:
        return False
    return ".." not in Path(value).parts


def validate_extensions(value: object) -> list[str]:
    """Validate bounded local extension registrations from manifest parameters."""
    if value is None:
        return []
    if not isinstance(value, list):
        return ["parameter adr_extensions must be an array"]
    errors: list[str] = []
    identifiers: list[str] = []
    expected = {"id", "kind", "schema", "required"}
    for index, item in enumerate(value):
        prefix = f"parameter adr_extensions[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if set(item) != expected:
            errors.append(f"{prefix} must contain only id, kind, schema, and required")
            continue
        identifier = item.get("id")
        if not isinstance(identifier, str) or EXTENSION_ID_RE.fullmatch(identifier) is None:
            errors.append(f"{prefix}.id is not a versioned Ego Hygiene extension ID")
        else:
            identifiers.append(identifier)
        if item.get("kind") not in {"metadata", "validation"}:
            errors.append(f"{prefix}.kind must be metadata or validation")
        if not _safe_local_schema(item.get("schema")):
            errors.append(f"{prefix}.schema must be a safe repository-local schemas/*.json path")
        if not isinstance(item.get("required"), bool):
            errors.append(f"{prefix}.required must be boolean")
    if len(identifiers) != len(set(identifiers)):
        errors.append("parameter adr_extensions must not repeat an extension ID")
    return errors


def validate_exceptions(value: object) -> list[str]:
    """Validate explicit local exceptions without expanding global policy authority."""
    if value is None:
        return []
    if not isinstance(value, list):
        return ["parameter adr_exceptions must be an array"]
    errors: list[str] = []
    expected = {"rule", "reason", "status", "owner", "approval_evidence", "expires"}
    for index, item in enumerate(value):
        prefix = f"parameter adr_exceptions[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if set(item) != expected:
            errors.append(
                f"{prefix} must contain only rule, reason, status, owner, approval_evidence, and expires"
            )
            continue
        for key in ("rule", "reason", "owner"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                errors.append(f"{prefix}.{key} must be a non-empty string")
        if isinstance(item.get("reason"), str) and len(item["reason"]) > 500:
            errors.append(f"{prefix}.reason must contain at most 500 characters")
        status = item.get("status")
        if status not in {"proposed", "approved", "expired"}:
            errors.append(f"{prefix}.status is invalid")
        approval = item.get("approval_evidence")
        if approval is not None and (
            not isinstance(approval, str) or URL_RE.match(approval) is None
        ):
            errors.append(f"{prefix}.approval_evidence must be null or an HTTP(S) URL")
        if status == "approved" and not isinstance(approval, str):
            errors.append(f"{prefix}.approval_evidence is required for an approved exception")
        expires = item.get("expires")
        if expires is not None:
            if not isinstance(expires, str):
                errors.append(f"{prefix}.expires must be null or an ISO date")
            else:
                try:
                    date.fromisoformat(expires)
                except ValueError:
                    errors.append(f"{prefix}.expires must be null or an ISO date")
    return errors


def _manifest_parameters(resolved: dict[str, Any]) -> tuple[list[Any], list[Any], list[str]]:
    parameters = resolved.get("parameters", {})
    if not isinstance(parameters, dict):
        return [], [], ["resolved manifest parameters must be an object"]
    extensions = parameters.get("adr_extensions", [])
    exceptions = parameters.get("adr_exceptions", [])
    errors = validate_extensions(extensions) + validate_exceptions(exceptions)
    valid_extensions = extensions if isinstance(extensions, list) else []
    valid_exceptions = exceptions if isinstance(exceptions, list) else []
    return valid_extensions, valid_exceptions, errors


def validate_blueprint(project: Path = ROOT) -> list[str]:
    """Validate the profile, template, capability, pin, and example contract."""
    project = project.resolve()
    errors: list[str] = []
    try:
        profile = load_strict_json(project / PROFILE_PATH)
        catalog = load_json(project / CATALOG_PATH)
        template = (project / SOURCE_PATH / TEMPLATE_PATH).read_text(encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"architecture-decision blueprint source is invalid: {error}"]

    expected_policy = {
        "contract": POLICY_CONTRACT,
        "version": POLICY_VERSION,
        "source": {
            "repository": POLICY_REPOSITORY,
            "revision": POLICY_REVISION,
            "path": POLICY_PATH,
        },
    }
    expected_profile_keys = {
        "$schema",
        "schema",
        "version",
        "status",
        "capability",
        "template_source",
        "render_command",
        "policy",
        "decision_directory",
        "index",
        "optional_parameters",
        "ownership",
        "files",
    }
    if set(profile) != expected_profile_keys:
        errors.append("blueprint profile has unsupported or missing fields")
    if profile.get("schema") != EXPECTED_SCHEMA:
        errors.append(f"blueprint schema must be {EXPECTED_SCHEMA}")
    if profile.get("version") != EXPECTED_VERSION:
        errors.append(f"blueprint version must be {EXPECTED_VERSION}")
    if profile.get("status") != "active":
        errors.append("architecture-decision blueprint must be active")
    if profile.get("capability") != EXPECTED_CAPABILITY:
        errors.append(f"blueprint capability must be {EXPECTED_CAPABILITY}")
    if profile.get("template_source") != SOURCE_PATH.as_posix():
        errors.append(f"blueprint template_source must be {SOURCE_PATH}")
    if profile.get("render_command") != (
        "python3 tools/architecture_decision_blueprint.py render-pack"
    ):
        errors.append("blueprint render_command must use the bounded ADR pack renderer")
    if profile.get("policy") != expected_policy:
        errors.append("blueprint policy must match the approved Hygiene v1.1.0 revision")
    if profile.get("decision_directory") != DECISION_DIRECTORY.as_posix():
        errors.append("blueprint decision_directory must be docs/decisions")
    if profile.get("index") != INDEX_PATH.as_posix():
        errors.append("blueprint index must be docs/decisions/README.md")
    optional_parameters = profile.get("optional_parameters")
    if not isinstance(optional_parameters, list) or set(optional_parameters) != {
        "adr_extensions",
        "adr_exceptions",
    }:
        errors.append("blueprint optional parameters must be adr_extensions and adr_exceptions")
    expected_ownership = {
        "generated": {
            TEMPLATE_PATH.as_posix(),
            INDEX_PATH.as_posix(),
            POLICY_REFERENCE_PATH.as_posix(),
        },
        "repository": {"docs/decisions/ADR-NNN-short-slug.md"},
    }
    ownership = profile.get("ownership")
    if not isinstance(ownership, dict) or any(
        set(ownership.get(kind, [])) != paths for kind, paths in expected_ownership.items()
    ):
        errors.append("blueprint generated and repository ownership paths are invalid")
    if profile.get("files") != source_inventory(project):
        errors.append("blueprint static file inventory is stale")

    if "{{repository}}" not in template:
        errors.append("ADR template must project the consuming repository identity")
    section_offsets = [template.find(f"## {section}") for section in REQUIRED_SECTIONS]
    if any(offset < 0 for offset in section_offsets) or section_offsets != sorted(section_offsets):
        errors.append("ADR template must contain the seven required sections in policy order")
    required_frontmatter = {
        "schema:", "id:", "title:", "status:", "date:", "decision_scope:",
        "visibility:", "owners:", "issue:", "pull_request:", "related:",
        "supersedes:", "superseded_by:", "affected_repositories:",
        "affected_contracts:", "implementation_status:", "evidence:",
        "exceptions:", "approval:",
    }
    if not all(
        any(line.startswith(key) for line in template.splitlines())
        for key in required_frontmatter
    ):
        errors.append("ADR template is missing required policy front matter")

    capability = catalog.get("capabilities", {}).get(EXPECTED_CAPABILITY)
    if not isinstance(capability, dict) or capability.get("owner") != "egohygiene/holon":
        errors.append("foundation catalog must expose the Holon-owned architecture-decisions capability")
    for class_name, repository_class in sorted(catalog.get("repository_classes", {}).items()):
        if EXPECTED_CAPABILITY not in repository_class.get("required_capabilities", []):
            errors.append(f"repository class {class_name} must require architecture-decisions")

    for path in sorted((project / "examples").glob("*.manifest.json")):
        try:
            manifest = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"{path.name}: unable to load manifest: {error}")
            continue
        resolved, manifest_errors = resolve_manifest(catalog, manifest)
        errors.extend(f"{path.name}: {error}" for error in manifest_errors)
        if resolved is not None:
            if resolved.get("pins", {}).get("adr_policy") != POLICY_PIN:
                errors.append(f"{path.name}: adr_policy must pin the approved Hygiene revision")
            _, _, parameter_errors = _manifest_parameters(resolved)
            errors.extend(f"{path.name}: {error}" for error in parameter_errors)
    return sorted(set(errors))


def _frontmatter_scalars(path: Path) -> dict[str, str]:
    """Read the four scalar fields needed for a deterministic index."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise BlueprintError(f"unable to read ADR {path}: {error}") from error
    if not text.startswith("---\n"):
        raise BlueprintError(f"ADR lacks YAML front matter: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise BlueprintError(f"ADR front matter is not terminated: {path}")
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line or line[0].isspace() or line.startswith("-") or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        if key in values:
            raise BlueprintError(f"ADR repeats front matter field {key}: {path}")
        value = raw.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    required = {"id", "title", "status", "date"}
    missing = required - set(values)
    if missing:
        raise BlueprintError(f"ADR {path} is missing index fields: {', '.join(sorted(missing))}")
    if not values["title"] or values["title"] in {">", "|"}:
        raise BlueprintError(f"ADR title must be one non-empty scalar: {path}")
    return values


def decision_records(repository_root: Path) -> list[dict[str, Any]]:
    """Read repository-owned ADR metadata in stable numeric order."""
    directory = repository_root / DECISION_DIRECTORY
    if not directory.exists():
        return []
    if directory.is_symlink():
        raise BlueprintError(f"decision directory must not be a symlink: {directory}")
    if not directory.is_dir():
        raise BlueprintError(f"decision directory is not a directory: {directory}")
    records: list[dict[str, Any]] = []
    identities: set[tuple[str, int]] = set()
    for path in sorted(directory.glob("*.md")):
        if path.is_symlink():
            raise BlueprintError(f"ADR must not be a symlink: {path}")
        if path.name in {"ADR-TEMPLATE.md", "README.md"}:
            continue
        match = ADR_FILENAME_RE.fullmatch(path.name)
        if match is None:
            if not path.name.startswith("ADR-"):
                continue
            raise BlueprintError(f"ADR filename does not preserve a numeric identity: {path.name}")
        values = _frontmatter_scalars(path)
        prefix = match.group(1)
        digits = match.group(2)
        number = int(digits)
        expected_id = f"{prefix}-{digits}"
        if values["id"] != expected_id:
            raise BlueprintError(f"ADR ID {values['id']} does not match filename {path.name}")
        identity = (prefix, number)
        if identity in identities:
            raise BlueprintError(f"ADR identity is repeated: {expected_id}")
        if values["status"] not in DECISION_STATUSES:
            raise BlueprintError(f"ADR {expected_id} has invalid decision status {values['status']}")
        try:
            date.fromisoformat(values["date"])
        except ValueError as error:
            raise BlueprintError(f"ADR {expected_id} has invalid date {values['date']}") from error
        identities.add(identity)
        records.append({
            "number": number,
            "id": expected_id,
            "title": values["title"],
            "status": values["status"],
            "date": values["date"],
            "filename": path.name,
        })
    return sorted(
        records,
        key=lambda record: (record["number"], record["id"], record["filename"]),
    )


def _table_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def render_index(repository: str, records: list[dict[str, Any]]) -> bytes:
    """Render the canonical human index deterministically."""
    lines = [
        "# Architecture decisions",
        "",
        (
            "<!-- Generated by egohygiene/holon architecture-decisions 1.0.0; "
            f"policy {POLICY_VERSION}@{POLICY_REVISION}. Do not edit by hand. -->"
        ),
        "",
        (
            "This repository inherits the Ego Hygiene ADR policy through "
            f"[{POLICY_REFERENCE_PATH.name}]({POLICY_REFERENCE_PATH.name})."
        ),
        f"Decision records are human-owned by `{repository}`; this index is a generated projection.",
        "",
        "## Decision index",
        "",
    ]
    if records:
        lines.extend([
            "| ID | Decision | Status | Date |",
            "| --- | --- | --- | --- |",
        ])
        for record in records:
            lines.append(
                f"| [{record['id']}]({record['filename']}) | "
                f"{_table_text(str(record['title']))} | "
                f"{str(record['status']).replace('_', ' ').title()} | {record['date']} |"
            )
    else:
        lines.append("No architecture decisions have been recorded yet.")
    lines.extend([
        "",
        "Create the next record from [ADR-TEMPLATE.md](ADR-TEMPLATE.md). Preserve missing",
        "numbers and every rejected, deprecated, accepted, or superseded record.",
        "",
    ])
    return "\n".join(lines).encode("utf-8")


def build_pack(
    project: Path,
    resolved: dict[str, Any],
    repository_root: Path,
) -> dict[str, bytes]:
    """Build the three generated scaffold files without changing the repository."""
    profile_errors = validate_blueprint(project)
    if profile_errors:
        raise BlueprintError("blueprint is invalid: " + "; ".join(profile_errors))
    if EXPECTED_CAPABILITY not in resolved.get("capabilities", []):
        raise BlueprintError("resolved manifest does not select architecture-decisions")
    if resolved.get("pins", {}).get("adr_policy") != POLICY_PIN:
        raise BlueprintError(f"resolved manifest adr_policy must equal {POLICY_PIN}")
    repository = resolved.get("repository")
    if not isinstance(repository, str) or re.fullmatch(
        r"egohygiene/(?:\.github|[a-z0-9][a-z0-9.-]*)", repository
    ) is None:
        raise BlueprintError("resolved manifest repository identity is invalid")
    extensions, exceptions, parameter_errors = _manifest_parameters(resolved)
    if parameter_errors:
        raise BlueprintError("; ".join(parameter_errors))
    policy_reference = {
        "schema": "egohygiene.architecture-decision-policy-reference/v1",
        "repository": repository,
        "policy": {
            "contract": POLICY_CONTRACT,
            "version": POLICY_VERSION,
            "source": {
                "repository": POLICY_REPOSITORY,
                "revision": POLICY_REVISION,
                "path": POLICY_PATH,
            },
        },
        "decision_directory": DECISION_DIRECTORY.as_posix(),
        "index": INDEX_PATH.as_posix(),
        "extensions": extensions,
        "exceptions": exceptions,
    }
    template = (project / SOURCE_PATH / TEMPLATE_PATH).read_text(encoding="utf-8")
    template = template.replace("{{repository}}", repository)
    records = decision_records(repository_root)
    return {
        POLICY_REFERENCE_PATH.as_posix(): pretty_json_bytes(policy_reference),
        TEMPLATE_PATH.as_posix(): template.encode("utf-8"),
        INDEX_PATH.as_posix(): render_index(repository, records),
    }


def write_pack(output: Path, desired: dict[str, bytes]) -> None:
    """Write a review pack without deleting or replacing different existing bytes."""
    output = Path(os.path.abspath(os.fspath(output)))
    for candidate in (output, *output.parents):
        if candidate.is_symlink():
            raise BlueprintError(f"render-pack output uses a symlink path component: {candidate}")
    if output.exists() and not output.is_dir():
        raise BlueprintError(f"render-pack output is not a directory: {output}")
    existing: set[str] = set()
    if output.exists():
        for path in output.rglob("*"):
            if path.is_symlink():
                raise BlueprintError(f"render-pack output contains a symlink: {path}")
            if path.is_file():
                existing.add(path.relative_to(output).as_posix())
    unexpected = existing - set(desired)
    if unexpected:
        raise BlueprintError(
            "render-pack output contains unexpected files: " + ", ".join(sorted(unexpected))
        )
    for relative, content in sorted(desired.items()):
        destination = output / relative
        if destination.exists() and destination.read_bytes() != content:
            raise BlueprintError(f"render-pack output already differs: {destination}")
    for relative, content in sorted(desired.items()):
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            atomic_write(destination, content)


def render_pack(project: Path, manifest_path: Path, repository_root: Path, output: Path) -> dict[str, bytes]:
    """Resolve a manifest, scan local ADRs, and emit a separate review pack."""
    project = project.resolve()
    repository_root = repository_root.resolve()
    output = Path(os.path.abspath(os.fspath(output)))
    if not repository_root.is_dir():
        raise BlueprintError(f"repository root is not a directory: {repository_root}")
    if output == repository_root or repository_root in output.parents:
        raise BlueprintError("render-pack output must be outside the target repository")
    catalog = load_json(project / CATALOG_PATH)
    manifest = load_json(manifest_path)
    resolved, errors = resolve_manifest(catalog, manifest)
    if errors:
        raise BlueprintError("foundation manifest is invalid: " + "; ".join(errors))
    assert resolved is not None
    desired = build_pack(project, resolved, repository_root)
    write_pack(output, desired)
    return desired


def main() -> int:
    """Validate the canonical profile or render one separate review pack."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("validate")
    render = subparsers.add_parser(
        "render-pack",
        help="Scan repository-owned ADRs and emit a generated review pack outside the target.",
    )
    render.add_argument("--manifest", type=Path, required=True)
    render.add_argument("--repository-root", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    project = arguments.project.expanduser().resolve()
    try:
        errors = validate_blueprint(project)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        if arguments.command == "render-pack":
            desired = render_pack(
                project,
                arguments.manifest.expanduser().resolve(),
                arguments.repository_root.expanduser().resolve(),
                arguments.output.expanduser().resolve(),
            )
            print(
                f"Rendered architecture-decision pack ({len(desired)} files) "
                f"to {arguments.output.expanduser().resolve()}"
            )
            return 0
        profile = load_strict_json(project / PROFILE_PATH)
        print(
            f"Validated architecture-decision blueprint {profile['version']} "
            f"({len(profile['files'])} static source file)"
        )
        return 0
    except (BlueprintError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"architecture-decision blueprint failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
