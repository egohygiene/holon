"""Compare the unchanged continuity fixture checker with full/shallow inputs.

All checkouts and the native binary are caller-supplied local audit inputs.
This script creates only temporary local clones and fixture repositories.
It never changes a supplied checkout or a retained artifact-contract file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def run(argv: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=180)


def git(root: Path, *args: str) -> str:
    result = run(["git", *args], cwd=root)
    if result.returncode:
        raise RuntimeError("local Git input inspection failed")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "holon-source",
        "aether-source",
        "hygiene-source",
        "egolint-source",
        "egolint-binary",
        "antidote-full-source",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    full = args.antidote_full_source.resolve()
    if git(full, "rev-parse", "--is-shallow-repository") != "false":
        raise RuntimeError("the full Antidote source must have complete local history")
    holon = args.holon_source.resolve()
    source_revision = git(full, "rev-parse", "HEAD")
    source_tree = git(full, "rev-parse", "HEAD^{tree}")
    with tempfile.TemporaryDirectory(prefix="holon-audit-native-depth-") as temporary:
        shallow = Path(temporary) / "antidote-shallow"
        cloned = run(["git", "clone", "--quiet", "--depth", "1", full.as_uri(), str(shallow)])
        if cloned.returncode:
            raise RuntimeError("could not create a disposable local depth-one clone")
        identities_match = (
            git(shallow, "rev-parse", "HEAD") == source_revision
            and git(shallow, "rev-parse", "HEAD^{tree}") == source_tree
        )
        outcomes = []
        for kind, source in (("full-history", full), ("depth-one", shallow)):
            argv = [
                sys.executable,
                str(holon / "tools/check_repository_continuity_fixtures.py"),
                "--aether-source", str(args.aether_source.resolve()),
                "--hygiene-source", str(args.hygiene_source.resolve()),
                "--egolint-source", str(args.egolint_source.resolve()),
                "--egolint-binary", str(args.egolint_binary.resolve()),
                "--antidote-source", str(source),
            ]
            result = run(argv, cwd=holon)
            output = result.stdout + result.stderr
            outcomes.append({
                "source_history": kind,
                "exit_code": result.returncode,
                "scenario_pass_lines": sum(line.startswith("PASS ") for line in result.stdout.splitlines()),
                "artifact_contract_passed": "PASS repository-continuity artifact contracts" in result.stdout,
                "artifact_contract_mismatch": "repository-continuity artifact contract changed without review" in result.stderr,
                "raw_output_sha256": hashlib.sha256(output.encode()).hexdigest(),
            })
        reproduced = (
            identities_match
            and outcomes[0]["exit_code"] == 1
            and outcomes[0]["artifact_contract_mismatch"]
            and outcomes[0]["scenario_pass_lines"] == 6
            and outcomes[1]["exit_code"] == 0
            and outcomes[1]["artifact_contract_passed"]
        )
        print(json.dumps({
            "scope": "Synthetic local fixture proof only; no canonical snapshots changed",
            "holon_source_revision": git(holon, "rev-parse", "HEAD"),
            "antidote_source_revision": source_revision,
            "antidote_source_tree": source_tree,
            "commit_and_tracked_tree_equal": identities_match,
            "outcomes": outcomes,
            "reproduced": reproduced,
        }, indent=2))
        return 0 if reproduced else 2


if __name__ == "__main__":
    raise SystemExit(main())
