#!/usr/bin/env python3
"""Bounded synthetic proofs for Holon blueprint audit; never edits the source tree."""

from __future__ import annotations

import argparse
import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    arguments = parser.parse_args()
    project = arguments.project.resolve()
    sys.path.insert(0, str(project / "tools"))
    import architecture_decision_blueprint as adr
    import repository_presentation_blueprint as presentation
    import react_vite_blueprint as react
    import site_suite_blueprint as suite
    from check_react_vite_fixture import write_aether_fixture
    from holon_contract import load_json, resolve_manifest
    from materialization import build_plan, render_plan, verify_target
    from materialization.common import render_source_bytes

    output = {"source_revision": "a7734dba83305276b12932fcd4ce348044d9a2e9", "results": {}}
    results = output["results"]
    blueprint = load_json(project / "blueprints/repository-presentation/blueprint.json")
    fixtures = load_json(project / "examples/repository-presentation-fixtures.json")
    fixture = next(item for item in fixtures["fixtures"] if item["name"] == "mantle")
    base_source = fixture["source"]

    def cli(root: Path, script: Path, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(script), *arguments], cwd=root,
                              text=True, capture_output=True, check=False)

    with tempfile.TemporaryDirectory(prefix="holon-blueprints-audit-") as temporary:
        temporary_root = Path(temporary)

        # A real HTTPS destination is rejected; the incomplete scheme is accepted.
        url_results = {}
        for label, value in [("real_https", "https://github.com/egohygiene/holon"),
                             ("incomplete_scheme", "https://")]:
            root = temporary_root / ("url-" + label)
            root.mkdir()
            source = copy.deepcopy(base_source)
            source["badges"][0]["destination"] = value
            (root / "source.json").write_text(json.dumps(source), encoding="utf-8")
            (root / "README.md").write_text(fixture["readme"], encoding="utf-8")
            completed = cli(root, project / "tools/repository_presentation_blueprint.py",
                            "preview", "--source", "source.json", "--readme", "README.md",
                            "--state", "state.json", "--plan", "plan.json")
            plan = json.loads((root / "plan.json").read_text())
            url_results[label] = {"destination": value, "exit_code": completed.returncode,
                                  "action": plan["action"],
                                  "error_codes": [item["code"] for item in plan["diagnostics"]
                                                  if item["severity"] == "error"],
                                  "literal_href_rendered": f'href="{value}"' in plan["proposedReadme"]}
        results["presentation_https_destination"] = url_results

        # A no-op advances the rollback snapshot; an upgrade rollback loses trusted state.
        lifecycle = {}
        for scenario in ("noop", "upgrade"):
            root = temporary_root / ("lifecycle-" + scenario)
            root.mkdir()
            readme_path, state_path = root / "README.md", root / "state.json"
            original = fixture["readme"]
            readme_path.write_text(original, encoding="utf-8")
            initial = presentation.build_plan(base_source, original, None, blueprint)
            presentation.apply_plan(initial, base_source, readme_path, state_path)
            before_state = state_path.read_bytes()
            source = copy.deepcopy(base_source)
            if scenario == "upgrade":
                source["slots"]["purpose"] = "A reviewed revised Mantle purpose."
            next_plan = presentation.build_plan(source, readme_path.read_text(),
                                                json.loads(before_state), blueprint)
            presentation.apply_plan(next_plan, source, readme_path, state_path)
            after_state = state_path.read_bytes()
            presentation.rollback(readme_path, state_path)
            restored = readme_path.read_text()
            resumed = presentation.build_plan(base_source, restored, None, blueprint)
            lifecycle[scenario] = {"action": next_plan["action"],
                                   "state_changed": before_state != after_state,
                                   "state_exists_after_rollback": state_path.exists(),
                                   "managed_region_remains": blueprint["markers"]["begin"] in restored,
                                   "restored_original_authored_readme": restored == original,
                                   "restored_pre_upgrade_readme": restored == initial["proposedReadme"],
                                   "next_preview_action": resumed["action"],
                                   "next_preview_error_codes": [d["code"] for d in resumed["diagnostics"]
                                                                if d["severity"] == "error"]}
        results["presentation_state_recovery"] = lifecycle

        # The CLI normalizes authored CRLF even outside its managed region.
        root = temporary_root / "line-endings"
        root.mkdir()
        original_bytes = b"# Repository-authored\r\n\r\nKeep these exact bytes.\r\n"
        (root / "README.md").write_bytes(original_bytes)
        (root / "source.json").write_text(json.dumps(base_source), encoding="utf-8")
        preview = cli(root, project / "tools/repository_presentation_blueprint.py", "preview",
                      "--source", "source.json", "--readme", "README.md", "--state", "state.json",
                      "--plan", "plan.json")
        applied = cli(root, project / "tools/repository_presentation_blueprint.py", "apply",
                      "--source", "source.json", "--readme", "README.md", "--state", "state.json",
                      "--plan", "plan.json")
        materialized = (root / "README.md").read_bytes()
        rolled = cli(root, project / "tools/repository_presentation_blueprint.py", "rollback",
                     "--readme", "README.md", "--state", "state.json")
        restored = (root / "README.md").read_bytes()
        results["presentation_authored_byte_preservation"] = {
            "preview_exit": preview.returncode, "apply_exit": applied.returncode,
            "rollback_exit": rolled.returncode,
            "authored_suffix_preserved": materialized.endswith(original_bytes),
            "authored_suffix_changed_to_lf": materialized.endswith(original_bytes.replace(b"\r\n", b"\n")),
            "rollback_restores_original_bytes": restored == original_bytes,
            "input_sha256": sha(original_bytes), "rollback_sha256": sha(restored)}

        # A pre-existing predictable temporary symlink is not among the plan's
        # checked inputs, so apply follows it and writes outside the README path.
        root = temporary_root / "presentation-symlink"
        target = root / "consumer"
        target.mkdir(parents=True)
        victim = root / "outside-consumer.txt"
        victim.write_text("Synthetic outside sentinel.\n", encoding="utf-8")
        original_victim = victim.read_bytes()
        (target / "README.md").write_text(fixture["readme"], encoding="utf-8")
        (target / "source.json").write_text(json.dumps(base_source), encoding="utf-8")
        preview = cli(target, project / "tools/repository_presentation_blueprint.py", "preview",
                      "--source", "source.json", "--readme", "README.md", "--state", "state.json",
                      "--plan", "plan.json")
        (target / "README.md.holon-tmp").symlink_to(victim)
        applied = cli(target, project / "tools/repository_presentation_blueprint.py", "apply",
                      "--source", "source.json", "--readme", "README.md", "--state", "state.json",
                      "--plan", "plan.json")
        results["presentation_temporary_symlink_write"] = {
            "preview_exit": preview.returncode, "apply_exit": applied.returncode,
            "outside_sentinel_changed": victim.read_bytes() != original_victim,
            "outside_sentinel_contains_generated_region": blueprint["markers"]["begin"] in victim.read_text(),
            "readme_became_symlink": (target / "README.md").is_symlink(),
            "state_written": (target / "state.json").is_file(),
            "limit": "Every file and symlink used here is synthetic and contained in one disposable temporary parent."}

        # Full generic materialization accepts ordinary quote-bearing metadata,
        # yet emits invalid JSON and interprets literal angle brackets as markup.
        catalog = load_json(project / "catalog/foundation.json")
        manifest = load_json(project / "examples/react-vite-site.manifest.json")
        manifest["parameters"]["site_title"] = 'A "quoted" product'
        manifest["parameters"]["site_description"] = 'Read "all" options & keep <details> literal.'
        resolved, errors = resolve_manifest(catalog, manifest)
        assert resolved is not None
        root = temporary_root / "quoted-metadata"
        target, aether = root / "consumer", root / "aether"
        target.mkdir(parents=True)
        write_aether_fixture(aether)
        plan, _ = build_plan(resolved, target, aether_source=aether,
                             render_source=project / "blueprints/react-vite/files")
        render_plan(plan, target, aether_source=aether,
                    render_source=project / "blueprints/react-vite/files")
        webmanifest = (target / "public/site.webmanifest").read_text()
        try:
            json.loads(webmanifest)
            json_error = None
        except json.JSONDecodeError as error:
            json_error = {"kind": type(error).__name__, "line": error.lineno,
                          "column": error.colno, "message": error.msg}

        class MetadataParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.description = None
                self.details_tags = 0

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if tag == "meta" and attributes.get("name") == "description":
                    self.description = attributes.get("content")
                self.details_tags += int(tag == "details")

        parsed = MetadataParser()
        parsed.feed((target / "index.html").read_text())
        results["react_metadata_context_escaping"] = {
            "manifest_resolution_errors": errors,
            "blueprint_parameter_errors": react.validate_parameters(resolved["parameters"]),
            "materialization_conflicts": plan["summary"].get("conflict", 0),
            "ownership_verification_errors": verify_target(target),
            "webmanifest_json_error": json_error,
            "input_description": manifest["parameters"]["site_description"],
            "parsed_html_description": parsed.description,
            "literal_details_became_html_elements": parsed.details_tags,
            "limit": "No browser exploit or external consumer execution is claimed."}

        # Exercise the actual packaged SSR replacement script with a bounded
        # serializer fixture. This isolates String.replace semantics, not React.
        root = temporary_root / "ssr-replacement"
        for directory in ("scripts", "dist", ".static-render"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        (root / "package.json").write_text('{"type":"module"}', encoding="utf-8")
        source_html = '<html><body><div id="root">FALLBACK</div></body></html>'
        rendered = '<main><h1>Price $&amp; tax</h1></main>'
        (root / "dist/index.html").write_text(source_html, encoding="utf-8")
        (root / ".static-render/static-entry.js").write_text(
            "export function render() { return " + json.dumps(rendered) + "; }\n", encoding="utf-8")
        shutil.copyfile(project / "blueprints/launchkit/files/scripts/render-static.mjs",
                        root / "scripts/render-static.mjs")
        native = subprocess.run(["node", "scripts/render-static.mjs"], cwd=root,
                                text=True, capture_output=True, check=False)
        observed_html = (root / "dist/index.html").read_text()
        expected_html = source_html.replace('<div id="root">FALLBACK</div>',
                                            '<div id="root">' + rendered + '</div>')
        results["launchkit_ssr_replacement_tokens"] = {
            "node_exit": native.returncode, "serializer_fixture_output": rendered,
            "literal_ssr_preserved": observed_html == expected_html,
            "unexpected_fallback_copies": observed_html.count("FALLBACK"),
            "nested_root_elements": observed_html.count('id="root"'),
            "limit": "The real packaged post-render script ran; its imported render function is a synthetic serializer fixture, not an executed React build."}

        # Both validators accept index as an ordinary page slug, then the real
        # source renderer overwrites the generated documentation/legal hubs.
        root = temporary_root / "reserved-routes"
        root.mkdir()
        manifest = load_json(project / "examples/site-suite-generic.manifest.json")
        content = manifest["parameters"]["site_suite_content"]
        content["documentation"]["pages"][0]["slug"] = "index"
        content["legal"]["pages"][0]["slug"] = "index"
        resolved, resolution_errors = resolve_manifest(catalog, manifest)
        assert resolved is not None
        source_root = project / "blueprints/zensical/files"
        for path in source_root.rglob("*"):
            if path.is_file():
                relative = path.relative_to(source_root)
                target_path = root / relative
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(render_source_bytes(path.read_bytes(), resolved, str(relative)))
        validated = cli(root, root / "site_docs.py", "validate")
        generated = subprocess.run([sys.executable, "-c", "import site_docs; content, settings = site_docs.validate_inputs(); site_docs.render_sources(content, settings)"],
                                   cwd=root, text=True, capture_output=True, check=False)
        observations = {}
        for surface, key in [("docs", "documentation"), ("legal", "legal")]:
            index = (root / "site-docs/.generated" / surface / "index.md").read_text()
            observations[surface] = {
                "expected_hub_heading": content[key]["title"],
                "observed_first_line": index.splitlines()[0],
                "page_heading": content[key]["pages"][0]["title"],
                "hub_introduction_preserved": content[key]["introduction"] in index}
        results["zensical_reserved_index_collision"] = {
            "manifest_resolution_errors": resolution_errors,
            "reference_validator_errors": suite.validate_site_content(content, "synthetic"),
            "consumer_validation_exit": validated.returncode,
            "consumer_source_generation_exit": generated.returncode,
            "surfaces": observations,
            "limit": "Source generation was executed; a new Zensical build is not claimed by this counterexample."}

        # This narrow provenance mismatch belongs to the already-open ADR pin
        # consistency issue rather than a new scaffold implementation project.
        profile = load_json(project / "blueprints/architecture-decisions/blueprint.json")
        index = adr.render_index("egohygiene/holon", []).decode()
        results["adr_existing_issue_63_provenance_note"] = {
            "profile_version": profile["version"],
            "profile_validation_errors": adr.validate_blueprint(project),
            "generated_by_comment": next(line for line in index.splitlines() if "Generated by" in line),
            "policy_version": adr.POLICY_VERSION, "policy_revision": adr.POLICY_REVISION,
            "coverage": "existing Holon issue #63; no closure or native acceptance is claimed"}

    output["runtime"] = {"python": sys.version.split()[0],
                          "node": subprocess.run(["node", "--version"], text=True, capture_output=True, check=True).stdout.strip()}
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
