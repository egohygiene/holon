"""Validate proposed deployment selections; this module never deploys or applies IaC."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/deployment-request.v1.schema.json"
CATALOG = ROOT / "catalog/deployment-profiles.v1.json"


def safe_relative(value: str) -> bool:
    """Recognize canonical portable source/artifact paths, never host paths."""
    return bool(value and "\\" not in value and ":" not in value
                and not PurePosixPath(value).is_absolute()
                and all(part not in {"", ".", ".."} for part in value.split("/")))


def safe_route(value: str) -> bool:
    """Keep route identities unambiguous across local/static/service adapters."""
    return bool(value == "/" or (value.startswith("/") and "\\" not in value
                and not re.search(r"[%?#\s]", value)
                and all(part not in {"", ".", ".."} for part in value[1:].rstrip("/").split("/"))))


def validate_selection(document: object) -> list[str]:
    """Check declared boundaries and compatibility without executing consumer code."""
    schema = json.loads(SCHEMA.read_text())
    errors = [f"{'/'.join(map(str, e.absolute_path)) or '/'}: invalid {e.validator} constraint"
              for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)]
    if errors:
        return errors
    catalog = json.loads(CATALOG.read_text())
    if document["profile"] not in catalog["framework_adapters"].get(document["framework"], []):
        errors.append("Framework adapter does not declare support for this deployment profile")
    if any(not safe_relative(path) for path in [document["artifact"]["path"], *document["build_inputs"]]):
        errors.append("Build/artifact paths must be canonical relative paths")
    if any(not safe_route(route) for route in [*document["routes"], *document["previous_routes"]]):
        errors.append("Routes must be canonical absolute URL paths")
    if not set(document["previous_routes"]).issubset(document["routes"]):
        errors.append("Existing routes must remain present; redirects require a separate reviewed migration")
    names = [entry["name"] for entry in document["configuration"]]
    if len(names) != len(set(names)):
        errors.append("Configuration names must be unique")
    for entry in document["configuration"]:
        if entry["classification"] == "server-secret" and entry["source"] != "external-secret-store":
            errors.append("Server secrets must reference an external secret store")
        if entry["classification"] == "server-secret" and entry["name"].startswith(("VITE_", "PUBLIC_", "NEXT_PUBLIC_")):
            errors.append("A secret cannot use a public client prefix")
    if document["profile"] == "static-site/v1":
        selected = document["static"]
        url = urlsplit(selected["canonical_url"])
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path != selected["base_path"]
                or not selected["base_path"].endswith("/") or not safe_route(selected["base_path"])):
            errors.append("Static canonical URL must be credential-free HTTPS with exactly the selected base path")
    else:
        runtime = document["runtime"]
        if any(not safe_route(runtime[key]) for key in ("health", "readiness")):
            errors.append("Health/readiness paths must be canonical routes")
    return errors


def validate_artifact(document: object, repository: Path) -> list[str]:
    """Inspect one selected output boundary; do not build, run or deploy it."""
    errors = validate_selection(document)
    if errors:
        return errors
    root = repository.resolve()
    artifact = root / document["artifact"]["path"]
    parents = [root.joinpath(*Path(document["artifact"]["path"]).parts[:index])
               for index in range(1, len(Path(document["artifact"]["path"]).parts) + 1)]
    if (any(path.is_symlink() for path in parents) or not artifact.exists()
            or not artifact.resolve().is_relative_to(root)
            or not (artifact.is_file() or artifact.is_dir())):
        return ["Selected artifact must exist inside the repository without a symlink boundary"]
    for name in document["build_inputs"]:
        source = root / name
        if (not source.is_file() or not source.resolve().is_relative_to(root)
                or any(root.joinpath(*Path(name).parts[:index]).is_symlink()
                       for index in range(1, len(Path(name).parts) + 1))):
            errors.append("A declared build input is unavailable or crosses a symlink boundary")
    if document["profile"] != "static-site/v1":
        return errors  # Runtime/provider qualification belongs to the consumer adapter.
    if not artifact.is_dir():
        return ["Static artifact must be a directory"]
    for path in artifact.rglob("*"):
        if path.is_symlink():
            errors.append("Static artifact contains an unsupported symlink")
        elif path.name.startswith(".env") or path.suffix in {".pem", ".key"} or path.name in {"id_rsa", "id_ed25519"}:
            errors.append("Static artifact contains a forbidden configuration/key file")
    for route in document["routes"]:
        relative = route.strip("/")
        expected = artifact / relative / "index.html" if not Path(relative).suffix else artifact / relative
        if not expected.is_file() or expected.is_symlink():
            errors.append("A declared static route has no ordinary output file")
    if not (artifact / document["static"]["not_found"]).is_file():
        errors.append("Static artifact is missing the selected 404 output")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection", type=Path)
    parser.add_argument("--artifact-root", type=Path, help="Optionally inspect output relative to this repository root")
    args = parser.parse_args()
    try:
        document = json.loads(args.selection.read_text())
        errors = validate_artifact(document, args.artifact_root) if args.artifact_root else validate_selection(document)
    except (OSError, ValueError) as error:
        print(f"Deployment selection unavailable: {error}", file=sys.stderr)
        return 2
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Deployment selection valid; no provider, publication or IaC action performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
