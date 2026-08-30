#!/usr/bin/env python3
"""Build, verify, and preview Holon's composed GitHub Pages site artifact."""

from __future__ import annotations

import argparse
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
DOCS_BUILD = ROOT / "site-docs/build"
SURFACES = ("docs", "architecture", "legal")
PLACEHOLDERS = ("lorem ipsum", "request a demo", "placeholder-", "example.com")


class PageParser(HTMLParser):
    """Collect structural accessibility facts and local references."""

    def __init__(self) -> None:
        super().__init__()
        self.identifiers: set[str] = set()
        self.references: list[str] = []
        self.duplicate_identifiers: set[str] = set()
        self.has_language = False
        self.has_main = False
        self.has_h1 = False
        self.has_title = False
        self.images_without_alt = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "html" and attributes.get("lang"):
            self.has_language = True
        if tag == "main":
            self.has_main = True
        if tag == "h1":
            self.has_h1 = True
        if tag == "title":
            self.has_title = True
        if tag == "img" and "alt" not in attributes:
            self.images_without_alt += 1
        if identifier := attributes.get("id"):
            if identifier in self.identifiers:
                self.duplicate_identifiers.add(identifier)
            self.identifiers.add(identifier)
        for attribute in ("href", "src"):
            if reference := attributes.get(attribute):
                self.references.append(reference)


def sha256(path: Path) -> str:
    """Return one file's lowercase SHA-256 identity."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> None:
    """Run one visible, fail-fast build command from the repository root."""
    print("+ " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def compose() -> None:
    """Mount the three Zensical artifacts below the selected landing output."""
    if not (DIST / "index.html").is_file():
        raise RuntimeError("the selected landing profile did not emit dist/index.html")
    for surface in SURFACES:
        source = DOCS_BUILD / surface
        target = DIST / surface
        if not (source / "index.html").is_file():
            raise RuntimeError(f"the {surface} source artifact is missing")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    metadata = {
        "schema": "holon.site-suite-artifact/v1",
        "content_sha256": sha256(ROOT / "site-docs/content.json"),
        "profile_sha256": sha256(ROOT / "holon.site-suite.json"),
        "routes": {
            "landing": "/",
            "documentation": "/docs/",
            "architecture": "/architecture/",
            "legal": "/legal/",
        },
    }
    (DIST / "site-suite.manifest.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def reference_target(page: Path, reference: str) -> tuple[Path | None, str | None]:
    """Resolve one local HTML reference without leaving the publication root."""
    split = urlsplit(reference)
    if split.scheme:
        if split.scheme not in {"https", "mailto", "data"}:
            raise RuntimeError(f"reference uses an unsupported URL scheme: {reference}")
        return None, None
    if split.netloc:
        raise RuntimeError(f"reference uses a protocol-relative URL: {reference}")
    if reference.startswith("#"):
        return page, unquote(split.fragment)
    raw_path = unquote(split.path)
    if raw_path.startswith("/"):
        candidate = DIST / raw_path.lstrip("/")
    else:
        candidate = page.parent / raw_path
    candidate = candidate.resolve()
    if not candidate.is_relative_to(DIST.resolve()):
        raise RuntimeError(f"reference leaves the publication artifact: {reference}")
    if raw_path.endswith("/") or candidate.is_dir():
        candidate /= "index.html"
    return candidate, unquote(split.fragment) or None


def verify() -> None:
    """Check routes, semantics, references, placeholders, and reduced motion."""
    required = [DIST / "index.html", *(DIST / surface / "index.html" for surface in SURFACES)]
    missing = [path.relative_to(DIST).as_posix() for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("site suite is missing routes: " + ", ".join(missing))

    parsers: dict[Path, PageParser] = {}
    for page in sorted(DIST.rglob("*.html")):
        html = page.read_text(encoding="utf-8")
        lowered = html.casefold()
        if placeholder := next((item for item in PLACEHOLDERS if item in lowered), None):
            raise RuntimeError(f"{page.relative_to(DIST)} contains placeholder copy: {placeholder}")
        parser = PageParser()
        parser.feed(html)
        parsers[page.resolve()] = parser
        if not all((parser.has_language, parser.has_main, parser.has_h1, parser.has_title)):
            raise RuntimeError(f"{page.relative_to(DIST)} lacks a language, title, main, or h1")
        if parser.images_without_alt:
            raise RuntimeError(f"{page.relative_to(DIST)} contains images without alt attributes")
        if parser.duplicate_identifiers:
            raise RuntimeError(f"{page.relative_to(DIST)} repeats element IDs")

    for page, parser in parsers.items():
        for reference in parser.references:
            target, fragment = reference_target(page, reference)
            if target is None:
                continue
            if not target.is_file():
                raise RuntimeError(
                    f"{page.relative_to(DIST.resolve())} references missing {reference}"
                )
            if fragment and target.suffix == ".html":
                target_parser = parsers.get(target.resolve())
                if target_parser is None:
                    target_parser = PageParser()
                    target_parser.feed(target.read_text(encoding="utf-8"))
                if fragment not in target_parser.identifiers:
                    raise RuntimeError(
                        f"{page.relative_to(DIST.resolve())} references missing fragment {reference}"
                    )

    styles = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(DIST.rglob("*.css"))
    )
    if "prefers-reduced-motion" not in styles:
        raise RuntimeError("the composed artifact lacks a reduced-motion contract")
    manifest = json.loads((DIST / "site-suite.manifest.json").read_text(encoding="utf-8"))
    if set(manifest.get("routes", {})) != {"landing", "documentation", "architecture", "legal"}:
        raise RuntimeError("the site-suite artifact manifest has an incomplete route contract")


def build() -> None:
    """Build the selected landing, build Zensical, compose, and verify output."""
    run(["pnpm", "build"])
    run([sys.executable, "site_docs.py", "build"])
    compose()
    verify()
    print("Built and verified landing, docs, architecture, and legal routes")


def check() -> None:
    """Run consumer quality gates once, then build the complete suite."""
    for script in ("format:check", "lint", "typecheck", "test"):
        run(["pnpm", script])
    build()


def preview(host: str, port: int, *, skip_build: bool) -> None:
    """Build and serve the exact GitHub Pages artifact locally."""
    if not skip_build:
        build()
    else:
        verify()
    handler = partial(SimpleHTTPRequestHandler, directory=str(DIST))
    with ThreadingHTTPServer((host, port), handler) as server:
        print(f"Serving composed site at http://{host}:{port}")
        server.serve_forever()


def main() -> int:
    """Dispatch the stable site-suite developer command surface."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build")
    subparsers.add_parser("check")
    subparsers.add_parser("verify")
    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("--host", default="127.0.0.1")
    preview_parser.add_argument("--port", type=int, default=8000)
    preview_parser.add_argument("--skip-build", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.command == "build":
            build()
        elif arguments.command == "check":
            check()
        elif arguments.command == "verify":
            verify()
            print("Verified composed site artifact")
        else:
            preview(arguments.host, arguments.port, skip_build=arguments.skip_build)
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
