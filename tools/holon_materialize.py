#!/usr/bin/env python3
"""Plan, render, verify, and roll back Holon repository materializations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from holon_contract import load_json, resolve_manifest
from materialization import (
    MaterializationError,
    build_plan,
    render_plan,
    rollback_target,
    verify_target,
)
from materialization.common import load_state, pretty_json_bytes, validate_target_root


def resolve_foundation_manifest(catalog_path: Path, manifest_path: Path) -> dict[str, Any]:
    """Resolve one foundation manifest through the existing HOL-01 contract."""
    try:
        catalog = load_json(catalog_path)
        manifest = load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise MaterializationError(f"unable to load foundation inputs: {error}") from error
    resolved, errors = resolve_manifest(catalog, manifest)
    if errors:
        raise MaterializationError("foundation manifest is invalid: " + "; ".join(errors))
    assert resolved is not None
    return resolved


def build_parser() -> argparse.ArgumentParser:
    """Build the Holon materialization command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("catalog/foundation.json"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Resolve inputs and write a dry-run change plan.")
    plan.add_argument("--manifest", type=Path, required=True)
    plan.add_argument("--target", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--render-source", type=Path)
    plan.add_argument("--render-overlay", type=Path, action="append", default=[])
    plan.add_argument("--aether-source", type=Path)

    render = subparsers.add_parser("render", help="Apply one previously reviewed plan.")
    render.add_argument("--plan", type=Path, required=True)
    render.add_argument("--target", type=Path, required=True)
    render.add_argument("--render-source", type=Path)
    render.add_argument("--render-overlay", type=Path, action="append", default=[])
    render.add_argument("--aether-source", type=Path)

    verify = subparsers.add_parser("verify", help="Verify the current generated ownership state.")
    verify.add_argument("--target", type=Path, required=True)

    rollback = subparsers.add_parser("rollback", help="Revert the latest safe materialization.")
    rollback.add_argument("--target", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Holon materialization CLI."""
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "plan":
            resolved = resolve_foundation_manifest(arguments.catalog, arguments.manifest)
            plan, _ = build_plan(
                resolved,
                arguments.target,
                render_source=arguments.render_source,
                render_overlays=arguments.render_overlay,
                aether_source=arguments.aether_source,
            )
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_bytes(pretty_json_bytes(plan))
            conflicts = plan["summary"].get("conflict", 0)
            print(
                f"wrote plan {arguments.output} ({plan['plan_id'][:12]}): "
                f"{len(plan['operations'])} operations, {conflicts} conflict(s)"
            )
            return 1 if conflicts else 0

        if arguments.command == "render":
            plan = load_json(arguments.plan)
            state = render_plan(
                plan,
                arguments.target,
                render_source=arguments.render_source,
                render_overlays=arguments.render_overlay,
                aether_source=arguments.aether_source,
            )
            print(
                f"rendered plan {state['plan_id'][:12]}: "
                f"{len(state['managed_files'])} managed file(s)"
            )
            return 0

        if arguments.command == "verify":
            errors = verify_target(arguments.target)
            if errors:
                for error in errors:
                    print(f"verify failed: {error}", file=sys.stderr)
                return 1
            state = load_state(validate_target_root(arguments.target))
            assert state is not None
            print(f"verified {len(state['managed_files'])} managed file(s)")
            return 0

        rollback_target(arguments.target)
        print("rolled back the latest Holon materialization")
        return 0
    except (MaterializationError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"holon materialization failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
