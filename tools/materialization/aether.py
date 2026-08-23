"""Pinned Aether release adapter for Holon materialization."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .common import MaterializationError, sha256_bytes, sha256_file

PROVIDER_PATHS: dict[str, tuple[str, str]] = {
    "github-copilot": ("github/repository/.github/agents", ".github/agents"),
    "vscode-copilot": ("github/repository/.github/agents", ".github/agents"),
    "claude-code": ("claude/repository/.claude/agents", ".claude/agents"),
    "opencode": ("opencode/repository/.opencode/agents", ".opencode/agents"),
}
NATIVE_STATES = {"native", "native-shared"}
HEX_REF_RE = re.compile(r"^[0-9a-f]{7,40}$")


def _split_pin(pin: str) -> tuple[str, str]:
    if "@" not in pin:
        raise MaterializationError(f"invalid Aether pin: {pin!r}")
    source, reference = pin.rsplit("@", 1)
    if not source or not reference:
        raise MaterializationError(f"invalid Aether pin: {pin!r}")
    return source, reference


def load_aether_projection_files(
    resolved_manifest: dict[str, Any], aether_source: Path
) -> tuple[dict[str, tuple[bytes, str]], dict[str, Any]]:
    """Verify and select provider projections from one pinned Aether distribution root."""
    pin = str((resolved_manifest.get("pins") or {}).get("aether", ""))
    if not pin:
        raise MaterializationError("resolved manifest selects aether-agents but has no Aether pin")
    _, reference = _split_pin(pin)

    projection_manifest_path = aether_source / "projections" / "manifest.v1.json"
    release_manifest_path = aether_source / "release" / "release-manifest.v1.json"
    provenance_path = aether_source / "release" / "release-provenance.v1.json"
    for path in (projection_manifest_path, release_manifest_path, provenance_path):
        if not path.is_file():
            raise MaterializationError(
                f"pinned Aether distribution is missing {path.relative_to(aether_source)}"
            )

    try:
        projection_manifest = json.loads(projection_manifest_path.read_text(encoding="utf-8"))
        release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MaterializationError(f"invalid Aether distribution metadata: {error}") from error

    release_tag = str(release_manifest.get("repository_release_tag", ""))
    provenance_tag = str(provenance.get("repository_release_tag", ""))
    commit_sha = str(provenance.get("commit_sha", ""))
    if release_tag != provenance_tag:
        raise MaterializationError("Aether release manifest and provenance tag disagree")
    if HEX_REF_RE.fullmatch(reference):
        if not commit_sha.startswith(reference):
            raise MaterializationError(
                f"Aether source commit {commit_sha!r} does not satisfy pin {reference!r}"
            )
    elif release_tag != reference:
        raise MaterializationError(
            f"Aether source release {release_tag!r} does not satisfy pin {reference!r}"
        )

    provider_states = {
        str(provider.get("id")): str(provider.get("status"))
        for provider in projection_manifest.get("providers", [])
        if isinstance(provider, dict)
    }
    output_hashes = {
        str(record.get("path")): str(record.get("sha256"))
        for record in projection_manifest.get("outputs", [])
        if isinstance(record, dict)
    }
    release_hashes = {
        str(record.get("path")): str(record.get("sha256"))
        for record in provenance.get("output_files", [])
        if isinstance(record, dict)
    }

    parameters = resolved_manifest.get("parameters", {})
    requested = (
        parameters.get("aether_providers", ["github-copilot"])
        if isinstance(parameters, dict)
        else ["github-copilot"]
    )
    if not isinstance(requested, list) or not requested or any(
        not isinstance(provider, str) or not provider for provider in requested
    ):
        raise MaterializationError(
            "parameters.aether_providers must be a non-empty array of provider IDs"
        )
    if len(requested) != len(set(requested)):
        raise MaterializationError("parameters.aether_providers must not contain duplicates")

    selected: dict[str, tuple[bytes, str]] = {}

    def add_verified(source_relative: str, destination: str, provider: str) -> None:
        source_path = aether_source / source_relative
        if not source_path.is_file():
            raise MaterializationError(f"Aether projection source is missing: {source_relative}")
        digest = sha256_file(source_path)
        if output_hashes.get(f"dist/{source_relative}") != digest:
            raise MaterializationError(f"Aether projection digest mismatch for {source_relative}")
        if release_hashes.get(source_relative) != digest:
            raise MaterializationError(
                f"Aether release provenance mismatch for {source_relative}"
            )
        content = source_path.read_bytes()
        existing = selected.get(destination)
        if existing is not None and sha256_bytes(existing[0]) != digest:
            raise MaterializationError(
                f"Aether providers collide with different content at {destination}"
            )
        selected[destination] = (
            content,
            f"aether:{pin}:{provider}:{source_relative}",
        )

    for provider in requested:
        status = provider_states.get(provider)
        if status not in NATIVE_STATES:
            if status == "manual-import":
                raise MaterializationError(
                    f"Aether provider {provider} is manual-import and cannot be materialized "
                    "as a native repository projection"
                )
            raise MaterializationError(
                f"Aether provider {provider!r} is not a supported native projection"
            )
        mapping = PROVIDER_PATHS.get(provider)
        if mapping is None:
            raise MaterializationError(
                f"Holon has no repository projection adapter for Aether provider {provider}"
            )
        source_prefix, destination_prefix = mapping
        source_root = aether_source / source_prefix
        if not source_root.is_dir():
            raise MaterializationError(
                f"Aether provider output directory is missing: {source_prefix}"
            )
        for source_path in sorted(source_root.rglob("*")):
            if source_path.is_file():
                relative = source_path.relative_to(source_root).as_posix()
                add_verified(
                    f"{source_prefix}/{relative}",
                    f"{destination_prefix}/{relative}",
                    provider,
                )

    if isinstance(parameters, dict) and parameters.get("github_mcp") is True:
        add_verified("mcp/github/.mcp.json", ".mcp.json", "github-mcp")

    return selected, {
        "pin": pin,
        "release_tag": release_tag,
        "commit_sha": commit_sha,
        "projection_interface_version": projection_manifest.get("interface_version"),
        "projection_manifest_sha256": sha256_file(projection_manifest_path),
        "providers": sorted(requested),
    }
