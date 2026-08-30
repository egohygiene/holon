#!/usr/bin/env python3
"""Validate, render, build, and preview Holon's Zensical-owned surfaces."""

from __future__ import annotations

import argparse
from datetime import date
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from html import escape
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
SITE_ROOT = ROOT / "site-docs"
CONTENT_PATH = SITE_ROOT / "content.json"
SETTINGS_PATH = SITE_ROOT / "settings.json"
GENERATED = SITE_ROOT / ".generated"
BUILD = SITE_ROOT / "build"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HTTPS_RE = re.compile(r"^https://\S+$")
PLACEHOLDERS = ("lorem ipsum", "request a demo", "placeholder-", "example.com")


class ContractError(ValueError):
    """Raised when a consumer's site-suite content violates the v1 contract."""


def load_object(path: Path) -> dict[str, Any]:
    """Load one JSON object without accepting a non-object root."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain a JSON object")
    return value


def require_fields(value: object, expected: set[str], location: str) -> dict[str, Any]:
    """Require one closed object with an exact field set."""
    if not isinstance(value, dict) or set(value) != expected:
        raise ContractError(f"{location} fields must be {', '.join(sorted(expected))}")
    return value


def require_text(value: object, location: str, *, maximum: int = 12000) -> str:
    """Return bounded non-placeholder text."""
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ContractError(f"{location} must contain 1 to {maximum} characters")
    lowered = value.casefold()
    if placeholder := next((item for item in PLACEHOLDERS if item in lowered), None):
        raise ContractError(f"{location} contains forbidden placeholder copy: {placeholder}")
    return value.strip()


def require_https(value: object, location: str) -> str:
    """Return one absolute HTTPS URL."""
    if not isinstance(value, str) or HTTPS_RE.fullmatch(value) is None:
        raise ContractError(f"{location} must be an HTTPS URL")
    return value


def validate_pages(value: object, location: str, *, legal: bool = False) -> list[dict[str, Any]]:
    """Validate ordered authored pages and stable route slugs."""
    if not isinstance(value, list) or not 1 <= len(value) <= (12 if legal else 30):
        raise ContractError(f"{location} must contain a bounded non-empty page list")
    pages: list[dict[str, Any]] = []
    slugs: set[str] = set()
    fields = {"slug", "title", "summary", "body", "lastUpdated"} if legal else {
        "slug",
        "title",
        "summary",
        "body",
    }
    for index, raw in enumerate(value):
        page = require_fields(raw, fields, f"{location}[{index}]")
        slug = require_text(page["slug"], f"{location}[{index}].slug", maximum=80)
        if SLUG_RE.fullmatch(slug) is None or slug in slugs:
            raise ContractError(f"{location}[{index}].slug must be unique kebab-case")
        slugs.add(slug)
        require_text(page["title"], f"{location}[{index}].title", maximum=500)
        require_text(page["summary"], f"{location}[{index}].summary", maximum=500)
        require_text(page["body"], f"{location}[{index}].body")
        if legal:
            updated = require_text(page["lastUpdated"], f"{location}[{index}].lastUpdated", maximum=10)
            try:
                date.fromisoformat(updated)
            except ValueError as error:
                raise ContractError(f"{location}[{index}].lastUpdated must be an ISO date") from error
        pages.append(page)
    return pages


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate content, product metadata, routes, and Identity input locations."""
    content = require_fields(
        load_object(CONTENT_PATH),
        {"schema", "product", "documentation", "architecture", "legal"},
        "site_suite_content",
    )
    if content["schema"] != "holon.site-suite-content/v1":
        raise ContractError("site_suite_content.schema must be holon.site-suite-content/v1")
    product = require_fields(
        content["product"], {"name", "description", "repositoryUrl"}, "product"
    )
    require_text(product["name"], "product.name", maximum=500)
    require_text(product["description"], "product.description", maximum=500)
    require_https(product["repositoryUrl"], "product.repositoryUrl")

    documentation = require_fields(
        content["documentation"], {"title", "introduction", "pages"}, "documentation"
    )
    require_text(documentation["title"], "documentation.title", maximum=500)
    require_text(documentation["introduction"], "documentation.introduction")
    validate_pages(documentation["pages"], "documentation.pages")

    architecture = require_fields(
        content["architecture"],
        {"title", "introduction", "diagram", "decisions"},
        "architecture",
    )
    require_text(architecture["title"], "architecture.title", maximum=500)
    require_text(architecture["introduction"], "architecture.introduction")
    require_text(architecture["diagram"], "architecture.diagram", maximum=8000)
    decisions = architecture["decisions"]
    if not isinstance(decisions, list) or not 1 <= len(decisions) <= 40:
        raise ContractError("architecture.decisions must contain 1 to 40 records")
    decision_ids: set[str] = set()
    for index, raw in enumerate(decisions):
        allowed = {"id", "title", "status", "summary", "href"}
        if not isinstance(raw, dict) or set(raw) - allowed or not {"id", "title", "status", "summary"} <= set(raw):
            raise ContractError(f"architecture.decisions[{index}] is malformed")
        identifier = require_text(raw["id"], f"architecture.decisions[{index}].id", maximum=80)
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", identifier) is None or identifier in decision_ids:
            raise ContractError(f"architecture.decisions[{index}].id is invalid or repeated")
        decision_ids.add(identifier)
        require_text(raw["title"], f"architecture.decisions[{index}].title", maximum=500)
        require_text(raw["summary"], f"architecture.decisions[{index}].summary")
        if raw["status"] not in {"proposed", "accepted", "superseded", "rejected"}:
            raise ContractError(f"architecture.decisions[{index}].status is invalid")
        if "href" in raw:
            require_https(raw["href"], f"architecture.decisions[{index}].href")

    legal = require_fields(content["legal"], {"title", "introduction", "pages"}, "legal")
    require_text(legal["title"], "legal.title", maximum=500)
    require_text(legal["introduction"], "legal.introduction")
    validate_pages(legal["pages"], "legal.pages", legal=True)

    settings = require_fields(
        load_object(SETTINGS_PATH),
        {
            "canonical_url",
            "identity_favicon_url",
            "identity_stylesheet",
            "repository",
            "repository_url",
            "site_description",
            "site_title",
        },
        "site-docs/settings.json",
    )
    for key in ("canonical_url", "identity_favicon_url", "identity_stylesheet", "repository_url"):
        require_https(settings[key], f"settings.{key}")
    for key in ("repository", "site_description", "site_title"):
        require_text(settings[key], f"settings.{key}", maximum=500)
    if not str(settings["canonical_url"]).endswith("/"):
        raise ContractError("settings.canonical_url must end with /")
    if product["repositoryUrl"] != settings["repository_url"]:
        raise ContractError("product.repositoryUrl must match settings.repository_url")
    return content, settings


def page_document(title: str, summary: str, body: str) -> str:
    """Render one authored Markdown page without framework-local truth."""
    return f"# {title}\n\n{summary}\n\n{body.rstrip()}\n"


def write_markdown(path: Path, content: str) -> None:
    """Write one generated Markdown file beneath the bounded source tree."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def config_text(surface: str, settings: dict[str, Any], docs_dir: Path, site_dir: Path) -> str:
    """Render one deterministic native Zensical TOML configuration."""
    suffix = {"docs": "Documentation", "architecture": "Architecture", "legal": "Legal"}[surface]
    base = str(settings["canonical_url"])
    values = {
        "site_url": f"{base}{surface}/",
        "site_name": f"{settings['site_title']} {suffix}",
        "site_description": settings["site_description"],
        "repo_url": settings["repository_url"],
        "repo_name": settings["repository"],
        "docs_dir": docs_dir.as_posix(),
        "site_dir": site_dir.as_posix(),
    }
    lines = ["[project]"]
    lines.extend(f"{key} = {json.dumps(value)}" for key, value in values.items())
    lines.extend(
        [
            'extra_css = ["stylesheets/extra.css"]',
            "",
            "[project.theme]",
            'custom_dir = "overrides"',
            'language = "en"',
            'features = ["content.code.copy", "navigation.footer", "navigation.sections", "navigation.top", "search.highlight"]',
            "",
            "[[project.theme.palette]]",
            'media = "(prefers-color-scheme: light)"',
            'scheme = "default"',
            'toggle.icon = "lucide/sun"',
            'toggle.name = "Switch to dark mode"',
            "",
            "[[project.theme.palette]]",
            'media = "(prefers-color-scheme: dark)"',
            'scheme = "slate"',
            'toggle.icon = "lucide/moon"',
            'toggle.name = "Switch to light mode"',
            "",
            "[project.markdown_extensions]",
            "attr_list = {}",
            "toc.permalink = true",
            'pymdownx.superfences.custom_fences = [{ name = "mermaid", class = "mermaid", format = "pymdownx.superfences.fence_code_format" }]',
            "",
        ]
    )
    return "\n".join(lines)


def render_sources(content: dict[str, Any], settings: dict[str, Any]) -> None:
    """Project typed content into three isolated Zensical source trees."""
    if GENERATED.exists():
        shutil.rmtree(GENERATED)
    stylesheet = (SITE_ROOT / "styles/extra.css").read_text(encoding="utf-8")
    documentation = content["documentation"]
    docs_root = GENERATED / "docs"
    doc_links = "\n".join(
        f"- [{page['title']}]({page['slug']}.md) — {page['summary']}"
        for page in documentation["pages"]
    )
    write_markdown(
        docs_root / "index.md",
        page_document(documentation["title"], documentation["introduction"], doc_links),
    )
    for page in documentation["pages"]:
        write_markdown(
            docs_root / f"{page['slug']}.md",
            page_document(page["title"], page["summary"], page["body"]),
        )

    architecture = content["architecture"]
    decisions = []
    for decision in architecture["decisions"]:
        title = (
            f"[{decision['id']}: {decision['title']}]({decision['href']})"
            if decision.get("href")
            else f"{decision['id']}: {decision['title']}"
        )
        decisions.append(
            f"## {title}\n\n**Status:** {decision['status']}\n\n{decision['summary']}"
        )
    architecture_body = (
        f"```mermaid\n{architecture['diagram'].rstrip()}\n```\n\n" + "\n\n".join(decisions)
    )
    architecture_root = GENERATED / "architecture"
    write_markdown(
        architecture_root / "index.md",
        page_document(architecture["title"], architecture["introduction"], architecture_body),
    )

    legal = content["legal"]
    legal_root = GENERATED / "legal"
    legal_links = "\n".join(
        f"- [{page['title']}]({page['slug']}.md) — {page['summary']}"
        for page in legal["pages"]
    )
    write_markdown(legal_root / "index.md", page_document(legal["title"], legal["introduction"], legal_links))
    for page in legal["pages"]:
        body = f"**Last updated:** {page['lastUpdated']}\n\n{page['body']}"
        write_markdown(
            legal_root / f"{page['slug']}.md",
            page_document(page["title"], page["summary"], body),
        )

    for surface in ("docs", "architecture", "legal"):
        surface_root = GENERATED / surface
        style_target = surface_root / "stylesheets/extra.css"
        style_target.parent.mkdir(parents=True, exist_ok=True)
        style_target.write_text(stylesheet, encoding="utf-8")
        config = SITE_ROOT / f"zensical.{surface}.toml"
        config.write_text(
            config_text(surface, settings, surface_root.relative_to(SITE_ROOT), Path("build") / surface),
            encoding="utf-8",
        )


def write_hub(settings: dict[str, Any]) -> None:
    """Write a semantic entry page for the standalone three-surface artifact."""
    title = escape(str(settings["site_title"]))
    description = escape(str(settings["site_description"]))
    html = f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{title} site surfaces</title></head>
<body><main><h1>{title}</h1><p>{description}</p><nav aria-label=\"Site surfaces\"><ul><li><a href=\"docs/\">Documentation</a></li><li><a href=\"architecture/\">Architecture</a></li><li><a href=\"legal/\">Legal</a></li></ul></nav></main></body></html>\n"""
    (BUILD / "index.html").write_text(html, encoding="utf-8")


def build() -> None:
    """Render content and run the exact Zensical build for every surface."""
    content, settings = validate_inputs()
    render_sources(content, settings)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    for surface in ("docs", "architecture", "legal"):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "zensical",
                "build",
                "--config-file",
                f"site-docs/zensical.{surface}.toml",
                "--clean",
                "--strict",
            ],
            cwd=ROOT,
            check=True,
        )
        if not (BUILD / surface / "index.html").is_file():
            raise RuntimeError(f"Zensical did not build the {surface} surface")
        # The composed Pages artifact owns one root 404 fallback. Zensical's
        # nested fallback currently links to an absent #__skip target, so it
        # is deliberately excluded instead of publishing a known a11y defect.
        (BUILD / surface / "404.html").unlink(missing_ok=True)
    write_hub(settings)


def preview(host: str, port: int, *, skip_build: bool) -> None:
    """Build and serve the standalone static artifact locally."""
    if not skip_build:
        build()
    handler = partial(SimpleHTTPRequestHandler, directory=str(BUILD))
    with ThreadingHTTPServer((host, port), handler) as server:
        print(f"Serving Zensical surfaces at http://{host}:{port}")
        server.serve_forever()


def main() -> int:
    """Dispatch the bounded Zensical profile command surface."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    subparsers.add_parser("build")
    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("--host", default="127.0.0.1")
    preview_parser.add_argument("--port", type=int, default=8000)
    preview_parser.add_argument("--skip-build", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.command == "validate":
            validate_inputs()
            print("Validated site-suite content contract")
        elif arguments.command == "build":
            build()
            print("Built documentation, architecture, and legal surfaces")
        else:
            preview(arguments.host, arguments.port, skip_build=arguments.skip_build)
    except (ContractError, json.JSONDecodeError, OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
