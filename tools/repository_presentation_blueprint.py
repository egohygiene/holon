#!/usr/bin/env python3
"""Render and safely materialize Holon's repository-presentation README region."""

from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_PATH = ROOT / "blueprints/repository-presentation/blueprint.json"
FIXTURES_PATH = ROOT / "examples/repository-presentation-fixtures.json"
SOURCE_SCHEMA = "holon.repository-presentation-source/v1"
PLAN_SCHEMA = "holon.repository-presentation-plan/v1"
STATE_SCHEMA = "holon.repository-presentation-state/v1"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SAFE_DESTINATION_RE = re.compile(r"^(?:https://|(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._#?-]+)$")
SLOT_TITLES = {
    "maturity_status": "Status",
    "quick_start": "Quick start",
    "architecture": "Architecture",
    "documentation": "Documentation",
    "development": "Development",
    "validation": "Validation",
    "contributing": "Contributing",
    "security": "Security",
    "support": "Support",
    "license": "License",
}
ORDERED_SECTIONS = (
    "quick_start",
    "architecture",
    "documentation",
    "development",
    "validation",
    "contributing",
    "security",
    "support",
    "license",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def diagnostic(code: str, severity: str, message: str, location: str = "") -> dict[str, str]:
    result = {"code": code, "severity": severity, "message": message}
    if location:
        result["location"] = location
    return result


def validate_blueprint(blueprint: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if blueprint.get("schema") != "holon.repository-presentation-blueprint/v1":
        errors.append("blueprint schema must be holon.repository-presentation-blueprint/v1")
    if blueprint.get("version") != "1.0.0" or blueprint.get("status") != "active":
        errors.append("blueprint must expose the reviewed active 1.0.0 contract")
    contracts = blueprint.get("contracts", {})
    hygiene = contracts.get("hygiene", {}) if isinstance(contracts, dict) else {}
    identity = contracts.get("identity", {}) if isinstance(contracts, dict) else {}
    egolint = contracts.get("egolint", {}) if isinstance(contracts, dict) else {}
    expected = {
        "hygiene": (
            hygiene.get("version"),
            hygiene.get("revision"),
            hygiene.get("digest"),
        ),
        "identity": (identity.get("version"), identity.get("revision")),
        "egolint": (egolint.get("version"), egolint.get("revision")),
    }
    if expected["hygiene"] != (
        "1.0.0-alpha.1",
        "cb2ed63425d29abada2d2bbb43a3b3e59d11aeb8",
        "44e0881519350e6747723995939c79c6fb4659e38a74b2c32e409866e7a186ba",
    ):
        errors.append("Hygiene profile pin is not the reviewed proposed contract")
    if expected["identity"] != (
        "1.0.0",
        "3c2fd3141371b355628e81f66f63159f19d63338",
    ):
        errors.append("Identity package pin is not the reviewed v1 contract")
    if expected["egolint"] != (
        "0.1.0-alpha.1",
        "4efe92a2609b3384fcf3b5cda343a4f64d108824",
    ):
        errors.append("Egolint validation pin is not immutable")
    profiles = blueprint.get("profiles")
    required_profiles = {
        "minimal", "library", "cli", "application", "publication",
        "private", "archived", "incubating",
    }
    if not isinstance(profiles, dict) or set(profiles) != required_profiles:
        errors.append("blueprint must define exactly the eight reviewed profiles")
    markers = blueprint.get("markers", {})
    if not isinstance(markers, dict) or not markers.get("begin") or not markers.get("end"):
        errors.append("blueprint managed-region markers are incomplete")
    return errors


def _safe_destination(value: object) -> bool:
    return isinstance(value, str) and bool(value) and SAFE_DESTINATION_RE.fullmatch(value) is not None and ".." not in value.split("/")


def _exception_slots(source: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    exceptions = source.get("exceptions", [])
    if not isinstance(exceptions, list):
        return result
    for item in exceptions:
        if isinstance(item, dict) and isinstance(item.get("slot"), str):
            result.add(item["slot"])
    return result


def validate_source(source: dict[str, Any], blueprint: dict[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    if source.get("schema") != SOURCE_SCHEMA:
        diagnostics.append(diagnostic("HOLON-PRESENT-SOURCE-001", "error", f"schema must be {SOURCE_SCHEMA}", "schema"))
    profile_name = source.get("profile")
    profiles = blueprint.get("profiles", {})
    profile = profiles.get(profile_name) if isinstance(profiles, dict) else None
    if not isinstance(profile, dict):
        diagnostics.append(diagnostic("HOLON-PRESENT-PROFILE-001", "error", "select one reviewed repository profile", "profile"))
        return diagnostics

    repository = source.get("repository")
    if not isinstance(repository, dict):
        diagnostics.append(diagnostic("HOLON-PRESENT-REPOSITORY-001", "error", "repository facts must be an object", "repository"))
    else:
        for key in ("name", "type", "visibility", "lifecycle"):
            if not isinstance(repository.get(key), str) or not repository[key].strip():
                diagnostics.append(diagnostic("HOLON-PRESENT-REPOSITORY-002", "error", f"repository.{key} is required", f"repository.{key}"))
        expected_axes = {
            "type": profile.get("repositoryType"),
            "visibility": profile.get("visibility"),
            "lifecycle": profile.get("lifecycle"),
        }
        for key, expected_value in expected_axes.items():
            if repository.get(key) != expected_value:
                diagnostics.append(diagnostic("HOLON-PRESENT-AXIS-001", "error", f"{profile_name} requires repository.{key}={expected_value}", f"repository.{key}"))

    slots = source.get("slots")
    if not isinstance(slots, dict):
        slots = {}
        diagnostics.append(diagnostic("HOLON-PRESENT-SLOTS-001", "error", "slots must be an object", "slots"))
    exceptions = source.get("exceptions")
    if not isinstance(exceptions, list):
        diagnostics.append(diagnostic("HOLON-PRESENT-EXCEPTION-001", "error", "exceptions must be an array", "exceptions"))
        exceptions = []
    allowed_slots = set(blueprint.get("slots", []))
    exception_slots: set[str] = set()
    for index, item in enumerate(exceptions):
        location = f"exceptions[{index}]"
        if not isinstance(item, dict) or set(item) != {"slot", "reason", "evidence"}:
            diagnostics.append(diagnostic("HOLON-PRESENT-EXCEPTION-002", "error", "exception requires slot, reason, and evidence", location))
            continue
        slot = item.get("slot")
        if slot not in allowed_slots:
            diagnostics.append(diagnostic("HOLON-PRESENT-EXCEPTION-003", "error", "exception names an unknown slot", f"{location}.slot"))
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            diagnostics.append(diagnostic("HOLON-PRESENT-EXCEPTION-004", "error", "exception reason is required", f"{location}.reason"))
        if not _safe_destination(item.get("evidence")):
            diagnostics.append(diagnostic("HOLON-PRESENT-EXCEPTION-005", "error", "exception evidence must be safe local or HTTPS", f"{location}.evidence"))
        if isinstance(slot, str):
            exception_slots.add(slot)

    opt_out = source.get("optOut")
    if not isinstance(opt_out, dict) or not isinstance(opt_out.get("enabled"), bool):
        diagnostics.append(diagnostic("HOLON-PRESENT-OPTOUT-001", "error", "optOut requires enabled and reason", "optOut"))
    elif opt_out["enabled"] and (not isinstance(opt_out.get("reason"), str) or not opt_out["reason"].strip()):
        diagnostics.append(diagnostic("HOLON-PRESENT-OPTOUT-002", "error", "opt-out requires a durable reason", "optOut.reason"))

    banner = source.get("banner")
    if banner is not None:
        required_banner = {"light", "dark", "highContrast", "alt", "fallback"}
        if not isinstance(banner, dict) or set(banner) != required_banner:
            diagnostics.append(diagnostic("HOLON-PRESENT-BANNER-001", "error", "banner requires light, dark, highContrast, alt, and fallback", "banner"))
        else:
            for key in ("light", "dark", "highContrast"):
                if not _safe_destination(banner[key]):
                    diagnostics.append(diagnostic("HOLON-PRESENT-BANNER-002", "error", f"banner.{key} must be safe local or HTTPS", f"banner.{key}"))
            for key in ("alt", "fallback"):
                if not isinstance(banner[key], str) or not banner[key].strip():
                    diagnostics.append(diagnostic("HOLON-PRESENT-BANNER-003", "error", f"banner.{key} must be readable text", f"banner.{key}"))

    badges = source.get("badges", [])
    states = blueprint.get("evidenceStates", {})
    if not isinstance(badges, list):
        diagnostics.append(diagnostic("HOLON-PRESENT-BADGE-001", "error", "badges must be an array", "badges"))
        badges = []
    for index, badge in enumerate(badges):
        location = f"badges[{index}]"
        required_badge = {"label", "state", "message", "image", "destination", "representedCommit"}
        if not isinstance(badge, dict) or set(badge) != required_badge:
            diagnostics.append(diagnostic("HOLON-PRESENT-BADGE-002", "error", "badge fields do not match the Identity descriptor projection", location))
            continue
        state = badge.get("state")
        if state not in states or badge.get("message") != states.get(state):
            diagnostics.append(diagnostic("HOLON-PRESENT-BADGE-003", "error", "badge state/message must match the pinned Hygiene profile", location))
        if badge.get("label") != "Hygienic":
            diagnostics.append(diagnostic("HOLON-PRESENT-BADGE-004", "error", "Hygiene badge label must be Hygienic", f"{location}.label"))
        if not _safe_destination(badge.get("image")) or not _safe_destination(badge.get("destination")):
            diagnostics.append(diagnostic("HOLON-PRESENT-BADGE-005", "error", "badge image and evidence destination must be safe local or HTTPS", location))
        if not isinstance(badge.get("representedCommit"), str) or COMMIT_RE.fullmatch(badge["representedCommit"]) is None:
            diagnostics.append(diagnostic("HOLON-PRESENT-BADGE-006", "error", "badge must bind a full represented commit", f"{location}.representedCommit"))

    required_slots = profile.get("requiredSlots", [])
    for slot in required_slots:
        present = banner is not None if slot == "banner" else bool(badges) if slot == "badges" else bool(slots.get(slot))
        if not present:
            if slot in exception_slots:
                diagnostics.append(diagnostic("HOLON-PRESENT-EXCEPTION-APPLIED", "warning", f"required slot {slot} is covered by a documented exception", f"slots.{slot}"))
            else:
                diagnostics.append(diagnostic("HOLON-PRESENT-REQUIRED-001", "error", f"TODO(blocker): repository must supply required {slot} facts", f"slots.{slot}"))
    navigation = slots.get("navigation", [])
    if navigation:
        if not isinstance(navigation, list):
            diagnostics.append(diagnostic("HOLON-PRESENT-NAV-001", "error", "navigation must be an array", "slots.navigation"))
        else:
            for index, item in enumerate(navigation):
                if not isinstance(item, dict) or set(item) != {"label", "destination"} or not item.get("label") or not _safe_destination(item.get("destination")):
                    diagnostics.append(diagnostic("HOLON-PRESENT-NAV-002", "error", "navigation entry requires label and safe destination", f"slots.navigation[{index}]"))
    return diagnostics


def _render_slot_marker(blueprint: dict[str, Any], slot: str) -> str:
    return f"{blueprint['markers']['slotPrefix']}{slot} -->"


def render_region(source: dict[str, Any], blueprint: dict[str, Any], diagnostics: list[dict[str, str]] | None = None) -> str:
    diagnostics = diagnostics if diagnostics is not None else validate_source(source, blueprint)
    markers = blueprint["markers"]
    lines = [markers["begin"], markers["generatedBy"]]
    repository = source.get("repository", {})
    banner = source.get("banner")
    if isinstance(banner, dict):
        lines.extend([
            "",
            _render_slot_marker(blueprint, "banner"),
            '<p align="center">',
            "  <picture>",
            f'    <source media="(prefers-contrast: more)" srcset="{banner["highContrast"]}">',
            f'    <source media="(prefers-color-scheme: dark)" srcset="{banner["dark"]}">',
            f'    <img src="{banner["light"]}" alt="{banner["alt"]}" width="640">',
            "  </picture>",
            "</p>",
            f'<p align="center"><strong>{banner["fallback"]}</strong></p>',
        ])
    lines.extend(["", _render_slot_marker(blueprint, "purpose")])
    purpose = source.get("slots", {}).get("purpose")
    lines.append(purpose if purpose else "> TODO(blocker): add a repository-authored purpose.")
    maturity = source.get("slots", {}).get("maturity_status")
    lines.extend(["", _render_slot_marker(blueprint, "maturity_status"), f"**Status:** {maturity}" if maturity else "> TODO(blocker): state maturity and support status."])

    badges = source.get("badges", [])
    if badges:
        lines.extend(["", _render_slot_marker(blueprint, "badges"), '<p align="center">'])
        for badge in badges:
            alt = f'{badge["label"]}: {badge["message"]}'
            lines.append(f'  <a href="{badge["destination"]}"><img src="{badge["image"]}" alt="{alt}"></a>')
        lines.extend(["</p>", f'<p align="center">Evidence profile {blueprint["contracts"]["hygiene"]["version"]}; represented revisions are linked above.</p>'])

    navigation = source.get("slots", {}).get("navigation")
    if navigation:
        links = " · ".join(f'[{item["label"]}]({item["destination"]})' for item in navigation)
        lines.extend(["", _render_slot_marker(blueprint, "navigation"), f'<p align="center">{links}</p>'])

    slots = source.get("slots", {})
    exception_slots = _exception_slots(source)
    required_slots = set(blueprint["profiles"][source.get("profile", "minimal")]["requiredSlots"])
    for slot in ORDERED_SECTIONS:
        value = slots.get(slot)
        if value:
            lines.extend(["", _render_slot_marker(blueprint, slot), f"## {SLOT_TITLES[slot]}", "", str(value)])
        elif slot in required_slots:
            lines.extend(["", _render_slot_marker(blueprint, slot), f"## {SLOT_TITLES[slot]}", ""])
            if slot in exception_slots:
                lines.append(f"> Exception recorded for required slot {slot}; see repository-owned exception evidence.")
            else:
                lines.append(f"> TODO(blocker): supply repository-owned {slot.replace('_', ' ')} facts.")

    lines.extend([
        "",
        _render_slot_marker(blueprint, "generated_metadata"),
        f"Generated by Holon repository-presentation {blueprint['version']} from repository-owned facts. "
        f"Hygiene {blueprint['contracts']['hygiene']['version']} ({blueprint['contracts']['hygiene']['status']}); "
        f"Identity package {blueprint['contracts']['identity']['version']}.",
        markers["end"],
    ])
    return "\n".join(lines) + "\n"


def _find_region(readme: str, blueprint: dict[str, Any]) -> tuple[int, int, str] | None:
    begin = blueprint["markers"]["begin"]
    end = blueprint["markers"]["end"]
    if readme.count(begin) != 1 or readme.count(end) != 1:
        return None
    start = readme.index(begin)
    finish = readme.index(end, start) + len(end)
    if finish < len(readme) and readme[finish] == "\n":
        finish += 1
    return start, finish, readme[start:finish]


def _plan_digest(plan: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in plan.items() if key != "planDigest"}
    return digest_text(canonical_json(unsigned))


def build_plan(source: dict[str, Any], readme: str, state: dict[str, Any] | None, blueprint: dict[str, Any]) -> dict[str, Any]:
    diagnostics = validate_source(source, blueprint)
    region = render_region(source, blueprint, diagnostics)
    begin = blueprint["markers"]["begin"]
    end = blueprint["markers"]["end"]
    action = "initialize"
    proposed = region + ("\n" if readme else "") + readme
    existing = None

    if source.get("optOut", {}).get("enabled") is True:
        action = "opt-out"
        proposed = readme
        diagnostics.append(diagnostic("HOLON-PRESENT-OPTOUT", "warning", "repository has explicitly opted out; no change proposed", "optOut"))
    elif readme.count(begin) != readme.count(end) or readme.count(begin) > 1:
        action = "conflict"
        proposed = readme
        diagnostics.append(diagnostic("HOLON-PRESENT-CONFLICT-001", "error", "managed-region markers are missing, duplicated, or unbalanced", "README.md"))
    elif readme.count(begin) == 1:
        existing = _find_region(readme, blueprint)
        if existing is None:
            action = "conflict"
            proposed = readme
            diagnostics.append(diagnostic("HOLON-PRESENT-CONFLICT-002", "error", "managed region cannot be parsed safely", "README.md"))
        elif not isinstance(state, dict) or state.get("schema") != STATE_SCHEMA:
            action = "conflict"
            proposed = readme
            diagnostics.append(diagnostic("HOLON-PRESENT-CONFLICT-003", "error", "existing managed region has no trusted state; adopt it manually before upgrade", "README.md"))
        elif state.get("generatedBlockDigest") != digest_text(existing[2]):
            action = "conflict"
            proposed = readme
            diagnostics.append(diagnostic("HOLON-PRESENT-CONFLICT-004", "error", "managed region differs from the last applied checksum", "README.md"))
        else:
            action = "upgrade"
            proposed = readme[:existing[0]] + region + readme[existing[1]:]
            if proposed == readme:
                action = "noop"

    if action not in {"conflict", "opt-out"} and any(item["severity"] == "error" for item in diagnostics):
        action = "blocked"

    diff = "".join(difflib.unified_diff(
        readme.splitlines(keepends=True),
        proposed.splitlines(keepends=True),
        fromfile="a/README.md",
        tofile="b/README.md",
    ))
    next_state = {
        "schema": STATE_SCHEMA,
        "blueprintVersion": blueprint["version"],
        "sourceDigest": digest_text(canonical_json(source)),
        "generatedBlockDigest": digest_text(region),
        "appliedReadmeDigest": digest_text(proposed),
        "rollbackReadme": readme,
    }
    plan = {
        "schema": PLAN_SCHEMA,
        "action": action,
        "inputReadmeDigest": digest_text(readme),
        "sourceDigest": digest_text(canonical_json(source)),
        "proposedReadmeDigest": digest_text(proposed),
        "proposedReadme": proposed,
        "diff": diff,
        "diagnostics": diagnostics,
        "nextState": next_state,
    }
    plan["planDigest"] = _plan_digest(plan)
    return plan


def apply_plan(plan: dict[str, Any], source: dict[str, Any], readme_path: Path, state_path: Path) -> None:
    if plan.get("schema") != PLAN_SCHEMA or plan.get("planDigest") != _plan_digest(plan):
        raise ValueError("plan is malformed or its checksum has changed")
    if plan.get("action") not in {"initialize", "upgrade", "noop"}:
        raise ValueError(f"plan action {plan.get('action')} is not materializable")
    current = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
    if digest_text(current) != plan.get("inputReadmeDigest"):
        raise ValueError("README changed after preview; create a new plan")
    if digest_text(canonical_json(source)) != plan.get("sourceDigest"):
        raise ValueError("source changed after preview; create a new plan")
    if digest_text(plan["proposedReadme"]) != plan.get("proposedReadmeDigest"):
        raise ValueError("proposed README checksum is invalid")
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    readme_tmp = readme_path.with_suffix(readme_path.suffix + ".holon-tmp")
    state_tmp = state_path.with_suffix(state_path.suffix + ".holon-tmp")
    readme_tmp.write_text(plan["proposedReadme"], encoding="utf-8")
    state_tmp.write_text(json.dumps(plan["nextState"], indent=2) + "\n", encoding="utf-8")
    readme_tmp.replace(readme_path)
    state_tmp.replace(state_path)


def rollback(readme_path: Path, state_path: Path) -> str:
    state = load_json(state_path)
    if state.get("schema") != STATE_SCHEMA:
        raise ValueError("rollback state schema is unsupported")
    current = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
    if digest_text(current) != state.get("appliedReadmeDigest"):
        raise ValueError("README changed after apply; rollback refuses to overwrite it")
    previous = state.get("rollbackReadme")
    if not isinstance(previous, str):
        raise ValueError("rollback snapshot is missing")
    readme_path.write_text(previous, encoding="utf-8")
    state_path.unlink()
    return previous


def validate_fixture_contract(source: dict[str, Any], region: str, blueprint: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    markers = blueprint["markers"]
    if region.count(markers["begin"]) != 1 or region.count(markers["end"]) != 1:
        errors.append("EGO-PRESENT-README-001: generated region markers are invalid")
    banner = source.get("banner")
    if banner and (banner["alt"] not in region or not all(banner[key] in region for key in ("light", "dark", "highContrast"))):
        errors.append("EGO-PRESENT-BANNER-001: accessible local banner projection is incomplete")
    for badge in source.get("badges", []):
        expected = f'{badge["label"]}: {badge["message"]}'
        if expected not in region or badge["destination"] not in region:
            errors.append("EGO-PRESENT-BADGE-001: evidence-bound badge projection is incomplete")
    required = blueprint["profiles"][source["profile"]]["requiredSlots"]
    exceptions = _exception_slots(source)
    for slot in required:
        marker_slot = "banner" if slot == "banner" else slot
        marker = _render_slot_marker(blueprint, marker_slot)
        if marker not in region and slot not in exceptions:
            errors.append(f"EGO-PRESENT-README-001: required slot {slot} has no semantic marker")
    lowered = region.casefold()
    for term in blueprint.get("prohibitedClaims", []):
        if term in lowered:
            errors.append(f"EGO-PRESENT-BADGE-001: prohibited unsupported claim {term}")
    return errors


def validate_fixtures(blueprint: dict[str, Any], fixture_document: dict[str, Any]) -> list[str]:
    errors = validate_blueprint(blueprint)
    pin = fixture_document.get("egolintPin", {})
    expected = blueprint.get("contracts", {}).get("egolint", {})
    if pin != expected:
        errors.append("fixture Egolint contract pin differs from the blueprint")
    seen: set[str] = set()
    for fixture in fixture_document.get("fixtures", []):
        name = fixture.get("name", "<unnamed>")
        source = fixture.get("source")
        readme = fixture.get("readme")
        if not isinstance(source, dict) or not isinstance(readme, str):
            errors.append(f"{name}: fixture source/readme is malformed")
            continue
        if name != "mantle":
            seen.add(name)
        diagnostics = validate_source(source, blueprint)
        errors.extend(f"{name}: {item['code']}: {item['message']}" for item in diagnostics if item["severity"] == "error")
        plan = build_plan(source, readme, None, blueprint)
        if plan["action"] != "initialize":
            errors.append(f"{name}: fixture did not produce an initialization plan")
        if not plan["proposedReadme"].endswith(readme):
            errors.append(f"{name}: initialization did not preserve authored README bytes")
        region = render_region(source, blueprint, diagnostics)
        errors.extend(f"{name}: {error}" for error in validate_fixture_contract(source, region, blueprint))
        if build_plan(source, readme, None, blueprint) != plan:
            errors.append(f"{name}: preview is not deterministic")
    if seen != set(blueprint.get("profiles", {})):
        errors.append("fixtures do not cover every repository-presentation profile")
    return sorted(set(errors))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("validate-fixtures")

    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("--source", type=Path, required=True)
    preview_parser.add_argument("--readme", type=Path, default=Path("README.md"))
    preview_parser.add_argument("--state", type=Path, default=Path(".holon/repository-presentation.state.json"))
    preview_parser.add_argument("--plan", type=Path)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--source", type=Path, required=True)
    apply_parser.add_argument("--readme", type=Path, default=Path("README.md"))
    apply_parser.add_argument("--state", type=Path, default=Path(".holon/repository-presentation.state.json"))
    apply_parser.add_argument("--plan", type=Path, required=True)

    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("--readme", type=Path, default=Path("README.md"))
    rollback_parser.add_argument("--state", type=Path, default=Path(".holon/repository-presentation.state.json"))

    args = parser.parse_args(argv)
    blueprint = load_json(BLUEPRINT_PATH)
    if args.command in {None, "validate-fixtures"}:
        errors = validate_fixtures(blueprint, load_json(FIXTURES_PATH))
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("repository-presentation blueprint and all fixtures are valid")
        return 0
    if args.command == "preview":
        source = load_json(args.source)
        readme = args.readme.read_text(encoding="utf-8") if args.readme.exists() else ""
        state = load_json(args.state) if args.state.exists() else None
        plan = build_plan(source, readme, state, blueprint)
        if args.plan:
            _write_json(args.plan, plan)
        for item in plan["diagnostics"]:
            print(f"{item['severity']}: {item['code']}: {item['message']}", file=sys.stderr)
        print(plan["diff"], end="")
        return 1 if plan["action"] in {"blocked", "conflict"} else 0
    if args.command == "apply":
        apply_plan(load_json(args.plan), load_json(args.source), args.readme, args.state)
        return 0
    if args.command == "rollback":
        rollback(args.readme, args.state)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
