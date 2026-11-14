"""Explicit site-artifact projection over the existing materialization engine.

The complete foundation still resolves and retains its requirements. This
projection renders only the selected website packs and cannot qualify or remove
the foundation's other capabilities.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from holon_contract import load_json, resolve_manifest
from launchkit_blueprint import validate_content as validate_launchkit_content
from react_vite_blueprint import EXPECTED_PARAMETERS, validate_parameters
from site_suite_blueprint import (
    COMMON_PARAMETERS,
    LAUNCHKIT_PARAMETERS,
    SUITE_PROFILE,
    validate_site_content,
)

from .common import (
    MaterializationError,
    canonical_bytes,
    load_state,
    sha256_bytes,
)
from .engine import build_plan, render_plan, rollback_target, verify_target

SCOPE_SCHEMA = "holon.site-suite-projection/v1"


def _inputs(
    manifest: dict[str, Any], variant: str, project: Path,
) -> tuple[dict[str, Any], Path, list[Path]]:
    """Resolve full intent, then label the deliberately narrower render scope."""
    resolved, errors = resolve_manifest(load_json(project / "catalog/foundation.json"), manifest)
    if errors or resolved is None:
        raise MaterializationError("foundation manifest is invalid: " + "; ".join(errors))
    profile = load_json(project / SUITE_PROFILE)
    if variant not in {"generic", "launchkit"}:
        raise MaterializationError("site-suite variant must be generic or launchkit")
    selected = profile["variants"][variant]
    capabilities = selected["capabilities"]
    if not set(capabilities) <= set(resolved["capabilities"]):
        raise MaterializationError("foundation manifest does not select the requested site variant")
    if variant == "generic" and "landing-launchkit" in resolved["capabilities"]:
        raise MaterializationError("the generic site variant cannot silently omit selected LaunchKit")
    parameters = resolved["parameters"]
    expected = LAUNCHKIT_PARAMETERS if variant == "launchkit" else COMMON_PARAMETERS
    if set(parameters) != expected:
        raise MaterializationError("site-suite parameters do not match the selected variant")
    errors = validate_parameters({key: parameters.get(key) for key in EXPECTED_PARAMETERS})
    errors.extend(validate_site_content(parameters["site_suite_content"], "site_suite_content"))
    if variant == "launchkit":
        errors.extend(validate_launchkit_content(parameters["launchkit_content"], "launchkit_content"))
    if errors:
        raise MaterializationError("site-suite content is invalid: " + "; ".join(errors))
    scoped = copy.deepcopy(resolved)
    scoped["capabilities"] = list(capabilities)
    scoped["site_suite_projection"] = {
        "schema_version": SCOPE_SCHEMA,
        "variant": variant,
        "qualification": "site-artifact-only",
        "foundation_qualification": "unqualified",
        "foundation_manifest": copy.deepcopy(manifest),
        "foundation_resolved_sha256": sha256_bytes(canonical_bytes(resolved)),
        "profile_sha256": sha256_bytes((project / SUITE_PROFILE).read_bytes()),
        "unqualified_capabilities": [
            capability for capability in resolved["capabilities"] if capability not in capabilities
        ],
    }
    return (
        scoped,
        project / selected["render_source"],
        [project / path for path in selected["render_overlays"]],
    )


def _scope(resolved: dict[str, Any], project: Path) -> tuple[Path, list[Path]]:
    """Reject malformed or altered scope metadata rather than trusting a label."""
    if not isinstance(resolved, dict):
        raise MaterializationError("site-suite projection must be an object")
    scope = resolved.get("site_suite_projection")
    if not isinstance(scope, dict) or scope.get("schema_version") != SCOPE_SCHEMA:
        raise MaterializationError("target or plan is not an explicit site-suite projection")
    manifest = scope.get("foundation_manifest")
    if not isinstance(manifest, dict):
        raise MaterializationError("site-suite projection has no foundation input")
    expected, source, overlays = _inputs(manifest, scope.get("variant"), project)
    if resolved != expected:
        raise MaterializationError("site-suite scope differs from its exact foundation and profile inputs")
    return source, overlays


def _target_scope(target: Path, project: Path) -> None:
    """Never downgrade a complete foundation or another engine's owned target."""
    state = load_state(target)
    if state is not None:
        _scope(state["resolved_manifest"], project)


def build_site_suite_plan(
    manifest: dict[str, Any], variant: str, target: Path, *, project: Path,
) -> dict[str, Any]:
    """Plan only canonical site packs; no Aether payload or release is invented."""
    _target_scope(target, project)
    resolved, source, overlays = _inputs(manifest, variant, project)
    plan, _ = build_plan(resolved, target, render_source=source, render_overlays=overlays)
    return plan


def render_site_suite_plan(
    plan: dict[str, Any], target: Path, *, project: Path,
) -> dict[str, Any]:
    """Reuse exact-plan, drift, ownership and recovery checks for site output."""
    _target_scope(target, project)
    source, overlays = _scope(plan.get("resolved_manifest"), project)
    return render_plan(plan, target, render_source=source, render_overlays=overlays)


def verify_site_suite_target(target: Path, *, project: Path) -> list[str]:
    """Verify retained site ownership without claiming whole-foundation readiness."""
    state = load_state(target)
    if state is None:
        raise MaterializationError("site-suite target has no materialization state")
    _scope(state["resolved_manifest"], project)
    return verify_target(target)


def rollback_site_suite_target(target: Path, *, project: Path) -> None:
    """Use guarded generic recovery only for an explicitly scoped target."""
    state = load_state(target)
    if state is None:
        raise MaterializationError("site-suite target has no materialization state")
    _scope(state["resolved_manifest"], project)
    rollback_target(target)
