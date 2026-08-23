"""Validate Holon's React/Vite dependency-policy contract."""

from __future__ import annotations

from datetime import date
import argparse
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
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value for value in values
            ):
                errors.append(f"baseline {key} must be a list of non-empty strings")
                continue
            if len(values) != len(set(values)):
                errors.append(f"baseline {key} must not contain duplicates")
            if key.endswith("_dependencies"):
                baseline_dependencies.update(values)

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
        if not isinstance(candidate_id, str) or not candidate_id:
            errors.append(f"{prefix} id must be a non-empty string")
        elif candidate_id in seen_ids:
            errors.append(f"candidate id is duplicated: {candidate_id}")
        else:
            seen_ids.add(candidate_id)

        if not isinstance(package, str) or not package:
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

        for url_key in ("upstream", "registry"):
            url = candidate.get(url_key)
            if not isinstance(url, str) or not url.startswith("https://"):
                errors.append(f"{prefix} {url_key} must be an https URL")

        runtime_dependencies = candidate.get("runtime_dependencies")
        if not isinstance(runtime_dependencies, int) or runtime_dependencies < 0:
            errors.append(
                f"{prefix} runtime_dependencies must be a non-negative integer"
            )

        alternatives = candidate.get("native_alternatives")
        if not isinstance(alternatives, list) or not alternatives:
            errors.append(f"{prefix} native_alternatives must be non-empty")

        evidence = candidate.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{prefix} evidence must be non-empty")

        if decision in {"optional", "defer", "reject"} and package in baseline_dependencies:
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
