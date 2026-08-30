#!/usr/bin/env python3
"""Materialize and execute generic and LaunchKit multi-surface consumers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from check_react_vite_fixture import available_port, run, write_aether_fixture
from holon_contract import load_json, resolve_manifest
from materialization import build_plan, render_plan, verify_target
from materialization.common import tree_digest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = Path("blueprints/site-suite/blueprint.json")
EXAMPLES = {
    "generic": Path("examples/site-suite-generic.manifest.json"),
    "launchkit": Path("examples/site-suite-optiflow.manifest.json"),
}
SNAPSHOTS = Path("tests/fixtures/site-suite/artifact-contracts.json")


def materialize(
    project: Path, name: str, manifest_path: Path, target: Path, aether: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Materialize one reviewed composition variant and prove a no-op replan."""
    profile = load_json(project / PROFILE)
    variant = profile["variants"][name]
    catalog = load_json(project / "catalog/foundation.json")
    manifest = load_json(project / manifest_path)
    resolved, errors = resolve_manifest(catalog, manifest)
    if errors or resolved is None:
        raise RuntimeError(f"{manifest_path} is invalid: {'; '.join(errors)}")
    source = project / variant["render_source"]
    overlays = [project / path for path in variant["render_overlays"]]
    plan, _ = build_plan(
        resolved,
        target,
        render_source=source,
        render_overlays=overlays,
        aether_source=aether,
    )
    if plan["summary"].get("conflict", 0):
        raise RuntimeError(f"{manifest_path} clean materialization contains a conflict")
    state = render_plan(
        plan,
        target,
        render_source=source,
        render_overlays=overlays,
        aether_source=aether,
    )
    if ownership_errors := verify_target(target):
        raise RuntimeError(f"{manifest_path} ownership is invalid: {'; '.join(ownership_errors)}")
    repeated, _ = build_plan(
        resolved,
        target,
        render_source=source,
        render_overlays=overlays,
        aether_source=aether,
    )
    if set(repeated["summary"]) != {"noop"}:
        raise RuntimeError(f"{manifest_path} repeated plan is not a no-op")
    sources = {record["source"] for record in state["managed_files"]}
    if not any(source_name.startswith("render-source:") for source_name in sources):
        raise RuntimeError(f"{name} lacks base React/Vite provenance")
    expected_indexes = range(3) if name == "launchkit" else range(2)
    for index in expected_indexes:
        if not any(source_name.startswith(f"render-overlay:{index}:") for source_name in sources):
            raise RuntimeError(f"{name} lacks overlay {index} provenance")
    return state, manifest


def install(target: Path) -> Path:
    """Install exact Node and hash-pinned Python graphs in the disposable consumer."""
    run(["pnpm", "install", "--frozen-lockfile", "--ignore-scripts"], cwd=target)
    virtual_environment = target / ".venv"
    run([sys.executable, "-m", "venv", str(virtual_environment)], cwd=target)
    python = virtual_environment / "bin/python"
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--require-hashes",
            "--requirement",
            "site-docs/requirements.lock.txt",
        ],
        cwd=target,
    )
    return python


def verify_preview(target: Path, python: Path, expected_title: str) -> None:
    """Serve the composed artifact and verify every canonical route over HTTP."""
    port = available_port()
    process = subprocess.Popen(
        [
            str(python),
            "site_suite.py",
            "preview",
            "--skip-build",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=target,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for route in ("/", "/docs/", "/architecture/", "/legal/"):
            deadline = time.monotonic() + 15
            while True:
                try:
                    with urlopen(f"http://127.0.0.1:{port}{route}", timeout=1) as response:
                        body = response.read().decode("utf-8")
                    break
                except URLError:
                    if process.poll() is not None:
                        raise RuntimeError("site-suite preview exited before becoming ready")
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f"site-suite preview did not serve {route}")
                    time.sleep(0.2)
            if "<main" not in body or (route == "/" and expected_title not in body):
                raise RuntimeError(f"site-suite preview returned incomplete content for {route}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def run_fixture(
    project: Path, name: str, manifest_path: Path, root: Path
) -> tuple[str, dict[str, Any]]:
    """Run one variant from clean materialization through deterministic preview."""
    target = root / name
    target.mkdir()
    aether = root / f"{name}-aether"
    write_aether_fixture(aether)
    state, manifest = materialize(project, name, manifest_path, target, aether)
    python = install(target)
    run([str(python), "site_suite.py", "check"], cwd=target)
    first = tree_digest(target / "dist")
    first_docs = tree_digest(target / "site-docs/build")
    shutil.rmtree(target / "dist")
    run([str(python), "site_suite.py", "build"], cwd=target)
    second = tree_digest(target / "dist")
    second_docs = tree_digest(target / "site-docs/build")
    if (first, first_docs) != (second, second_docs):
        raise RuntimeError(f"{name} site-suite output is not byte-reproducible")
    verify_preview(target, python, manifest["parameters"]["site_title"])
    snapshot = {
        "dist_tree_sha256": first,
        "zensical_tree_sha256": first_docs,
        "managed_files": len(state["managed_files"]),
        "landing": "launchkit" if name == "launchkit" else "react-vite",
    }
    print(f"PASS {name}: {snapshot['managed_files']} managed files, dist {first[:12]}")
    return name, snapshot


def integration_check(project: Path, *, write_snapshots: bool = False) -> None:
    """Prove both variants and compare exact reviewed artifact contracts."""
    observed: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="holon-site-suite-") as temporary:
        root = Path(temporary)
        for name, manifest_path in EXAMPLES.items():
            fixture_name, snapshot = run_fixture(project, name, manifest_path, root)
            observed[fixture_name] = snapshot
    snapshot_path = project / SNAPSHOTS
    if write_snapshots:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(observed, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif not snapshot_path.is_file():
        raise RuntimeError(f"site-suite artifact snapshot is missing: {SNAPSHOTS}")
    else:
        expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if observed != expected:
            raise RuntimeError("site-suite artifact contract changed without review")
    print("PASS site-suite contracts: generic and LaunchKit variants")


def main() -> int:
    """Run or refresh the complete multi-surface clean-room proof."""
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
