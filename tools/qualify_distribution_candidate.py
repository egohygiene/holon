#!/usr/bin/env python3
"""Exercise a verified candidate outside its producer checkout, without fetches.

The child receives only extracted archive bytes, Python's standard library and
a scrubbed environment. This is finite candidate qualification, not publication.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

from distribution_candidate import canonical, digest, object_json, safe_path, verify
from materialization.common import canonical_bytes as materialization_bytes


def consume(root: Path, output: Path) -> dict:
    if platform.system() != "Linux" or platform.machine() != "x86_64" or platform.python_version() != "3.12.14":
        raise ValueError("this finite candidate is qualified only on Linux x86_64/Python 3.12.14")
    if (root / ".git").exists() or (root / "../.git").exists():
        raise ValueError("consumer must use an extracted artifact, not a Git checkout")
    if not Path(__file__).resolve().is_relative_to(root) or not sys.flags.no_site:
        raise ValueError("consumer must execute the extracted script with site packages disabled")
    for entry in sys.path:
        path = Path(entry).resolve()
        if not path.is_relative_to(root) and not path.is_relative_to(Path(sys.base_prefix).resolve()):
            raise ValueError("consumer import path contains undeclared source or dependency inputs")
    manifest = object_json((root / "DISTRIBUTION.json").read_bytes())
    if manifest["status"] != "candidate-only":
        raise ValueError("consumer must retain candidate scope")
    for name, record in manifest["files"].items():
        if digest((root / safe_path(name)).read_bytes()) != record["sha256"]:
            raise ValueError("consumer payload changed after archive verification")
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    runtime = Path(sys.executable).resolve()
    environment = {"PATH": str(runtime.parent), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}

    def run(arguments, *, success=True):
        result = subprocess.run([str(runtime), "-B", "-S", *arguments], cwd=root,
                                env=environment, text=True, capture_output=True, check=False)
        rows.append({"interface": arguments[0], "command": arguments[1] if len(arguments) > 1 else "",
                     "exit_code": result.returncode})
        if (result.returncode == 0) != success:
            raise ValueError(f"artifact command did not preserve its expected result: {arguments[0]}: {result.stderr[-1500:]}")
        return result

    def lifecycle(command, target, *arguments, success=True):
        return run(["tools/holon_materialize.py", "site-suite", command,
                    "--target", str(target), *map(str, arguments)], success=success)

    def managed(target):
        state = object_json((target / ".holon/materialization-state.v1.json").read_bytes())
        return {item["path"]: digest((target / item["path"]).read_bytes()) for item in state["managed_files"]}

    run(["tools/holon_contract.py", "validate-catalog"])
    variants = []
    for variant, example in (("generic", "site-suite-generic.manifest.json"),
                             ("launchkit", "site-suite-optiflow.manifest.json")):
        manifest_path = root / "examples" / example
        run(["tools/holon_contract.py", "validate", "--manifest", str(manifest_path)])
        resolved_path = output / (variant + "-resolved.json")
        run(["tools/holon_contract.py", "resolve", "--manifest", str(manifest_path), "--output", str(resolved_path)])
        pairs = []
        for suffix in ("first-name", "different-checkout-name"):
            target = output / (variant + "-" + suffix)
            plan = output / (variant + "-" + suffix + ".plan.json")
            lifecycle("plan", target, "--manifest", manifest_path, "--variant", variant, "--output", plan)
            if target.exists():
                raise ValueError("planning changed the consumer target")
            lifecycle("render", target, "--plan", plan)
            lifecycle("verify", target)
            pairs.append((target, plan))
        target, plan = pairs[0]
        if object_json(plan.read_bytes())["plan_id"] != object_json(pairs[1][1].read_bytes())["plan_id"]:
            raise ValueError("candidate plan depends on consumer directory")
        baseline = managed(target)
        if baseline != managed(pairs[1][0]):
            raise ValueError("managed output depends on consumer directory")
        state_before = (target / ".holon/materialization-state.v1.json").read_bytes()
        scope = object_json(plan.read_bytes())["resolved_manifest"]["site_suite_projection"]
        resolved = object_json(resolved_path.read_bytes())
        if digest(materialization_bytes(resolved)) != scope["foundation_resolved_sha256"]:
            raise ValueError("archive resolver and site projection disagree on complete foundation intent")
        if scope["foundation_qualification"] != "unqualified" or "aether-agents" not in scope["unqualified_capabilities"]:
            raise ValueError("candidate promoted omitted foundation requirements")
        noop = output / (variant + "-noop.json")
        lifecycle("plan", target, "--manifest", manifest_path, "--variant", variant, "--output", noop)
        if set(object_json(noop.read_bytes())["summary"]) != {"noop"}:
            raise ValueError("repeated consumer plan is not a no-op")
        changed = object_json(manifest_path.read_bytes())
        changed["parameters"]["site_description"] += " Reviewed candidate update."
        changed_path = output / (variant + "-changed.json")
        changed_path.write_bytes(canonical(changed))
        upgrade = output / (variant + "-upgrade.json")
        lifecycle("plan", target, "--manifest", changed_path, "--variant", variant, "--output", upgrade)
        lifecycle("render", target, "--plan", upgrade)
        if managed(target) == baseline:
            raise ValueError("real consumer update did not change generated output")
        lifecycle("rollback", target)
        if managed(target) != baseline or (target / ".holon/materialization-state.v1.json").read_bytes() != state_before:
            raise ValueError("guarded rollback did not restore exact prior managed output/state")
        lifecycle("verify", target)
        edited = target / "src/app.tsx"
        edited.write_bytes(edited.read_bytes() + b"\n// candidate consumer edit\n")
        before = managed(target)
        lifecycle("rollback", target, success=False)
        if managed(target) != before:
            raise ValueError("refused rollback changed consumer bytes")
        conflict = output / (variant + "-unowned")
        conflict.mkdir()
        (conflict / "README.md").write_text("Owned by the consumer.\n")
        conflict_plan = output / (variant + "-conflict.json")
        lifecycle("plan", conflict, "--manifest", manifest_path, "--variant", variant,
                  "--output", conflict_plan, success=False)
        lifecycle("render", conflict, "--plan", conflict_plan, success=False)
        if (conflict / "README.md").read_text() != "Owned by the consumer.\n":
            raise ValueError("conflict overwrote consumer content")
        variants.append({"variant": variant, "managed_files": len(baseline),
                         "managed_inventory_sha256": digest(canonical(baseline)),
                         "plan_directory_independent": True, "managed_bytes_directory_independent": True,
                         "noop": True, "actual_update": True, "exact_rollback": True,
                         "edited_rollback_refused": True, "unowned_conflict_preserved": True,
                         "foundation_qualification": scope["foundation_qualification"],
                         "unqualified_capabilities": scope["unqualified_capabilities"]})
    denied_target = output / "full-foundation-denied"
    denied_plan = output / "full-foundation-denied.json"
    denied = run(["tools/holon_materialize.py", "plan", "--manifest", "examples/site-suite-generic.manifest.json",
                  "--target", str(denied_target), "--render-source", "blueprints/react-vite/files",
                  "--output", str(denied_plan)], success=False)
    if "provide a pinned Aether distribution" not in denied.stderr or denied_target.exists() or denied_plan.exists():
        raise ValueError("ordinary full-foundation Aether gate was not retained")
    return {"schema": "holon.distribution-clean-room/v1", "outcome": "passed",
            "source_commit": manifest["source_commit"], "version": manifest["version"],
            "python": platform.python_version(), "platform": {"system": platform.system(), "machine": platform.machine()},
            "python_site_packages_enabled": not bool(sys.flags.no_site), "environment_keys": sorted(environment),
            "import_path_scope": "extracted archive and interpreter standard library only",
            "git_checkout_available": False, "provider_credentials": "not-supplied",
            "network_commands": "none", "source_checkout_or_workspace_inputs": "none",
            "variants": variants, "full_foundation_requires_aether": True, "commands": rows,
            "frontend_build_qualification": "deferred; this candidate qualifies source materialization only",
            "publication": "not-performed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--consume", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--work", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.consume:
        print(json.dumps(consume(args.consume, args.work), sort_keys=True))
        return
    if not args.candidate:
        parser.error("--candidate is required")
    candidate = object_json(args.candidate.read_bytes())
    archive = args.candidate.parent / safe_path(candidate["archive"])
    with tempfile.TemporaryDirectory(prefix="holon82-clean-room-") as temporary:
        base = Path(temporary)
        verified = verify(archive, candidate["archive_sha256"], base / "extracted")
        root = base / "extracted/holon"
        executable = Path(sys.executable).resolve()
        result = subprocess.run([str(executable), "-B", "-S", str(root / "tools/qualify_distribution_candidate.py"),
                                 "--consume", str(root), "--work", str(base / "consumer-output")],
                                cwd=root, env={"PATH": str(executable.parent), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
                                text=True, capture_output=True, check=False)
        if result.returncode:
            parser.exit(1, "clean-room qualification failed: " + result.stderr[-2000:])
        receipt = object_json(result.stdout.encode())
        receipt["archive"] = verified
        if args.result:
            with args.result.open("xb") as stream:
                stream.write(canonical(receipt))
        print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
