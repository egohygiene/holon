#!/usr/bin/env python3
"""Validate Holon's Zensical pack and multi-surface composition profile."""

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
from launchkit_blueprint import validate_content as validate_launchkit_content
from materialization.common import MaterializationError, TEMPLATE_TOKEN_RE, render_source_bytes
from react_vite_blueprint import load_strict_json, validate_parameters

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path("catalog/foundation.json")
ZENSICAL_PROFILE = Path("blueprints/zensical/blueprint.json")
ZENSICAL_FILES = Path("blueprints/zensical/files")
ZENSICAL_AUDIT = Path("blueprints/zensical/upstream-audit.json")
SUITE_PROFILE = Path("blueprints/site-suite/blueprint.json")
SUITE_FILES = Path("blueprints/site-suite/files")
REACT_PROFILE = Path("blueprints/react-vite/blueprint.json")
REACT_FILES = Path("blueprints/react-vite/files")
LAUNCHKIT_PROFILE = Path("blueprints/launchkit/blueprint.json")
LAUNCHKIT_FILES = Path("blueprints/launchkit/files")
EXAMPLES = {
    "generic": Path("examples/site-suite-generic.manifest.json"),
    "launchkit": Path("examples/site-suite-optiflow.manifest.json"),
}
ZENSICAL_VERSION = "0.0.57"
ZENSICAL_COMMIT = "f18bb9957cb2740e5dd66d4a438c780b4e15d64c"
COMMON_PARAMETERS = {
    "canonical_url",
    "identity_favicon_url",
    "identity_stylesheet",
    "package_name",
    "repository_url",
    "site_base_path",
    "site_description",
    "site_suite_content",
    "site_title",
}
LAUNCHKIT_PARAMETERS = COMMON_PARAMETERS | {
    "identity_social_image_url",
    "launchkit_content",
}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HTTPS_RE = re.compile(r"^https://\S+$")
PLACEHOLDERS = ("lorem ipsum", "request a demo", "placeholder-", "example.com")


def sha256(path: Path) -> str:
    """Return one file's lowercase SHA-256 identity."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(project: Path, source: Path) -> list[dict[str, str]]:
    """Build one deterministic rendered-pack inventory."""
    root = project / source
    return [
        {"path": path.relative_to(root).as_posix(), "sha256": sha256(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def text_errors(value: object, location: str, *, maximum: int = 12000) -> list[str]:
    """Validate bounded authored content without template placeholders."""
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        return [f"{location} must contain 1 to {maximum} characters"]
    lowered = value.casefold()
    return [
        f"{location} contains forbidden placeholder copy: {placeholder}"
        for placeholder in PLACEHOLDERS
        if placeholder in lowered
    ]


def page_errors(value: object, location: str, *, legal: bool = False) -> list[str]:
    """Validate authored documentation or legal page records."""
    maximum = 12 if legal else 30
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        return [f"{location} must contain 1 to {maximum} pages"]
    errors: list[str] = []
    expected = {"slug", "title", "summary", "body", "lastUpdated"} if legal else {
        "slug",
        "title",
        "summary",
        "body",
    }
    slugs: set[str] = set()
    for index, page in enumerate(value):
        item = f"{location}[{index}]"
        if not isinstance(page, dict) or set(page) != expected:
            errors.append(f"{item} fields must be {', '.join(sorted(expected))}")
            continue
        slug = page.get("slug")
        if not isinstance(slug, str) or SLUG_RE.fullmatch(slug) is None or slug in slugs:
            errors.append(f"{item}.slug must be unique kebab-case")
        else:
            slugs.add(slug)
        for key in ("title", "summary", "body"):
            errors.extend(text_errors(page.get(key), f"{item}.{key}"))
        if legal:
            updated = page.get("lastUpdated")
            if not isinstance(updated, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated) is None:
                errors.append(f"{item}.lastUpdated must be an ISO date")
    return errors


def validate_site_content(value: object, location: str) -> list[str]:
    """Validate the portable v1 content model used by generated Zensical source."""
    if not isinstance(value, dict):
        return [f"{location} must be an object"]
    errors: list[str] = []
    expected = {"schema", "product", "documentation", "architecture", "legal"}
    if set(value) != expected:
        errors.append(f"{location} fields must be {', '.join(sorted(expected))}")
    if value.get("schema") != "holon.site-suite-content/v1":
        errors.append(f"{location}.schema is invalid")

    product = value.get("product")
    if not isinstance(product, dict) or set(product) != {"name", "description", "repositoryUrl"}:
        errors.append(f"{location}.product is malformed")
    else:
        errors.extend(text_errors(product["name"], f"{location}.product.name", maximum=500))
        errors.extend(text_errors(product["description"], f"{location}.product.description", maximum=500))
        if not isinstance(product["repositoryUrl"], str) or HTTPS_RE.fullmatch(product["repositoryUrl"]) is None:
            errors.append(f"{location}.product.repositoryUrl must use HTTPS")

    documentation = value.get("documentation")
    if not isinstance(documentation, dict) or set(documentation) != {"title", "introduction", "pages"}:
        errors.append(f"{location}.documentation is malformed")
    else:
        errors.extend(text_errors(documentation["title"], f"{location}.documentation.title", maximum=500))
        errors.extend(text_errors(documentation["introduction"], f"{location}.documentation.introduction"))
        errors.extend(page_errors(documentation["pages"], f"{location}.documentation.pages"))

    architecture = value.get("architecture")
    if not isinstance(architecture, dict) or set(architecture) != {
        "title",
        "introduction",
        "diagram",
        "decisions",
    }:
        errors.append(f"{location}.architecture is malformed")
    else:
        for key in ("title", "introduction", "diagram"):
            errors.extend(text_errors(architecture[key], f"{location}.architecture.{key}"))
        decisions = architecture["decisions"]
        if not isinstance(decisions, list) or not 1 <= len(decisions) <= 40:
            errors.append(f"{location}.architecture.decisions must contain 1 to 40 records")
        else:
            identifiers: set[str] = set()
            for index, decision in enumerate(decisions):
                item = f"{location}.architecture.decisions[{index}]"
                required = {"id", "title", "status", "summary"}
                if not isinstance(decision, dict) or set(decision) - (required | {"href"}) or not required <= set(decision):
                    errors.append(f"{item} is malformed")
                    continue
                identifier = decision["id"]
                if not isinstance(identifier, str) or identifier in identifiers:
                    errors.append(f"{item}.id must be unique")
                else:
                    identifiers.add(identifier)
                for key in ("id", "title", "summary"):
                    errors.extend(text_errors(decision[key], f"{item}.{key}"))
                if decision["status"] not in {"proposed", "accepted", "superseded", "rejected"}:
                    errors.append(f"{item}.status is invalid")
                if "href" in decision and (
                    not isinstance(decision["href"], str) or HTTPS_RE.fullmatch(decision["href"]) is None
                ):
                    errors.append(f"{item}.href must use HTTPS")

    legal = value.get("legal")
    if not isinstance(legal, dict) or set(legal) != {"title", "introduction", "pages"}:
        errors.append(f"{location}.legal is malformed")
    else:
        errors.extend(text_errors(legal["title"], f"{location}.legal.title", maximum=500))
        errors.extend(text_errors(legal["introduction"], f"{location}.legal.introduction"))
        errors.extend(page_errors(legal["pages"], f"{location}.legal.pages", legal=True))
    return errors


def renderable_errors(
    project: Path, sources: list[Path], resolved: dict[str, Any], location: str
) -> list[str]:
    """Ensure every source token resolves for one composition variant."""
    errors: list[str] = []
    for source_root in sources:
        for source in sorted((project / source_root).rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(project / source_root).as_posix()
            try:
                rendered = render_source_bytes(source.read_bytes(), resolved, relative)
            except (MaterializationError, ValueError) as error:
                errors.append(f"{location}: {source_root}/{relative}: {error}")
                continue
            if TEMPLATE_TOKEN_RE.search(rendered.decode("utf-8", errors="ignore")):
                errors.append(f"{location}: {source_root}/{relative} leaves unresolved tokens")
    return errors


def validate_blueprints(project: Path = ROOT) -> list[str]:
    """Validate profiles, provenance, inputs, variants, and generated inventories."""
    project = project.resolve()
    errors: list[str] = []
    try:
        catalog = load_json(project / CATALOG)
        zensical = load_strict_json(project / ZENSICAL_PROFILE)
        audit = load_strict_json(project / ZENSICAL_AUDIT)
        suite = load_strict_json(project / SUITE_PROFILE)
        react = load_strict_json(project / REACT_PROFILE)
        launchkit = load_strict_json(project / LAUNCHKIT_PROFILE)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"site-suite source is invalid: {error}"]

    if zensical.get("schema") != "holon.zensical-blueprint/v1" or zensical.get("version") != "1.0.0":
        errors.append("Zensical profile schema/version is invalid")
    if zensical.get("status") != "active" or zensical.get("capability") != "docs-zensical":
        errors.append("Zensical profile must expose active docs-zensical")
    if zensical.get("render_source") != ZENSICAL_FILES.as_posix():
        errors.append("Zensical profile render source is invalid")
    if zensical.get("files") != inventory(project, ZENSICAL_FILES):
        errors.append("Zensical rendered-pack inventory is stale")
    toolchain = zensical.get("toolchain", {})
    if toolchain.get("zensical") != ZENSICAL_VERSION:
        errors.append("Zensical toolchain version is not pinned")
    if audit.get("release") != f"v{ZENSICAL_VERSION}" or audit.get("commit") != ZENSICAL_COMMIT:
        errors.append("Zensical upstream release/commit evidence is stale")
    if zensical.get("upstream", {}).get("commit") != ZENSICAL_COMMIT:
        errors.append("Zensical profile does not pin the audited commit")
    notice = (project / ZENSICAL_FILES / "site-docs/THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    if ZENSICAL_COMMIT not in notice or "MIT License" not in notice:
        errors.append("Zensical third-party notice lacks release attribution")
    lock = (project / ZENSICAL_FILES / "site-docs/requirements.lock.txt").read_text(encoding="utf-8")
    if f"zensical=={ZENSICAL_VERSION}" not in lock or "--hash=sha256:" not in lock:
        errors.append("Zensical dependency lock lacks exact hash-pinned evidence")
    if str(project) in lock or "/workspace/" in lock:
        errors.append("Zensical dependency lock embeds a source-machine path")
    capability = catalog.get("capabilities", {}).get("docs-zensical", {})
    if set(capability.get("requires", [])) != {"architecture-context", "egolint-quality"}:
        errors.append("docs-zensical must compose architecture context and Egolint/Relay quality")

    if suite.get("schema") != "holon.site-suite-profile/v1" or suite.get("version") != "1.0.0":
        errors.append("site-suite profile schema/version is invalid")
    if suite.get("status") != "active" or suite.get("files") != inventory(project, SUITE_FILES):
        errors.append("site-suite overlay status or inventory is invalid")
    expected_profiles = {
        "react_vite": (REACT_PROFILE, react),
        "launchkit": (LAUNCHKIT_PROFILE, launchkit),
        "zensical": (ZENSICAL_PROFILE, zensical),
    }
    profiles = suite.get("profiles", {})
    for name, (path, profile) in expected_profiles.items():
        record = profiles.get(name, {}) if isinstance(profiles, dict) else {}
        if record.get("path") != path.as_posix() or record.get("version") != profile.get("version"):
            errors.append(f"site-suite {name} profile reference is invalid")
        if record.get("sha256") != sha256(project / path):
            errors.append(f"site-suite {name} profile digest is stale")
    if suite.get("routes") != {
        "landing": "/",
        "documentation": "/docs/",
        "architecture": "/architecture/",
        "legal": "/legal/",
    }:
        errors.append("site-suite route contract is invalid")
    if suite.get("publication", {}).get("owner") != "egohygiene/relay":
        errors.append("site-suite must leave publication ownership with Relay")
    slots = suite.get("composition_slots", {})
    if slots.get("agent_ready_web", {}).get("status") != "contract-pending":
        errors.append("site-suite must not claim open Agent-Ready Web contracts")
    if slots.get("legal_policy", {}).get("issues") != [11]:
        errors.append("site-suite must preserve the open reusable legal-source boundary")

    variants = suite.get("variants", {})
    expected_overlays = {
        "generic": [ZENSICAL_FILES.as_posix(), SUITE_FILES.as_posix()],
        "launchkit": [
            LAUNCHKIT_FILES.as_posix(),
            ZENSICAL_FILES.as_posix(),
            SUITE_FILES.as_posix(),
        ],
    }
    selected_capabilities: dict[str, set[str]] = {}
    for name, example_path in EXAMPLES.items():
        variant = variants.get(name, {}) if isinstance(variants, dict) else {}
        if variant.get("render_source") != REACT_FILES.as_posix():
            errors.append(f"site-suite {name} must use the generic React/Vite source")
        if variant.get("render_overlays") != expected_overlays[name]:
            errors.append(f"site-suite {name} overlay order is invalid")
        manifest = load_json(project / example_path)
        resolved, resolve_errors = resolve_manifest(catalog, manifest)
        errors.extend(f"{example_path}: {error}" for error in resolve_errors)
        if resolved is None:
            continue
        capabilities = set(resolved.get("capabilities", []))
        selected_capabilities[name] = capabilities
        required = {"site-react-vite", "docs-zensical", "egolint-quality", "relay-ci"}
        if not required <= capabilities:
            errors.append(f"{example_path} does not resolve the complete site-suite chain")
        if (name == "launchkit") != ("landing-launchkit" in capabilities):
            errors.append(f"{example_path} selects the wrong landing variant")
        if not {"landing", "docs", "architecture", "legal"} <= set(resolved.get("sites", [])):
            errors.append(f"{example_path} does not select every public surface")
        parameters = resolved.get("parameters")
        expected_parameters = LAUNCHKIT_PARAMETERS if name == "launchkit" else COMMON_PARAMETERS
        if not isinstance(parameters, dict) or set(parameters) != expected_parameters:
            errors.append(f"{example_path} parameters do not match the {name} variant")
            continue
        errors.extend(
            validate_parameters(
                {
                    key: parameters.get(key)
                    for key in {
                        "canonical_url",
                        "identity_stylesheet",
                        "package_name",
                        "site_base_path",
                        "site_description",
                        "site_title",
                    }
                }
            )
        )
        for key in ("identity_favicon_url", "repository_url"):
            if not isinstance(parameters.get(key), str) or HTTPS_RE.fullmatch(parameters[key]) is None:
                errors.append(f"{example_path}:{key} must use HTTPS")
        content = parameters.get("site_suite_content")
        errors.extend(validate_site_content(content, f"{example_path}:site_suite_content"))
        if isinstance(content, dict) and isinstance(content.get("product"), dict):
            if content["product"].get("repositoryUrl") != parameters.get("repository_url"):
                errors.append(f"{example_path} repeats inconsistent repository metadata")
        if name == "launchkit":
            errors.extend(
                validate_launchkit_content(
                    parameters.get("launchkit_content"), f"{example_path}:launchkit_content"
                )
            )
        source_paths = [REACT_FILES, *(Path(path) for path in expected_overlays[name])]
        errors.extend(renderable_errors(project, source_paths, resolved, str(example_path)))

    if selected_capabilities.get("generic") == selected_capabilities.get("launchkit"):
        errors.append("site-suite pilots do not prove distinct landing capability sets")
    return sorted(set(errors))


def write_inventories(project: Path) -> None:
    """Refresh profile inventories and exact composed-profile digests in dependency order."""
    zensical_path = project / ZENSICAL_PROFILE
    zensical = load_strict_json(zensical_path)
    zensical["files"] = inventory(project, ZENSICAL_FILES)
    zensical_path.write_text(json.dumps(zensical, indent=2) + "\n", encoding="utf-8")

    suite_path = project / SUITE_PROFILE
    suite = load_strict_json(suite_path)
    suite["profiles"]["react_vite"]["sha256"] = sha256(project / REACT_PROFILE)
    suite["profiles"]["launchkit"]["sha256"] = sha256(project / LAUNCHKIT_PROFILE)
    suite["profiles"]["zensical"]["sha256"] = sha256(project / ZENSICAL_PROFILE)
    suite["files"] = inventory(project, SUITE_FILES)
    suite_path.write_text(json.dumps(suite, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    """Validate the profiles or refresh their generated evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--write-inventories", action="store_true")
    arguments = parser.parse_args()
    project = arguments.project.expanduser().resolve()
    if arguments.write_inventories:
        write_inventories(project)
    errors = validate_blueprints(project)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    zensical = load_strict_json(project / ZENSICAL_PROFILE)
    suite = load_strict_json(project / SUITE_PROFILE)
    print(
        f"Validated Zensical {zensical['version']} ({len(zensical['files'])} files) "
        f"and site-suite {suite['version']} ({len(suite['files'])} overlay files, 2 variants)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
