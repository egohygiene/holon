#!/usr/bin/env python3
"""Materialize and execute the clean-room React/Vite blueprint consumer."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from holon_contract import load_json, resolve_manifest
from materialization import build_plan, render_plan, verify_target
from materialization.common import tree_digest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = Path("examples/react-vite-site.manifest.json")
SOURCE = Path("blueprints/react-vite/files")


def sha256_bytes(content: bytes) -> str:
    """Return one byte payload's SHA-256 identity."""
    import hashlib

    return hashlib.sha256(content).hexdigest()


def write_json(path: Path, value: object) -> None:
    """Write deterministic fixture JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_aether_fixture(destination: Path, *, tag: str = "v0.1.0") -> None:
    """Create the minimum pinned Aether release accepted by materialization."""
    agent = b"---\nname: Architect\n---\n\n# Architect\n"
    agent_path = destination / "github/repository/.github/agents/architect.agent.md"
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    agent_path.write_bytes(agent)
    digest = sha256_bytes(agent)
    write_json(
        destination / "projections/manifest.v1.json",
        {
            "schema_version": "aether.projection-manifest/v1",
            "interface_version": "1.0.0",
            "providers": [
                {
                    "id": "github-copilot",
                    "status": "native",
                    "adapter": "github-agent-markdown",
                    "shares_output_with": None,
                    "unsupported_features": [],
                }
            ],
            "outputs": [
                {
                    "path": "dist/github/repository/.github/agents/architect.agent.md",
                    "sha256": digest,
                }
            ],
        },
    )
    write_json(
        destination / "release/release-manifest.v1.json",
        {"repository_release_tag": tag, "artifacts": []},
    )
    write_json(
        destination / "release/release-provenance.v1.json",
        {
            "repository_release_tag": tag,
            "commit_sha": "0123456789abcdef0123456789abcdef01234567",
            "output_files": [
                {
                    "path": "github/repository/.github/agents/architect.agent.md",
                    "sha256": digest,
                }
            ],
        },
    )


def materialize_example(project: Path, target: Path, aether: Path) -> dict[str, Any]:
    """Resolve and materialize the canonical generic-site example."""
    catalog = load_json(project / "catalog/foundation.json")
    manifest = load_json(project / EXAMPLE)
    resolved, errors = resolve_manifest(catalog, manifest)
    if errors or resolved is None:
        raise RuntimeError("example manifest is invalid: " + "; ".join(errors))
    plan, _ = build_plan(
        resolved,
        target,
        render_source=project / SOURCE,
        aether_source=aether,
    )
    if plan["summary"].get("conflict", 0):
        raise RuntimeError("clean-room materialization contains a conflict")
    state = render_plan(
        plan,
        target,
        render_source=project / SOURCE,
        aether_source=aether,
    )
    verification = verify_target(target)
    if verification:
        raise RuntimeError("materialized ownership is invalid: " + "; ".join(verification))
    repeated, _ = build_plan(
        resolved,
        target,
        render_source=project / SOURCE,
        aether_source=aether,
    )
    if set(repeated["summary"]) != {"noop"}:
        raise RuntimeError(f"repeated materialization is not a no-op: {repeated['summary']}")
    return state


class LocalReferenceParser(HTMLParser):
    """Collect local static references from built HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.references.append(value)


def verify_distribution(target: Path) -> None:
    """Verify Pages fallback, metadata, and local built references."""
    distribution = target / "dist"
    index = distribution / "index.html"
    fallback = distribution / "404.html"
    if not index.is_file() or not fallback.is_file():
        raise RuntimeError("production build is missing index.html or 404.html")
    if index.read_bytes() != fallback.read_bytes():
        raise RuntimeError("static-host fallback must be byte-identical to index.html")
    html = index.read_text(encoding="utf-8")
    if 'rel="canonical"' not in html or 'href="https://example.egohygiene.io/"' not in html:
        raise RuntimeError("production build is missing its canonical URL")
    parser = LocalReferenceParser()
    parser.feed(html)
    for reference in parser.references:
        if reference.startswith(("https://", "http://", "mailto:", "#", "data:")):
            continue
        path = reference.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if path and not (distribution / path).is_file():
            raise RuntimeError(f"production HTML references a missing local asset: {reference}")


def available_port() -> int:
    """Reserve and return one currently available local TCP port."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def verify_preview(target: Path) -> None:
    """Start the canonical preview command and verify its HTML response."""
    port = available_port()
    process = subprocess.Popen(
        [
            "pnpm",
            "preview",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--strictPort",
        ],
        cwd=target,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 15
        while True:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout is not None else ""
                raise RuntimeError(f"preview server exited unexpectedly: {output}")
            try:
                with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                    body = response.read().decode("utf-8")
                break
            except URLError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("preview server did not become ready")
                time.sleep(0.2)
        if "Example React/Vite Site" not in body:
            raise RuntimeError("preview response does not contain generated site metadata")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def run(command: list[str], *, cwd: Path) -> None:
    """Run one clean-room validation command without a shell."""
    print("+ " + " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def verify_cycle_guard(target: Path) -> None:
    """Prove the generated lint command rejects a real circular import."""
    first = target / "src/cycle-a.ts"
    second = target / "src/cycle-b.ts"
    first.write_text('import "./cycle-b";\n', encoding="utf-8")
    second.write_text('import "./cycle-a";\n', encoding="utf-8")
    try:
        result = subprocess.run(
            ["pnpm", "lint"],
            cwd=target,
            check=False,
            capture_output=True,
            text=True,
        )
        diagnostics = result.stdout + result.stderr
        if result.returncode == 0 or "no-circular" not in diagnostics:
            raise RuntimeError("generated lint did not reject a circular dependency")
    finally:
        first.unlink(missing_ok=True)
        second.unlink(missing_ok=True)


def integration_check(project: Path) -> None:
    """Run the complete clean materialization, build, and preview proof."""
    with tempfile.TemporaryDirectory(prefix="holon-react-vite-") as temporary:
        root = Path(temporary)
        target = root / "consumer"
        target.mkdir()
        aether = root / "aether-dist"
        write_aether_fixture(aether)
        state = materialize_example(project, target, aether)
        run(["pnpm", "install", "--frozen-lockfile", "--ignore-scripts"], cwd=target)
        run(["pnpm", "check"], cwd=target)
        verify_cycle_guard(target)
        verify_distribution(target)
        first_digest = tree_digest(target / "dist")
        shutil.rmtree(target / "dist")
        run(["pnpm", "build"], cwd=target)
        verify_distribution(target)
        second_digest = tree_digest(target / "dist")
        if first_digest != second_digest:
            raise RuntimeError("two production builds are not byte-identical")
        verify_preview(target)
        print(
            "PASS clean React/Vite consumer: "
            f"{len(state['managed_files'])} managed files, dist {first_digest[:12]}"
        )


def main() -> int:
    """Run the clean-room integration check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT)
    arguments = parser.parse_args()
    integration_check(arguments.project.expanduser().resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
