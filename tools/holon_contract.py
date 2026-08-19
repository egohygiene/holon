#!/usr/bin/env python3
"""Validate and resolve Holon repository foundation manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA_VERSION = "1.0.0"
SECURITY_LEVELS = ("baseline", "hardened", "regulated")
MUTABLE_REFS = {"main", "master", "head", "latest", "edge", "dev", "snapshot"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{path} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{path} must not contain duplicates")
    return value


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"catalog schema_version must be {SCHEMA_VERSION}")
    if tuple(catalog.get("security_levels", [])) != SECURITY_LEVELS:
        errors.append("catalog security_levels must be baseline, hardened, regulated")
    capabilities = catalog.get("capabilities")
    classes = catalog.get("repository_classes")
    if not isinstance(capabilities, dict) or not capabilities:
        return errors + ["catalog capabilities must be a non-empty object"]
    if not isinstance(classes, dict) or not classes:
        return errors + ["catalog repository_classes must be a non-empty object"]

    names = set(capabilities)
    dependency_graph: dict[str, list[str]] = {}
    for name, capability in capabilities.items():
        if not isinstance(capability, dict):
            errors.append(f"capability {name} must be an object")
            continue
        try:
            requires = _string_list(capability.get("requires"), f"capability {name}.requires")
            conflicts = _string_list(
                capability.get("conflicts"), f"capability {name}.conflicts"
            )
            _string_list(capability.get("outputs"), f"capability {name}.outputs")
        except ValueError as error:
            errors.append(str(error))
            continue
        dependency_graph[name] = requires
        unknown = (set(requires) | set(conflicts)) - names
        if unknown:
            errors.append(f"capability {name} references unknown capabilities: {', '.join(sorted(unknown))}")
        if name in requires or name in conflicts:
            errors.append(f"capability {name} cannot require or conflict with itself")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str, stack: list[str]) -> None:
        if name in visiting:
            start = stack.index(name)
            errors.append(f"capability dependency cycle: {' -> '.join(stack[start:] + [name])}")
            return
        if name in visited:
            return
        visiting.add(name)
        for dependency in dependency_graph.get(name, []):
            visit(dependency, stack + [name])
        visiting.remove(name)
        visited.add(name)

    for name in sorted(names):
        visit(name, [])

    for name, repository_class in classes.items():
        if not isinstance(repository_class, dict):
            errors.append(f"repository class {name} must be an object")
            continue
        if repository_class.get("security_floor") not in SECURITY_LEVELS:
            errors.append(f"repository class {name} has an invalid security floor")
        combined: list[str] = []
        for field in ("required_capabilities", "default_capabilities", "allowed_capabilities"):
            try:
                values = _string_list(repository_class.get(field), f"repository class {name}.{field}")
                combined.extend(values)
            except ValueError as error:
                errors.append(str(error))
        unknown = set(combined) - names
        if unknown:
            errors.append(f"repository class {name} references unknown capabilities: {', '.join(sorted(unknown))}")
        if len(combined) != len(set(combined)):
            errors.append(f"repository class {name} repeats a capability across policy lists")
    return sorted(set(errors))


def immutable_pin(value: Any) -> bool:
    if not isinstance(value, str) or "@" not in value:
        return False
    source, reference = value.rsplit("@", 1)
    if not source or not reference or reference.lower() in MUTABLE_REFS:
        return False
    if source.startswith("ghcr.io/"):
        return bool(re.fullmatch(r"sha256:[0-9a-f]{64}", reference))
    return bool(
        re.fullmatch(r"[0-9a-f]{7,40}", reference)
        or re.fullmatch(r"(?:architecture-|foundation-)?v[0-9]+\.[0-9]+\.[0-9]+", reference)
    )


def resolve_manifest(
    catalog: dict[str, Any], manifest: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[str]]:
    errors = validate_catalog(catalog)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"manifest schema_version must be {SCHEMA_VERSION}")
    classes = catalog.get("repository_classes", {})
    class_name = manifest.get("repository_class")
    repository_class = classes.get(class_name) if isinstance(classes, dict) else None
    if not isinstance(repository_class, dict):
        return None, sorted(set(errors + [f"unknown repository class: {class_name}"]))

    security_level = manifest.get("security_level")
    if security_level not in SECURITY_LEVELS:
        errors.append("manifest security_level is invalid")
    elif SECURITY_LEVELS.index(security_level) < SECURITY_LEVELS.index(
        repository_class["security_floor"]
    ):
        errors.append(
            f"manifest security_level weakens the {class_name} floor of "
            f"{repository_class['security_floor']}"
        )

    selection = manifest.get("capabilities")
    if not isinstance(selection, dict):
        return None, sorted(set(errors + ["manifest capabilities must be an object"]))
    try:
        included = set(_string_list(selection.get("include"), "capabilities.include"))
        excluded = set(_string_list(selection.get("exclude"), "capabilities.exclude"))
    except ValueError as error:
        return None, sorted(set(errors + [str(error)]))
    if included & excluded:
        errors.append("a capability cannot be both included and excluded")

    required = set(repository_class["required_capabilities"])
    defaults = set(repository_class["default_capabilities"])
    allowed = required | defaults | set(repository_class["allowed_capabilities"])
    unknown = (included | excluded) - set(catalog["capabilities"])
    if unknown:
        errors.append(f"manifest references unknown capabilities: {', '.join(sorted(unknown))}")
    disallowed = included - allowed
    if disallowed:
        errors.append(f"capabilities not allowed for {class_name}: {', '.join(sorted(disallowed))}")
    weakening = excluded & required
    if weakening:
        errors.append(f"required capabilities cannot be excluded: {', '.join(sorted(weakening))}")

    selected = (required | defaults | included) - excluded
    queue = list(sorted(selected))
    while queue:
        name = queue.pop(0)
        capability = catalog["capabilities"].get(name)
        if not isinstance(capability, dict):
            continue
        for dependency in capability["requires"]:
            if dependency not in selected:
                selected.add(dependency)
                queue.append(dependency)

    for name in sorted(selected):
        conflicts = set(catalog["capabilities"][name]["conflicts"]) & selected
        if conflicts:
            errors.append(f"capability {name} conflicts with: {', '.join(sorted(conflicts))}")

    pins = manifest.get("pins")
    if not isinstance(pins, dict):
        errors.append("manifest pins must be an object")
        pins = {}
    required_pins = {"architecture", "foundation"}
    if "aether-agents" in selected:
        required_pins.add("aether")
    if "realm-devcontainer" in selected:
        required_pins.add("realm")
    for name in sorted(required_pins):
        if not immutable_pin(pins.get(name)):
            errors.append(f"pin {name} must use an immutable tag, commit, or OCI digest")

    if errors:
        return None, sorted(set(errors))

    ordered: list[str] = []
    seen: set[str] = set()

    def order(name: str) -> None:
        if name in seen:
            return
        for dependency in sorted(catalog["capabilities"][name]["requires"]):
            if dependency in selected:
                order(dependency)
        seen.add(name)
        ordered.append(name)

    for name in sorted(selected):
        order(name)
    sites = sorted(set(repository_class["default_sites"]) | set(manifest.get("sites", [])))
    resolved = {
        "schema_version": "1.0.0",
        "repository": manifest.get("repository"),
        "repository_class": class_name,
        "security_level": security_level,
        "pins": {name: pins[name] for name in sorted(required_pins)},
        "capabilities": ordered,
        "sites": sites,
        "preserve_paths": sorted(set(manifest.get("preserve_paths", []))),
        "parameters": manifest.get("parameters", {}),
        "ownership": {
            "generator": "egohygiene/holon",
            "preserve_paths": sorted(set(manifest.get("preserve_paths", []))),
        },
    }
    return resolved, []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", type=Path, default=Path("catalog/foundation.json")
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-catalog")
    validate = subparsers.add_parser("validate")
    validate.add_argument("--manifest", type=Path, required=True)
    resolve = subparsers.add_parser("resolve")
    resolve.add_argument("--manifest", type=Path, required=True)
    resolve.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        catalog = load_json(arguments.catalog)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"catalog load failed: {error}", file=sys.stderr)
        return 2
    if arguments.command == "validate-catalog":
        errors = validate_catalog(catalog)
        if errors:
            for error in errors:
                print(f"catalog validation failed: {error}", file=sys.stderr)
            return 1
        print(
            f"catalog valid: {len(catalog['repository_classes'])} classes, "
            f"{len(catalog['capabilities'])} capabilities"
        )
        return 0
    try:
        manifest = load_json(arguments.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"manifest load failed: {error}", file=sys.stderr)
        return 2
    resolved, errors = resolve_manifest(catalog, manifest)
    if errors:
        for error in errors:
            print(f"manifest validation failed: {error}", file=sys.stderr)
        return 1
    assert resolved is not None
    if arguments.command == "resolve":
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(resolved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"wrote {arguments.output}")
    else:
        print(
            f"manifest valid: {resolved['repository']} resolves "
            f"{len(resolved['capabilities'])} capabilities"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
