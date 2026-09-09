#!/usr/bin/env python3
"""Prove repository-continuity reconciliation across publish-safe fixtures.

The checker is deliberately offline. Callers provide clean local checkouts at
the exact revisions declared by Holon's profile plus a caller-built EgoLint
binary. No branch, network fallback, credential, clock, or provider client is
used while constructing or validating the disposable repositories.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from materialization.common import canonical_bytes, pretty_json_bytes  # noqa: E402
from materialization.continuity import (  # noqa: E402
    MANAGED_BEGIN,
    MANAGED_END,
    STATE_RELATIVE_PATH,
    MaterializationError,
    apply_continuity_plan,
    build_continuity_plan,
    rollback_continuity_target,
    validate_continuity_request,
    verify_continuity_target,
)
from repository_continuity_profile import (  # noqa: E402
    load_json,
    validate_profile,
    verify_sources,
)

CASES_PATH = Path("tests/fixtures/repository-continuity/cases.v1.json")
MIGRATION_MAP_PATH = Path(
    "tests/fixtures/repository-continuity/antidote-migration-map.v1.json"
)
SNAPSHOTS_PATH = Path(
    "tests/fixtures/repository-continuity/artifact-contracts.json"
)
PROFILE_FILE = Path("catalog/repository-continuity-materialization.json")
EGO_POLICY_PATH = Path(".egolint-fixture/repository-continuity.toml")
EGO_REPORT_PATH = Path(".reports/egolint/repository-continuity.json")
SURFACES = (
    "CONTINUITY.md",
    "AGENTS.md",
    ".github/copilot-instructions.md",
    "CLAUDE.md",
)
EXPECTED_FIXTURE_IDS = {
    "research-publication",
    "library-cli",
    "site-application",
    "organization-meta",
    "private-creative",
    "antidote-migration",
}
EXPECTED_COVERAGE = {
    "new",
    "existing",
    "provisional",
    "opt-out",
    "unsupported",
    "conflict",
    "upgrade",
    "parallel",
    "rollback",
    "antidote-migration",
}
EXPECTED_EGOLINT_VERSION = "egolint 0.1.0-alpha.1"
EXPECTED_EGOLINT_SCHEMA_SHA256 = (
    "cf865611886602765a5c56efc89b2910c1bbdde3d75c7668c5e9cdcea994848b"
)
EXPECTED_EGOLINT_REPORT_SCHEMA_SHA256 = (
    "fc9d7c1a9175209e0c958cf74dded0cb974ff86c7d46130e7a7ae731f0147276"
)
EXPECTED_POSITIVE_DIAGNOSTICS = {"EGO-CONTINUITY-CONTRACT-001"}
TIMESTAMP = "2026-09-09T00:00:00Z"
IMMUTABLE_REFERENCE = (
    "https://github.com/egohygiene/aether/blob/"
    "b7597301c4d22a9bcd580967b5753138bb368111/"
    "library/organization/specs/methodology/repository-continuity.spec.md"
)
PRIOR_MANAGED_BLOCK_MARKER = "<!-- holon-fixture-prior-managed-block/v1 -->"


class FixtureError(RuntimeError):
    """Raised when a fixture cannot prove its reviewed contract."""


def digest(content: bytes) -> str:
    """Return one lowercase SHA-256 digest."""
    return hashlib.sha256(content).hexdigest()


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run one local command and retain bounded diagnostics on failure."""
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        stdout = result.stdout.decode("utf-8", errors="replace")[-4000:]
        stderr = result.stderr.decode("utf-8", errors="replace")[-4000:]
        raise FixtureError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return result


def write_bytes(path: Path, content: bytes) -> None:
    """Write one disposable fixture file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_text(path: Path, content: str) -> None:
    """Write one UTF-8 disposable fixture file."""
    write_bytes(path, content.encode("utf-8"))


def read_optional(path: Path) -> bytes | None:
    """Read a file when it exists."""
    return path.read_bytes() if path.is_file() else None


def require_clean_revision(path: Path, repository: str, revision: str) -> None:
    """Bind a caller-supplied checkout to one clean immutable commit."""
    if not path.is_dir() or not (path / ".git").exists():
        raise FixtureError(f"{repository} source is not a Git checkout: {path}")
    observed = run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"], cwd=path
    ).stdout.decode("ascii").strip()
    if observed != revision:
        raise FixtureError(
            f"{repository} source revision mismatch: expected {revision}, got {observed}"
        )
    dirty = run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=path
    ).stdout
    if dirty:
        raise FixtureError(f"{repository} source checkout has local changes")


def require_regular_binary(path: Path) -> Path:
    """Reject a binary path containing any caller-supplied symbolic link."""
    absolute = path if path.is_absolute() else (Path.cwd() / path).absolute()
    candidate = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        candidate /= part
        if candidate.is_symlink():
            raise FixtureError(f"EgoLint binary path contains a symlink: {candidate}")
    if not absolute.is_file():
        raise FixtureError(f"EgoLint binary is missing or not regular: {absolute}")
    return absolute.resolve(strict=True)


def validate_fixture_contract(cases: dict[str, Any]) -> None:
    """Validate the closed six-fixture case matrix."""
    expected_keys = {
        "schema_version",
        "evaluation_date",
        "git_fixture",
        "source_pins",
        "required_coverage",
        "fixtures",
    }
    if set(cases) != expected_keys:
        raise FixtureError("fixture case catalog has missing or unknown fields")
    if cases["schema_version"] != "holon.repository-continuity-fixtures/v1":
        raise FixtureError("fixture case catalog has an unsupported schema version")
    if cases["evaluation_date"] != "2026-09-09":
        raise FixtureError("fixture evaluation date changed without contract review")
    git_fixture = cases["git_fixture"]
    if not isinstance(git_fixture, dict) or set(git_fixture) != {
        "author_email",
        "author_name",
        "timestamp",
    }:
        raise FixtureError("fixture Git identity contract is malformed")
    pins = cases["source_pins"]
    if not isinstance(pins, dict) or set(pins) != {
        "aether",
        "hygiene",
        "egolint",
        "antidote",
    }:
        raise FixtureError("fixture source pins are incomplete")
    for name, pin in pins.items():
        if not isinstance(pin, dict) or set(pin) != {"repository", "revision"}:
            raise FixtureError(f"fixture source pin is malformed: {name}")
        if not isinstance(pin["revision"], str) or len(pin["revision"]) != 40:
            raise FixtureError(f"fixture source revision is not full length: {name}")
    if set(cases["required_coverage"]) != EXPECTED_COVERAGE:
        raise FixtureError("fixture catalog does not declare exact issue #45 coverage")
    fixtures = cases["fixtures"]
    if not isinstance(fixtures, list) or len(fixtures) != len(EXPECTED_FIXTURE_IDS):
        raise FixtureError("fixture catalog must contain exactly six fixtures")
    ids: set[str] = set()
    coverage: set[str] = set()
    fixture_keys = {
        "id",
        "repository",
        "repository_profile",
        "repository_class",
        "visibility",
        "providers",
        "setup",
        "requirements",
    }
    for fixture in fixtures:
        if not isinstance(fixture, dict) or set(fixture) != fixture_keys:
            raise FixtureError("fixture record has missing or unknown fields")
        if fixture["id"] in ids:
            raise FixtureError(f"duplicate fixture ID: {fixture['id']}")
        ids.add(fixture["id"])
        requirements = fixture["requirements"]
        if not isinstance(requirements, list) or not requirements:
            raise FixtureError(f"fixture requirements are empty: {fixture['id']}")
        coverage.update(requirements)
        if fixture["visibility"] == "private" and fixture["id"] != "private-creative":
            raise FixtureError("only the synthetic private fixture may be private")
    if ids != EXPECTED_FIXTURE_IDS or coverage != EXPECTED_COVERAGE:
        raise FixtureError("fixture matrix does not cover the exact reviewed cases")


def verify_inputs(
    project: Path,
    cases: dict[str, Any],
    sources: dict[str, Path],
    antidote_source: Path,
    egolint_binary: Path,
) -> dict[str, Any]:
    """Verify source commits, all profile artifacts, and EgoLint fingerprints."""
    pins = cases["source_pins"]
    for name, role in (
        ("aether", "portable-contract"),
        ("hygiene", "organization-policy"),
        ("egolint", "validator"),
    ):
        pin = pins[name]
        require_clean_revision(sources[role], pin["repository"], pin["revision"])
    antidote_pin = pins["antidote"]
    require_clean_revision(
        antidote_source,
        antidote_pin["repository"],
        antidote_pin["revision"],
    )
    profile = load_json(project / PROFILE_FILE)
    errors = validate_profile(profile)
    if errors:
        raise FixtureError("repository-continuity profile is invalid: " + "; ".join(errors))
    verified_artifacts = verify_sources(profile, sources)
    verified_binary = require_regular_binary(egolint_binary)
    version = run([str(verified_binary), "--version"]).stdout.decode("utf-8").strip()
    if version != EXPECTED_EGOLINT_VERSION:
        raise FixtureError(f"unexpected EgoLint version: {version}")
    schema = run([str(verified_binary), "schema", "repository-continuity"]).stdout
    report_schema = run(
        [str(verified_binary), "schema", "repository-continuity-report"]
    ).stdout
    if digest(schema) != EXPECTED_EGOLINT_SCHEMA_SHA256:
        raise FixtureError("EgoLint continuity schema fingerprint does not match the pin")
    if digest(report_schema) != EXPECTED_EGOLINT_REPORT_SCHEMA_SHA256:
        raise FixtureError("EgoLint continuity report fingerprint does not match the pin")
    return {
        "profile_sha256": digest((project / PROFILE_FILE).read_bytes()),
        "verified_profile_artifacts": verified_artifacts,
        "egolint": {
            "repository": pins["egolint"]["repository"],
            "revision": pins["egolint"]["revision"],
            "version": version,
            "continuity_schema_sha256": digest(schema),
            "report_schema_sha256": digest(report_schema),
        },
    }


def fixture_policy(repository: str, visibility: str, providers: list[str]) -> str:
    """Render the pinned EgoLint policy with fixture-local projection paths."""
    paths = {
        "github-copilot": ".github/copilot-instructions.md",
        "claude-code": "CLAUDE.md",
    }
    projection_lines = ",\n".join(f'  "{paths[provider]}"' for provider in providers)
    projections = f"[\n{projection_lines}\n]" if projection_lines else "[]"
    return f'''schema-version = 1
id = "egolint.repository-continuity-validation/v1"
repository = "{repository}"
rollout-stage = "observe"
repository-kind = "standard"
visibility = "{visibility}"
lifecycle = "active"
continuity-path = "CONTINUITY.md"
agents-path = "AGENTS.md"
provider-projections = {projections}
profile-path = "vendor/hygiene/repository-continuity-policy.v1.json"
schema-path = "vendor/aether/aether.repository-continuity.v1.schema.json"
instruction-path = "vendor/aether/repository-continuity.INSTRUCTION.md"
template-path = "vendor/aether/CONTINUITY.template.md"

[hygiene-lock]
id = "egohygiene.repository-continuity-policy/v1"
version = "1.0.0-alpha.1"
status = "proposed"
source-repository = "egohygiene/hygiene"
source-revision = "43386f5749116717585ead7459b4945e0ac50d06"
source-path = "catalog/repository-continuity-policy.json"
digest = "a17178482d67e141009b07d6715727612fbf7f372be8c471a124149752c2ca64"

[aether-lock]
id = "aether.repository-continuity/v1"
selected-version = "1.0.0"
minimum-version = "1.0.0"
maximum-version-exclusive = "2.0.0"
lifecycle = "draft"
release-included = false
source-repository = "egohygiene/aether"
source-revision = "b7597301c4d22a9bcd580967b5753138bb368111"
source-path = "library/organization/specs/methodology/repository-continuity.spec.md"
'''


def prepare_validation_files(
    target: Path,
    fixture: dict[str, Any],
    aether_source: Path,
    hygiene_source: Path,
) -> None:
    """Install exact local validation projections and harmless canonical docs."""
    copies = {
        hygiene_source / "catalog/repository-continuity-policy.json": (
            target / "vendor/hygiene/repository-continuity-policy.v1.json"
        ),
        aether_source / "catalog/schemas/aether.repository-continuity.v1.schema.json": (
            target / "vendor/aether/aether.repository-continuity.v1.schema.json"
        ),
        aether_source
        / "library/organization/instructions/repository-continuity/INSTRUCTION.md": (
            target / "vendor/aether/repository-continuity.INSTRUCTION.md"
        ),
        aether_source
        / "library/organization/skills/methodology/maintain-repository-continuity/templates/CONTINUITY.template.md": (
            target / "vendor/aether/CONTINUITY.template.md"
        ),
    }
    for source, destination in copies.items():
        write_bytes(destination, source.read_bytes())
    write_text(
        target / EGO_POLICY_PATH,
        fixture_policy(
            fixture["repository"], fixture["visibility"], fixture["providers"]
        ),
    )
    context = (
        "# Ecosystem context\n\n"
        "<!-- egohygiene-context: repository-context/v2 -->\n"
        'generated-by: "egohygiene/hygiene:repository-context@2.0.0"\n'
        'continuity-policy: "egohygiene.repository-continuity-policy/v1@1.0.0-alpha.1"\n'
    )
    if not (target / "docs/ecosystem/CONTEXT.md").exists():
        write_text(target / "docs/ecosystem/CONTEXT.md", context)
    defaults = {
        "README.md": "# Synthetic continuity fixture\n\nPublic-safe local evidence only.\n",
        "ARCHITECTURE.md": "# Architecture\n\nThe fixture has no external authority or network dependency.\n",
        "ROADMAP.md": "# Roadmap\n\nValidate one bounded continuity scenario.\n",
    }
    for relative, content in defaults.items():
        if not (target / relative).exists():
            write_text(target / relative, content)


def initialize_repository(target: Path, cases: dict[str, Any]) -> str:
    """Create one byte-reproducible local baseline commit."""
    git_fixture = cases["git_fixture"]
    run(["git", "init", "--initial-branch=main"], cwd=target)
    run(["git", "add", "."], cwd=target)
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_NAME": git_fixture["author_name"],
            "GIT_AUTHOR_EMAIL": git_fixture["author_email"],
            "GIT_AUTHOR_DATE": git_fixture["timestamp"],
            "GIT_COMMITTER_NAME": git_fixture["author_name"],
            "GIT_COMMITTER_EMAIL": git_fixture["author_email"],
            "GIT_COMMITTER_DATE": git_fixture["timestamp"],
        }
    )
    run(
        ["git", "commit", "--no-gpg-sign", "-m", "fixture baseline"],
        cwd=target,
        environment=environment,
    )
    return run(["git", "rev-parse", "HEAD"], cwd=target).stdout.decode("ascii").strip()


def commit_upgrade_baseline(target: Path, cases: dict[str, Any]) -> str:
    """Commit a deterministic prior-profile materialization."""
    git_fixture = cases["git_fixture"]
    run(["git", "add", "."], cwd=target)
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_NAME": git_fixture["author_name"],
            "GIT_AUTHOR_EMAIL": git_fixture["author_email"],
            "GIT_AUTHOR_DATE": git_fixture["timestamp"],
            "GIT_COMMITTER_NAME": git_fixture["author_name"],
            "GIT_COMMITTER_EMAIL": git_fixture["author_email"],
            "GIT_COMMITTER_DATE": git_fixture["timestamp"],
        }
    )
    run(
        ["git", "commit", "--no-gpg-sign", "-m", "prior profile fixture"],
        cwd=target,
        environment=environment,
    )
    return run(["git", "rev-parse", "HEAD"], cwd=target).stdout.decode("ascii").strip()


def common_request(
    fixture: dict[str, Any],
    base_revision: str,
    *,
    parallel: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build one complete offline/provisional Aether request."""
    parallel = parallel or []
    repository = {
        "id": fixture["repository"],
        "visibility": fixture["visibility"],
        "default_branch": "main",
    }
    private = fixture["visibility"] == "private"
    continuity = {
        "schema_version": "aether.repository-continuity/v1",
        "repository": {**repository, "continuity_path": "CONTINUITY.md"},
        "document": {
            "status": "active",
            "updated_at": TIMESTAMP,
            "max_bytes": 16384,
            "max_lines": 240,
            "stale_reason": None,
            "superseded_by": None,
        },
        "scope": {
            "purpose": "Resume one bounded, offline repository-continuity fixture.",
            "includes": [
                "Verified local baseline and candidate state.",
                "Material changes and canonical owners.",
                "Exact validation results and environment limitations.",
                "Blockers, risks, and deferred work.",
                "Next dependency-ready action and roadmap order.",
            ],
            "excludes": [
                "conversation transcripts",
                "duplicated architecture, roadmap, and changelog content",
            ],
            "precedence": [
                "user-and-runtime-instructions",
                "scoped-repository-instructions",
                "live-repository-and-work-tracker-state",
                "canonical-repository-sources",
                "continuity-checkpoint",
            ],
            "canonical_sources": ["README.md", "ARCHITECTURE.md", "ROADMAP.md"],
        },
        "work": {
            "objective": f"Prove the {fixture['id']} continuity fixture without network access.",
            "success_conditions": [
                "The preview, application, verification, no-op replan, and rollback are deterministic.",
                "The contract-fingerprinted EgoLint structural, freshness, and local-Git evidence layers are valid.",
            ],
            "active_issue": None,
            "next": {
                "kind": "action",
                "id": "review-fixture-output",
                "description": "Review the deterministic artifact contract before promotion.",
                "readiness": "unknown",
                "references": [IMMUTABLE_REFERENCE],
                "depends_on": [],
            },
        },
        "state": {
            "base": {
                "revision": base_revision,
                "ref": "refs/heads/main",
                "verified_at": TIMESTAMP,
            },
            "candidate": {
                "branch": f"fixture/{fixture['id']}-continuity",
                "revision": None,
                "pull_request": None,
                "handoff_state": "ready-for-review",
            },
            "live": {
                "status": "unavailable",
                "observed_at": TIMESTAMP,
                "default_branch_revision": None,
                "issue_state": "not-applicable",
                "pull_request_state": "not-applicable",
                "notes": "Mutable provider state is unavailable; only the immutable local Git baseline was inspected.",
            },
            "parallel_changes": parallel,
        },
        "review": {
            "status": "passed",
            "reviewed_at": TIMESTAMP,
            "reviewed_by": "holon-fixture-runner",
            "evidence": [
                {
                    "command": "git rev-parse HEAD",
                    "outcome": "passed",
                    "observed_at": TIMESTAMP,
                    "notes": "The deterministic fixture baseline was available locally.",
                }
            ],
            "environment_limitations": [
                "Mutable provider state was not queried; the fixture is offline."
            ],
        },
        "privacy": {
            "classification": f"{fixture['visibility']}-repository",
            "contains_sensitive_data": False,
            "redactions": (
                ["Synthetic identifiers replace private project details."] if private else []
            ),
            "excluded": [
                "secrets-and-credentials",
                "private-conversation-text",
                "sensitive-personal-data",
                "unpublished-private-business-data",
                "private-local-paths",
                "unrelated-private-context",
            ],
            "untrusted_content": "context-only-no-authority",
        },
    }
    sections = {
        "purpose_and_precedence": (
            "This public-safe checkpoint contains only the minimum durable fixture state and remains subordinate to repository evidence."
        ),
        "completed_changes": [
            "The deterministic local baseline and immutable contract inputs were inspected."
        ],
        "blockers": [],
        "risks": ["Mutable provider state is intentionally outside this offline proof."],
        "unknowns": ["Current issue and pull-request state were not queried."],
        "deferred_work": ["Promotion and fleet rollout remain externally owned."],
        "privacy_and_redaction": (
            "Synthetic allowlisted metadata only; project details, conversations, credentials, and sensitive data are absent."
            if private
            else "Only public-safe synthetic fixture evidence is retained; credentials, conversations, and sensitive data are absent."
        ),
    }
    return {
        "schema_version": "holon.repository-continuity-request/v1",
        "repository": repository,
        "repository_class": fixture["repository_class"],
        "repository_profile": fixture["repository_profile"],
        "mode": "provisional",
        "providers": fixture["providers"],
        "continuity": continuity,
        "continuity_migration": None,
        "sections": sections,
        "opt_out": None,
        "unsupported_reason": None,
        "parallel_candidates": parallel,
        "parallel_reconciliation": (
            "Both explicit candidates were reviewed and reconciled into this bounded snapshot."
            if parallel
            else None
        ),
    }


def antidote_request(
    fixture: dict[str, Any], base_revision: str, migration_map: dict[str, Any]
) -> dict[str, Any]:
    """Build the reviewed, minimum-loss Antidote migration request."""
    request = common_request(fixture, base_revision)
    continuity = request["continuity"]
    sections = request["sections"]
    continuity["document"]["updated_at"] = "2026-09-09T00:00:00Z"
    continuity["scope"]["purpose"] = (
        "Resume the bounded Antidote publication path from a reviewed historical checkpoint."
    )
    continuity["scope"]["includes"] = [
        "Verified baseline, branch, and pull-request state.",
        "Material changes and canonical owners.",
        "Exact validation results and environment limitations.",
        "Blockers, risks, and deferred work.",
        "Next dependency-ready issue and roadmap order.",
    ]
    continuity["scope"]["canonical_sources"] = [
        "AGENTS.md",
        "ARCHITECTURE.md",
        "ROADMAP.md",
        "paper/roadmap.md",
        "paper/paper.tex",
        "research/notes/CLAIM_LEDGER.md",
    ]
    continuity["work"] = {
        "objective": "Migrate the useful Antidote handoff state without widening the publication scope.",
        "success_conditions": [
            "Every complete legacy section is retained, mapped, or explicitly superseded with immutable evidence.",
            "The publication path, claim boundaries, and exact validation evidence remain reviewable.",
        ],
        "active_issue": None,
        "next": {
            "kind": "issue",
            "id": "egohygiene/antidote#48",
            "description": "Run the reviewable-paper and live-publication gate.",
            "readiness": "unknown",
            "references": ["https://github.com/egohygiene/antidote/issues/48"],
            "depends_on": ["egohygiene/antidote#47"],
        },
    }
    continuity["state"] = {
        "base": {
            "revision": base_revision,
            "ref": "refs/heads/main",
            "verified_at": "2026-09-07T19:20:47Z",
        },
        "candidate": {
            "branch": None,
            "revision": None,
            "pull_request": None,
            "handoff_state": "no-active-change",
        },
        "live": {
            "status": "unavailable",
            "observed_at": TIMESTAMP,
            "default_branch_revision": None,
            "issue_state": "unknown",
            "pull_request_state": "unknown",
            "notes": "The pinned Git merge is available locally; current mutable tracker state is unavailable and must be rechecked.",
        },
        "parallel_changes": [],
    }
    continuity["review"] = {
        "status": "passed",
        "reviewed_at": "2026-09-07T19:20:47Z",
        "reviewed_by": "antidote-maintainers",
        "evidence": [
            {
                "command": "make test",
                "outcome": "passed",
                "observed_at": "2026-09-07T19:20:47Z",
                "notes": "102 tests pass.",
            },
            {
                "command": "make check-all",
                "outcome": "passed",
                "observed_at": "2026-09-07T19:20:47Z",
                "notes": "Neutral and Ego Hygiene PDF, accessible HTML, provenance, and arXiv-source outputs build reproducibly.",
            },
            {
                "command": "task check-all",
                "outcome": "passed",
                "observed_at": "2026-09-07T19:20:47Z",
                "notes": "Task 3.53.1 passes the same two-theme gate.",
            },
            {
                "command": "task check-site",
                "outcome": "passed",
                "observed_at": "2026-09-07T19:20:47Z",
                "notes": "Holon 2600baff6f6d944094da81b77e1a9a2e9e7a1cd6 Pages staging, routes, manifests, and checksums pass.",
            },
            {
                "command": "manual PDF inspection",
                "outcome": "passed",
                "observed_at": "2026-09-07T19:20:47Z",
                "notes": "The 63-page title, abstract, conclusion, and claim-index pages were visually inspected after pagination repair.",
            },
            {
                "command": "source-governance validation",
                "outcome": "passed",
                "observed_at": "2026-09-07T19:20:47Z",
                "notes": "96 catalog sources, 48 verified bibliography entries, 43 manuscript citation keys, 22 architecture mappings, 9 comparator rows, and 9 novelty decisions pass.",
            },
        ],
        "environment_limitations": [
            "Current GitHub issue and pull-request state was not queried by this offline migration."
        ],
    }
    sections.update(
        {
            "purpose_and_precedence": (
                "This file is the durable handoff checkpoint for work that spans conversations. It summarizes current execution state; it does not override `AGENTS.md`, the architecture corpus, governed research records, roadmaps, or live GitHub state."
            ),
            "completed_changes": [
                "Before issue #47, the last merged baseline was `main` at `f4dc9326e07ad99d08557d0695e2bee8918657ec` via PR #88, completing #46. PR #90 on `codex/issue-47-synthesis` then completed issue #47 and is merged in the pinned base. Work remains one scoped issue and one reviewable pull request at a time; the maintainer merges.",
                "Paper `0.1.0` remains `draft` until #48. Title: *Antidote: A Governed Framework for Inspectable Person-and-Moment Generative Audio Journeys*. Subtitle: *System Design and Prospective Feasibility Protocol*.",
                "RQ1 is answered only at system-design level; RQ2 technical feasibility and RQ3 within-person advisory usefulness remain unanswered. Evidence remains a synthetic rule-guided session with a deterministic mock worker; no qualifying real-model package or formal human study exists, and collection authority remains false.",
                "The manuscript has 17 active final visuals and no active prose placeholders; two evidence-contingent Results figures remain retired pending qualifying T0 and T1 packages. Cited and additional-reading bibliography sources remain separate governed sets and must not be reduced to in-text citations.",
                "Issue #47 finalized the evidence-bounded abstract and subtitle metadata; replaced the conclusion reservation with a design-level answer, five bounded contributions, and RQ2/RQ3 gates; added the appendix claim-class index; removed two prose placeholders and tightened Related Work and Discussion transitions; advanced manuscript contract `0.5.0`, reconciled the claim ledger, and updated regression tests; and added #89 after #74 and before #75, distinct from demo-dependent product-site work #63--#66.",
            ],
            "blockers": [],
            "risks": [
                "#48 owns holistic review and live verification of the merged custom-domain paper and PDF; local Pages staging is not live-publication proof. #89 owns later publication-hub aesthetic and usability polish and must not expand the manuscript gate.",
                "Magazine and LinkedIn translations must not add efficacy, mechanism, safety, or completed-study claims. Human collection, autonomous personalization, and adaptation remain inactive.",
            ],
            "unknowns": [
                "Current mutable GitHub issue state must be rechecked before this historical fixture is used operationally."
            ],
            "deferred_work": [
                "After #48, preserve this order: #70 freeze the magazine contract/page map; #71 author evidence-traceable source; #72 design and visuals; #73 web/digital/print artifacts; #74 publish and activate the hub slot; #89 publication-first launch-site polish; #75 combined versioned release/archive; #76 human-approved LinkedIn launch.",
                "#89 remains after #74 and before #75. Separately gated prototype and real-model work must not delay publication unless a paper claim depends on it.",
            ],
            "privacy_and_redaction": (
                "Public-repository checkpoint; prohibited private journal, therapy, health, participant, credential, model-token, conversation, sensitive-personal, unpublished-business, private-path, and unrelated-context data is absent."
            ),
        }
    )
    migration_file = next(
        item for item in migration_map["source"]["files"] if item["path"] == "CONTINUITY.md"
    )
    request["continuity_migration"] = {
        "expected_sha256": migration_file["sha256"],
        "reason": (
            "Reviewed lossless migration of every complete legacy Antidote checkpoint section at the pinned merge revision."
        ),
        "evidence_url": (
            "https://github.com/egohygiene/antidote/blob/"
            f"{base_revision}/CONTINUITY.md"
        ),
    }
    return request


def assert_request(request: dict[str, Any], profile: dict[str, Any]) -> None:
    """Reject a fixture request that bypasses the public validator."""
    errors = validate_continuity_request(request, profile)
    if errors:
        raise FixtureError("fixture request is invalid: " + "; ".join(errors))


def operation_contract(operation: dict[str, Any]) -> dict[str, Any]:
    """Reduce one plan operation to its stable reviewed evidence."""
    return {
        "path": operation["path"],
        "action": operation["action"],
        "previous_sha256": operation["previous_sha256"],
        "proposed_sha256": operation["proposed_sha256"],
        "managed_block_sha256": operation["managed_block_sha256"],
        "diff_sha256": digest(operation["diff"].encode("utf-8")),
    }


def surface_preimages(target: Path) -> dict[str, bytes | None]:
    """Capture every approved surface and adapter state before application."""
    return {
        **{relative: read_optional(target / relative) for relative in SURFACES},
        STATE_RELATIVE_PATH: read_optional(target / STATE_RELATIVE_PATH),
    }


def surface_digests(target: Path) -> dict[str, str]:
    """Record every materialized surface digest."""
    result: dict[str, str] = {}
    for relative in SURFACES:
        path = target / relative
        if path.is_file():
            result[relative] = digest(path.read_bytes())
    return result


def verify_private_surface(target: Path) -> dict[str, Any]:
    """Enforce a small synthetic allowlist on the rendered private checkpoint."""
    content = (target / "CONTINUITY.md").read_bytes()
    text = content.decode("utf-8")
    required = (
        'classification: "private-repository"',
        "contains_sensitive_data: false",
        "Synthetic allowlisted metadata only",
        "fixture-org/private-creative",
    )
    for value in required:
        if value not in text:
            raise FixtureError(f"private fixture omitted required safety marker: {value}")
    prohibited = (
        re.compile(r"(?:gh[pousr]_|sk-)[A-Za-z0-9_-]{12,}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"(?:/Users/[^/\s]+|/home/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+)"),
        re.compile(r"github\.com/fixture-org/private-creative/(?:issues|pull)/"),
    )
    if any(pattern.search(text) for pattern in prohibited):
        raise FixtureError("private fixture contains prohibited or mutable project data")
    if len(content) > 10000 or len(content.splitlines()) > 200:
        raise FixtureError("private fixture exceeds its minimum-information proof budget")
    return {
        "bytes": len(content),
        "lines": len(content.splitlines()),
        "classification": "private-repository",
        "contains_sensitive_data": False,
    }


def remove_egolint_report(target: Path) -> None:
    """Remove only the disposable validator report before rollback comparison."""
    report = target / EGO_REPORT_PATH
    if report.exists():
        report.unlink()
    for relative in (Path(".reports/egolint"), Path(".reports")):
        directory = target / relative
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()


def egolint_environment() -> dict[str, str]:
    """Prevent ambient EgoLint configuration or credentials from entering proof."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("EGOLINT_")
        and key not in {"GH_TOKEN", "GITHUB_TOKEN", "GITLAB_TOKEN"}
    }
    environment["CI"] = "1"
    environment["NO_COLOR"] = "1"
    return environment


def validate_with_egolint(
    target: Path,
    fixture: dict[str, Any],
    egolint_binary: Path,
    base_revision: str,
    disposition: str,
) -> tuple[dict[str, Any], bytes]:
    """Run and semantically inspect a contract-fingerprinted offline validator."""
    remove_egolint_report(target)
    command = [
        str(egolint_binary),
        "--workspace",
        str(target),
        "validate",
        "--repository-continuity",
        EGO_POLICY_PATH.as_posix(),
        "--continuity-base",
        base_revision,
        "--continuity-head",
        "working-tree",
        "--continuity-disposition",
        disposition,
        "--continuity-transition",
        "pull-request",
        "--continuity-live-verification",
        "unavailable",
        "--continuity-evaluation-date",
        "2026-09-09",
    ]
    run(command, environment=egolint_environment())
    report_path = target / EGO_REPORT_PATH
    if not report_path.is_file():
        raise FixtureError("EgoLint did not emit its repository-continuity report")
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    if report.get("contract") != "egolint.repository-continuity-report/v1":
        raise FixtureError("EgoLint report contract is not v1")
    if report.get("repository") != fixture["repository"]:
        raise FixtureError("EgoLint report repository does not match the fixture")
    if report.get("rollout_stage") != "observe" or report.get("applicability") != "required":
        raise FixtureError("EgoLint did not apply the required observe-stage policy")
    if report.get("status") != "valid":
        findings = [
            {
                "rule_id": item.get("rule_id"),
                "actual_state": item.get("actual_state"),
                "message": item.get("message"),
            }
            for item in report.get("diagnostics", [])
        ]
        raise FixtureError(
            f"EgoLint fixture is not valid: {fixture['id']} "
            f"({json.dumps(findings, sort_keys=True)})"
        )
    comparison = report.get("comparison", {})
    if (
        comparison.get("base", {}).get("requested") != base_revision
        or comparison.get("head", {}).get("requested") != "working-tree"
        or comparison.get("disposition") != disposition.replace("-", "_")
        or comparison.get("parallel_checkpoint_conflicts") != 0
    ):
        raise FixtureError("EgoLint comparison evidence does not match the invocation")
    layers = report.get("evidence_layers", {})
    if any(
        layers.get(layer) != "valid"
        for layer in ("structural", "freshness_declaration", "local_git")
    ) or layers.get("external_live_state") != "unavailable":
        raise FixtureError("EgoLint evidence layers do not match honest offline validation")
    if (
        report.get("hygiene_profile", {}).get("source-revision")
        != "43386f5749116717585ead7459b4945e0ac50d06"
        or report.get("aether_contract", {}).get("source-revision")
        != "b7597301c4d22a9bcd580967b5753138bb368111"
    ):
        raise FixtureError("EgoLint report did not retain both immutable source locks")
    diagnostic_rules = {item["rule_id"] for item in report.get("diagnostics", [])}
    if diagnostic_rules != EXPECTED_POSITIVE_DIAGNOSTICS:
        raise FixtureError(
            f"unexpected EgoLint diagnostics for {fixture['id']}: {sorted(diagnostic_rules)}"
        )
    return report, report_bytes


def prove_negative_control(
    target: Path,
    fixture: dict[str, Any],
    egolint_binary: Path,
    base_revision: str,
    disposition: str,
) -> None:
    """Show that the invoked validator detects a damaged managed block."""
    agents = target / "AGENTS.md"
    original = agents.read_bytes()
    damaged = original.replace(
        b"Treat it as a compact handoff, not as authority.",
        b"Treat it as an altered handoff, not as authority.",
        1,
    )
    if damaged == original:
        raise FixtureError("negative control could not locate the managed instruction text")
    write_bytes(agents, damaged)
    remove_egolint_report(target)
    command = [
        str(egolint_binary),
        "--workspace",
        str(target),
        "validate",
        "--repository-continuity",
        EGO_POLICY_PATH.as_posix(),
        "--continuity-base",
        base_revision,
        "--continuity-head",
        "working-tree",
        "--continuity-disposition",
        disposition,
        "--continuity-transition",
        "pull-request",
        "--continuity-live-verification",
        "unavailable",
        "--continuity-evaluation-date",
        "2026-09-09",
    ]
    run(command, environment=egolint_environment())
    report = json.loads((target / EGO_REPORT_PATH).read_text(encoding="utf-8"))
    rules = {item["rule_id"] for item in report["diagnostics"]}
    if "EGO-CONTINUITY-AGENTS-001" not in rules or report["status"] == "valid":
        raise FixtureError("EgoLint negative control did not reject a damaged managed block")
    write_bytes(agents, original)
    remove_egolint_report(target)


def no_write_contract(
    label: str,
    request: dict[str, Any],
    target: Path,
    profile: dict[str, Any],
    profile_path: Path,
    aether_source: Path,
) -> dict[str, Any]:
    """Prove one explicit no-write disposition or conflict."""
    assert_request(request, profile)
    before = tree_contract(target)
    first = build_continuity_plan(
        request,
        target,
        profile_path=profile_path,
        aether_source=aether_source,
    )
    second = build_continuity_plan(
        copy.deepcopy(request),
        target,
        profile_path=profile_path,
        aether_source=aether_source,
    )
    if first != second or first["next_state"] is not None:
        raise FixtureError(f"{label} no-write plan is not deterministic and closed")
    if first["summary"].get("conflict", 0):
        if any(
            operation["action"] == "conflict" and operation["diff"]
            for operation in first["operations"]
        ):
            raise FixtureError(f"{label} conflict operation contains a diff")
    elif any(operation["diff"] for operation in first["operations"]):
        raise FixtureError(f"{label} no-write disposition contains a diff")
    expected_non_materializable = sorted(
        action
        for action in first["summary"]
        if action in {"conflict", "opt-out", "unsupported"}
    )
    expected_error = (
        "continuity plan is not materializable: "
        + ", ".join(expected_non_materializable)
    )
    try:
        apply_continuity_plan(
            first,
            target,
            profile_path=profile_path,
            aether_source=aether_source,
        )
    except MaterializationError as error:
        if str(error) != expected_error:
            raise FixtureError(
                f"{label} failed for the wrong reason: {error}"
            ) from error
    else:
        raise FixtureError(f"{label} no-write plan unexpectedly applied")
    if tree_contract(target) != before:
        raise FixtureError(f"{label} no-write plan changed the target")
    return {
        "id": label,
        "plan_id": first["plan_id"],
        "summary": first["summary"],
        "operations": [operation_contract(item) for item in first["operations"]],
        "target_tree_sha256": digest(canonical_bytes(before)),
    }


def tree_contract(target: Path) -> dict[str, str]:
    """Return a deterministic content map excluding disposable Git/report data."""
    result: dict[str, str] = {}
    for path in sorted(target.rglob("*")):
        relative = path.relative_to(target)
        if ".git" in relative.parts or relative.parts[:2] == (".reports", "egolint"):
            continue
        if path.is_symlink():
            result[relative.as_posix()] = "symlink:" + os.readlink(path)
        elif path.is_file():
            result[relative.as_posix()] = digest(path.read_bytes())
    return result


def exercise_positive(
    fixture: dict[str, Any],
    request: dict[str, Any],
    target: Path,
    profile: dict[str, Any],
    profile_path: Path,
    aether_source: Path,
    egolint_binary: Path,
    base_revision: str,
    *,
    disposition: str = "updated",
    prove_validator_control: bool = False,
) -> dict[str, Any]:
    """Prove deterministic preview through exact rollback for one positive case."""
    assert_request(request, profile)
    first = build_continuity_plan(
        request,
        target,
        profile_path=profile_path,
        aether_source=aether_source,
    )
    second = build_continuity_plan(
        copy.deepcopy(request),
        target,
        profile_path=profile_path,
        aether_source=aether_source,
    )
    if first != second:
        raise FixtureError(f"{fixture['id']} preview is not deterministic")
    if first["summary"].get("conflict", 0):
        raise FixtureError(f"{fixture['id']} positive plan contains a conflict")
    preimages = surface_preimages(target)
    state = apply_continuity_plan(
        first,
        target,
        profile_path=profile_path,
        aether_source=aether_source,
    )
    if errors := verify_continuity_target(target):
        raise FixtureError(f"{fixture['id']} adapter verification failed: {'; '.join(errors)}")
    private_safety = (
        verify_private_surface(target)
        if fixture["visibility"] == "private"
        else None
    )
    report, report_bytes = validate_with_egolint(
        target,
        fixture,
        egolint_binary,
        base_revision,
        disposition,
    )
    if prove_validator_control:
        prove_negative_control(
            target,
            fixture,
            egolint_binary,
            base_revision,
            disposition,
        )
    repeat_request = copy.deepcopy(request)
    repeated = build_continuity_plan(
        repeat_request,
        target,
        profile_path=profile_path,
        aether_source=aether_source,
    )
    if set(repeated["summary"]) - {"noop", "preserve"}:
        raise FixtureError(f"{fixture['id']} repeat plan is not an idempotent no-write plan")
    before_repeat = tree_contract(target)
    if build_continuity_plan(
        copy.deepcopy(repeat_request),
        target,
        profile_path=profile_path,
        aether_source=aether_source,
    ) != repeated:
        raise FixtureError(f"{fixture['id']} repeat preview is not deterministic")
    repeated_state = apply_continuity_plan(
        repeated,
        target,
        profile_path=profile_path,
        aether_source=aether_source,
    )
    if repeated_state != state or tree_contract(target) != before_repeat:
        raise FixtureError(f"{fixture['id']} repeat apply is not byte-idempotent")
    applied = surface_digests(target)
    state_bytes = (target / STATE_RELATIVE_PATH).read_bytes()
    remove_egolint_report(target)
    rollback_continuity_target(target)
    for relative, expected in preimages.items():
        if read_optional(target / relative) != expected:
            raise FixtureError(f"{fixture['id']} rollback did not restore {relative}")
    result = {
        "base_revision": base_revision,
        "plan_id": first["plan_id"],
        "summary": first["summary"],
        "operations": [operation_contract(item) for item in first["operations"]],
        "applied_surfaces": applied,
        "applied_surface_tree_sha256": digest(canonical_bytes(applied)),
        "state_sha256": digest(state_bytes),
        "state_contract_sha256": digest(canonical_bytes(state)),
        "state_profile_sha256": state["profile_sha256"],
        "state_profile_version": state["profile_version"],
        "repeat_summary": repeated["summary"],
        "rollback_preimages": {
            relative: digest(content) if content is not None else None
            for relative, content in preimages.items()
        },
        "egolint": {
            "status": report["status"],
            "disposition": report["comparison"]["disposition"],
            "evidence_layers": report["evidence_layers"],
            "diagnostic_rule_ids": [
                item["rule_id"] for item in report["diagnostics"]
            ],
            "report_sha256": digest(report_bytes),
        },
    }
    if private_safety is not None:
        result["private_safety"] = private_safety
    return result


def managed_block(content: bytes) -> bytes:
    """Extract the one canonical marker-delimited managed block."""
    text = content.decode("utf-8")
    start = text.index(MANAGED_BEGIN)
    end = text.index(MANAGED_END, start) + len(MANAGED_END)
    if end < len(text) and text[end] == "\n":
        end += 1
    return text[start:end].encode("utf-8")


def prior_fixture_profile(
    root: Path, profile: dict[str, Any]
) -> tuple[Path, str]:
    """Create a test-only prior Holon profile without changing source pins."""
    old_profile = copy.deepcopy(profile)
    old_profile["version"] = "1.0.0-alpha.0"
    old_profile["purpose"] = (
        "Test-only prior Holon profile for deterministic state-upgrade evidence; "
        "all portable source pins and artifact bytes remain unchanged."
    )
    profile_path = root / "prior-holon-profile.json"
    write_bytes(profile_path, pretty_json_bytes(old_profile))
    return profile_path, digest(profile_path.read_bytes())


def seed_prior_managed_blocks(
    target: Path, state: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Seed a recovery-valid, state-bound prior Holon block rendering.

    The synthetic marker models a previous Holon rendering of the same exact
    Aether source bytes. It is fixture state, never attributed to an Aether
    commit or substituted into the caller-supplied source checkout.
    """
    state = copy.deepcopy(state)
    state_records = {record["path"]: record for record in state["surfaces"]}
    prior_digests: dict[str, str] = {}
    insertion = (
        MANAGED_BEGIN.encode("utf-8")
        + b"\n"
        + PRIOR_MANAGED_BLOCK_MARKER.encode("utf-8")
        + b"\n"
    )
    marker = MANAGED_BEGIN.encode("utf-8") + b"\n"
    for relative in SURFACES[1:]:
        path = target / relative
        current = path.read_bytes()
        seeded = current.replace(marker, insertion, 1)
        if seeded == current or seeded.count(PRIOR_MANAGED_BLOCK_MARKER.encode("utf-8")) != 1:
            raise FixtureError(f"could not seed the prior managed block: {relative}")
        write_bytes(path, seeded)
        record = state_records[relative]
        record["applied_file_sha256"] = digest(seeded)
        record["managed_block_sha256"] = digest(managed_block(seeded))
        prior_digests[relative] = record["managed_block_sha256"]

    rollback_path = target / state["rollback_manifest"]
    rollback = load_json(rollback_path)
    for operation in rollback["operations"]:
        relative = operation["path"]
        if relative in prior_digests:
            operation["expected_after_sha256"] = digest((target / relative).read_bytes())
    rollback_bytes = pretty_json_bytes(rollback)
    write_bytes(rollback_path, rollback_bytes)
    state["rollback_sha256"] = digest(rollback_bytes)
    write_bytes(target / STATE_RELATIVE_PATH, pretty_json_bytes(state))
    if errors := verify_continuity_target(target):
        raise FixtureError("seeded prior managed blocks are invalid: " + "; ".join(errors))
    return state, prior_digests


def mode_request(base: dict[str, Any], mode: str) -> dict[str, Any]:
    """Convert a positive request into a closed no-write disposition."""
    request = copy.deepcopy(base)
    request["mode"] = mode
    request["continuity"] = None
    request["sections"] = None
    request["continuity_migration"] = None
    request["parallel_candidates"] = []
    request["parallel_reconciliation"] = None
    request["providers"] = []
    if mode == "opt-out":
        request["opt_out"] = {
            "enabled": True,
            "reason": "Maintainers retain a reviewed repository-specific checkpoint.",
            "reference": IMMUTABLE_REFERENCE,
        }
        request["unsupported_reason"] = None
    elif mode == "unsupported":
        request["repository_profile"] = "generated-mirror"
        request["repository_class"] = "generated"
        request["opt_out"] = None
        request["unsupported_reason"] = (
            "Generated mirrors are outside the reviewed continuity profile."
        )
    else:
        raise FixtureError(f"unsupported no-write fixture mode: {mode}")
    return request


def run_standard_fixture(
    fixture: dict[str, Any],
    target: Path,
    cases: dict[str, Any],
    profile: dict[str, Any],
    project_profile_path: Path,
    aether_source: Path,
    hygiene_source: Path,
    egolint_binary: Path,
) -> dict[str, Any]:
    """Run research, library, organization, or private fixture cases."""
    prepare_validation_files(target, fixture, aether_source, hygiene_source)
    if fixture["setup"] == "authored-agents":
        write_text(
            target / "AGENTS.md",
            "# Repository instructions\n\nKeep this authored library release rule unchanged.\n",
        )
    base_revision = initialize_repository(target, cases)
    request = common_request(fixture, base_revision)
    no_write: list[dict[str, Any]] = []
    if fixture["id"] == "organization-meta":
        candidates = [
            {
                "provider": "github",
                "id": "fixture-org/organization-meta#101",
                "url": "https://github.com/fixture-org/organization-meta/pull/101",
            },
            {
                "provider": "github",
                "id": "fixture-org/organization-meta#102",
                "url": "https://github.com/fixture-org/organization-meta/pull/102",
            },
        ]
        conflict = copy.deepcopy(request)
        conflict.update(
            {
                "mode": "parallel-conflict",
                "continuity": None,
                "sections": None,
                "providers": [],
                "parallel_candidates": candidates,
                "parallel_reconciliation": None,
            }
        )
        no_write.append(
            no_write_contract(
                "parallel-conflict",
                conflict,
                target,
                profile,
                project_profile_path,
                aether_source,
            )
        )
        request = common_request(fixture, base_revision, parallel=candidates)
    elif fixture["id"] == "private-creative":
        for mode in ("opt-out", "unsupported"):
            no_write.append(
                no_write_contract(
                    mode,
                    mode_request(request, mode),
                    target,
                    profile,
                    project_profile_path,
                    aether_source,
                )
            )
    result = exercise_positive(
        fixture,
        request,
        target,
        profile,
        project_profile_path,
        aether_source,
        egolint_binary,
        base_revision,
        prove_validator_control=fixture["id"] == "research-publication",
    )
    result["no_write_scenarios"] = no_write
    if fixture["id"] == "library-cli":
        authored = (target / "AGENTS.md").read_bytes()
        expected = b"# Repository instructions\n\nKeep this authored library release rule unchanged.\n"
        if authored != expected:
            raise FixtureError("library rollback did not byte-preserve authored AGENTS.md")
    return result


def run_site_fixture(
    fixture: dict[str, Any],
    target: Path,
    root: Path,
    cases: dict[str, Any],
    profile: dict[str, Any],
    project_profile_path: Path,
    aether_source: Path,
    hygiene_source: Path,
    egolint_binary: Path,
) -> dict[str, Any]:
    """Prove malformed-marker refusal and a source-preserving profile upgrade."""
    prepare_validation_files(target, fixture, aether_source, hygiene_source)
    authored = {
        "AGENTS.md": "# Site agent rules\n\nPreserve the deployment boundary.\n",
        ".github/copilot-instructions.md": "# Copilot rules\n\nPreserve the route contract.\n",
        "CLAUDE.md": "# Claude rules\n\nPreserve the accessibility gate.\n",
    }
    for relative, content in authored.items():
        write_text(target / relative, content)
    support_revision = initialize_repository(target, cases)
    malformed = common_request(fixture, support_revision)
    original_agents = (target / "AGENTS.md").read_bytes()
    write_text(
        target / "AGENTS.md",
        original_agents.decode("utf-8")
        + f"\n{MANAGED_BEGIN}\n{MANAGED_BEGIN}\n{MANAGED_END}\n",
    )
    marker_conflict = no_write_contract(
        "malformed-marker-conflict",
        malformed,
        target,
        profile,
        project_profile_path,
        aether_source,
    )
    write_bytes(target / "AGENTS.md", original_agents)
    old_profile_path, old_profile_digest = prior_fixture_profile(root, profile)
    old_profile = load_json(old_profile_path)
    old_request = common_request(fixture, support_revision)
    assert_request(old_request, old_profile)
    old_plan = build_continuity_plan(
        old_request,
        target,
        profile_path=old_profile_path,
        aether_source=aether_source,
    )
    prior_state = apply_continuity_plan(
        old_plan,
        target,
        profile_path=old_profile_path,
        aether_source=aether_source,
    )
    prior_state, prior_managed_block_sha256 = seed_prior_managed_blocks(
        target, prior_state
    )
    prior_surfaces = surface_digests(target)
    prior_state_contract_sha256 = digest(canonical_bytes(prior_state))
    base_revision = commit_upgrade_baseline(target, cases)
    request = common_request(fixture, base_revision)
    result = exercise_positive(
        fixture,
        request,
        target,
        profile,
        project_profile_path,
        aether_source,
        egolint_binary,
        base_revision,
        disposition="reviewed-no-change",
    )
    current_profile_sha256 = digest(project_profile_path.read_bytes())
    update_paths = {
        operation["path"]
        for operation in result["operations"]
        if operation["action"] == "update"
    }
    if update_paths != set(SURFACES[1:]) or result["summary"] != {
        "preserve": 1,
        "update": 3,
    }:
        raise FixtureError("site fixture did not upgrade all trusted managed blocks")
    if any(
        result["applied_surfaces"][relative] == prior_surfaces[relative]
        for relative in SURFACES[1:]
    ):
        raise FixtureError("site managed-block upgrade left a prior block unchanged")
    if result["state_contract_sha256"] == prior_state_contract_sha256:
        raise FixtureError("site profile upgrade did not change adapter state")
    if (
        result["state_profile_sha256"] != current_profile_sha256
        or result["state_profile_version"] != profile["version"]
        or result["state_profile_sha256"] == prior_state["profile_sha256"]
        or result["state_profile_version"] == prior_state["profile_version"]
    ):
        raise FixtureError("site profile upgrade did not bind the current profile")
    result["prior_profile_sha256"] = old_profile_digest
    result["prior_profile_version"] = old_profile["version"]
    result["prior_managed_block_sha256"] = prior_managed_block_sha256
    result["prior_state_contract_sha256"] = prior_state_contract_sha256
    result["no_write_scenarios"] = [marker_conflict]
    for relative, prefix in authored.items():
        if not (target / relative).read_bytes().startswith(prefix.encode("utf-8")):
            raise FixtureError(f"site rollback lost authored prose: {relative}")
    return result


def source_section(content: bytes, start: int, end: int) -> bytes:
    """Normalize one complete source section exactly as reviewed by the map."""
    lines = content.decode("utf-8").splitlines()
    return ("\n".join(lines[start - 1 : end]).strip() + "\n").encode("utf-8")


def json_pointer(document: Any, pointer: str) -> Any:
    """Resolve a small RFC 6901 pointer used by the migration map."""
    value = document
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def rendered_section(markdown: str, heading: str) -> str:
    """Extract one level-two rendered section."""
    marker = f"## {heading}"
    start = markdown.index(marker)
    next_start = markdown.find("\n## ", start + len(marker))
    return markdown[start:] if next_start < 0 else markdown[start:next_start]


def normalized_text(value: Any) -> str:
    """Flatten JSON or Markdown for line-wrap-insensitive atom checks."""
    if isinstance(value, dict):
        return " ".join(normalized_text(value[key]) for key in sorted(value))
    if isinstance(value, list):
        return " ".join(normalized_text(item) for item in value)
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True)
    return " ".join(value.split()).casefold()


def verify_antidote_mapping(
    request: dict[str, Any],
    proposed_continuity: bytes,
    proposed_agents: bytes,
    antidote_source: Path,
    aether_source: Path,
    migration_map: dict[str, Any],
) -> None:
    """Prove complete-section mapping and exact authored AGENTS preservation."""
    if migration_map.get("schema_version") != (
        "holon.antidote-continuity-migration-map/v1"
    ):
        raise FixtureError("Antidote migration map schema is unsupported")
    source = migration_map["source"]
    if source["repository"] != "egohygiene/antidote":
        raise FixtureError("Antidote migration map repository is incorrect")
    merge_evidence = source.get("merge_evidence")
    expected_merge_url = (
        f"https://github.com/{source['repository']}/commit/{source['revision']}"
    )
    if not isinstance(merge_evidence, dict) or set(merge_evidence) != {
        "url",
        "subject",
        "parents",
    }:
        raise FixtureError("Antidote merge evidence contract is malformed")
    commit_object = run(
        ["git", "cat-file", "commit", source["revision"]], cwd=antidote_source
    ).stdout.decode("utf-8")
    observed_parents = [
        line.removeprefix("parent ")
        for line in commit_object.splitlines()
        if line.startswith("parent ")
    ]
    observed_subject = run(
        ["git", "show", "--no-patch", "--format=%s", source["revision"]],
        cwd=antidote_source,
    ).stdout.decode("utf-8").strip()
    if (
        merge_evidence["url"] != expected_merge_url
        or merge_evidence["parents"] != observed_parents
        or merge_evidence["subject"] != observed_subject
        or len(observed_parents) != 2
    ):
        raise FixtureError("Antidote pinned merge evidence changed")
    for file_record in source["files"]:
        content = (antidote_source / file_record["path"]).read_bytes()
        if (
            len(content) != file_record["bytes"]
            or len(content.splitlines()) != file_record["lines"]
            or digest(content) != file_record["sha256"]
        ):
            raise FixtureError(f"Antidote source file changed: {file_record['path']}")
        blob = run(
            [
                "git",
                "rev-parse",
                f"{source['revision']}:{file_record['path']}",
            ],
            cwd=antidote_source,
        ).stdout.decode("ascii").strip()
        mode = run(
            ["git", "ls-tree", source["revision"], file_record["path"]],
            cwd=antidote_source,
        ).stdout.decode("ascii").split()[0]
        if blob != file_record["git_blob"] or mode != file_record["mode"]:
            raise FixtureError(f"Antidote Git identity changed: {file_record['path']}")
    legacy = (antidote_source / "CONTINUITY.md").read_bytes()
    legacy_headings = {
        line[3:]
        for line in legacy.decode("utf-8").splitlines()
        if line.startswith("## ")
    }
    mappings = migration_map["mappings"]
    current_checkpoint = next(
        (item for item in mappings if item.get("id") == "current-checkpoint"), None
    )
    if (
        not isinstance(current_checkpoint, dict)
        or current_checkpoint.get("disposition") != "superseded-with-evidence"
        or current_checkpoint.get("evidence_url") != merge_evidence["url"]
    ):
        raise FixtureError("Antidote checkpoint supersession is not merge-evidence-bound")
    mapped_headings = {
        item["source"]["heading"]
        for item in mappings
        if item["source"]["path"] == "CONTINUITY.md"
        and item["source"]["heading"] != "Preamble"
    }
    if mapped_headings != legacy_headings:
        raise FixtureError("Antidote migration map does not cover every complete legacy section")
    rendered = proposed_continuity.decode("utf-8")
    for mapping in mappings:
        source_record = mapping["source"]
        if source_record["path"] == "CONTINUITY.md":
            section = source_section(
                legacy, source_record["line_start"], source_record["line_end"]
            )
            if digest(section) != source_record["normalized_sha256"]:
                raise FixtureError(f"Antidote source section changed: {mapping['id']}")
        elif mapping["id"] == "agents-whole-file":
            if digest((antidote_source / "AGENTS.md").read_bytes()) != source_record[
                "normalized_sha256"
            ]:
                raise FixtureError("Antidote AGENTS.md source changed")
        else:
            raise FixtureError(f"unsupported Antidote map source: {mapping['id']}")
        target_values: list[Any] = []
        for target in mapping["targets"]:
            if target.startswith("/"):
                target_values.append(json_pointer(request, target))
            elif target.startswith("rendered:"):
                heading = target.removeprefix("rendered:")
                if heading == "AGENTS.md outside managed block":
                    target_values.append(proposed_agents.decode("utf-8"))
                else:
                    target_values.append(rendered_section(rendered, heading))
            else:
                raise FixtureError(f"unsupported Antidote map target: {target}")
        haystack = normalized_text(target_values)
        for atom in mapping["required_atoms"]:
            if normalized_text(atom) not in haystack:
                raise FixtureError(
                    f"Antidote migration atom is not retained: {mapping['id']}: {atom}"
                )
    ordered = ["#48", "#70", "#71", "#72", "#73", "#74", "#89", "#75", "#76"]
    order_text = normalized_text(
        [request["continuity"]["work"]["next"], request["sections"]["deferred_work"][0]]
    )
    positions = [order_text.index(value) for value in ordered]
    if positions != sorted(positions):
        raise FixtureError("Antidote dependency path order was not retained")
    legacy_agents = (antidote_source / "AGENTS.md").read_bytes()
    pinned_block = managed_block(
        (aether_source / "dist/codex/repository/AGENTS.md").read_bytes()
    )
    if proposed_agents != legacy_agents + b"\n" + pinned_block:
        raise FixtureError("Antidote AGENTS.md was not byte-preserved outside one pinned block")


def run_antidote_fixture(
    fixture: dict[str, Any],
    target: Path,
    profile: dict[str, Any],
    project_profile_path: Path,
    aether_source: Path,
    hygiene_source: Path,
    antidote_source: Path,
    egolint_binary: Path,
    migration_map: dict[str, Any],
) -> dict[str, Any]:
    """Run the exact pinned Antidote prototype migration and stale-CAS refusal."""
    run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(antidote_source), str(target)]
    )
    base_revision = run(["git", "rev-parse", "HEAD"], cwd=target).stdout.decode("ascii").strip()
    if base_revision != migration_map["source"]["revision"]:
        raise FixtureError("disposable Antidote checkout is not at the mapped revision")
    prepare_validation_files(target, fixture, aether_source, hygiene_source)
    request = antidote_request(fixture, base_revision, migration_map)
    stale = copy.deepcopy(request)
    stale["continuity_migration"]["expected_sha256"] = "0" * 64
    stale_contract = no_write_contract(
        "stale-migration-conflict",
        stale,
        target,
        profile,
        project_profile_path,
        aether_source,
    )
    preview = build_continuity_plan(
        request,
        target,
        profile_path=project_profile_path,
        aether_source=aether_source,
    )
    continuity_operation = next(
        item for item in preview["operations"] if item["path"] == "CONTINUITY.md"
    )
    agents_operation = next(
        item for item in preview["operations"] if item["path"] == "AGENTS.md"
    )
    verify_antidote_mapping(
        request,
        continuity_operation["proposed_content"].encode("utf-8"),
        agents_operation["proposed_content"].encode("utf-8"),
        antidote_source,
        aether_source,
        migration_map,
    )
    result = exercise_positive(
        fixture,
        request,
        target,
        profile,
        project_profile_path,
        aether_source,
        egolint_binary,
        base_revision,
    )
    result["migration_map_sha256"] = digest(canonical_bytes(migration_map))
    result["no_write_scenarios"] = [stale_contract]
    return result


def run_fixture(
    fixture: dict[str, Any],
    root: Path,
    cases: dict[str, Any],
    profile: dict[str, Any],
    project_profile_path: Path,
    sources: dict[str, Path],
    antidote_source: Path,
    egolint_binary: Path,
    migration_map: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch one fixture class into a fresh disposable target."""
    target = root / fixture["id"]
    if fixture["id"] == "antidote-migration":
        return run_antidote_fixture(
            fixture,
            target,
            profile,
            project_profile_path,
            sources["portable-contract"],
            sources["organization-policy"],
            antidote_source,
            egolint_binary,
            migration_map,
        )
    target.mkdir(parents=True)
    if fixture["id"] == "site-application":
        return run_site_fixture(
            fixture,
            target,
            root,
            cases,
            profile,
            project_profile_path,
            sources["portable-contract"],
            sources["organization-policy"],
            egolint_binary,
        )
    return run_standard_fixture(
        fixture,
        target,
        cases,
        profile,
        project_profile_path,
        sources["portable-contract"],
        sources["organization-policy"],
        egolint_binary,
    )


def integration_check(
    project: Path,
    *,
    aether_source: Path,
    hygiene_source: Path,
    egolint_source: Path,
    egolint_binary: Path,
    antidote_source: Path,
    write_snapshots: bool = False,
) -> dict[str, Any]:
    """Run every #45 case twice and compare the reviewed artifact contract."""
    cases = load_json(project / CASES_PATH)
    migration_map = load_json(project / MIGRATION_MAP_PATH)
    validate_fixture_contract(cases)
    sources = {
        "portable-contract": aether_source.resolve(),
        "organization-policy": hygiene_source.resolve(),
        "validator": egolint_source.resolve(),
    }
    binary_path = (
        egolint_binary
        if egolint_binary.is_absolute()
        else (Path.cwd() / egolint_binary).absolute()
    )
    provenance = verify_inputs(
        project,
        cases,
        sources,
        antidote_source.resolve(),
        binary_path,
    )
    verified_binary = require_regular_binary(binary_path)
    profile = load_json(project / PROFILE_FILE)
    observed: dict[str, Any] = {
        "schema_version": "holon.repository-continuity-artifact-contracts/v1",
        **provenance,
        "fixtures": {},
    }
    for fixture in cases["fixtures"]:
        results: list[dict[str, Any]] = []
        for run_index in range(2):
            with tempfile.TemporaryDirectory(
                prefix=f"holon-continuity-{fixture['id']}-{run_index}-"
            ) as temporary:
                results.append(
                    run_fixture(
                        fixture,
                        Path(temporary),
                        cases,
                        profile,
                        project / PROFILE_FILE,
                        sources,
                        antidote_source.resolve(),
                        verified_binary,
                        migration_map,
                    )
                )
        if results[0] != results[1]:
            raise FixtureError(f"fresh rerun changed artifact evidence: {fixture['id']}")
        observed["fixtures"][fixture["id"]] = results[0]
        summary = results[0]["summary"]
        print(f"PASS {fixture['id']}: {summary}")
    snapshot_path = project / SNAPSHOTS_PATH
    if write_snapshots:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(pretty_json_bytes(observed))
    elif not snapshot_path.is_file():
        raise FixtureError(f"artifact contract is missing: {SNAPSHOTS_PATH}")
    else:
        expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if observed != expected:
            raise FixtureError(
                "repository-continuity artifact contract changed without review"
            )
    print("PASS repository-continuity artifact contracts")
    return observed


def build_parser() -> argparse.ArgumentParser:
    """Build the explicit local-source checker interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--aether-source", type=Path, required=True)
    parser.add_argument("--hygiene-source", type=Path, required=True)
    parser.add_argument("--egolint-source", type=Path, required=True)
    parser.add_argument("--egolint-binary", type=Path, required=True)
    parser.add_argument("--antidote-source", type=Path, required=True)
    parser.add_argument("--write-snapshots", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the complete local-only fixture proof."""
    arguments = build_parser().parse_args(argv)
    try:
        integration_check(
            arguments.project.expanduser().resolve(),
            aether_source=arguments.aether_source.expanduser().resolve(),
            hygiene_source=arguments.hygiene_source.expanduser().resolve(),
            egolint_source=arguments.egolint_source.expanduser().resolve(),
            egolint_binary=arguments.egolint_binary.expanduser(),
            antidote_source=arguments.antidote_source.expanduser().resolve(),
            write_snapshots=arguments.write_snapshots,
        )
    except (FixtureError, MaterializationError, ValueError, OSError) as error:
        print(f"repository-continuity fixture check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
