"""Validate Holon's React/Vite dependency-policy contract."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "egohygiene.holon.react-vite-dependency-policy/v1"
ALLOWED_DECISIONS = {"adopt", "optional", "defer", "reject"}
ALLOWED_ENVIRONMENTS = {"node-cli", "node-runtime", "browser-runtime"}


def load_policy(path: Path) -> dict[str, Any]:
    """Load one dependency-policy JSON document."""
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("dependency policy must be a JSON object")
    return value


def is_non_empty_string(value: object) -> bool:
    """Return whether a value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def validate_string_list(
    value: object,
    label: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    """Validate a list of non-empty strings and return contract errors."""
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    if not allow_empty and not value:
        return [f"{label} must be non-empty"]
    if any(not is_non_empty_string(item) for item in value):
        return [f"{label} must contain only non-empty strings"]
    if len(value) != len(set(value)):
        return [f"{label} must not contain duplicates"]
    return []


def validate_policy(policy: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors for the React/Vite dependency policy."""
    errors: list[str] = []

    if policy.get("schema") != EXPECTED_SCHEMA:
        errors.append(f"schema must be {EXPECTED_SCHEMA}")
    if policy.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if policy.get("profile") != "react-vite":
        errors.append("profile must be react-vite")
    if policy.get("status") not in {"proposed", "accepted", "superseded"}:
        errors.append("status must be proposed, accepted, or superseded")

    verified = policy.get("last_verified")
    if not isinstance(verified, str):
        errors.append("last_verified must be an ISO date")
    else:
        try:
            date.fromisoformat(verified)
        except ValueError:
            errors.append("last_verified must be an ISO date")

    principles = policy.get("principles")
    expected_principles = {
        "platform_first",
        "browser_runtime_dependencies_are_capability_driven",
        "node_build_dependencies_are_capability_driven",
        "client_and_node_dependencies_are_separate",
    }
    if not isinstance(principles, dict):
        errors.append("principles must be an object")
    else:
        for principle in sorted(expected_principles):
            if principles.get(principle) is not True:
                errors.append(f"principle {principle} must be true")

    baseline = policy.get("baseline")
    baseline_dependencies: set[str] = set()
    if not isinstance(baseline, dict):
        errors.append("baseline must be an object")
    else:
        for key in (
            "browser_runtime_dependencies",
            "node_runtime_dependencies",
            "node_development_dependencies",
            "optional_capabilities",
        ):
            values = baseline.get(key)
            errors.extend(
                validate_string_list(
                    values,
                    f"baseline {key}",
                    allow_empty=True,
                )
            )
            if key.endswith("_dependencies") and isinstance(values, list):
                baseline_dependencies.update(
                    value for value in values if isinstance(value, str)
                )

    supply_chain = policy.get("supply_chain")
    if not isinstance(supply_chain, dict):
        errors.append("supply_chain must be an object")
    else:
        if supply_chain.get("version_policy") != "exact-reviewed-version":
            errors.append("supply_chain version_policy must be exact-reviewed-version")
        if supply_chain.get("lockfile_policy") != "frozen":
            errors.append("supply_chain lockfile_policy must be frozen")
        if supply_chain.get("transitive_dependency_review") is not True:
            errors.append("supply_chain transitive_dependency_review must be true")
        if supply_chain.get("revalidate_on_major_upgrade") is not True:
            errors.append("supply_chain revalidate_on_major_upgrade must be true")
        incidents = supply_chain.get("known_incidents")
        if not isinstance(incidents, list):
            errors.append("supply_chain known_incidents must be a list")
        else:
            for index, incident in enumerate(incidents):
                prefix = f"supply_chain known_incidents[{index}]"
                if not isinstance(incident, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                for key in ("package", "affected_version", "resolution", "note"):
                    if not is_non_empty_string(incident.get(key)):
                        errors.append(f"{prefix} {key} must be a non-empty string")

    candidates = policy.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("candidates must be a non-empty list")
        return errors

    seen_ids: set[str] = set()
    seen_packages: set[str] = set()
    for index, candidate in enumerate(candidates):
        prefix = f"candidate[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{prefix} must be an object")
            continue

        candidate_id = candidate.get("id")
        package = candidate.get("package")
        if not is_non_empty_string(candidate_id):
            errors.append(f"{prefix} id must be a non-empty string")
        elif candidate_id in seen_ids:
            errors.append(f"candidate id is duplicated: {candidate_id}")
        else:
            seen_ids.add(candidate_id)

        if not is_non_empty_string(package):
            errors.append(f"{prefix} package must be a non-empty string")
        elif package in seen_packages:
            errors.append(f"candidate package is duplicated: {package}")
        else:
            seen_packages.add(package)

        decision = candidate.get("decision")
        if decision not in ALLOWED_DECISIONS:
            errors.append(f"{prefix} decision is invalid: {decision}")
        environment = candidate.get("environment")
        if environment not in ALLOWED_ENVIRONMENTS:
            errors.append(f"{prefix} environment is invalid: {environment}")

        for key in (
            "current_version",
            "license",
            "module_format",
            "maintenance",
            "runtime_footprint",
            "testability",
            "outcome",
            "adoption_guard",
            "replacement_or_removal",
        ):
            if not is_non_empty_string(candidate.get(key)):
                errors.append(f"{prefix} {key} must be a non-empty string")

        for url_key in ("upstream", "registry"):
            url = candidate.get(url_key)
            if not isinstance(url, str) or not url.startswith("https://"):
                errors.append(f"{prefix} {url_key} must be an https URL")

        runtime_dependencies = candidate.get("runtime_dependencies")
        if (
            not isinstance(runtime_dependencies, int)
            or isinstance(runtime_dependencies, bool)
            or runtime_dependencies < 0
        ):
            errors.append(
                f"{prefix} runtime_dependencies must be a non-negative integer"
            )

        compatibility = candidate.get("compatibility")
        if not isinstance(compatibility, dict):
            errors.append(f"{prefix} compatibility must be an object")
        else:
            if not is_non_empty_string(compatibility.get("node")):
                errors.append(f"{prefix} compatibility node must be a non-empty string")
            if not isinstance(compatibility.get("browser_runtime"), bool):
                errors.append(f"{prefix} compatibility browser_runtime must be boolean")

        errors.extend(
            validate_string_list(
                candidate.get("native_alternatives"),
                f"{prefix} native_alternatives",
            )
        )
        errors.extend(
            validate_string_list(
                candidate.get("security_notes"),
                f"{prefix} security_notes",
                allow_empty=True,
            )
        )
        errors.extend(
            validate_string_list(
                candidate.get("evidence"),
                f"{prefix} evidence",
            )
        )

        if (
            decision in {"optional", "defer", "reject"}
            and isinstance(package, str)
            and package in baseline_dependencies
        ):
            errors.append(
                f"{prefix} {package} is {decision} and must not appear in baseline dependencies"
            )

    return errors


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate the canonical React/Vite dependency policy."
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("catalog/react-vite-dependencies.json"),
        help="Path to the dependency-policy JSON document.",
    )
    return parser.parse_args()


def main() -> int:
    """Validate the requested policy and return a shell-friendly status code."""
    arguments = parse_arguments()
    policy = load_policy(arguments.policy)
    errors = validate_policy(policy)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Validated {arguments.policy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
