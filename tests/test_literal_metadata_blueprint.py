"""Consumer-content regressions for encoded metadata and exact static insertion."""

from __future__ import annotations

import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from holon_contract import load_json, resolve_manifest  # noqa: E402
from materialization import build_plan, render_plan, verify_target  # noqa: E402
from materialization.common import MaterializationError, render_source_bytes  # noqa: E402


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.metadata: dict[str, str | None] = {}
        self.canonical: str | None = None
        self.text: dict[str, list[str]] = {"title": [], "h1": [], "p": []}
        self.current: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        attributes = dict(attrs)
        if tag == "meta":
            name = attributes.get("name") or attributes.get("property")
            if name:
                self.metadata[name] = attributes.get("content")
        if tag == "link" and attributes.get("rel") == "canonical":
            self.canonical = attributes.get("href")
        if tag in self.text:
            self.current = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == self.current:
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.current:
            self.text[self.current].append(data)


class BlueprintLiteralContentTests(unittest.TestCase):
    def test_generated_metadata_round_trips_without_interpreting_consumer_copy(self) -> None:
        title = 'A "quoted" <img src=x> title & apostrophe\' \\ café 雪 $& $` $\' {{parameter.site_description}}'
        description = 'Literal </p><script>not markup</script> & "quotes" \\ ✓'
        canonical = 'https://example.invalid/?label="quotes"&other=<value>'
        for name, overlays in (
            ("react-vite-site", []),
            ("launchkit-optiflow", [ROOT / "blueprints/launchkit/files"]),
        ):
            with self.subTest(profile=name), tempfile.TemporaryDirectory() as directory:
                manifest = load_json(ROOT / f"examples/{name}.manifest.json")
                manifest["parameters"].update({
                    "site_title": title, "site_description": description,
                    "canonical_url": canonical,
                })
                resolved, errors = resolve_manifest(load_json(ROOT / "catalog/foundation.json"), manifest)
                self.assertEqual(errors, [])
                assert resolved is not None
                resolved = copy.deepcopy(resolved)
                resolved["capabilities"].remove("aether-agents")
                target = Path(directory) / "consumer"
                target.mkdir()
                inputs = {"render_source": ROOT / "blueprints/react-vite/files", "render_overlays": overlays}
                plan, _ = build_plan(resolved, target, **inputs)
                render_plan(plan, target, **inputs)
                self.assertEqual(verify_target(target), [])
                parser = MetadataParser()
                parser.feed((target / "index.html").read_text(encoding="utf-8"))
                self.assertEqual("".join(parser.text["title"]), title)
                self.assertEqual("".join(parser.text["h1"]), title)
                self.assertEqual(parser.metadata["description"], description)
                self.assertEqual(parser.canonical, canonical)
                self.assertNotIn("img", parser.tags)
                self.assertEqual(parser.tags.count("script"), 1)
                if overlays:
                    self.assertEqual(parser.metadata["og:title"], title)
                webmanifest = json.loads((target / "public/site.webmanifest").read_bytes())
                self.assertEqual(webmanifest["name"], title)
                self.assertEqual(webmanifest["description"], description)
                if not overlays:
                    provenance = json.loads((target / "holon.blueprint.json").read_bytes())
                    self.assertEqual(provenance["canonical_url"], canonical)
                repeated, _ = build_plan(resolved, target, **inputs)
                self.assertTrue(all(operation["action"] in {"noop", "preserve"} for operation in repeated["operations"]))

    def test_explicit_html_tokens_require_strings_and_source_tokens_still_fail_closed(self) -> None:
        resolved = {"repository": "owner/repository", "repository_class": "product",
                    "security_level": "hardened", "parameters": {"value": ["structured"]}}
        for source in (b"{{parameter_html.value}}", b"{{parameter_json.missing}}"):
            with self.subTest(source=source), self.assertRaises(MaterializationError):
                render_source_bytes(source, resolved, "source.html")

    @unittest.skipUnless(shutil.which("node"), "Node is needed for packaged static-assembly qualification")
    def test_packaged_static_assembly_preserves_every_dollar_replacement_token(self) -> None:
        markup = '<main><p>Literal $& $` $\' $$ \\ 雪</p></main>'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "dist").mkdir()
            (root / ".static-render").mkdir()
            (root / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
            script = root / "scripts/render-static.mjs"
            shutil.copyfile(ROOT / "blueprints/launchkit/files/scripts/render-static.mjs", script)
            (root / ".static-render/static-entry.js").write_text(
                f"export function render() {{ return {json.dumps(markup, ensure_ascii=False)}; }}\n",
                encoding="utf-8",
            )
            prefix, suffix = "<html><body>", "</body></html>"
            (root / "dist/index.html").write_text(
                prefix + '<div id="root"><noscript>fallback</noscript></div>' + suffix,
                encoding="utf-8",
            )
            result = subprocess.run(["node", str(script)], cwd=root, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = (root / "dist/index.html").read_text(encoding="utf-8")
            self.assertEqual(output, prefix + '<div id="root">' + markup + "</div>" + suffix)
            self.assertEqual(output.count('id="root"'), 1)
            self.assertNotIn("fallback", output)
            self.assertFalse((root / ".static-render").exists())
