#!/usr/bin/env python3
"""Validate Holon's versioned generic React/Vite blueprint."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from holon_contract import load_json, resolve_manifest
from materialization.common import (
    MaterializationError,
    TEMPLATE_TOKEN_RE,
    render_source_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = Path("blueprints/react-vite/blueprint.json")
SOURCE_PATH = Path("blueprints/react-vite/files")
CATALOG_PATH = Path("catalog/foundation.json")
EXAMPLE_PATH = Path("examples/react-vite-site.manifest.json")
EXPECTED_SCHEMA = "holon.react-vite-blueprint/v1"
EXPECTED_VERSION = "1.0.0"
EXPECTED_CAPABILITY = "site-react-vite"
EXPECTED_PARAMETERS = {
    "canonical_url",
    "identity_stylesheet",
    "package_name",
    "site_base_path",
    "site_description",
    "site_title",
}
BASE_TOKENS = {"repository", "repository_name", "repository_class"}
EXACT_PACKAGE_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


class DuplicateKeyError(ValueError):
    """Raised when JSON silently repeats an object key."""


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object while rejecting duplicate keys."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_strict_json(path: Path) -> dict[str, Any]:
    """Load a strict JSON object from one blueprint-owned source."""
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def sha256(path: Path) -> str:
    """Return the SHA-256 identity of one template file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_inventory(project: Path) -> list[dict[str, str]]:
    """Build the canonical sorted template-file inventory."""
    source = project / SOURCE_PATH
    return [
        {"path": path.relative_to(source).as_posix(), "sha256": sha256(path)}
        for path in sorted(source.rglob("*"))
        if path.is_file()
    ]


def validate_parameters(parameters: object) -> list[str]:
    """Validate the example's scalar React/Vite parameter contract."""
    if not isinstance(parameters, dict):
        return ["React/Vite parameters must be an object"]
    errors: list[str] = []
    missing = EXPECTED_PARAMETERS - set(parameters)
    unexpected = set(parameters) - EXPECTED_PARAMETERS
    if missing:
        errors.append("React/Vite parameters are missing: " + ", ".join(sorted(missing)))
    if unexpected:
        errors.append(
            "React/Vite parameters are not declared by the blueprint: "
            + ", ".join(sorted(unexpected))
        )
    for name in sorted(EXPECTED_PARAMETERS & set(parameters)):
        value = parameters[name]
        if not isinstance(value, str) or not value.strip():
            errors.append(f"React/Vite parameter {name} must be a non-empty string")
    canonical_url = parameters.get("canonical_url")
    if isinstance(canonical_url, str) and not canonical_url.startswith("https://"):
        errors.append("React/Vite canonical_url must use HTTPS")
    base_path = parameters.get("site_base_path")
    if isinstance(base_path, str) and (
        not base_path.startswith("/") or not base_path.endswith("/")
    ):
        errors.append("React/Vite site_base_path must begin and end with /")
    package_name = parameters.get("package_name")
    if isinstance(package_name, str) and re.fullmatch(
        r"(?:@[a-z0-9.-]+/)?[a-z0-9][a-z0-9._-]*", package_name
    ) is None:
        errors.append("React/Vite package_name is not a safe npm package name")
    return errors


def validate_dependencies(profile: dict[str, Any], package: dict[str, Any]) -> list[str]:
    """Keep the generated package aligned with the reviewed dependency contract."""
    errors: list[str] = []
    dependencies = profile.get("dependencies")
    if not isinstance(dependencies, dict):
        return ["blueprint dependencies must be an object"]
    runtime = dependencies.get("runtime")
    development = dependencies.get("development")
    forbidden = dependencies.get("forbidden_baseline")
    if runtime != package.get("dependencies"):
        errors.append("package runtime dependencies diverge from the blueprint profile")
    if development != package.get("devDependencies"):
        errors.append("package development dependencies diverge from the blueprint profile")
    combined: dict[str, object] = {}
    if isinstance(runtime, dict):
        combined.update(runtime)
    if isinstance(development, dict):
        combined.update(development)
    for name, version in sorted(combined.items()):
        if not isinstance(version, str) or EXACT_PACKAGE_VERSION.fullmatch(version) is None:
            errors.append(f"blueprint dependency {name} must use one exact reviewed version")
    if not isinstance(forbidden, list):
        errors.append("blueprint forbidden_baseline must be a list")
    else:
        present = set(str(name) for name in forbidden) & set(combined)
        if present:
            errors.append(
                "forbidden baseline dependencies are present: "
                + ", ".join(sorted(present))
            )
    if any("storybook" in name.casefold() for name in combined):
        errors.append("Storybook must not enter the generic baseline")
    if "publint" in combined:
        errors.append("publint must remain capability-gated for a publishable package")
    return errors


def validate_blueprint(project: Path = ROOT) -> list[str]:
    """Validate profile, capability, template, example, and provenance alignment."""
    project = project.resolve()
    errors: list[str] = []
    try:
        profile = load_strict_json(project / PROFILE_PATH)
        package = load_strict_json(project / SOURCE_PATH / "package.json")
        quality = load_strict_json(
            project / SOURCE_PATH / "egolint.javascript-package-quality.json"
        )
        materialized = load_strict_json(project / SOURCE_PATH / "holon.blueprint.json")
        catalog = load_json(project / CATALOG_PATH)
        example = load_json(project / EXAMPLE_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"React/Vite blueprint source is invalid: {error}"]

    if profile.get("schema") != EXPECTED_SCHEMA:
        errors.append(f"blueprint schema must be {EXPECTED_SCHEMA}")
    if profile.get("version") != EXPECTED_VERSION:
        errors.append(f"blueprint version must be {EXPECTED_VERSION}")
    if profile.get("status") != "active":
        errors.append("React/Vite blueprint must be active")
    if profile.get("capability") != EXPECTED_CAPABILITY:
        errors.append(f"blueprint capability must be {EXPECTED_CAPABILITY}")
    if profile.get("extends") is not None:
        errors.append("generic React/Vite foundation must not extend LaunchKit or another profile")
    if profile.get("render_source") != SOURCE_PATH.as_posix():
        errors.append(f"blueprint render_source must be {SOURCE_PATH}")
    if set(profile.get("required_parameters", [])) != EXPECTED_PARAMETERS:
        errors.append("blueprint required_parameters do not match the v1 contract")

    toolchain = profile.get("toolchain")
    if not isinstance(toolchain, dict):
        errors.append("blueprint toolchain must be an object")
    else:
        if package.get("packageManager") != toolchain.get("package_manager"):
            errors.append("package manager does not match the blueprint toolchain")
        engines = package.get("engines")
        if not isinstance(engines, dict) or engines.get("node") != toolchain.get("node"):
            errors.append("Node engine does not match the blueprint toolchain")

    errors.extend(validate_dependencies(profile, package))
    expected_scripts = {
        "dev",
        "build",
        "preview",
        "format:check",
        "lint",
        "typecheck",
        "test",
        "test:watch",
        "check",
    }
    scripts = package.get("scripts")
    if not isinstance(scripts, dict) or set(scripts) != expected_scripts:
        errors.append("generated package scripts do not match the canonical command surface")
    elif scripts.get("check") != (
        "pnpm format:check && pnpm lint && pnpm typecheck && pnpm test && pnpm build"
    ):
        errors.append("pnpm check must remain the canonical local and CI sequence")

    expected_quality = {
        "$schema": "https://egohygiene.io/schemas/egolint/javascript-package-quality-manifest/v1.json",
        "schema_version": 1,
        "profile": "react-library",
        "package_path": ".",
        "publication": "private",
    }
    if quality != expected_quality:
        errors.append("generated Egolint manifest diverges from its consumer contract")
    if materialized.get("blueprint") != "react-vite" or materialized.get(
        "blueprint_version"
    ) != profile.get("version"):
        errors.append("materialized blueprint provenance is inconsistent")

    capability = catalog.get("capabilities", {}).get(EXPECTED_CAPABILITY)
    if not isinstance(capability, dict) or capability.get("owner") != "egohygiene/holon":
        errors.append("foundation catalog must expose the Holon-owned site-react-vite capability")
    for class_name, repository_class in sorted(catalog.get("repository_classes", {}).items()):
        if EXPECTED_CAPABILITY not in repository_class.get("allowed_capabilities", []):
            errors.append(f"repository class {class_name} cannot opt into site-react-vite")

    resolved, resolve_errors = resolve_manifest(catalog, example)
    errors.extend(f"example manifest: {error}" for error in resolve_errors)
    if resolved is not None:
        if EXPECTED_CAPABILITY not in resolved.get("capabilities", []):
            errors.append("example manifest does not resolve site-react-vite")
        if "landing-launchkit" in resolved.get("capabilities", []):
            errors.append("generic example must not resolve the LaunchKit capability")
        errors.extend(validate_parameters(resolved.get("parameters")))

    actual_inventory = source_inventory(project)
    declared_inventory = profile.get("files")
    if declared_inventory != actual_inventory:
        errors.append("blueprint file inventory is stale or contains orphaned entries")
    declared_paths = [
        record.get("path")
        for record in declared_inventory or []
        if isinstance(record, dict)
    ]
    for path, count in Counter(declared_paths).items():
        if count > 1:
            errors.append(f"blueprint inventory repeats path: {path}")

    parameters = resolved.get("parameters", {}) if resolved is not None else {}
    token_names: set[str] = set()
    if resolved is not None:
        for source in sorted((project / SOURCE_PATH).rglob("*")):
            if not source.is_file():
                continue
            try:
                text = source.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for token in TEMPLATE_TOKEN_RE.findall(text):
                token_names.add(token[2:-2])
            try:
                render_source_bytes(
                    source.read_bytes(),
                    resolved,
                    source.relative_to(project / SOURCE_PATH).as_posix(),
                )
            except (MaterializationError, ValueError) as error:
                errors.append(str(error))
    allowed_tokens = BASE_TOKENS | {
        token
        for name in EXPECTED_PARAMETERS
        for token in (f"parameter.{name}", f"parameter_json.{name}")
    }
    if token_names - allowed_tokens:
        errors.append(
            "blueprint uses undeclared template tokens: "
            + ", ".join(sorted(token_names - allowed_tokens))
        )
    used_parameters = {
        name.split(".", 1)[1]
        for name in token_names
        if name.startswith(("parameter.", "parameter_json."))
    }
    if used_parameters != set(parameters):
        errors.append("example parameters and template parameter usage must match exactly")

    lockfile = (project / SOURCE_PATH / "pnpm-lock.yaml").read_text(encoding="utf-8")
    for name, version in sorted((package.get("dependencies") or {}).items()):
        if f"specifier: {version}" not in lockfile:
            errors.append(f"lockfile does not pin runtime dependency {name}@{version}")
    for name, version in sorted((package.get("devDependencies") or {}).items()):
        if f"specifier: {version}" not in lockfile:
            errors.append(f"lockfile does not pin development dependency {name}@{version}")
    return sorted(set(errors))


def write_inventory(project: Path) -> None:
    """Refresh the deterministic template inventory in the profile."""
    path = project / PROFILE_PATH
    profile = load_strict_json(path)
    profile["files"] = source_inventory(project)
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> int:
    """Validate the blueprint or refresh its inventory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--write-inventory", action="store_true")
    arguments = parser.parse_args()
    project = arguments.project.expanduser().resolve()
    if arguments.write_inventory:
        write_inventory(project)
    errors = validate_blueprint(project)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    profile = load_strict_json(project / PROFILE_PATH)
    print(
        f"Validated React/Vite blueprint {profile['version']} "
        f"({len(profile['files'])} managed template files)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
