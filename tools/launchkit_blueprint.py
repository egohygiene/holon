#!/usr/bin/env python3
"""Validate Holon's derived LaunchKit developer-product landing blueprint."""

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
from materialization.common import MaterializationError, TEMPLATE_TOKEN_RE, render_source_bytes
from react_vite_blueprint import load_strict_json, validate_parameters

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = Path("blueprints/launchkit/blueprint.json")
OVERLAY_PATH = Path("blueprints/launchkit/files")
BASE_PROFILE_PATH = Path("blueprints/react-vite/blueprint.json")
BASE_SOURCE_PATH = Path("blueprints/react-vite/files")
AUDIT_PATH = Path("blueprints/launchkit/upstream-audit.json")
CATALOG_PATH = Path("catalog/foundation.json")
EXAMPLE_PATHS = (
    Path("examples/launchkit-optiflow.manifest.json"),
    Path("examples/launchkit-mantle.manifest.json"),
)
EXPECTED_SCHEMA = "holon.launchkit-blueprint/v1"
EXPECTED_CONTENT_SCHEMA = "holon.launchkit-content/v1"
EXPECTED_VERSION = "1.0.0"
EXPECTED_COMMIT = "b51f64e1bd88a01608c1561a2d3240f230de4f46"
BASE_PARAMETERS = {
    "canonical_url",
    "identity_stylesheet",
    "package_name",
    "site_base_path",
    "site_description",
    "site_title",
}
EXPECTED_PARAMETERS = BASE_PARAMETERS | {
    "identity_favicon_url",
    "identity_social_image_url",
    "launchkit_content",
}
PLACEHOLDER_PATTERNS = (
    "lorem ipsum",
    "request a demo",
    "sign up",
    "logo template",
    "placeholder-",
    "mintlify.com",
    "substack.com",
    "wellfound.com",
)
LINK_RE = re.compile(r"^(?:https://|/|#)\S+$")
SAFE_PACKAGE_RE = re.compile(r"(?:@[a-z0-9.-]+/)?[a-z0-9][a-z0-9._-]*")


def sha256(path: Path) -> str:
    """Return one file's lowercase SHA-256 identity."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def overlay_inventory(project: Path) -> list[dict[str, str]]:
    """Build the canonical sorted overlay inventory."""
    source = project / OVERLAY_PATH
    return [
        {"path": path.relative_to(source).as_posix(), "sha256": sha256(path)}
        for path in sorted(source.rglob("*"))
        if path.is_file()
    ]


def validate_link(value: object, location: str) -> list[str]:
    """Validate one public or same-page link."""
    if not isinstance(value, str) or LINK_RE.fullmatch(value) is None:
        return [f"{location} must be an HTTPS, root-relative, or fragment link"]
    return []


def validate_text(value: object, location: str, *, maximum: int = 500) -> list[str]:
    """Validate bounded human-visible copy and reject upstream placeholders."""
    if not isinstance(value, str) or not value.strip():
        return [f"{location} must be a non-empty string"]
    errors: list[str] = []
    if len(value) > maximum:
        errors.append(f"{location} exceeds {maximum} characters")
    lowered = value.casefold()
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern in lowered:
            errors.append(f"{location} contains forbidden upstream placeholder copy: {pattern}")
    return errors


def validate_links(value: object, location: str, *, minimum: int = 0) -> list[str]:
    """Validate a bounded array of unique labeled links."""
    if not isinstance(value, list) or len(value) < minimum or len(value) > 12:
        return [f"{location} must contain between {minimum} and 12 links"]
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, link in enumerate(value):
        item = f"{location}[{index}]"
        if not isinstance(link, dict) or set(link) != {"label", "href"}:
            errors.append(f"{item} contains unsupported fields")
            continue
        errors.extend(validate_text(link.get("label"), f"{item}.label"))
        errors.extend(validate_link(link.get("href"), f"{item}.href"))
        identity = (str(link.get("label")), str(link.get("href")))
        if identity in seen:
            errors.append(f"{location} repeats link {identity[0]!r}")
        seen.add(identity)
    return errors


def validate_actions(value: object, location: str) -> list[str]:
    """Validate one to three explicit primary or secondary calls to action."""
    if not isinstance(value, list) or not 1 <= len(value) <= 3:
        return [f"{location} must contain between 1 and 3 actions"]
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, action in enumerate(value):
        item = f"{location}[{index}]"
        if not isinstance(action, dict) or set(action) != {"label", "href", "tone"}:
            errors.append(f"{item} must contain label, href, and tone")
            continue
        errors.extend(validate_text(action["label"], f"{item}.label"))
        errors.extend(validate_link(action["href"], f"{item}.href"))
        if action["tone"] not in {"primary", "secondary"}:
            errors.append(f"{item}.tone is invalid")
        identity = (str(action["label"]), str(action["href"]))
        if identity in seen:
            errors.append(f"{location} repeats action {identity[0]!r}")
        seen.add(identity)
    return errors


def validate_cards(value: object, location: str, *, minimum: int = 1) -> list[str]:
    """Validate a bounded developer-product card collection."""
    if not isinstance(value, list) or not minimum <= len(value) <= 8:
        return [f"{location} must contain between {minimum} and 8 cards"]
    errors: list[str] = []
    titles: set[str] = set()
    for index, card in enumerate(value):
        item = f"{location}[{index}]"
        if not isinstance(card, dict):
            errors.append(f"{item} must be an object")
            continue
        if set(card) - {"eyebrow", "title", "description", "href"}:
            errors.append(f"{item} contains unsupported fields")
        if "eyebrow" in card:
            errors.extend(validate_text(card["eyebrow"], f"{item}.eyebrow"))
        errors.extend(validate_text(card.get("title"), f"{item}.title"))
        errors.extend(validate_text(card.get("description"), f"{item}.description"))
        if "href" in card:
            errors.extend(validate_link(card["href"], f"{item}.href"))
        title = str(card.get("title"))
        if title in titles:
            errors.append(f"{location} repeats title {title!r}")
        titles.add(title)
    return errors


def validate_section_cards(value: object, location: str) -> list[str]:
    """Validate one optional heading plus cards section."""
    if not isinstance(value, dict):
        return [f"{location} must be an object"]
    errors: list[str] = []
    expected = {"eyebrow", "title", "description", "items"}
    if set(value) != expected:
        errors.append(f"{location} fields must be {', '.join(sorted(expected))}")
    for key in ("eyebrow", "title", "description"):
        errors.extend(validate_text(value.get(key), f"{location}.{key}"))
    errors.extend(validate_cards(value.get("items"), f"{location}.items"))
    return errors


def validate_content(content: object, location: str) -> list[str]:
    """Validate the complete v1 LaunchKit manifest content contract."""
    if not isinstance(content, dict):
        return [f"{location} must be an object"]
    errors: list[str] = []
    allowed = {
        "schema",
        "identity",
        "navigation",
        "announcement",
        "hero",
        "proof",
        "demo",
        "features",
        "useCases",
        "code",
        "architecture",
        "integrations",
        "trust",
        "faq",
        "finalCta",
        "footer",
    }
    required = {"schema", "identity", "hero", "features", "footer"}
    if missing := required - set(content):
        errors.append(f"{location} is missing: {', '.join(sorted(missing))}")
    if unexpected := set(content) - allowed:
        errors.append(f"{location} has unsupported fields: {', '.join(sorted(unexpected))}")
    if content.get("schema") != EXPECTED_CONTENT_SCHEMA:
        errors.append(f"{location}.schema must be {EXPECTED_CONTENT_SCHEMA}")

    identity = content.get("identity")
    if not isinstance(identity, dict) or set(identity) - {"wordmark", "logo"}:
        errors.append(f"{location}.identity is malformed")
    else:
        errors.extend(validate_text(identity.get("wordmark"), f"{location}.identity.wordmark"))
        logo = identity.get("logo")
        if logo is not None:
            if not isinstance(logo, dict) or set(logo) != {"src", "alt"}:
                errors.append(f"{location}.identity.logo is malformed")
            else:
                errors.extend(validate_link(logo.get("src"), f"{location}.identity.logo.src"))
                errors.extend(validate_text(logo.get("alt"), f"{location}.identity.logo.alt"))

    if "navigation" in content:
        errors.extend(validate_links(content["navigation"], f"{location}.navigation"))
    if announcement := content.get("announcement"):
        errors.extend(validate_links([announcement], f"{location}.announcement", minimum=1))

    hero = content.get("hero")
    if not isinstance(hero, dict) or set(hero) != {"eyebrow", "title", "description", "actions"}:
        errors.append(f"{location}.hero is malformed")
    else:
        for key in ("eyebrow", "title", "description"):
            errors.extend(validate_text(hero.get(key), f"{location}.hero.{key}"))
        errors.extend(validate_actions(hero.get("actions"), f"{location}.hero.actions"))

    errors.extend(validate_section_cards(content.get("features"), f"{location}.features"))
    for key in ("useCases", "architecture", "integrations"):
        if key in content:
            errors.extend(validate_section_cards(content[key], f"{location}.{key}"))

    proof = content.get("proof")
    if proof is not None:
        if not isinstance(proof, dict) or set(proof) != {"title", "items"}:
            errors.append(f"{location}.proof is malformed")
        else:
            errors.extend(validate_text(proof.get("title"), f"{location}.proof.title"))
            items = proof.get("items")
            if not isinstance(items, list) or not 1 <= len(items) <= 12:
                errors.append(f"{location}.proof.items must contain 1 to 12 strings")
            else:
                for index, item in enumerate(items):
                    errors.extend(validate_text(item, f"{location}.proof.items[{index}]"))

    demo = content.get("demo")
    if demo is not None:
        if not isinstance(demo, dict) or set(demo) - {"eyebrow", "title", "description", "asset", "metrics"}:
            errors.append(f"{location}.demo is malformed")
        else:
            for key in ("eyebrow", "title", "description"):
                errors.extend(validate_text(demo.get(key), f"{location}.demo.{key}"))
            metrics = demo.get("metrics")
            if not isinstance(metrics, list) or not 1 <= len(metrics) <= 4:
                errors.append(f"{location}.demo.metrics must contain 1 to 4 records")
            else:
                for index, metric in enumerate(metrics):
                    if not isinstance(metric, dict) or set(metric) != {"label", "value"}:
                        errors.append(f"{location}.demo.metrics[{index}] is malformed")
                    else:
                        errors.extend(validate_text(metric["label"], f"{location}.demo.metrics[{index}].label"))
                        errors.extend(validate_text(metric["value"], f"{location}.demo.metrics[{index}].value"))

    code = content.get("code")
    if code is not None:
        expected = {"eyebrow", "title", "description", "language", "value"}
        if not isinstance(code, dict) or set(code) != expected:
            errors.append(f"{location}.code is malformed")
        else:
            for key in expected:
                errors.extend(validate_text(code[key], f"{location}.code.{key}", maximum=4000))

    trust = content.get("trust")
    if trust is not None:
        expected = {"eyebrow", "title", "description", "links"}
        if not isinstance(trust, dict) or set(trust) != expected:
            errors.append(f"{location}.trust is malformed")
        else:
            for key in ("eyebrow", "title", "description"):
                errors.extend(validate_text(trust[key], f"{location}.trust.{key}"))
            errors.extend(validate_links(trust["links"], f"{location}.trust.links", minimum=1))

    faq = content.get("faq")
    if faq is not None:
        expected = {"eyebrow", "title", "description", "items"}
        if not isinstance(faq, dict) or set(faq) != expected:
            errors.append(f"{location}.faq is malformed")
        else:
            for key in ("eyebrow", "title", "description"):
                errors.extend(validate_text(faq[key], f"{location}.faq.{key}"))
            items = faq["items"]
            if not isinstance(items, list) or len(items) > 12:
                errors.append(f"{location}.faq.items must contain at most 12 records")
                items = []
            for index, item in enumerate(items):
                if not isinstance(item, dict) or set(item) != {"question", "answer"}:
                    errors.append(f"{location}.faq.items[{index}] is malformed")
                else:
                    errors.extend(
                        validate_text(item["question"], f"{location}.faq.items[{index}].question")
                    )
                    errors.extend(
                        validate_text(item["answer"], f"{location}.faq.items[{index}].answer")
                    )

    final_cta = content.get("finalCta")
    if final_cta is not None:
        expected = {"title", "description", "actions"}
        if not isinstance(final_cta, dict) or set(final_cta) != expected:
            errors.append(f"{location}.finalCta is malformed")
        else:
            errors.extend(validate_text(final_cta["title"], f"{location}.finalCta.title"))
            errors.extend(validate_text(final_cta["description"], f"{location}.finalCta.description"))
            errors.extend(validate_actions(final_cta["actions"], f"{location}.finalCta.actions"))

    footer = content.get("footer")
    if not isinstance(footer, dict) or set(footer) != {"summary", "groups", "legal"}:
        errors.append(f"{location}.footer is malformed")
    else:
        errors.extend(validate_text(footer["summary"], f"{location}.footer.summary"))
        groups = footer.get("groups")
        if not isinstance(groups, list) or len(groups) > 4:
            errors.append(f"{location}.footer.groups must contain at most 4 groups")
        else:
            for index, group in enumerate(groups):
                if not isinstance(group, dict) or set(group) != {"title", "links"}:
                    errors.append(f"{location}.footer.groups[{index}] is malformed")
                else:
                    errors.extend(validate_text(group["title"], f"{location}.footer.groups[{index}].title"))
                    errors.extend(validate_links(group["links"], f"{location}.footer.groups[{index}].links", minimum=1))
        errors.extend(validate_links(footer["legal"], f"{location}.footer.legal", minimum=1))
    return errors


def validate_blueprint(project: Path = ROOT) -> list[str]:
    """Validate composition, provenance, content, inventory, and pilot boundaries."""
    project = project.resolve()
    errors: list[str] = []
    try:
        profile = load_strict_json(project / PROFILE_PATH)
        base_profile = load_strict_json(project / BASE_PROFILE_PATH)
        audit = load_strict_json(project / AUDIT_PATH)
        catalog = load_json(project / CATALOG_PATH)
        overlay_package = load_strict_json(project / OVERLAY_PATH / "package.json")
        base_package = load_strict_json(project / BASE_SOURCE_PATH / "package.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"LaunchKit blueprint source is invalid: {error}"]

    if profile.get("schema") != EXPECTED_SCHEMA or profile.get("version") != EXPECTED_VERSION:
        errors.append("LaunchKit profile schema/version is not the reviewed v1 contract")
    if profile.get("status") != "active" or profile.get("capability") != "landing-launchkit":
        errors.append("LaunchKit profile must expose the active landing-launchkit capability")
    extension = profile.get("extends")
    if not isinstance(extension, dict):
        errors.append("LaunchKit profile must extend the React/Vite profile")
    else:
        if extension.get("version") != base_profile.get("version"):
            errors.append("LaunchKit base version does not match the React/Vite profile")
        if extension.get("sha256") != sha256(project / BASE_PROFILE_PATH):
            errors.append("LaunchKit base profile digest is stale")
    if profile.get("render_source") != BASE_SOURCE_PATH.as_posix():
        errors.append("LaunchKit must use the canonical React/Vite render source")
    if profile.get("render_overlays") != [OVERLAY_PATH.as_posix()]:
        errors.append("LaunchKit must use exactly one reviewed ordered overlay")
    if set(profile.get("required_parameters", [])) != EXPECTED_PARAMETERS:
        errors.append("LaunchKit required parameters do not match the v1 contract")

    if audit.get("commit") != EXPECTED_COMMIT or profile.get("upstream", {}).get("commit") != EXPECTED_COMMIT:
        errors.append("LaunchKit upstream commit is not pinned consistently")
    if audit.get("license", {}).get("spdx") != "MIT":
        errors.append("LaunchKit upstream audit must record the MIT license")
    notice = (project / OVERLAY_PATH / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    if EXPECTED_COMMIT not in notice or "Copyright (c) 2025 Evil Martians" not in notice:
        errors.append("generated third-party notice lacks pinned LaunchKit attribution")

    capability = catalog.get("capabilities", {}).get("landing-launchkit", {})
    if set(capability.get("requires", [])) != {"architecture-context", "site-react-vite"}:
        errors.append("landing-launchkit must depend on architecture-context and site-react-vite")
    if base_profile.get("extends") is not None:
        errors.append("the generic React/Vite profile must remain independent of LaunchKit")

    base_dependencies = {
        **(base_package.get("dependencies") or {}),
        **(base_package.get("devDependencies") or {}),
    }
    overlay_dependencies = {
        **(overlay_package.get("dependencies") or {}),
        **(overlay_package.get("devDependencies") or {}),
    }
    if overlay_dependencies != base_dependencies:
        errors.append("LaunchKit must not add dependencies to the React/Vite foundation")
    if "render-static.mjs" not in str(overlay_package.get("scripts", {}).get("build")):
        errors.append("LaunchKit build must pre-render semantic HTML")

    actual_inventory = overlay_inventory(project)
    declared_inventory = profile.get("files")
    if declared_inventory != actual_inventory:
        errors.append("LaunchKit overlay inventory is stale or contains orphaned entries")
    paths = [record.get("path") for record in declared_inventory or [] if isinstance(record, dict)]
    for path, count in Counter(paths).items():
        if count > 1:
            errors.append(f"LaunchKit overlay inventory repeats path: {path}")
    forbidden_paths = [path for path in paths if path.startswith(("fonts/", "vendor/", "images/"))]
    if forbidden_paths:
        errors.append("LaunchKit overlay copied forbidden upstream assets: " + ", ".join(forbidden_paths))

    selected_sections: list[set[str]] = []
    for example_path in EXAMPLE_PATHS:
        manifest = load_json(project / example_path)
        resolved, resolve_errors = resolve_manifest(catalog, manifest)
        errors.extend(f"{example_path}: {error}" for error in resolve_errors)
        if resolved is None:
            continue
        capabilities = set(resolved.get("capabilities", []))
        if not {"landing-launchkit", "site-react-vite", "egolint-quality", "relay-ci"} <= capabilities:
            errors.append(f"{example_path} does not resolve the complete composition chain")
        parameters = resolved.get("parameters")
        if not isinstance(parameters, dict):
            errors.append(f"{example_path} parameters must be an object")
            continue
        if set(parameters) != EXPECTED_PARAMETERS:
            errors.append(f"{example_path} parameters do not match the LaunchKit v1 contract")
        errors.extend(validate_parameters({key: parameters.get(key) for key in BASE_PARAMETERS}))
        package_name = parameters.get("package_name")
        if not isinstance(package_name, str) or SAFE_PACKAGE_RE.fullmatch(package_name) is None:
            errors.append(f"{example_path} package_name is invalid")
        for key in ("identity_favicon_url", "identity_social_image_url"):
            errors.extend(validate_link(parameters.get(key), f"{example_path}:{key}"))
        content = parameters.get("launchkit_content")
        errors.extend(validate_content(content, f"{example_path}:launchkit_content"))
        if isinstance(content, dict):
            selected_sections.append(set(content))
        for source in sorted((project / OVERLAY_PATH).rglob("*")):
            if not source.is_file():
                continue
            try:
                rendered = render_source_bytes(
                    source.read_bytes(), resolved, source.relative_to(project / OVERLAY_PATH).as_posix()
                )
            except (MaterializationError, ValueError) as error:
                errors.append(f"{example_path}: {error}")
                continue
            if TEMPLATE_TOKEN_RE.search(rendered.decode("utf-8", errors="ignore")):
                errors.append(f"{example_path} leaves unresolved overlay tokens")

    if len(selected_sections) == 2 and selected_sections[0] == selected_sections[1]:
        errors.append("LaunchKit pilot fixtures must select materially different section sets")

    overlay_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted((project / OVERLAY_PATH).rglob("*"))
        if path.is_file() and not path.name.endswith((".test.ts", ".test.tsx"))
    ).casefold()
    for placeholder in PLACEHOLDER_PATTERNS:
        if placeholder in overlay_text:
            errors.append(f"LaunchKit overlay contains upstream placeholder/reference: {placeholder}")
    return sorted(set(errors))


def write_inventory(project: Path) -> None:
    """Refresh the deterministic LaunchKit overlay inventory."""
    path = project / PROFILE_PATH
    profile = load_strict_json(path)
    profile["files"] = overlay_inventory(project)
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> int:
    """Validate the blueprint or refresh its overlay inventory."""
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
        f"Validated LaunchKit blueprint {profile['version']} "
        f"({len(profile['files'])} overlay files, {len(EXAMPLE_PATHS)} pilot fixtures)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
