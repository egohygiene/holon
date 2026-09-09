#!/usr/bin/env python3
"""Prove Holon's committed continuity dogfood through the public CLI."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "holon_materialize.py"
DEFAULT_REQUEST = ROOT / "examples" / "holon-continuity.request.json"
DEFAULT_PROFILE = ROOT / "catalog" / "repository-continuity-materialization.json"
STATE_RELATIVE_PATH = ".holon/repository-continuity-state.v1.json"
REQUIRED_SURFACES = ("AGENTS.md", "CONTINUITY.md")
FORBIDDEN_EXECUTABLES = ("curl", "gh", "git", "wget")


class DogfoodError(RuntimeError):
    """Raised when committed dogfood or its disposable lifecycle diverges."""


def digest(content: bytes) -> str:
    """Return one lowercase SHA-256 digest."""
    return sha256(content).hexdigest()


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one required JSON object."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DogfoodError(f"unable to load JSON object {path}: {error}") from error
    if not isinstance(value, dict):
        raise DogfoodError(f"expected one JSON object in {path}")
    return value


def path_contract(root: Path) -> dict[str, dict[str, str | int]]:
    """Fingerprint paths, kinds, modes, symlink targets, and regular-file bytes."""
    result: dict[str, dict[str, str | int]] = {}
    if not root.is_dir() or root.is_symlink():
        raise DogfoodError(f"expected a regular directory: {root}")
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            record: dict[str, str | int] = {
                "kind": "symlink",
                "mode": stat.S_IMODE(metadata.st_mode),
                "target": os.readlink(path),
            }
        elif stat.S_ISREG(metadata.st_mode):
            record = {
                "kind": "file",
                "mode": stat.S_IMODE(metadata.st_mode),
                "sha256": digest(path.read_bytes()),
            }
        elif stat.S_ISDIR(metadata.st_mode):
            record = {
                "kind": "directory",
                "mode": stat.S_IMODE(metadata.st_mode),
            }
        else:
            raise DogfoodError(f"unsupported path kind in contract: {path}")
        result[relative] = record
    return result


def contract_digest(contract: dict[str, dict[str, str | int]]) -> str:
    """Digest one canonical path contract without recording host paths."""
    return digest(
        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def prepare_environment(root: Path) -> tuple[dict[str, str], Path]:
    """Install local traps and remove credential-like values from child processes."""
    trap_root = root / "command-traps"
    trap_root.mkdir()
    trap_log = root / "forbidden-command.log"
    for name in FORBIDDEN_EXECUTABLES:
        path = trap_root / name
        path.write_text(
            "#!/bin/sh\n"
            f"printf \"%s\\n\" \"$0\" >> {shlex.quote(str(trap_log))}\n"
            "exit 97\n",
            encoding="utf-8",
        )
        path.chmod(0o700)

    environment = os.environ.copy()
    for name in list(environment):
        upper = name.upper()
        if any(
            marker in upper
            for marker in ("API_KEY", "CREDENTIAL", "PASSWORD", "SECRET", "TOKEN")
        ):
            environment.pop(name, None)
    environment["PATH"] = str(trap_root) + os.pathsep + environment.get("PATH", "")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment, trap_log


def run_cli(arguments: list[str], environment: dict[str, str]) -> dict[str, Any]:
    """Run one public continuity command and require a JSON-only success envelope."""
    completed = subprocess.run(
        [sys.executable, str(CLI), "continuity", *arguments],
        cwd=ROOT,
        env=environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise DogfoodError(
            "continuity CLI failed: "
            + completed.stderr.strip()
            + ("; stdout: " + completed.stdout.strip() if completed.stdout.strip() else "")
        )
    if completed.stderr:
        raise DogfoodError(f"continuity CLI wrote unexpected stderr: {completed.stderr}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise DogfoodError(f"continuity CLI stdout is not one JSON document: {error}") from error
    if not isinstance(result, dict) or result.get("ok") is not True or result.get("errors") != []:
        raise DogfoodError("continuity CLI returned an invalid success envelope")
    if result.get("schema_version") != "holon.repository-continuity-cli-result/v1":
        raise DogfoodError("continuity CLI returned an unsupported result schema")
    return result


def require_summary(result: dict[str, Any], expected: dict[str, int]) -> None:
    """Require one exact deterministic operation summary."""
    if result.get("summary") != expected:
        raise DogfoodError(
            f"unexpected continuity summary: {result.get('summary')!r}; expected {expected!r}"
        )


def managed_artifacts(target: Path) -> dict[str, bytes]:
    """Read required surfaces, state, and the state-bound rollback manifest."""
    state_path = target / STATE_RELATIVE_PATH
    state = load_json_object(state_path)
    surfaces = state.get("surfaces")
    if not isinstance(surfaces, list):
        raise DogfoodError("continuity state has no surface inventory")
    paths = [record.get("path") for record in surfaces if isinstance(record, dict)]
    if paths != ["AGENTS.md", "CONTINUITY.md"]:
        raise DogfoodError(f"Holon dogfood must own exactly two required surfaces: {paths!r}")
    rollback_relative = state.get("rollback_manifest")
    if not isinstance(rollback_relative, str):
        raise DogfoodError("continuity state has no rollback manifest reference")
    relative_paths = [*REQUIRED_SURFACES, STATE_RELATIVE_PATH, rollback_relative]
    result: dict[str, bytes] = {}
    for relative in relative_paths:
        path = target / relative
        if not path.is_file() or path.is_symlink():
            raise DogfoodError(f"dogfood artifact is missing or non-regular: {relative}")
        result[relative] = path.read_bytes()
    return result


def create_disposable_target(root: Path) -> Path:
    """Create an empty consumer with representative Git metadata."""
    target = root / "target"
    git_root = target / ".git"
    (git_root / "objects" / "fixture").mkdir(parents=True)
    (git_root / "HEAD").write_bytes(b"ref: refs/heads/main\n")
    (git_root / "config").write_bytes(
        b"[core]\n\trepositoryformatversion = 0\n\tbare = false\n"
    )
    (git_root / "objects" / "fixture" / "sentinel").write_bytes(
        b"Holon continuity must not mutate Git metadata.\n"
    )
    return target


def disposable_lifecycle(
    root: Path,
    *,
    request: Path,
    profile: Path,
    aether_source: Path,
    environment: dict[str, str],
) -> tuple[dict[str, Any], dict[str, bytes], str]:
    """Exercise create, verify, exact no-op apply, and rollback through the CLI."""
    target = create_disposable_target(root)
    review = root / "review"
    review.mkdir()
    git_before = path_contract(target / ".git")

    plan_path = review / "create-plan.json"
    preview_path = review / "create-preview.json"
    planned = run_cli(
        [
            "plan",
            "--request",
            str(request),
            "--target",
            str(target),
            "--profile",
            str(profile),
            "--aether-source",
            str(aether_source),
            "--output",
            str(plan_path),
        ],
        environment,
    )
    require_summary(planned, {"create": 2})
    plan_id = planned.get("plan_id")
    if not isinstance(plan_id, str):
        raise DogfoodError("create plan did not return a plan ID")
    previewed = run_cli(
        [
            "preview",
            "--plan",
            str(plan_path),
            "--target",
            str(target),
            "--output",
            str(preview_path),
        ],
        environment,
    )
    if previewed.get("plan_id") != plan_id or not isinstance(
        previewed.get("preview_id"), str
    ):
        raise DogfoodError("preview receipt does not bind the create plan")
    applied = run_cli(
        [
            "apply",
            "--plan",
            str(plan_path),
            "--preview-receipt",
            str(preview_path),
            "--reviewed-plan-id",
            plan_id,
            "--target",
            str(target),
            "--profile",
            str(profile),
            "--aether-source",
            str(aether_source),
        ],
        environment,
    )
    require_summary(applied, {"create": 2})
    verified = run_cli(["verify", "--target", str(target)], environment)
    if verified.get("status") != "verified":
        raise DogfoodError("created dogfood target did not verify")

    artifacts = managed_artifacts(target)
    tree_after_create = path_contract(target)
    state_sha256 = digest(artifacts[STATE_RELATIVE_PATH])
    if verified.get("state_sha256") != state_sha256:
        raise DogfoodError("verify result did not bind the exact continuity state")

    noop_plan_path = review / "noop-plan.json"
    noop_preview_path = review / "noop-preview.json"
    noop_plan = run_cli(
        [
            "plan",
            "--request",
            str(request),
            "--target",
            str(target),
            "--profile",
            str(profile),
            "--aether-source",
            str(aether_source),
            "--output",
            str(noop_plan_path),
        ],
        environment,
    )
    require_summary(noop_plan, {"noop": 2})
    noop_plan_id = noop_plan.get("plan_id")
    if not isinstance(noop_plan_id, str):
        raise DogfoodError("no-op plan did not return a plan ID")
    run_cli(
        [
            "preview",
            "--plan",
            str(noop_plan_path),
            "--target",
            str(target),
            "--output",
            str(noop_preview_path),
        ],
        environment,
    )
    noop_apply = run_cli(
        [
            "apply",
            "--plan",
            str(noop_plan_path),
            "--preview-receipt",
            str(noop_preview_path),
            "--reviewed-plan-id",
            noop_plan_id,
            "--target",
            str(target),
            "--profile",
            str(profile),
            "--aether-source",
            str(aether_source),
        ],
        environment,
    )
    require_summary(noop_apply, {"noop": 2})
    if path_contract(target) != tree_after_create:
        raise DogfoodError("same-request no-op apply changed disposable target bytes")

    run_cli(
        [
            "rollback",
            "--target",
            str(target),
            "--expected-state-sha256",
            state_sha256,
        ],
        environment,
    )
    for relative in (*REQUIRED_SURFACES, STATE_RELATIVE_PATH):
        if (target / relative).exists() or (target / relative).is_symlink():
            raise DogfoodError(f"rollback did not restore missing preimage: {relative}")
    if path_contract(target / ".git") != git_before:
        raise DogfoodError("continuity lifecycle changed disposable .git metadata")

    report = {
        "create_plan_id": plan_id,
        "noop_plan_id": noop_plan_id,
        "state_sha256": state_sha256,
        "git_entry_count": len(git_before),
    }
    return report, artifacts, contract_digest(git_before)


def assert_root_parity(
    *,
    root: Path,
    request: Path,
    profile: Path,
    aether_source: Path,
    disposable_artifacts: dict[str, bytes],
    review: Path,
    environment: dict[str, str],
) -> dict[str, str]:
    """Preview and apply an exact root no-op, then prove total tree parity."""
    root_tree_before = path_contract(root)
    root_git_before = path_contract(root / ".git")

    plan_path = review / "root-noop-plan.json"
    preview_path = review / "root-noop-preview.json"
    planned = run_cli(
        [
            "plan",
            "--request",
            str(request),
            "--target",
            str(root),
            "--profile",
            str(profile),
            "--aether-source",
            str(aether_source),
            "--output",
            str(plan_path),
        ],
        environment,
    )
    require_summary(planned, {"noop": 2})
    plan_id = planned.get("plan_id")
    if not isinstance(plan_id, str):
        raise DogfoodError("root no-op plan did not return a plan ID")
    previewed = run_cli(
        [
            "preview",
            "--plan",
            str(plan_path),
            "--target",
            str(root),
            "--output",
            str(preview_path),
        ],
        environment,
    )
    preview_id = previewed.get("preview_id")
    if previewed.get("plan_id") != plan_id or not isinstance(preview_id, str):
        raise DogfoodError("root preview receipt does not bind the exact no-op plan")
    applied = run_cli(
        [
            "apply",
            "--plan",
            str(plan_path),
            "--preview-receipt",
            str(preview_path),
            "--reviewed-plan-id",
            plan_id,
            "--target",
            str(root),
            "--profile",
            str(profile),
            "--aether-source",
            str(aether_source),
        ],
        environment,
    )
    require_summary(applied, {"noop": 2})
    verified = run_cli(["verify", "--target", str(root)], environment)
    if verified.get("status") != "verified":
        raise DogfoodError("committed Holon continuity state did not verify after no-op apply")

    root_artifacts = managed_artifacts(root)
    if root_artifacts != disposable_artifacts:
        changed = sorted(
            path
            for path in set(root_artifacts) | set(disposable_artifacts)
            if root_artifacts.get(path) != disposable_artifacts.get(path)
        )
        raise DogfoodError(
            "committed root artifacts differ from clean request materialization: "
            + ", ".join(changed)
        )
    root_tree_after = path_contract(root)
    if root_tree_after != root_tree_before:
        changed = sorted(
            path
            for path in set(root_tree_before) | set(root_tree_after)
            if root_tree_before.get(path) != root_tree_after.get(path)
        )
        raise DogfoodError(
            "reviewed root no-op apply changed repository bytes: " + ", ".join(changed)
        )
    if path_contract(root / ".git") != root_git_before:
        raise DogfoodError("reviewed root no-op apply changed .git metadata")
    state_sha256 = digest(root_artifacts[STATE_RELATIVE_PATH])
    if verified.get("state_sha256") != state_sha256:
        raise DogfoodError("root verify result did not bind the exact continuity state")
    return {
        "plan_id": plan_id,
        "preview_id": preview_id,
        "state_sha256": state_sha256,
        "tree_sha256": contract_digest(root_tree_before),
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone dogfood proof CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--aether-source", type=Path, required=True)
    parser.add_argument(
        "--lifecycle-only",
        action="store_true",
        help="Exercise the disposable CLI lifecycle before root artifacts are materialized.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Verify exact root parity and a reversible, Git-preserving disposable lifecycle."""
    arguments = build_parser().parse_args(argv)
    repository_root = arguments.repository_root.resolve()
    request = arguments.request.resolve()
    profile = arguments.profile.resolve()
    aether_source = arguments.aether_source.resolve()
    try:
        load_json_object(request)
        load_json_object(profile)
        with tempfile.TemporaryDirectory(prefix="holon-continuity-dogfood-") as raw:
            temporary_root = Path(raw)
            environment, trap_log = prepare_environment(temporary_root)
            lifecycle, artifacts, git_sha256 = disposable_lifecycle(
                temporary_root,
                request=request,
                profile=profile,
                aether_source=aether_source,
                environment=environment,
            )
            root_result = None
            if not arguments.lifecycle_only:
                root_result = assert_root_parity(
                    root=repository_root,
                    request=request,
                    profile=profile,
                    aether_source=aether_source,
                    disposable_artifacts=artifacts,
                    review=temporary_root / "review",
                    environment=environment,
                )
            if trap_log.exists():
                names = trap_log.read_text(encoding="utf-8").splitlines()
                raise DogfoodError(
                    "continuity dogfood invoked forbidden external commands: "
                    + ", ".join(names)
                )
        report = {
            "schema_version": "holon.repository-continuity-dogfood-report/v1",
            "status": "valid",
            "root_parity": "skipped" if arguments.lifecycle_only else "exact",
            "root_state_sha256": (
                None if root_result is None else root_result["state_sha256"]
            ),
            "root_noop_plan_id": (
                None if root_result is None else root_result["plan_id"]
            ),
            "root_preview_id": (
                None if root_result is None else root_result["preview_id"]
            ),
            "root_tree_sha256": (
                None if root_result is None else root_result["tree_sha256"]
            ),
            "disposable_state_sha256": lifecycle["state_sha256"],
            "create_plan_id": lifecycle["create_plan_id"],
            "noop_plan_id": lifecycle["noop_plan_id"],
            "git_contract_sha256": git_sha256,
            "git_entry_count": lifecycle["git_entry_count"],
            "forbidden_external_commands": [],
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (DogfoodError, OSError, ValueError) as error:
        print(f"Holon continuity dogfood failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
