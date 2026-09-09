#!/usr/bin/env python3
"""Validate Holon's pinned repository-continuity materialization profile."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


PROFILE_SCHEMA = "holon.repository-continuity-materialization-profile/v1"
PROFILE_PATH = Path("catalog/repository-continuity-materialization.json")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MANAGED_BEGIN = "<!-- BEGIN AETHER REPOSITORY-CONTINUITY -->"
MANAGED_END = "<!-- END AETHER REPOSITORY-CONTINUITY -->"

TOP_LEVEL_KEYS = {
    "schema_version",
    "version",
    "status",
    "owner",
    "updated",
    "purpose",
    "rollout",
    "sources",
    "surfaces",
    "reconciliation",
    "repository_profiles",
    "information_safety",
    "ownership",
}
SOURCE_KEYS = {
    "id",
    "role",
    "repository",
    "revision",
    "version",
    "lifecycle",
    "release_included",
    "artifacts",
}
ARTIFACT_KEYS = {"id", "kind", "path", "sha256", "url"}
SURFACE_KEYS = {
    "id",
    "path",
    "kind",
    "ownership",
    "strategy",
    "source_role",
    "source_artifact",
    "begin_marker",
    "end_marker",
    "required",
}
PROFILE_KEYS = {
    "id",
    "repository_classes",
    "visibilities",
    "requirement",
}
RECONCILIATION_KEYS = {
    "preserve_outside_managed_block",
    "require_exactly_one_managed_block",
    "duplicate_or_malformed_markers",
    "unmanaged_existing_instruction",
    "existing_continuity",
    "explicit_opt_out",
    "unsupported_state",
    "symlink_or_non_regular",
}
EXPECTED_SOURCES = {
    "portable-contract": (
        "aether-continuity",
        "egohygiene/aether",
        "1.0.0",
        "draft",
        False,
    ),
    "organization-policy": (
        "hygiene-continuity",
        "egohygiene/hygiene",
        "1.0.0-alpha.1",
        "proposed",
        False,
    ),
    "validator": (
        "egolint-continuity",
        "egohygiene/egolint",
        "0.1.0-alpha.1",
        "proposed",
        False,
    ),
}
EXPECTED_ARTIFACTS = {
    "portable-contract": {
        "repository-continuity-schema": (
            "schema",
            "catalog/schemas/aether.repository-continuity.v1.schema.json",
        ),
        "repository-continuity-specification": (
            "specification",
            "library/organization/specs/methodology/repository-continuity.spec.md",
        ),
        "repository-continuity-instruction": (
            "instruction",
            "library/organization/instructions/repository-continuity/INSTRUCTION.md",
        ),
        "continuity-dispositions": (
            "disposition-catalog",
            "library/organization/instructions/repository-continuity/continuity-dispositions.v1.json",
        ),
        "maintain-repository-continuity": (
            "skill",
            "library/organization/skills/methodology/maintain-repository-continuity/SKILL.md",
        ),
        "continuity-template": (
            "template",
            "library/organization/skills/methodology/maintain-repository-continuity/templates/CONTINUITY.template.md",
        ),
        "codex-repository-instructions": (
            "provider-projection",
            "dist/codex/repository/AGENTS.md",
        ),
        "claude-repository-instructions": (
            "provider-projection",
            "dist/claude/repository/CLAUDE.md",
        ),
        "github-copilot-instructions": (
            "provider-projection",
            "dist/github/repository/.github/copilot-instructions.md",
        ),
    },
    "organization-policy": {
        "repository-continuity-policy": ("policy", "catalog/repository-continuity-policy.json"),
        "repository-context-contract": ("contract", "contracts/repository-context.toml"),
        "repository-continuity-policy-schema": (
            "schema",
            "schemas/repository-continuity-policy.v1.schema.json",
        ),
        "repository-context-schema": (
            "schema",
            "schemas/repository-context.v2.schema.json",
        ),
    },
    "validator": {
        "repository-continuity-rule-catalog": (
            "rule-catalog",
            ".config/rules/repository-continuity.v1.toml",
        ),
        "repository-continuity-schema": (
            "schema",
            "schemas/repository-continuity.schema.json",
        ),
        "repository-continuity-report-schema": (
            "report-schema",
            "schemas/repository-continuity-report.schema.json",
        ),
    },
}
EXPECTED_SURFACES = {
    "CONTINUITY.md": (
        "continuity-checkpoint",
        "repository-owned",
        "evidence-grounded-template",
        "portable-contract",
        "continuity-template",
        True,
    ),
    "AGENTS.md": (
        "agent-instructions",
        "repository-owned",
        "managed-block",
        "portable-contract",
        "codex-repository-instructions",
        True,
    ),
    ".github/copilot-instructions.md": (
        "github-copilot-instructions",
        "repository-owned",
        "managed-block",
        "portable-contract",
        "github-copilot-instructions",
        False,
    ),
    "CLAUDE.md": (
        "claude-code-instructions",
        "repository-owned",
        "managed-block",
        "portable-contract",
        "claude-repository-instructions",
        False,
    ),
}
EXPECTED_PROFILES = {
    "research-publication",
    "library-cli",
    "site-application",
    "organization-meta",
    "private-creative",
}
REPOSITORY_CLASSES = {"library", "tool", "product", "publication"}
VISIBILITIES = {"public", "private", "internal"}
PROHIBITED_DATA = {
    "secrets-and-credentials",
    "private-conversation-text",
    "sensitive-personal-data",
    "unpublished-private-business-data",
    "private-local-paths",
    "unrelated-private-context",
}


class ProfileError(RuntimeError):
    """Raised when source verification cannot proceed safely."""


def load_json(path: Path) -> dict[str, Any]:
    """Load one JSON object."""
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _closed_keys(value: Any, expected: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return False
    missing = expected - set(value)
    unknown = set(value) - expected
    if missing:
        errors.append(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        errors.append(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    return not missing and not unknown


def _string_list(value: Any, label: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        errors.append(f"{label} must contain non-empty strings")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{label} must not contain duplicates")
    return value


def _safe_source_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and "." not in path.parts and ".." not in path.parts


def _validate_sources(profile: dict[str, Any], errors: list[str]) -> dict[str, dict[str, Any]]:
    sources = profile.get("sources")
    if not isinstance(sources, list):
        errors.append("sources must be an array")
        return {}
    by_role: dict[str, dict[str, Any]] = {}
    artifact_ids: set[tuple[str, str]] = set()
    artifact_paths: set[tuple[str, str]] = set()
    for index, source in enumerate(sources):
        label = f"sources[{index}]"
        if not _closed_keys(source, SOURCE_KEYS, label, errors):
            continue
        role = source["role"]
        if not isinstance(role, str) or role not in EXPECTED_SOURCES:
            errors.append(f"{label}.role is unsupported: {role!r}")
            continue
        if role in by_role:
            errors.append(f"sources repeats role {role}")
        by_role[role] = source
        (
            expected_id,
            expected_repository,
            expected_version,
            expected_lifecycle,
            expected_release_included,
        ) = EXPECTED_SOURCES[role]
        if source["id"] != expected_id:
            errors.append(f"{label}.id must be {expected_id}")
        if source["repository"] != expected_repository:
            errors.append(f"{label}.repository must be {expected_repository}")
        if not isinstance(source["revision"], str) or not REVISION_RE.fullmatch(source["revision"]):
            errors.append(f"{label}.revision must be a full lowercase commit SHA")
        if not isinstance(source["version"], str) or not SEMVER_RE.fullmatch(
            source["version"]
        ):
            errors.append(f"{label}.version must be semantic")
        if not isinstance(source["lifecycle"], str) or source["lifecycle"] not in {
            "draft",
            "proposed",
            "implemented",
            "released",
            "deprecated",
        }:
            errors.append(f"{label}.lifecycle is unsupported")
        if not isinstance(source["release_included"], bool):
            errors.append(f"{label}.release_included must be boolean")
        if (
            source["version"],
            source["lifecycle"],
            source["release_included"],
        ) != (
            expected_version,
            expected_lifecycle,
            expected_release_included,
        ):
            errors.append(f"{label} overclaims or does not match its approved source version")
        artifacts = source["artifacts"]
        if not isinstance(artifacts, list) or not artifacts:
            errors.append(f"{label}.artifacts must be a non-empty array")
            continue
        for artifact_index, artifact in enumerate(artifacts):
            artifact_label = f"{label}.artifacts[{artifact_index}]"
            if not _closed_keys(artifact, ARTIFACT_KEYS, artifact_label, errors):
                continue
            artifact_id = artifact["id"]
            path = artifact["path"]
            if not isinstance(artifact_id, str) or not artifact_id:
                errors.append(f"{artifact_label}.id must be a non-empty string")
            if not isinstance(artifact["kind"], str) or artifact["kind"] not in {
                "schema",
                "specification",
                "instruction",
                "disposition-catalog",
                "skill",
                "template",
                "provider-projection",
                "policy",
                "contract",
                "rule-catalog",
                "report-schema",
            }:
                errors.append(f"{artifact_label}.kind is unsupported")
            if not _safe_source_path(path):
                errors.append(f"{artifact_label}.path must be a safe repository-relative path")
            if not isinstance(artifact["sha256"], str) or not SHA256_RE.fullmatch(
                artifact["sha256"]
            ):
                errors.append(f"{artifact_label}.sha256 must be lowercase SHA-256")
            expected_url = (
                f"https://github.com/{source['repository']}/blob/{source['revision']}/{path}"
            )
            if artifact["url"] != expected_url:
                errors.append(f"{artifact_label}.url must pin the declared repository and revision")
            if isinstance(artifact_id, str) and (role, artifact_id) in artifact_ids:
                errors.append(f"{label}.artifacts repeats id {artifact_id}")
            if isinstance(path, str) and (role, path) in artifact_paths:
                errors.append(f"{label}.artifacts repeats path {path}")
            if isinstance(artifact_id, str):
                artifact_ids.add((role, artifact_id))
            if isinstance(path, str):
                artifact_paths.add((role, path))
        actual_artifacts = {
            artifact.get("id"): (artifact.get("kind"), artifact.get("path"))
            for artifact in artifacts
            if isinstance(artifact, dict) and isinstance(artifact.get("id"), str)
        }
        if actual_artifacts != EXPECTED_ARTIFACTS[role]:
            errors.append(f"{label}.artifacts must declare the exact approved {role} inputs")
    missing_roles = set(EXPECTED_SOURCES) - set(by_role)
    if missing_roles:
        errors.append(f"sources is missing roles: {', '.join(sorted(missing_roles))}")
    return by_role


def _validate_rollout(
    profile: dict[str, Any], sources: dict[str, dict[str, Any]], errors: list[str]
) -> None:
    rollout = profile.get("rollout")
    keys = {"stage", "maximum_stage_before_release", "activation_gate", "unavailable_behavior"}
    if not _closed_keys(rollout, keys, "rollout", errors):
        return
    if not isinstance(rollout["stage"], str) or rollout["stage"] not in {
        "observe",
        "ratchet",
        "enforce",
    }:
        errors.append("rollout.stage is unsupported")
    if rollout["maximum_stage_before_release"] != "observe":
        errors.append("rollout.maximum_stage_before_release must be observe")
    gates = _string_list(rollout["activation_gate"], "rollout.activation_gate", errors)
    if not gates:
        errors.append("rollout.activation_gate must not be empty")
    if rollout["unavailable_behavior"] != "fail-closed-with-explicit-provisional-state":
        errors.append("rollout.unavailable_behavior must fail closed")
    unreleased = any(
        source.get("lifecycle") != "released" or source.get("release_included") is not True
        for source in sources.values()
    )
    if unreleased and rollout["stage"] != "observe":
        errors.append("unreleased sources require rollout.stage observe")
    if unreleased and profile.get("status") != "proposed":
        errors.append("unreleased sources require profile status proposed")


def _artifact_exists(sources: dict[str, dict[str, Any]], role: str, artifact_id: str) -> bool:
    source = sources.get(role, {})
    return any(
        isinstance(artifact, dict) and artifact.get("id") == artifact_id
        for artifact in source.get("artifacts", [])
    )


def _validate_surfaces(
    profile: dict[str, Any], sources: dict[str, dict[str, Any]], errors: list[str]
) -> None:
    surfaces = profile.get("surfaces")
    if not isinstance(surfaces, list):
        errors.append("surfaces must be an array")
        return
    by_path: dict[str, dict[str, Any]] = {}
    for index, surface in enumerate(surfaces):
        label = f"surfaces[{index}]"
        if not _closed_keys(surface, SURFACE_KEYS, label, errors):
            continue
        path = surface["path"]
        if not _safe_source_path(path):
            errors.append(f"{label}.path must be a safe repository-relative path")
            continue
        if path in by_path:
            errors.append(f"surfaces repeats path {path}")
        by_path[path] = surface
        if surface["kind"] != "file":
            errors.append(f"{label}.kind must be file")
        if surface["source_role"] not in EXPECTED_SOURCES:
            errors.append(f"{label}.source_role is unsupported")
        elif not _artifact_exists(sources, surface["source_role"], surface["source_artifact"]):
            errors.append(f"{label}.source_artifact is not declared by its source")
        if surface["strategy"] == "managed-block":
            if surface["begin_marker"] != MANAGED_BEGIN or surface["end_marker"] != MANAGED_END:
                errors.append(f"{label} must use the canonical Aether managed-block markers")
        elif surface["strategy"] == "evidence-grounded-template":
            if surface["begin_marker"] is not None or surface["end_marker"] is not None:
                errors.append(f"{label} template surface cannot declare managed-block markers")
        else:
            errors.append(f"{label}.strategy is unsupported")
    if set(by_path) != set(EXPECTED_SURFACES):
        errors.append("surfaces must declare the exact approved continuity destinations")
    for path, expected in EXPECTED_SURFACES.items():
        surface = by_path.get(path)
        if surface is None:
            continue
        expected_id, ownership, strategy, source_role, source_artifact, required = expected
        if (
            surface["id"],
            surface["ownership"],
            surface["strategy"],
            surface["source_role"],
            surface["source_artifact"],
            surface["required"],
        ) != (
            expected_id,
            ownership,
            strategy,
            source_role,
            source_artifact,
            required,
        ):
            errors.append(f"surface {path} does not match its approved contract")


def _validate_repository_profiles(profile: dict[str, Any], errors: list[str]) -> None:
    profiles = profile.get("repository_profiles")
    if not isinstance(profiles, list):
        errors.append("repository_profiles must be an array")
        return
    ids: set[str] = set()
    for index, repository_profile in enumerate(profiles):
        label = f"repository_profiles[{index}]"
        if not _closed_keys(repository_profile, PROFILE_KEYS, label, errors):
            continue
        profile_id = repository_profile["id"]
        if not isinstance(profile_id, str) or not profile_id:
            errors.append(f"{label}.id must be a non-empty string")
        if isinstance(profile_id, str) and profile_id in ids:
            errors.append(f"repository_profiles repeats id {profile_id}")
        if isinstance(profile_id, str):
            ids.add(profile_id)
        classes = set(
            _string_list(
                repository_profile["repository_classes"],
                f"{label}.repository_classes",
                errors,
            )
        )
        if not classes or not classes <= REPOSITORY_CLASSES:
            errors.append(f"{label}.repository_classes contains unsupported values")
        visibilities = set(
            _string_list(
                repository_profile["visibilities"],
                f"{label}.visibilities",
                errors,
            )
        )
        if not visibilities or not visibilities <= VISIBILITIES:
            errors.append(f"{label}.visibilities contains unsupported values")
        if not isinstance(
            repository_profile["requirement"], str
        ) or repository_profile["requirement"] not in {"required", "advisory"}:
            errors.append(f"{label}.requirement is unsupported")
    if ids != EXPECTED_PROFILES:
        errors.append("repository_profiles must cover all five #42 proof profiles")


def _validate_reconciliation(profile: dict[str, Any], errors: list[str]) -> None:
    reconciliation = profile.get("reconciliation")
    if not _closed_keys(
        reconciliation,
        RECONCILIATION_KEYS,
        "reconciliation",
        errors,
    ):
        return
    expected = {
        "preserve_outside_managed_block": True,
        "require_exactly_one_managed_block": True,
        "duplicate_or_malformed_markers": "conflict-no-write",
        "unmanaged_existing_instruction": "insert-managed-block-with-preservation",
        "existing_continuity": "preserve-repository-owned",
        "explicit_opt_out": "supported-no-change-with-recorded-reason",
        "unsupported_state": "conflict-no-write",
        "symlink_or_non_regular": "conflict-no-write",
    }
    for key, value in expected.items():
        if reconciliation[key] != value:
            errors.append(f"reconciliation.{key} must be {value}")


def _validate_information_safety(profile: dict[str, Any], errors: list[str]) -> None:
    safety = profile.get("information_safety")
    keys = {"minimum_necessary", "untrusted_content", "excluded", "private_output"}
    if not _closed_keys(safety, keys, "information_safety", errors):
        return
    if safety["minimum_necessary"] is not True:
        errors.append("information_safety.minimum_necessary must be true")
    if safety["untrusted_content"] != "context-only-no-authority":
        errors.append("information_safety.untrusted_content must deny authority")
    excluded = set(_string_list(safety["excluded"], "information_safety.excluded", errors))
    if excluded != PROHIBITED_DATA:
        errors.append("information_safety.excluded must contain the complete prohibited-data set")
    if safety["private_output"] != "allowlisted-metadata-only":
        errors.append("information_safety.private_output must be allowlisted metadata only")


def _validate_ownership(profile: dict[str, Any], errors: list[str]) -> None:
    ownership = profile.get("ownership")
    expected = {
        "portable_contract": "egohygiene/aether",
        "organization_policy": "egohygiene/hygiene",
        "validation": "egohygiene/egolint",
        "materialization": "egohygiene/holon",
        "semantic_checkpoint": "consumer-repository",
        "preflight_and_ci": "egohygiene/relay",
        "fleet_rollout": "egohygiene/pace",
    }
    if not _closed_keys(ownership, set(expected), "ownership", errors):
        return
    for key, value in expected.items():
        if ownership[key] != value:
            errors.append(f"ownership.{key} must be {value}")


def validate_profile(profile: dict[str, Any]) -> list[str]:
    """Return deterministic contract errors for one materialization profile."""
    errors: list[str] = []
    _closed_keys(profile, TOP_LEVEL_KEYS, "profile", errors)
    if profile.get("schema_version") != PROFILE_SCHEMA:
        errors.append(f"schema_version must be {PROFILE_SCHEMA}")
    if not isinstance(profile.get("version"), str) or not SEMVER_RE.fullmatch(
        profile["version"]
    ):
        errors.append("version must be semantic")
    if not isinstance(profile.get("status"), str) or profile.get("status") not in {
        "proposed",
        "active",
        "deprecated",
    }:
        errors.append("status is unsupported")
    if profile.get("owner") != "egohygiene/holon":
        errors.append("owner must be egohygiene/holon")
    if not isinstance(profile.get("updated"), str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}", profile["updated"]
    ):
        errors.append("updated must be YYYY-MM-DD")
    if not isinstance(profile.get("purpose"), str) or not profile["purpose"].strip():
        errors.append("purpose must be a non-empty string")
    sources = _validate_sources(profile, errors)
    _validate_rollout(profile, sources, errors)
    _validate_surfaces(profile, sources, errors)
    _validate_reconciliation(profile, errors)
    _validate_repository_profiles(profile, errors)
    _validate_information_safety(profile, errors)
    _validate_ownership(profile, errors)
    return sorted(set(errors))


def parse_source_roots(values: list[str]) -> dict[str, Path]:
    """Parse repeatable role=path source-root arguments."""
    roots: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ProfileError(f"source must use role=path: {value!r}")
        role, raw_path = value.split("=", 1)
        if role not in EXPECTED_SOURCES:
            raise ProfileError(f"unsupported source role: {role!r}")
        if role in roots:
            raise ProfileError(f"source role repeated: {role}")
        roots[role] = Path(raw_path)
    missing = set(EXPECTED_SOURCES) - set(roots)
    if missing:
        raise ProfileError(f"missing source roots: {', '.join(sorted(missing))}")
    return roots


def verify_sources(profile: dict[str, Any], roots: dict[str, Path]) -> int:
    """Verify every artifact byte-for-byte against caller-supplied immutable checkouts."""
    errors = validate_profile(profile)
    if errors:
        raise ProfileError("profile is invalid: " + "; ".join(errors))
    verified = 0
    for source in profile["sources"]:
        role = source["role"]
        root = roots[role].resolve()
        if not root.is_dir():
            raise ProfileError(f"source root is not a directory for {role}: {root}")
        for artifact in source["artifacts"]:
            path = root / artifact["path"]
            resolved = path.resolve()
            if resolved != root and root not in resolved.parents:
                raise ProfileError(f"source artifact escapes {role} root: {artifact['path']}")
            if path.is_symlink() or not path.is_file():
                raise ProfileError(f"source artifact is missing or not a regular file: {role}:{artifact['path']}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != artifact["sha256"]:
                raise ProfileError(
                    f"source artifact digest mismatch: {role}:{artifact['path']}"
                )
            verified += 1
    return verified


def build_parser() -> argparse.ArgumentParser:
    """Build the profile validator CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=PROFILE_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="Validate the locked profile structure and lifecycle.")
    verify = subparsers.add_parser(
        "verify-sources", help="Verify artifact bytes from three caller-supplied immutable checkouts."
    )
    verify.add_argument(
        "--source",
        action="append",
        default=[],
        help="Source checkout as role=path; repeat for portable-contract, organization-policy, and validator.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run profile validation or source-byte verification."""
    arguments = build_parser().parse_args(argv)
    try:
        profile = load_json(arguments.profile)
        errors = validate_profile(profile)
        if errors:
            for error in errors:
                print(f"continuity profile invalid: {error}", file=sys.stderr)
            return 1
        if arguments.command == "validate":
            artifact_count = sum(len(source["artifacts"]) for source in profile["sources"])
            print(
                f"continuity profile valid: {len(profile['sources'])} sources, "
                f"{artifact_count} artifacts, rollout {profile['rollout']['stage']}"
            )
            return 0
        roots = parse_source_roots(arguments.source)
        verified = verify_sources(profile, roots)
        print(f"verified {verified} continuity artifacts across {len(roots)} sources")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, ProfileError) as error:
        print(f"continuity profile failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
