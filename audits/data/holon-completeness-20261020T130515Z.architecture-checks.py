"""Bounded read-only Holon documentation checks; no authority or conformance claim."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml


def inspect(root: Path) -> dict:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    files = subprocess.check_output(["git", "ls-files", "--", "*.md"], cwd=root, text=True).splitlines()
    documents = {}
    missing = []
    checked = 0
    skipped = 0
    for relative in files:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        if path.parent == root and text.startswith("---\n"):
            frontmatter = yaml.safe_load(text.split("---", 2)[1])
            if isinstance(frontmatter, dict) and frontmatter.get("schema") == "aether.architecture-document/v1":
                documents[relative] = frontmatter
        for match in re.finditer(r"!?\[[^\]\n]+\]\(([^)\n]+)\)", text):
            destination = match.group(1).strip().split(" ", 1)[0].strip("<>")
            parsed = urlsplit(destination)
            if parsed.scheme or destination.startswith("#") or not parsed.path:
                skipped += 1
                continue
            if any(token in parsed.path for token in ("{{", "${", "<", ">")):
                skipped += 1
                continue
            checked += 1
            target = (path.parent / unquote(parsed.path)).resolve()
            if not target.exists():
                missing.append({"source": relative, "line": text.count("\n", 0, match.start()) + 1, "destination": destination})
    ids = [item["id"] for item in documents.values()]
    duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
    graph = {item["id"]: item.get("depends_on", []) for item in documents.values()}
    unknown = sorted({dependency for dependencies in graph.values() for dependency in dependencies if dependency not in graph})
    cycles = []
    visited = set()
    def visit(node: str, stack: list[str]) -> None:
        if node in stack:
            cycles.append(stack[stack.index(node):] + [node])
            return
        if node in visited:
            return
        for dependency in graph.get(node, []):
            visit(dependency, stack + [node])
        visited.add(node)
    for identifier in graph:
        visit(identifier, [])
    audit_paths = subprocess.check_output(["git", "log", "--all", "--format=%H", "--", "audits", ".audits"], cwd=root, text=True).splitlines()
    tracked = subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines()
    return {
        "format": "holon.audit-documentation-checks/v1",
        "format_status": "audit-local-observation-not-production-contract",
        "revision": revision,
        "runtime": {"python": sys.version.split()[0], "pyyaml": yaml.__version__},
        "markdown": {"tracked_files": len(files), "checked_relative_inline_destinations": checked, "skipped_external_fragment_or_template_destinations": skipped, "missing_destinations": missing},
        "architecture_graph": {"document_count": len(documents), "duplicate_ids": duplicate_ids, "unknown_depends_on_ids": unknown, "cycles": cycles, "statuses": {relative: item["status"] for relative, item in documents.items()}, "graph": graph},
        "history": {"prior_audit_path_commits_in_all_reachable_refs": len(audit_paths), "tracked_audit_paths": [path for path in tracked if path.startswith(("audits/", ".audits/"))], "tracked_staging_paths": [path for path in tracked if path.startswith(".staging/")]},
        "limits": ["Checks inline Markdown destination existence only; anchors, external URLs, reference-style destinations, rendering and prose semantics are excluded.", "The 18-document graph check covers declared root architecture IDs and depends_on edges, not the full Mermaid graph or governing specification conformance.", "No repository audit reports were found under the inspected canonical audit paths; upstream-audit.json files are source-intake evidence rather than prior repository completeness reports."]
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.repository.resolve())
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"revision": result["revision"], "markdown": result["markdown"], "architecture_documents": result["architecture_graph"]["document_count"], "cycles": result["architecture_graph"]["cycles"], "unknown_ids": result["architecture_graph"]["unknown_depends_on_ids"], "history": result["history"]}, indent=2))
