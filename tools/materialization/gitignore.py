"""Deterministic lifecycle planning for pinned Empathy composition artifacts.

Empathy resolves profiles and composes rules. This adapter verifies its data
contract and compares the reviewed bytes with a consumer; it executes no source
code and does not infer local additions from an existing ignore file.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
import re
from typing import Any

from .common import (
    MaterializationError,
    canonical_bytes,
    sha256_bytes,
)
from .gitignore_state import (
    digest_value as _digest, file_image, foreign_state, load_recovery, load_state,
    no_symlinks as _no_symlinks, object_fields as _object,
    relative_path as _relative, require as _require, target_root,
)

SOURCE_PROFILE = Path(__file__).resolve().parents[2] / "catalog/gitignore-materialization.json"
REQUEST_SCHEMA = "holon.gitignore-request/v1"
PLAN_SCHEMA = "holon.gitignore-plan/v2"


def _strings(value: Any, label: str) -> None:
    _require(isinstance(value, list) and all(isinstance(item, str) for item in value),
             f"{label} must be an array of strings")
    _require(len(value) == len(set(value)), f"{label} must not contain duplicates")


def _read_source(root: Path, relative: str) -> bytes:
    path = _no_symlinks(root / _relative(relative))
    _require(path.is_file(), f"source must be a regular file: {relative}")
    return path.read_bytes()


def _load_sources(source_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    profile = json.loads(SOURCE_PROFILE.read_text(encoding="utf-8"))
    source_root = _no_symlinks(source_root)
    catalog = json.loads(_read_source(source_root, profile["catalog_path"]))
    _require(sha256_bytes(canonical_bytes(catalog)) == profile["catalog_sha256"],
             "Empathy catalog digest mismatch; supply the accepted pinned source")
    artifact = next(item for item in catalog["artifacts"] if item["id"] == "gitignore")
    definition = artifact["composition"]
    contents = {}
    # Verify the full registered fragment set, even unselected overlays.
    for source in [definition["baseline"], *definition["overlays"]]:
        raw = _read_source(source_root, source["path"])
        _require(sha256_bytes(raw) == source["sha256"],
                 f"Empathy source digest mismatch: {source['path']}")
        contents[source["id"]] = raw.decode("utf-8")
    return profile, catalog, contents


def _verify_inputs(
    request: dict[str, Any], composition: dict[str, Any], source_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    _object(request, {"schema_version", "repository", "source_revision", "profiles",
                      "scopes", "composition_sha256", "adopt"}, "gitignore request")
    _require(request["schema_version"] == REQUEST_SCHEMA, "unsupported gitignore request schema")
    _require(isinstance(request["repository"], str) and re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", request["repository"]
    ) is not None, "repository must use owner/name form")
    profile, catalog, contents = _load_sources(source_root)
    _require(request["source_revision"] == profile["revision"],
             "unsupported Empathy revision; update Holon's source pin through review")
    _digest(request["composition_sha256"], "composition_sha256")
    _require(sha256_bytes(canonical_bytes(composition)) == request["composition_sha256"],
             "composition digest mismatch; regenerate and review the request")
    _object(composition, {"format", "status", "generator", "foundation", "repository",
                          "profiles", "source", "files"}, "Empathy composition")
    _require(composition["format"] == profile["format"]
             and composition["foundation"] == profile["foundation"]
             and composition["status"] == "plan-only"
             and composition["generator"] == "tools/foundation.py plan-gitignore",
             "unsupported Empathy composition contract")
    _require(composition["repository"] == request["repository"], "composition repository mismatch")
    _strings(request["profiles"], "profiles")
    profiles = {item["id"]: item for item in catalog["profiles"]}
    _require("universal" in request["profiles"] and all(
        item in profiles for item in request["profiles"]
    ), "profiles must include universal and only registered Empathy profiles")
    _require(composition["profiles"] == request["profiles"], "composition profiles mismatch")
    # Profiles are already resolved by Empathy, not resolved again by Holon.
    for identifier in request["profiles"]:
        _require(set(profiles[identifier].get("requires", [])) <= set(request["profiles"]),
                 f"profiles are not resolved: {identifier} has missing dependencies")
        _require(not set(profiles[identifier].get("conflicts", [])) & set(request["profiles"]),
                 f"conflicting resolved profile selection: {identifier}")
    _object(composition["source"], {"owner", "catalog_sha256", "resolved_manifest_sha256"},
            "composition source")
    _require(composition["source"]["owner"] == profile["repository"]
             and composition["source"]["catalog_sha256"] == profile["catalog_sha256"],
             "composition source provenance mismatch")
    _digest(composition["source"]["resolved_manifest_sha256"], "resolved_manifest_sha256")
    _require(isinstance(request["scopes"], list) and bool(request["scopes"]),
             "scopes must be a nonempty array")
    _require(isinstance(composition["files"], list)
             and len(composition["files"]) == len(request["scopes"]),
             "composition must contain exactly the selected scopes")
    definition = next(item for item in catalog["artifacts"] if item["id"] == "gitignore")["composition"]
    overlays = {source["id"]: source for source in definition["overlays"]}
    paths = set()
    records = []
    for scope, file in zip(request["scopes"], composition["files"]):
        _object(scope, {"root", "overlays", "local_additions"}, "scope")
        root = scope["root"]
        if root != ".":
            _relative(root)
            _require(".gitignore" not in {part.casefold() for part in root.split("/")},
                     "scope cannot be beneath a .gitignore file")
        path = ".gitignore" if root == "." else f"{root}/.gitignore"
        _require(path.casefold() not in paths, "scope paths must be unique ignoring case")
        paths.add(path.casefold())
        _strings(scope["overlays"], "scope overlays")
        local = scope["local_additions"]
        _require(isinstance(local, str) and "\r" not in local and "\0" not in local
                 and (not local or local.endswith("\n")),
                 "local_additions must be empty or LF-terminated text without CR or NUL")
        layers = []
        # These are v1 wire-format delimiters, not a second rule baseline.
        chunks = ["# Composed ignore rules; see the foundation plan for source hashes.\n"]
        for identifier in scope["overlays"]:
            _require(identifier in overlays, f"unknown overlay: {identifier}")
            source = overlays[identifier]
            _require(source["profile"] in request["profiles"],
                     f"overlay {identifier} requires profile {source['profile']}")
            layers.append({"kind": "overlay", "owner": profile["repository"], **source})
            chunks.extend([f"\n# Profile: {identifier}\n", contents[identifier]])
        layers.append({"kind": "local", "owner": request["repository"],
                       "sha256": sha256_bytes(local.encode("utf-8"))})
        chunks.extend(["\n# Repository-owned local additions.\n", local])
        baseline = definition["baseline"]
        layers.append({"kind": "baseline", "owner": profile["repository"], **baseline})
        chunks.extend(["\n# Universal baseline (last in every declared scope).\n",
                       contents[baseline["id"]]])
        _object(file, {"path", "ownership", "override", "layers", "content", "content_sha256"},
                "composition file")
        _require(file["path"] == path and file["ownership"] == "repository-owned"
                 and file["override"] in (None, "preserve"), "composition path/ownership mismatch")
        _require(file["layers"] == layers and file["content"] == "".join(chunks),
                 f"composition layers, ordering, or local text mismatch: {path}")
        _require(file["content_sha256"] == sha256_bytes(file["content"].encode("utf-8")),
                 f"composition content digest mismatch: {path}")
        records.append({**file, "selection": scope})
    _require(".gitignore" in paths, "scopes must include repository root '.'")
    _require(isinstance(request["adopt"], list), "adopt must be an array")
    adopt = {}
    for record in request["adopt"]:
        _object(record, {"path", "before_sha256"}, "adoption record")
        path = _relative(record["path"])
        _require(path in {item["path"] for item in records} and path not in adopt,
                 "adoption paths must be unique selected outputs")
        _digest(record["before_sha256"], "adoption before_sha256")
        adopt[path] = record["before_sha256"]
    return profile, records, adopt


def _diff(path: str, before: str, after: str, *, exists: bool) -> str:
    lines = difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                 fromfile=f"a/{path}" if exists else "/dev/null", tofile=f"b/{path}")
    return "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
                   for line in lines)


def build_gitignore_plan(
    request: dict[str, Any], composition: dict[str, Any], target: Path, *, empathy_source: Path,
) -> dict[str, Any]:
    """Inspect target ownership and exact proposed bytes without writing."""
    profile, files, adopt = _verify_inputs(request, composition, empathy_source)
    target = target_root(target)
    state, state_raw = load_state(target)
    if state is not None:
        _require(state["repository"] == request["repository"], "target belongs to a different repository")
        load_recovery(target, state)
    previous = {record["path"]: record for record in state["files"]} if state else {}
    foreign_paths, foreign_sha = foreign_state(target)
    selected = {file["path"]: file for file in files}
    for old_path in previous:
        _require(not any(path.casefold() == old_path.casefold() and path != old_path for path in selected),
                 "case-only scope renames require explicit reconciliation")
    operations = []
    for path in sorted(set(selected) | set(previous)):
        file = selected.get(path)
        prior = previous.get(path)
        current = None
        kind = "missing"
        reason = "file is absent; create the verified composition after review"
        try:
            current = file_image(target, path)
            if current is not None:
                kind = "file"
        except MaterializationError as error:
            kind = "unsafe"
            reason = str(error) + "; reconcile the target path and re-plan"
        except OSError as error:
            kind = "unsafe"
            reason = f"cannot read target (errno {error.errno}); inspect permissions and re-plan"
        action = "create"
        if kind == "unsafe":
            action = "conflict"
        elif file is not None and file["override"] == "preserve" and path in adopt:
            action = "conflict"
            reason = "preserve and adopt conflict; review the explicit selection"
        elif path.casefold() in foreign_paths and (prior or file["override"] != "preserve"):
            action = "conflict"
            reason = "generic Holon state owns this path; reconcile ownership before gitignore adoption"
        elif prior is not None:
            if current != prior["image"]:
                action = "conflict"
                reason = "tracked file is missing, edited, or has mode drift; preserve edits and re-plan"
            elif file is None or file["override"] == "preserve":
                action = "release"
                reason = "selection releases tracking; retain current bytes without deleting the file"
            elif current["sha256"] == file["content_sha256"]:
                action = "noop"
                reason = "verified tracked bytes already match the composition"
            else:
                action = "update"
                reason = "tracked preimage is unchanged; apply the explicit new composition after review"
        elif file["override"] == "preserve":
            action = "preserve"
            reason = "Empathy explicitly preserves this repository-owned path"
        elif path in adopt:
            if current is None or current["sha256"] != adopt[path] or current["sha256"] != file["content_sha256"]:
                action = "conflict"
                reason = "adoption requires reviewed current bytes identical to the composition; reconcile and re-plan"
            else:
                action = "adopt"
                reason = "explicit exact-byte adoption; track provenance without rewriting the file"
        elif current is not None:
            action = "conflict"
            reason = ("existing file has no explicit adoption record; review exact-byte adoption"
                      if current["sha256"] == file["content_sha256"] else
                      "existing text differs; explicitly reconcile local additions in Empathy and re-plan")
        content = file["content"] if file else prior["image"]["content"]
        proposed_sha = file["content_sha256"] if file else prior["image"]["sha256"]
        if action == "release":
            content, proposed_sha = current["content"], current["sha256"]
        before_text = current["content"] if current else None
        operations.append({
            "path": path, "action": action, "reason": reason, "before_kind": kind,
            "before_sha256": current["sha256"] if current else None,
            "before_mode": current["mode"] if current else None,
            "proposed_sha256": proposed_sha,
            "proposed_mode": current["mode"] if current else 0o644,
            "before_content": before_text, "proposed_content": content,
            "diff": _diff(path, before_text or "", content, exists=current is not None)
            if kind != "unsafe" and (current is None or before_text is not None) else None,
            "ownership": "repository-owned", "override": file["override"] if file else "preserve",
            "selection": file["selection"] if file and action != "release" else prior["selection"],
            "layers": file["layers"] if file and action != "release" else prior["layers"],
        })
    summary = {}
    for operation in operations:
        summary[operation["action"]] = summary.get(operation["action"], 0) + 1
    payload = {
        "schema_version": PLAN_SCHEMA, "status": "plan-only", "repository": request["repository"],
        "request": request, "source": profile, "composition_source": composition["source"],
        "prior_state_sha256": sha256_bytes(state_raw) if state_raw is not None else None,
        "foreign_state_sha256": foreign_sha, "operations": operations, "summary": summary,
    }
    return {**payload, "plan_id": sha256_bytes(canonical_bytes(payload))}


def check_gitignore_plan(
    plan: dict[str, Any], request: dict[str, Any], composition: dict[str, Any], target: Path,
    *, empathy_source: Path,
) -> None:
    """Reject obsolete, tampered, conflicted, or stale plans without mutation."""
    _require(isinstance(plan, dict) and plan.get("schema_version") == PLAN_SCHEMA,
             "unsupported gitignore plan schema; regenerate a v2 plan for the ownership lifecycle")
    current = build_gitignore_plan(request, composition, target, empathy_source=empathy_source)
    _require(plan == current, "gitignore plan is stale or changed; generate and review a new plan")
    _require(not current["summary"].get("conflict"), "gitignore plan has conflicts; reconcile and re-plan")
