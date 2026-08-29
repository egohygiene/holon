#!/usr/bin/env python3
"""Materialize and execute both clean-room LaunchKit pilot consumers."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from check_react_vite_fixture import run, verify_preview, write_aether_fixture
from holon_contract import load_json, resolve_manifest
from materialization import build_plan, render_plan, verify_target
from materialization.common import tree_digest

ROOT = Path(__file__).resolve().parents[1]
BASE_SOURCE = Path("blueprints/react-vite/files")
OVERLAY = Path("blueprints/launchkit/files")
EXAMPLES = (
    Path("examples/launchkit-optiflow.manifest.json"),
    Path("examples/launchkit-mantle.manifest.json"),
)
SNAPSHOTS = Path("tests/fixtures/launchkit/visual-contracts.json")
PLACEHOLDERS = (
    "lorem ipsum",
    "request a demo",
    "sign up",
    "logo template",
    "placeholder-",
    "mintlify.com",
    "substack.com",
    "wellfound.com",
)


class ReferenceParser(HTMLParser):
    """Collect IDs and local links from one production HTML page."""

    def __init__(self) -> None:
        super().__init__()
        self.identifiers: set[str] = set()
        self.references: list[str] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "id" and value:
                self.identifiers.add(value)
            if name in {"href", "src"} and value:
                self.references.append(value)


def sha256(content: bytes) -> str:
    """Return one byte payload's lowercase SHA-256 identity."""
    return hashlib.sha256(content).hexdigest()


def materialize(project: Path, manifest_path: Path, target: Path, aether: Path) -> dict[str, Any]:
    """Resolve and materialize one composed LaunchKit fixture."""
    catalog = load_json(project / "catalog/foundation.json")
    manifest = load_json(project / manifest_path)
    resolved, errors = resolve_manifest(catalog, manifest)
    if errors or resolved is None:
        raise RuntimeError(f"{manifest_path} is invalid: {'; '.join(errors)}")
    plan, _ = build_plan(
        resolved,
        target,
        render_source=project / BASE_SOURCE,
        render_overlays=[project / OVERLAY],
        aether_source=aether,
    )
    if plan["summary"].get("conflict", 0):
        raise RuntimeError(f"{manifest_path} clean materialization contains a conflict")
    state = render_plan(
        plan,
        target,
        render_source=project / BASE_SOURCE,
        render_overlays=[project / OVERLAY],
        aether_source=aether,
    )
    if errors := verify_target(target):
        raise RuntimeError(f"{manifest_path} ownership is invalid: {'; '.join(errors)}")
    repeated, _ = build_plan(
        resolved,
        target,
        render_source=project / BASE_SOURCE,
        render_overlays=[project / OVERLAY],
        aether_source=aether,
    )
    if set(repeated["summary"]) != {"noop"}:
        raise RuntimeError(f"{manifest_path} repeated plan is not a no-op: {repeated['summary']}")
    sources = {record["source"] for record in state["managed_files"]}
    if not any(source.startswith("render-source:") for source in sources):
        raise RuntimeError("composed fixture contains no React/Vite base provenance")
    if not any(source.startswith("render-overlay:0:") for source in sources):
        raise RuntimeError("composed fixture contains no LaunchKit overlay provenance")
    return state


def normalized_html(html: str) -> bytes:
    """Remove content-derived Vite asset hashes from a visual contract snapshot."""
    normalized = re.sub(r"assets/index-[A-Za-z0-9_-]+\.(css|js)", r"assets/index.<\1>", html)
    return normalized.encode("utf-8")


def verify_distribution(target: Path, manifest: dict[str, Any]) -> dict[str, str]:
    """Verify static content, metadata, links, fallbacks, and visual-contract inputs."""
    distribution = target / "dist"
    index = distribution / "index.html"
    fallback = distribution / "404.html"
    if not index.is_file() or index.read_bytes() != fallback.read_bytes():
        raise RuntimeError("LaunchKit index and static-host fallback must be byte-identical")
    html = index.read_text(encoding="utf-8")
    parameters = manifest["parameters"]
    required = (
        'data-launchkit-static="true"',
        f'href="{parameters["canonical_url"]}"',
        f'content="{parameters["identity_social_image_url"]}"',
        f'href="{parameters["identity_favicon_url"]}"',
        "<header",
        "<main",
        "<footer",
        'id="features"',
    )
    for marker in required:
        if marker not in html:
            raise RuntimeError(f"production HTML is missing {marker}")
    lowered = html.casefold()
    for placeholder in PLACEHOLDERS:
        if placeholder in lowered:
            raise RuntimeError(f"production HTML contains upstream placeholder copy: {placeholder}")

    parser = ReferenceParser()
    parser.feed(html)
    for reference in parser.references:
        if reference.startswith("#"):
            if reference[1:] not in parser.identifiers:
                raise RuntimeError(f"production HTML has a broken fragment link: {reference}")
            continue
        if reference.startswith(("https://", "mailto:", "data:")):
            continue
        path = reference.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if path and not (distribution / path).is_file():
            raise RuntimeError(f"production HTML references a missing local asset: {reference}")

    css = b"".join(path.read_bytes() for path in sorted((distribution / "assets").glob("*.css")))
    if not css:
        raise RuntimeError("production build emitted no stylesheet")
    return {
        "semantic_html_sha256": sha256(normalized_html(html)),
        "stylesheet_sha256": sha256(css),
        "dist_tree_sha256": tree_digest(distribution),
    }


def run_fixture(project: Path, manifest_path: Path, root: Path) -> tuple[str, dict[str, str]]:
    """Execute one pilot from clean materialization through live preview."""
    manifest = load_json(project / manifest_path)
    name = manifest["repository"].split("/", 1)[-1]
    target = root / name
    target.mkdir()
    aether = root / f"{name}-aether"
    write_aether_fixture(aether)
    state = materialize(project, manifest_path, target, aether)
    run(["pnpm", "install", "--frozen-lockfile", "--ignore-scripts"], cwd=target)
    run(["pnpm", "check"], cwd=target)
    first = verify_distribution(target, manifest)
    shutil.rmtree(target / "dist")
    run(["pnpm", "build"], cwd=target)
    second = verify_distribution(target, manifest)
    if first != second:
        raise RuntimeError(f"{name} production output is not byte-reproducible")
    verify_preview(target, manifest["parameters"]["site_title"])
    print(
        f"PASS {name}: {len(state['managed_files'])} managed files, "
        f"dist {first['dist_tree_sha256'][:12]}"
    )
    return name, first


def integration_check(project: Path, *, write_snapshots: bool = False) -> None:
    """Run both pilots and compare their stable visual contracts."""
    observed: dict[str, dict[str, str]] = {}
    with tempfile.TemporaryDirectory(prefix="holon-launchkit-") as temporary:
        root = Path(temporary)
        for manifest_path in EXAMPLES:
            name, snapshot = run_fixture(project, manifest_path, root)
            observed[name] = snapshot
    snapshot_path = project / SNAPSHOTS
    if write_snapshots:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(observed, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif not snapshot_path.is_file():
        raise RuntimeError(f"LaunchKit visual snapshot is missing: {SNAPSHOTS}")
    else:
        expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if observed != expected:
            raise RuntimeError("LaunchKit semantic HTML/CSS visual contract changed")
    print(f"PASS LaunchKit visual contracts: {len(observed)} materially different pilots")


def main() -> int:
    """Run or refresh the LaunchKit clean-room pilot proof."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--write-snapshots", action="store_true")
    arguments = parser.parse_args()
    integration_check(
        arguments.project.expanduser().resolve(), write_snapshots=arguments.write_snapshots
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
