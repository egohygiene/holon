#!/usr/bin/env python3
"""Build real literal-content consumers; optionally qualify their browser hydration.

The browser mode uses an already installed Python Playwright and Chromium. Neither
is added to the generated application's dependencies or downloaded by this tool.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Iterator
from urllib.error import URLError
from urllib.request import urlopen

from check_react_vite_fixture import available_port, run, write_aether_fixture
from holon_contract import load_json, resolve_manifest
from launchkit_blueprint import validate_content
from materialization import build_plan, render_plan, verify_target
from materialization.common import tree_digest
from react_vite_blueprint import validate_parameters

ROOT = Path(__file__).resolve().parents[1]
TITLE = '"Q" O\'Reilly & <x-lit>x</x-lit> \\ café 雪 $& $` $\' $$'
DESCRIPTION = 'Literal "copy" </p><x-lit>x</x-lit> & \\ café 雪 $& $` $\' $$'
CANONICAL = 'https://example.invalid/?label="quotes"&other=<value>'


class MetadataParser(HTMLParser):
    """Inspect emitted HTML through its parser semantics rather than raw escaping."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.metadata: dict[str, str | None] = {}
        self.canonical: str | None = None
        self.text: dict[str, list[str]] = {"title": [], "h1": []}
        self.current: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        attributes = dict(attrs)
        if tag == "meta" and (name := attributes.get("name") or attributes.get("property")):
            self.metadata[name] = attributes.get("content")
        if tag == "link" and attributes.get("rel") == "canonical":
            self.canonical = attributes.get("href")
        if tag in self.text:
            self.current = tag

    def handle_endtag(self, tag: str) -> None:
        if self.current == tag:
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.current:
            self.text[self.current].append(data)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def materialize(project: Path, root: Path, kind: str) -> tuple[Path, dict[str, Any]]:
    example = "react-vite-site" if kind == "generic" else "launchkit-optiflow"
    manifest = load_json(project / f"examples/{example}.manifest.json")
    parameters = manifest["parameters"]
    parameters.update(site_title=TITLE, site_description=DESCRIPTION, canonical_url=CANONICAL)
    base_names = {"canonical_url", "identity_stylesheet", "package_name", "site_base_path",
                  "site_description", "site_title"}
    require(not validate_parameters({key: parameters[key] for key in base_names}), "invalid metadata fixture")
    if kind == "launchkit":
        parameters["identity_favicon_url"] = "/literal-icon.svg"
        parameters["identity_social_image_url"] = "/literal-icon.svg"
        content = parameters["launchkit_content"]
        content["identity"]["wordmark"] = TITLE
        content["hero"].update(title=TITLE, description=DESCRIPTION)
        require(not validate_content(content, "literal-fixture"), "invalid LaunchKit fixture")
    resolved, errors = resolve_manifest(load_json(project / "catalog/foundation.json"), manifest)
    require(not errors and resolved is not None, f"invalid foundation fixture: {errors}")
    target = root / kind
    target.mkdir()
    aether = root / f"{kind}-aether"
    write_aether_fixture(aether)
    inputs = {"render_source": project / "blueprints/react-vite/files", "aether_source": aether}
    if kind == "launchkit":
        inputs["render_overlays"] = [project / "blueprints/launchkit/files"]
    plan, _ = build_plan(resolved, target, **inputs)
    require(not plan["summary"].get("conflict"), "clean materialization conflict")
    state = render_plan(plan, target, **inputs)
    require(not verify_target(target), "materialized ownership is invalid")
    repeated, _ = build_plan(resolved, target, **inputs)
    require(set(repeated["summary"]) == {"noop"}, "repeated materialization is not a no-op")
    # A consumer-owned local identity fixture prevents unrelated external requests.
    if kind == "launchkit":
        (target / "public/literal-icon.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><path d="M0 0h1v1H0z"/></svg>\n',
            encoding="utf-8",
        )
    (root / f"{kind}.manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return target, {"managed_files": len(state["managed_files"]), "materialization_noop": True,
                    "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()}


def verify_distribution(target: Path, kind: str) -> dict[str, Any]:
    distribution = target / "dist"
    raw = (distribution / "index.html").read_bytes()
    require(raw == (distribution / "404.html").read_bytes(), "fallback bytes differ")
    metadata = MetadataParser()
    metadata.feed(raw.decode())
    require("".join(metadata.text["title"]) == TITLE, "title did not round-trip")
    require(metadata.metadata["description"] == DESCRIPTION, "description did not round-trip")
    require(metadata.canonical == CANONICAL, "canonical attribute did not round-trip")
    require("x-lit" not in metadata.tags, "consumer text became HTML structure")
    webmanifest = json.loads((distribution / "site.webmanifest").read_bytes())
    require(webmanifest["name"] == TITLE and webmanifest["description"] == DESCRIPTION,
            "web manifest did not round-trip")
    if kind == "launchkit":
        require(metadata.metadata["og:title"] == TITLE, "OpenGraph title did not round-trip")
        require(metadata.tags.count("noscript") == 0, "static assembly duplicated the fallback")
        require(metadata.tags.count("main") == 1, "static assembly duplicated the main landmark")
        require("".join(metadata.text["h1"]) == TITLE, "actual React serializer lost literal tokens")
        require(raw.count(b'id="root"') == 1, "static assembly duplicated the root")
    return {"dist_tree_sha256": tree_digest(distribution), "metadata_and_manifest_exact": True,
            "static_root_and_literal_tokens_exact": kind == "launchkit"}


@contextmanager
def preview(target: Path) -> Iterator[str]:
    port = available_port()
    with (target / "preview.log").open("w") as log:
        process = subprocess.Popen(["pnpm", "preview", "--host", "127.0.0.1", "--port", str(port),
                                    "--strictPort"], cwd=target, stdout=log, stderr=subprocess.STDOUT)
        try:
            url = f"http://127.0.0.1:{port}/"
            deadline = time.monotonic() + 20
            while True:
                require(process.poll() is None, "preview exited before becoming ready")
                try:
                    with urlopen(url, timeout=1) as response:
                        require(response.status == 200, "preview HTTP status is not 200")
                    break
                except URLError:
                    require(time.monotonic() < deadline, "preview did not become ready")
                    time.sleep(0.1)
            yield url
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def browser_check(target: Path, kind: str, chromium: str) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    with preview(target) as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=chromium, headless=True)
        errors: list[str] = []
        console_errors: list[dict[str, Any]] = []
        context = browser.new_context()
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: console_errors.append(
            {"text": message.text, "url": message.location.get("url", "")}
        ) if message.type == "error" else None)
        page.goto(url, wait_until="networkidle")
        require(page.locator("#root h1").text_content() == TITLE, "actual React DOM lost title")
        require(page.locator("meta[name=description]").get_attribute("content") == DESCRIPTION,
                "browser metadata lost description")
        require(page.locator("link[rel=canonical]").get_attribute("href") == CANONICAL,
                "browser canonical attribute lost data")
        require(page.locator("#root").count() == 1 and page.locator("x-lit").count() == 0,
                "browser DOM duplicated root or interpreted literal markup")
        require(page.evaluate("() => Object.keys(document.getElementById('root')).some(key => key.startsWith('__reactContainer$'))"),
                "the real React client did not attach to the root")
        page.reload(wait_until="networkidle")
        require(page.locator("#root h1").text_content() == TITLE, "reload lost literal title")
        require(not errors, f"browser runtime errors: {errors}")
        require(not console_errors, f"browser console errors: {console_errors}")
        no_js = browser.new_context(java_script_enabled=False)
        static_page = no_js.new_page()
        static_page.goto(url, wait_until="networkidle")
        require(static_page.locator("#root h1").text_content() == TITLE, "no-JS content lost literal title")
        require(static_page.locator("#root main").count() == 1, "no-JS main is duplicated")
        result = {"browser": browser.version, "javascript_dom": "passed", "reload": "passed",
                  "no_javascript_content": "passed", "react_attached": True,
                  "hydration": "passed" if kind == "launchkit" else "not-applicable-client-rendered",
                  "request_interception": False, "certificate_bypass": False,
                  "page_errors": errors, "console_errors": console_errors,
                  "transport": "actual-local-pnpm-preview-http"}
        context.close()
        no_js.close()
        browser.close()
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--work-directory", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    args = parser.parse_args()
    project = args.project.resolve()
    root = args.work_directory.resolve()
    require(not root.exists(), "work directory must be new; existing consumers are never overwritten")
    root.mkdir(parents=True)
    report: dict[str, Any] = {"schema": "holon.literal-consumer-qualification/v1alpha1",
                            "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project, text=True).strip(),
                            "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=project)),
                            "started_at": datetime.now(timezone.utc).isoformat(), "consumers": {}}
    for kind in ("generic", "launchkit"):
        target, result = materialize(project, root, kind)
        run(["pnpm", "install", "--frozen-lockfile", "--ignore-scripts"], cwd=target)
        run(["pnpm", "check"], cwd=target)
        first = verify_distribution(target, kind)
        shutil.rmtree(target / "dist")
        run(["pnpm", "build"], cwd=target)
        require(first == verify_distribution(target, kind), "actual builds are not byte-identical")
        result.update(first, byte_identical_builds=2)
        if args.browser:
            result["browser"] = browser_check(target, kind, args.chromium)
        else:
            result["browser"] = {"status": "not-run"}
        report["consumers"][kind] = result
    report.update(outcome="passed", finished_at=datetime.now(timezone.utc).isoformat())
    args.receipt.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PASS real literal metadata consumers: generic and LaunchKit")


if __name__ == "__main__":
    main()
