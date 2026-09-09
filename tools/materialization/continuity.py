"""Deterministic repository-continuity planning and reconciliation adapter."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import difflib
from datetime import datetime
import ipaddress
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

try:
    from ..repository_continuity_profile import (
        EXPECTED_ARTIFACTS,
        EXPECTED_SOURCES,
        load_json,
        validate_profile,
    )
except ImportError:  # Imported as top-level ``materialization`` by the CLI and tests.
    from repository_continuity_profile import (
        EXPECTED_ARTIFACTS,
        EXPECTED_SOURCES,
        load_json,
        validate_profile,
    )

from .common import (
    MaterializationError,
    atomic_write,
    canonical_bytes,
    pretty_json_bytes,
    safe_relative_path,
    sha256_bytes,
    sha256_file,
    target_path,
    validate_target_root,
)


ADAPTER_VERSION = "1.0.0"
REQUEST_SCHEMA = "holon.repository-continuity-request/v1"
PLAN_SCHEMA = "holon.repository-continuity-plan/v1"
STATE_SCHEMA = "holon.repository-continuity-state/v1"
ROLLBACK_SCHEMA = "holon.repository-continuity-rollback/v1"
STATE_RELATIVE_PATH = ".holon/repository-continuity-state.v1.json"
BACKUPS_RELATIVE_PATH = ".holon/repository-continuity-backups"
LOCK_RELATIVE_PATH = ".holon/repository-continuity.lock"
MANAGED_BEGIN = "<!-- BEGIN AETHER REPOSITORY-CONTINUITY -->"
MANAGED_END = "<!-- END AETHER REPOSITORY-CONTINUITY -->"
MAX_BYTES = 16384
MAX_LINES = 240

REQUEST_KEYS = {
    "schema_version",
    "repository",
    "repository_class",
    "repository_profile",
    "mode",
    "providers",
    "continuity",
    "continuity_migration",
    "sections",
    "opt_out",
    "unsupported_reason",
    "parallel_candidates",
    "parallel_reconciliation",
}
REPOSITORY_KEYS = {"id", "visibility", "default_branch"}
SECTION_KEYS = {
    "purpose_and_precedence",
    "completed_changes",
    "blockers",
    "risks",
    "unknowns",
    "deferred_work",
    "privacy_and_redaction",
}
REFERENCE_KEYS = {"provider", "id", "url"}
OPT_OUT_KEYS = {"enabled", "reason", "reference"}
CONTINUITY_MIGRATION_KEYS = {"expected_sha256", "reason", "evidence_url"}
MODES = {"materialize", "provisional", "opt-out", "unsupported", "parallel-conflict"}
PROVIDERS = {"github-copilot", "claude-code"}
SURFACE_PATHS = {
    "CONTINUITY.md",
    "AGENTS.md",
    ".github/copilot-instructions.md",
    "CLAUDE.md",
}
PROFILE_CLASSES = {
    "research-publication": {"publication"},
    "library-cli": {"library", "tool"},
    "site-application": {"product"},
    "organization-meta": {"library", "tool", "product", "publication"},
    "private-creative": {"product", "publication"},
}
PROFILE_VISIBILITIES = {
    "research-publication": {"public", "private", "internal"},
    "library-cli": {"public", "private", "internal"},
    "site-application": {"public", "private", "internal"},
    "organization-meta": {"public", "private", "internal"},
    "private-creative": {"private", "internal"},
}
VISIBILITIES = {"public", "private", "internal"}
SOURCE_ROLE_REPOSITORIES = {
    "portable-contract": "egohygiene/aether",
    "organization-policy": "egohygiene/hygiene",
    "validator": "egohygiene/egolint",
}
PRECEDENCE = [
    "user-and-runtime-instructions",
    "scoped-repository-instructions",
    "live-repository-and-work-tracker-state",
    "canonical-repository-sources",
    "continuity-checkpoint",
]
EXCLUDED = [
    "secrets-and-credentials",
    "private-conversation-text",
    "sensitive-personal-data",
    "unpublished-private-business-data",
    "private-local-paths",
    "unrelated-private-context",
]
REQUIRED_HEADINGS = [
    "Purpose and precedence",
    "Resume protocol",
    "Current objective and success conditions",
    "State snapshot",
    "Completed and material changes",
    "Validation and review evidence",
    "Blockers, risks, unknowns, and deferred work",
    "Next dependency-ready work",
    "Parallel changes and reconciliation",
    "Privacy and redaction",
    "Handoff update protocol",
    "Compaction and supersession",
]
PROHIBITED_TEXT_PATTERNS = {
    "credential token": re.compile(r"(?:gh[pousr]_|sk-)[A-Za-z0-9_-]{12,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "private local path": re.compile(r"(?:/Users/[^/\s]+|/home/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+)"),
}
RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)


def _closed_keys(value: Any, expected: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return False
    missing = expected - set(value)
    unknown = set(value) - expected
    if missing:
        errors.append(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        errors.append(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    return not missing and not unknown


def _nonempty_string(value: Any, label: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
        return False
    return True


def _enum_string(
    value: Any,
    allowed: set[str],
    label: str,
    errors: list[str],
) -> bool:
    if not isinstance(value, str) or value not in allowed:
        errors.append(f"{label} is unsupported")
        return False
    return True


def _date_time(value: Any, label: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not RFC3339_RE.fullmatch(value):
        errors.append(f"{label} must be an RFC 3339 date-time")
        return False
    normalized = value[:-1] + "+00:00" if value[-1] in {"Z", "z"} else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        errors.append(f"{label} must be an RFC 3339 date-time")
        return False
    return True


def _https_url(value: Any, label: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not value or any(
        character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
        for character in value
    ) or "\\" in value:
        errors.append(f"{label} must be an https URL")
        return False
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        parsed.port
    except ValueError:
        errors.append(f"{label} must be an https URL")
        return False
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        errors.append(f"{label} must be an https URL")
        return False
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError:
            errors.append(f"{label} must be an https URL")
            return False
        labels = ascii_hostname.rstrip(".").split(".")
        if (
            len(ascii_hostname) > 253
            or not labels
            or any(
                not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", item)
                for item in labels
            )
        ):
            errors.append(f"{label} must be an https URL")
            return False
    return True


def _string_list(
    value: Any,
    label: str,
    errors: list[str],
    *,
    minimum: int = 0,
) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        errors.append(f"{label} must contain non-empty strings")
        return []
    if len(value) < minimum:
        errors.append(f"{label} must contain at least {minimum} item(s)")
    if len(value) != len(set(value)):
        errors.append(f"{label} must not contain duplicates")
    return value


def _validate_reference(value: Any, label: str, errors: list[str]) -> None:
    if not _closed_keys(value, REFERENCE_KEYS, label, errors):
        return
    for key in ("provider", "id", "url"):
        _nonempty_string(value[key], f"{label}.{key}", errors)
    _https_url(value["url"], f"{label}.url", errors)
    if value["provider"] == "github" and isinstance(value["id"], str):
        match = re.fullmatch(
            r"([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)#([1-9][0-9]*)",
            value["id"],
        )
        if match is None:
            errors.append(
                f"{label}.id must use owner/repository#number form for GitHub"
            )
        elif isinstance(value["url"], str) and value["url"] != (
            f"https://github.com/{match.group(1)}/issues/{match.group(2)}"
        ) and value["url"] != (
            f"https://github.com/{match.group(1)}/pull/{match.group(2)}"
        ):
            errors.append(f"{label}.url must match its GitHub repository and number")


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for child in value.values() for text in _walk_strings(child)]
    if isinstance(value, list):
        return [text for child in value for text in _walk_strings(child)]
    return []


def _validate_safety(value: dict[str, Any], errors: list[str]) -> None:
    for text in _walk_strings(value):
        for label, pattern in PROHIBITED_TEXT_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"request contains prohibited {label} material")


def _validate_continuity_metadata(
    continuity: Any,
    repository: dict[str, Any],
    mode: str,
    errors: list[str],
) -> None:
    keys = {"schema_version", "repository", "document", "scope", "work", "state", "review", "privacy"}
    if not _closed_keys(continuity, keys, "continuity", errors):
        return
    if continuity["schema_version"] != "aether.repository-continuity/v1":
        errors.append("continuity.schema_version is unsupported")

    metadata_repository = continuity["repository"]
    expected_repository = {
        "id": repository.get("id"),
        "visibility": repository.get("visibility"),
        "default_branch": repository.get("default_branch"),
        "continuity_path": "CONTINUITY.md",
    }
    if metadata_repository != expected_repository:
        errors.append("continuity.repository must match the request repository")

    document = continuity["document"]
    document_keys = {"status", "updated_at", "max_bytes", "max_lines", "stale_reason", "superseded_by"}
    if _closed_keys(document, document_keys, "continuity.document", errors):
        _enum_string(
            document["status"],
            {"active", "stale", "superseded"},
            "continuity.document.status",
            errors,
        )
        if document["max_bytes"] != MAX_BYTES or document["max_lines"] != MAX_LINES:
            errors.append("continuity.document must use the fixed v1 size limits")
        _date_time(document["updated_at"], "continuity.document.updated_at", errors)
        if document["status"] == "active" and (
            document["stale_reason"] is not None or document["superseded_by"] is not None
        ):
            errors.append("active continuity cannot declare stale or superseded state")
        if document["status"] == "stale":
            _nonempty_string(
                document["stale_reason"],
                "stale continuity stale_reason",
                errors,
            )
            if document["superseded_by"] is not None:
                errors.append("stale continuity cannot declare superseded_by")
        if document["status"] == "superseded":
            _nonempty_string(
                document["superseded_by"],
                "superseded continuity superseded_by",
                errors,
            )
            if document["stale_reason"] is not None:
                errors.append("superseded continuity cannot declare stale_reason")

    scope = continuity["scope"]
    scope_keys = {"purpose", "includes", "excludes", "precedence", "canonical_sources"}
    if _closed_keys(scope, scope_keys, "continuity.scope", errors):
        _nonempty_string(scope["purpose"], "continuity.scope.purpose", errors)
        _string_list(scope["includes"], "continuity.scope.includes", errors, minimum=1)
        _string_list(scope["canonical_sources"], "continuity.scope.canonical_sources", errors, minimum=1)
        if scope["excludes"] != [
            "conversation transcripts",
            "duplicated architecture, roadmap, and changelog content",
        ]:
            errors.append("continuity.scope.excludes must preserve the portable exclusions")
        if scope["precedence"] != PRECEDENCE:
            errors.append("continuity.scope.precedence must preserve portable authority order")

    work = continuity["work"]
    if _closed_keys(work, {"objective", "success_conditions", "active_issue", "next"}, "continuity.work", errors):
        _nonempty_string(work["objective"], "continuity.work.objective", errors)
        _string_list(work["success_conditions"], "continuity.work.success_conditions", errors, minimum=1)
        if work["active_issue"] is not None:
            _validate_reference(work["active_issue"], "continuity.work.active_issue", errors)
        next_work = work["next"]
        next_keys = {"kind", "id", "description", "readiness", "references", "depends_on"}
        if _closed_keys(next_work, next_keys, "continuity.work.next", errors):
            _enum_string(
                next_work["kind"],
                {"issue", "action"},
                "continuity.work.next.kind",
                errors,
            )
            _enum_string(
                next_work["readiness"],
                {"ready", "blocked", "unknown"},
                "continuity.work.next.readiness",
                errors,
            )
            _nonempty_string(next_work["id"], "continuity.work.next.id", errors)
            _nonempty_string(next_work["description"], "continuity.work.next.description", errors)
            references = _string_list(
                next_work["references"],
                "continuity.work.next.references",
                errors,
                minimum=1,
            )
            for index, reference in enumerate(references):
                _https_url(
                    reference,
                    f"continuity.work.next.references[{index}]",
                    errors,
                )
            _string_list(next_work["depends_on"], "continuity.work.next.depends_on", errors)

    state = continuity["state"]
    state_keys = {"base", "candidate", "live", "parallel_changes"}
    if _closed_keys(state, state_keys, "continuity.state", errors):
        base = state["base"]
        if _closed_keys(base, {"revision", "ref", "verified_at"}, "continuity.state.base", errors):
            if base["revision"] != "unborn" and not (
                isinstance(base["revision"], str)
                and re.fullmatch(r"[0-9a-f]{40}", base["revision"])
            ):
                errors.append("continuity.state.base.revision must be unborn or a full commit SHA")
            _nonempty_string(base["ref"], "continuity.state.base.ref", errors)
            _date_time(base["verified_at"], "continuity.state.base.verified_at", errors)
        candidate = state["candidate"]
        candidate_keys = {"branch", "revision", "pull_request", "handoff_state"}
        if _closed_keys(candidate, candidate_keys, "continuity.state.candidate", errors):
            if candidate["branch"] is not None:
                _nonempty_string(candidate["branch"], "continuity.state.candidate.branch", errors)
            if candidate["revision"] is not None and not (
                isinstance(candidate["revision"], str)
                and re.fullmatch(r"[0-9a-f]{40}", candidate["revision"])
            ):
                errors.append("continuity.state.candidate.revision must be null or a full commit SHA")
            if candidate["pull_request"] is not None:
                _validate_reference(
                    candidate["pull_request"],
                    "continuity.state.candidate.pull_request",
                    errors,
                )
            _enum_string(
                candidate["handoff_state"],
                {
                    "no-active-change",
                    "in-progress",
                    "ready-for-review",
                    "review-reference-recorded",
                    "post-merge-reconciliation",
                    "abandoned",
                },
                "continuity.state.candidate.handoff_state",
                errors,
            )
        live = state["live"]
        live_keys = {"status", "observed_at", "default_branch_revision", "issue_state", "pull_request_state", "notes"}
        if _closed_keys(live, live_keys, "continuity.state.live", errors):
            _enum_string(
                live["status"],
                {"verified", "partial", "unavailable"},
                "continuity.state.live.status",
                errors,
            )
            if mode == "materialize" and live["status"] != "verified":
                errors.append("materialize mode requires verified live state; use provisional mode")
            if mode == "provisional" and live["status"] == "verified":
                errors.append("provisional mode must expose partial or unavailable live state")
            _date_time(
                live["observed_at"],
                "continuity.state.live.observed_at",
                errors,
            )
            _nonempty_string(live["notes"], "continuity.state.live.notes", errors)
            if live["default_branch_revision"] is not None and not (
                isinstance(live["default_branch_revision"], str)
                and re.fullmatch(r"[0-9a-f]{40}", live["default_branch_revision"])
            ):
                errors.append(
                    "continuity.state.live.default_branch_revision must be null or a full commit SHA"
                )
            if live["status"] == "verified" and live["default_branch_revision"] is None:
                errors.append("verified live state requires a default branch revision")
            _enum_string(
                live["issue_state"],
                {"open", "closed", "unknown", "not-applicable"},
                "continuity.state.live.issue_state",
                errors,
            )
            _enum_string(
                live["pull_request_state"],
                {"draft", "open", "merged", "closed", "unknown", "not-applicable"},
                "continuity.state.live.pull_request_state",
                errors,
            )
        parallel_changes = state["parallel_changes"]
        if not isinstance(parallel_changes, list):
            errors.append("continuity.state.parallel_changes must be an array")
        else:
            for index, reference in enumerate(parallel_changes):
                _validate_reference(reference, f"continuity.state.parallel_changes[{index}]", errors)

    review = continuity["review"]
    review_keys = {"status", "reviewed_at", "reviewed_by", "evidence", "environment_limitations"}
    if _closed_keys(review, review_keys, "continuity.review", errors):
        _enum_string(
            review["status"],
            {"passed", "partial", "failed", "not-run"},
            "continuity.review.status",
            errors,
        )
        if review["status"] == "not-run":
            if review["reviewed_at"] is not None or review["reviewed_by"] is not None:
                errors.append("not-run review must not declare reviewer metadata")
        elif isinstance(review["status"], str) and review["status"] in {
            "passed",
            "partial",
            "failed",
        }:
            _date_time(review["reviewed_at"], "continuity.review.reviewed_at", errors)
            _nonempty_string(review["reviewed_by"], "continuity.review.reviewed_by", errors)
        evidence = review["evidence"]
        if not isinstance(evidence, list) or not evidence:
            errors.append("continuity.review.evidence must be a non-empty array")
        else:
            evidence_keys = {"command", "outcome", "observed_at", "notes"}
            for index, item in enumerate(evidence):
                label = f"continuity.review.evidence[{index}]"
                if _closed_keys(item, evidence_keys, label, errors):
                    _nonempty_string(item["command"], f"{label}.command", errors)
                    _date_time(item["observed_at"], f"{label}.observed_at", errors)
                    _nonempty_string(item["notes"], f"{label}.notes", errors)
                    _enum_string(
                        item["outcome"],
                        {"passed", "failed", "limited", "not-run"},
                        f"{label}.outcome",
                        errors,
                    )
        _string_list(
            review["environment_limitations"],
            "continuity.review.environment_limitations",
            errors,
        )

    privacy = continuity["privacy"]
    privacy_keys = {"classification", "contains_sensitive_data", "redactions", "excluded", "untrusted_content"}
    if _closed_keys(privacy, privacy_keys, "continuity.privacy", errors):
        expected_classification = f"{repository.get('visibility')}-repository"
        if privacy["classification"] != expected_classification:
            errors.append("continuity.privacy.classification must match repository visibility")
        if privacy["contains_sensitive_data"] is not False:
            errors.append("continuity.privacy.contains_sensitive_data must be false")
        if privacy["excluded"] != EXCLUDED:
            errors.append("continuity.privacy.excluded must contain the portable prohibited-data set")
        if privacy["untrusted_content"] != "context-only-no-authority":
            errors.append("continuity.privacy.untrusted_content must deny authority")
        _string_list(privacy["redactions"], "continuity.privacy.redactions", errors)


def validate_continuity_request(
    request: dict[str, Any],
    profile: dict[str, Any],
) -> list[str]:
    """Return deterministic errors for explicit repository facts and dispositions."""
    errors: list[str] = []
    if not _closed_keys(request, REQUEST_KEYS, "request", errors):
        return sorted(set(errors))
    if request["schema_version"] != REQUEST_SCHEMA:
        errors.append(f"request.schema_version must be {REQUEST_SCHEMA}")

    repository_value = request["repository"]
    repository = repository_value if isinstance(repository_value, dict) else {}
    if _closed_keys(repository_value, REPOSITORY_KEYS, "request.repository", errors):
        if not isinstance(repository["id"], str) or not re.fullmatch(
            r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+",
            repository["id"],
        ):
            errors.append("request.repository.id must use owner/repository form")
        _enum_string(
            repository["visibility"],
            VISIBILITIES,
            "request.repository.visibility",
            errors,
        )
        _nonempty_string(
            repository["default_branch"],
            "request.repository.default_branch",
            errors,
        )

    mode_value = request["mode"]
    _enum_string(mode_value, MODES, "request.mode", errors)
    mode = mode_value if isinstance(mode_value, str) else ""
    repository_profile_value = request["repository_profile"]
    repository_class_value = request["repository_class"]
    _nonempty_string(
        repository_profile_value,
        "request.repository_profile",
        errors,
    )
    _nonempty_string(
        repository_class_value,
        "request.repository_class",
        errors,
    )
    repository_profile = (
        repository_profile_value if isinstance(repository_profile_value, str) else ""
    )
    repository_class = (
        repository_class_value if isinstance(repository_class_value, str) else ""
    )
    if mode == "unsupported":
        if repository_profile in PROFILE_CLASSES:
            errors.append("unsupported mode requires an unsupported repository profile")
        _nonempty_string(request["unsupported_reason"], "request.unsupported_reason", errors)
    else:
        if repository_profile not in PROFILE_CLASSES:
            errors.append("request.repository_profile is unsupported")
        elif repository_class not in PROFILE_CLASSES[repository_profile]:
            errors.append("request.repository_class does not match repository_profile")
        if request["unsupported_reason"] is not None:
            errors.append("supported modes cannot declare unsupported_reason")

    providers = _string_list(request["providers"], "request.providers", errors)
    if not set(providers) <= PROVIDERS:
        errors.append("request.providers contains an unsupported provider")

    candidates_value = request["parallel_candidates"]
    candidates = candidates_value if isinstance(candidates_value, list) else []
    if not isinstance(candidates_value, list):
        errors.append("request.parallel_candidates must be an array")
    else:
        for index, reference in enumerate(candidates):
            _validate_reference(reference, f"request.parallel_candidates[{index}]", errors)
        if any(
            candidate == previous
            for index, candidate in enumerate(candidates)
            for previous in candidates[:index]
        ):
            errors.append("request.parallel_candidates must not contain duplicates")
        if mode == "parallel-conflict" and len(candidates) < 2:
            errors.append("parallel-conflict mode requires at least two candidates")
        if candidates and mode in {"materialize", "provisional"}:
            _nonempty_string(
                request["parallel_reconciliation"],
                "request.parallel_reconciliation",
                errors,
            )
    reconciliation = request["parallel_reconciliation"]
    if reconciliation is not None:
        _nonempty_string(reconciliation, "request.parallel_reconciliation", errors)
    if mode in {"opt-out", "unsupported", "parallel-conflict"}:
        if reconciliation is not None:
            errors.append(f"{mode} mode cannot declare parallel_reconciliation")
        if mode in {"opt-out", "unsupported"} and candidates:
            errors.append(f"{mode} mode cannot declare parallel_candidates")
    elif not candidates and reconciliation is not None:
        errors.append("parallel_reconciliation requires parallel_candidates")

    if mode == "opt-out":
        opt_out = request["opt_out"]
        if _closed_keys(opt_out, OPT_OUT_KEYS, "request.opt_out", errors):
            if opt_out["enabled"] is not True:
                errors.append("request.opt_out.enabled must be true")
            _nonempty_string(opt_out["reason"], "request.opt_out.reason", errors)
            if opt_out["reference"] is not None:
                _nonempty_string(opt_out["reference"], "request.opt_out.reference", errors)
    elif request["opt_out"] is not None:
        errors.append("request.opt_out is only valid in opt-out mode")

    writes_content = mode in {"materialize", "provisional"}
    if writes_content:
        _validate_continuity_metadata(request["continuity"], repository, mode, errors)
        if isinstance(request["continuity"], dict):
            continuity_state = request["continuity"].get("state")
            if isinstance(continuity_state, dict) and continuity_state.get(
                "parallel_changes"
            ) != candidates:
                errors.append(
                    "continuity.state.parallel_changes must exactly match parallel_candidates"
                )
        sections = request["sections"]
        if _closed_keys(sections, SECTION_KEYS, "request.sections", errors):
            _nonempty_string(
                sections["purpose_and_precedence"],
                "request.sections.purpose_and_precedence",
                errors,
            )
            _nonempty_string(
                sections["privacy_and_redaction"],
                "request.sections.privacy_and_redaction",
                errors,
            )
            for key in (
                "completed_changes",
                "blockers",
                "risks",
                "unknowns",
                "deferred_work",
            ):
                minimum = 1 if mode == "provisional" and key == "unknowns" else 0
                _string_list(
                    sections[key],
                    f"request.sections.{key}",
                    errors,
                    minimum=minimum,
                )
        migration = request["continuity_migration"]
        if migration is not None:
            if _closed_keys(
                migration,
                CONTINUITY_MIGRATION_KEYS,
                "request.continuity_migration",
                errors,
            ):
                if not isinstance(migration["expected_sha256"], str) or not re.fullmatch(
                    r"[0-9a-f]{64}", migration["expected_sha256"]
                ):
                    errors.append(
                        "request.continuity_migration.expected_sha256 must be SHA-256"
                    )
                _nonempty_string(
                    migration["reason"],
                    "request.continuity_migration.reason",
                    errors,
                )
                _https_url(
                    migration["evidence_url"],
                    "request.continuity_migration.evidence_url",
                    errors,
                )
    elif (
        request["continuity"] is not None
        or request["continuity_migration"] is not None
        or request["sections"] is not None
    ):
        errors.append(f"{mode} mode cannot carry materializable continuity content")

    declared_profiles = {item["id"]: item for item in profile["repository_profiles"]}
    if mode != "unsupported" and repository_profile not in declared_profiles:
        errors.append("request.repository_profile is absent from the pinned profile")
    elif mode != "unsupported":
        declared_profile = declared_profiles[repository_profile]
        profile_visibility = set(declared_profile["visibilities"])
        profile_classes = set(declared_profile["repository_classes"])
        visibility = repository.get("visibility")
        if not isinstance(visibility, str) or visibility not in profile_visibility:
            errors.append("request repository visibility is not allowed by repository_profile")
        if repository_class not in profile_classes:
            errors.append("request repository class is not allowed by repository_profile")

    _validate_safety(request, errors)
    return sorted(set(errors))


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise MaterializationError(f"unsupported YAML scalar type: {type(value).__name__}")


def _yaml_lines(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key in sorted(value):
            child = value[key]
            if not isinstance(key, str):
                raise MaterializationError("continuity metadata keys must be strings")
            if isinstance(child, (dict, list)):
                if isinstance(child, list) and not child:
                    lines.append(f"{prefix}{key}: []")
                else:
                    lines.append(f"{prefix}{key}:")
                    lines.extend(_yaml_lines(child, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(child)}")
        return lines
    if isinstance(value, list):
        lines = []
        for child in value:
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_yaml_lines(child, indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(child)}")
        return lines
    return [f"{prefix}{_yaml_scalar(value)}"]


def _bullet_lines(values: list[str], empty: str = "None observed.") -> list[str]:
    return [f"- {value}" for value in values] if values else [f"- {empty}"]


def _reference_text(reference: dict[str, Any] | None) -> str:
    if reference is None:
        return "None"
    return f"[{reference['provider']} {reference['id']}]({reference['url']})"


def _continuity_structure_errors(content: bytes) -> list[str]:
    errors: list[str] = []
    if len(content) > MAX_BYTES:
        errors.append(f"CONTINUITY.md exceeds {MAX_BYTES} UTF-8 bytes")
    if len(content.splitlines()) > MAX_LINES:
        errors.append(f"CONTINUITY.md exceeds {MAX_LINES} lines")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return [*errors, "CONTINUITY.md is not UTF-8"]
    positions = [text.find(f"## {heading}") for heading in REQUIRED_HEADINGS]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        errors.append("CONTINUITY.md required headings are missing or out of order")
    if any(text.count(f"## {heading}") != 1 for heading in REQUIRED_HEADINGS):
        errors.append("CONTINUITY.md required headings must appear exactly once")
    if re.search(r"<[A-Za-z][^>]*>", text):
        errors.append("CONTINUITY.md contains unresolved template placeholders")
    return errors


def render_continuity(
    request: dict[str, Any],
    template_sections: dict[str, str],
) -> bytes:
    """Render a complete Aether v1 checkpoint from validated explicit facts."""
    continuity = request["continuity"]
    sections = request["sections"]
    repository = continuity["repository"]
    work = continuity["work"]
    state = continuity["state"]
    review = continuity["review"]
    privacy = continuity["privacy"]
    lines = ["---", *_yaml_lines(continuity), "---", ""]
    lines.extend(
        [
            f"# {repository['id'].split('/', 1)[-1]} continuity",
            "",
            "## Purpose and precedence",
            "",
            sections["purpose_and_precedence"],
            "",
            "This checkpoint is subordinate to the authority order recorded in its front matter; it does not replace repository instructions, architecture, roadmaps, decisions, Git, or the work tracker.",
            "",
            "## Resume protocol",
            "",
            *template_sections["Resume protocol"].splitlines(),
            "",
            "## Current objective and success conditions",
            "",
            f"- Objective: {work['objective']}",
            *[f"- Success: {value}" for value in work["success_conditions"]],
            "",
            "## State snapshot",
            "",
            f"- Verified base: `{state['base']['revision']}` at `{state['base']['ref']}`, checked `{state['base']['verified_at']}`.",
            f"- Candidate: branch `{state['candidate']['branch'] or 'none'}`; revision `{state['candidate']['revision'] or 'not recorded'}`; handoff `{state['candidate']['handoff_state']}`; pull request {_reference_text(state['candidate']['pull_request'])}.",
            f"- Live observation: `{state['live']['status']}` at `{state['live']['observed_at']}`; default branch `{state['live']['default_branch_revision'] or 'unavailable'}`; issue `{state['live']['issue_state']}`; pull request `{state['live']['pull_request_state']}`. {state['live']['notes']}",
            "",
            "## Completed and material changes",
            "",
            *_bullet_lines(sections["completed_changes"]),
            "",
            "## Validation and review evidence",
            "",
        ]
    )
    for evidence in review["evidence"]:
        lines.append(
            f"- `{evidence['command']}` — {evidence['outcome']} at {evidence['observed_at']}. {evidence['notes']}"
        )
    if review["environment_limitations"]:
        lines.append("- Environment limitations: " + "; ".join(review["environment_limitations"]))
    else:
        lines.append("- Environment limitations: None observed.")
    lines.extend(
        [
            "",
            "## Blockers, risks, unknowns, and deferred work",
            "",
            "### Blockers",
            "",
            *_bullet_lines(sections["blockers"]),
            "",
            "### Risks",
            "",
            *_bullet_lines(sections["risks"]),
            "",
            "### Unknowns",
            "",
            *_bullet_lines(sections["unknowns"]),
            "",
            "### Deferred",
            "",
            *_bullet_lines(sections["deferred_work"]),
            "",
            "## Next dependency-ready work",
            "",
            f"{work['next']['kind'].title()} `{work['next']['id']}` is `{work['next']['readiness']}`: {work['next']['description']}",
            "",
            "References: " + ", ".join(work["next"]["references"]),
            "",
            "Depends on: " + (", ".join(work["next"]["depends_on"]) or "None."),
            "",
            "## Parallel changes and reconciliation",
            "",
        ]
    )
    if state["parallel_changes"]:
        lines.extend(f"- {_reference_text(reference)}" for reference in state["parallel_changes"])
        lines.extend(["", request["parallel_reconciliation"]])
    else:
        lines.append("None observed.")
    lines.extend(
        [
            "",
            "## Privacy and redaction",
            "",
            sections["privacy_and_redaction"],
            "",
            f"Classification: `{privacy['classification']}`. Prohibited sensitive data present: `false`. Applied redaction categories: {', '.join(privacy['redactions']) or 'none'}.",
            "",
            "## Handoff update protocol",
            "",
            *template_sections["Handoff update protocol"].splitlines(),
            "",
            "## Compaction and supersession",
            "",
            *template_sections["Compaction and supersession"].splitlines(),
        ]
    )
    content = ("\n".join(lines) + "\n").encode("utf-8")
    structure_errors = _continuity_structure_errors(content)
    if structure_errors:
        raise MaterializationError(
            "rendered CONTINUITY.md is invalid: " + "; ".join(structure_errors)
        )
    return content


def _profile_artifact(
    profile: dict[str, Any],
    role: str,
    artifact_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    for source in profile["sources"]:
        if source["role"] != role:
            continue
        for artifact in source["artifacts"]:
            if artifact["id"] == artifact_id:
                return source, artifact
    raise MaterializationError(
        f"continuity profile does not declare {role}:{artifact_id}"
    )


def _read_pinned_artifact(
    profile: dict[str, Any],
    source_root: Path,
    role: str,
    artifact_id: str,
) -> tuple[bytes, dict[str, Any]]:
    source, artifact = _profile_artifact(profile, role, artifact_id)
    root = source_root.resolve()
    path = source_root / artifact["path"]
    candidate = source_root
    for part in artifact["path"].split("/"):
        candidate = candidate / part
        if candidate.is_symlink():
            raise MaterializationError(
                f"continuity source artifact uses a symlink: {artifact['path']}"
            )
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise MaterializationError(
            f"continuity source artifact escapes its root: {artifact['path']}"
        )
    if not path.is_file():
        raise MaterializationError(
            f"continuity source artifact is missing or not a regular file: {artifact['path']}"
        )
    content = path.read_bytes()
    if sha256_bytes(content) != artifact["sha256"]:
        raise MaterializationError(
            f"continuity source artifact digest mismatch: {artifact['path']}"
        )
    return content, {
        "role": role,
        "artifact": artifact_id,
        "repository": source["repository"],
        "revision": source["revision"],
        "version": source["version"],
        "lifecycle": source["lifecycle"],
        "release_included": source["release_included"],
        "path": artifact["path"],
        "sha256": artifact["sha256"],
    }


def _managed_block(content: bytes, artifact_id: str) -> bytes:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MaterializationError(
            f"continuity provider projection is not UTF-8: {artifact_id}"
        ) from error
    region = _canonical_marker_region(text)
    if region is None:
        raise MaterializationError(
            f"continuity provider projection has invalid, reversed, inline, or fenced managed markers: {artifact_id}"
        )
    return region[2].encode("utf-8")


def _template_headings(content: bytes) -> list[str]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MaterializationError("continuity template is not UTF-8") from error
    return [line[3:] for line in text.splitlines() if line.startswith("## ")]


def _template_static_sections(content: bytes) -> dict[str, str]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MaterializationError("continuity template is not UTF-8") from error
    matches = list(re.finditer(r"^## (.+)$", text, flags=re.MULTILINE))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        finish = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[match.end():finish].strip("\n")
    static_headings = {
        "Resume protocol",
        "Handoff update protocol",
        "Compaction and supersession",
    }
    for heading in static_headings:
        body = sections.get(heading)
        if not body:
            raise MaterializationError(
                f"pinned continuity template has no static {heading!r} body"
            )
        if re.search(r"<[A-Za-z][^>]*>", body):
            raise MaterializationError(
                f"pinned continuity template static {heading!r} body has placeholders"
            )
    return {heading: sections[heading] for heading in sorted(static_headings)}


def _source_contracts(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Return path-independent, complete source pins for plan and state provenance."""
    contracts = []
    for source in profile["sources"]:
        artifacts = [
            {
                "id": artifact["id"],
                "kind": artifact["kind"],
                "path": artifact["path"],
                "sha256": artifact["sha256"],
                "url": artifact["url"],
            }
            for artifact in sorted(source["artifacts"], key=lambda item: item["id"])
        ]
        contracts.append(
            {
                "id": source["id"],
                "role": source["role"],
                "repository": source["repository"],
                "revision": source["revision"],
                "version": source["version"],
                "lifecycle": source["lifecycle"],
                "release_included": source["release_included"],
                "artifacts": artifacts,
            }
        )
    return sorted(contracts, key=lambda item: item["role"])


def _load_inputs(
    profile_path: Path,
    aether_source: Path,
) -> tuple[dict[str, Any], dict[str, bytes], dict[str, str], dict[str, Any]]:
    try:
        profile = load_json(profile_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise MaterializationError(f"unable to load continuity profile: {error}") from error
    profile_errors = validate_profile(profile)
    if profile_errors:
        raise MaterializationError(
            "continuity profile is invalid: " + "; ".join(profile_errors)
        )
    if not aether_source.is_dir():
        raise MaterializationError(
            f"continuity Aether source is not a directory: {aether_source}"
        )
    if aether_source.is_symlink():
        raise MaterializationError("continuity Aether source root cannot be a symlink")

    template, template_provenance = _read_pinned_artifact(
        profile,
        aether_source,
        "portable-contract",
        "continuity-template",
    )
    if _template_headings(template) != REQUIRED_HEADINGS:
        raise MaterializationError(
            "pinned continuity template headings do not match the supported v1 renderer"
        )
    template_sections = _template_static_sections(template)

    selected: dict[str, bytes] = {}
    provenance = [template_provenance]
    surface_artifacts = {
        "AGENTS.md": "codex-repository-instructions",
        ".github/copilot-instructions.md": "github-copilot-instructions",
        "CLAUDE.md": "claude-repository-instructions",
    }
    for path, artifact_id in surface_artifacts.items():
        projection, record = _read_pinned_artifact(
            profile,
            aether_source,
            "portable-contract",
            artifact_id,
        )
        selected[path] = _managed_block(projection, artifact_id)
        provenance.append(record)
    return profile, selected, template_sections, {
        "profile_sha256": sha256_file(profile_path),
        "profile_version": profile["version"],
        "rollout_stage": profile["rollout"]["stage"],
        "source_contracts": _source_contracts(profile),
        "artifacts": sorted(provenance, key=lambda item: item["artifact"]),
    }


def _load_state_snapshot(
    target: Path,
) -> tuple[dict[str, Any] | None, bytes | None]:
    path = _secure_target_path(target, STATE_RELATIVE_PATH)
    if not path.exists():
        return None, None
    if path.is_symlink() or not path.is_file():
        raise MaterializationError("continuity state is not a regular file")
    try:
        state_bytes = path.read_bytes()
        state = json.loads(state_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MaterializationError(f"unable to read continuity state: {error}") from error
    expected_keys = {
        "schema_version",
        "adapter_version",
        "repository",
        "repository_profile",
        "mode",
        "request_sha256",
        "profile_sha256",
        "profile_version",
        "rollout_stage",
        "source_contracts",
        "surfaces",
        "plan_id",
        "rollback_manifest",
        "rollback_sha256",
    }
    if not isinstance(state, dict) or set(state) != expected_keys:
        raise MaterializationError("unsupported or malformed continuity state")
    if state.get("schema_version") != STATE_SCHEMA:
        raise MaterializationError("unsupported or malformed continuity state")
    if state.get("adapter_version") != ADAPTER_VERSION:
        raise MaterializationError("continuity state has an unsupported adapter_version")
    if not isinstance(state.get("mode"), str) or state["mode"] not in {
        "materialize",
        "provisional",
    }:
        raise MaterializationError("continuity state has an unsupported mode")
    if not isinstance(state.get("rollout_stage"), str) or state[
        "rollout_stage"
    ] not in {"observe", "ratchet", "enforce"}:
        raise MaterializationError("continuity state has an unsupported rollout_stage")
    for key in ("repository_profile", "profile_version"):
        if not isinstance(state.get(key), str) or not state[key].strip():
            raise MaterializationError(f"continuity state has invalid {key}")
    for key in ("request_sha256", "profile_sha256", "plan_id"):
        if not isinstance(state.get(key), str) or not re.fullmatch(
            r"[0-9a-f]{64}", state[key]
        ):
            raise MaterializationError(f"continuity state has invalid {key}")
    if not isinstance(state.get("repository"), str) or not re.fullmatch(
        r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", state["repository"]
    ):
        raise MaterializationError("continuity state has invalid repository")
    _validate_state_source_contracts(state.get("source_contracts"))
    if not isinstance(state.get("surfaces"), list):
        raise MaterializationError("continuity state surfaces must be an array")
    expected_rollback = re.fullmatch(
        re.escape(f"{BACKUPS_RELATIVE_PATH}/{state['plan_id']}/")
        + r"attempt-[0-9]{3,}/rollback\.v1\.json",
        state["rollback_manifest"],
    ) if isinstance(state.get("rollback_manifest"), str) else None
    if expected_rollback is None:
        raise MaterializationError("continuity state has an unsafe rollback_manifest")
    if not isinstance(state.get("rollback_sha256"), str) or not re.fullmatch(
        r"[0-9a-f]{64}", state["rollback_sha256"]
    ):
        raise MaterializationError("continuity state has invalid rollback_sha256")
    return state, state_bytes


def _load_state(target: Path) -> dict[str, Any] | None:
    state, _ = _load_state_snapshot(target)
    return state


def _validate_state_source_contracts(value: Any) -> None:
    source_keys = {
        "id",
        "role",
        "repository",
        "revision",
        "version",
        "lifecycle",
        "release_included",
        "artifacts",
    }
    artifact_keys = {"id", "kind", "path", "sha256", "url"}
    if not isinstance(value, list) or len(value) != 3:
        raise MaterializationError(
            "continuity state source_contracts must contain three pins"
        )
    roles: set[str] = set()
    for source in value:
        if not isinstance(source, dict) or set(source) != source_keys:
            raise MaterializationError("continuity state contains a malformed source pin")
        role = source["role"]
        expected_source = EXPECTED_SOURCES.get(role) if isinstance(role, str) else None
        if (
            not isinstance(role, str)
            or role not in SOURCE_ROLE_REPOSITORIES
            or role in roles
            or expected_source is None
            or source["id"] != expected_source[0]
            or source["repository"] != expected_source[1]
            or not isinstance(source["revision"], str)
            or not re.fullmatch(r"[0-9a-f]{40}", source["revision"])
            or source["version"] != expected_source[2]
            or source["lifecycle"] != expected_source[3]
            or source["release_included"] is not expected_source[4]
            or not isinstance(source["artifacts"], list)
            or len(source["artifacts"]) != len(EXPECTED_ARTIFACTS[role])
        ):
            raise MaterializationError("continuity state contains an invalid source pin")
        roles.add(role)
        artifact_ids: set[str] = set()
        for artifact in source["artifacts"]:
            if not isinstance(artifact, dict) or set(artifact) != artifact_keys:
                raise MaterializationError(
                    "continuity state contains malformed source artifact provenance"
                )
            artifact_id = artifact["id"]
            path = artifact["path"]
            expected_artifact = (
                EXPECTED_ARTIFACTS[role].get(artifact_id)
                if isinstance(artifact_id, str)
                else None
            )
            if (
                not isinstance(artifact_id, str)
                or artifact_id in artifact_ids
                or expected_artifact is None
                or not isinstance(path, str)
                or artifact["kind"] != expected_artifact[0]
                or path != expected_artifact[1]
                or not isinstance(artifact["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"])
                or artifact["url"]
                != f"https://github.com/{source['repository']}/blob/{source['revision']}/{path}"
            ):
                raise MaterializationError(
                    "continuity state contains invalid source artifact provenance"
                )
            try:
                safe_relative_path(path, allow_internal=True)
            except MaterializationError as error:
                raise MaterializationError(
                    "continuity state contains unsafe source artifact provenance"
                ) from error
            artifact_ids.add(artifact_id)
        if artifact_ids != set(EXPECTED_ARTIFACTS[role]):
            raise MaterializationError(
                "continuity state source artifacts do not match the approved profile"
            )
    if roles != set(SOURCE_ROLE_REPOSITORIES):
        raise MaterializationError("continuity state source roles are incomplete")


def _state_surfaces(state: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if state is None:
        return {}
    if not 2 <= len(state["surfaces"]) <= 4:
        raise MaterializationError("continuity state must contain two to four surfaces")
    portable_contract = next(
        source
        for source in state["source_contracts"]
        if source["role"] == "portable-contract"
    )
    result: dict[str, dict[str, Any]] = {}
    for record in state["surfaces"]:
        expected_keys = {
            "path",
            "owner",
            "adapter_owner",
            "strategy",
            "applied_file_sha256",
            "managed_block_sha256",
            "source",
            "source_usage",
        }
        if not isinstance(record, dict) or set(record) != expected_keys:
            raise MaterializationError("malformed surface record in continuity state")
        path = record["path"]
        if not isinstance(path, str) or path not in SURFACE_PATHS:
            raise MaterializationError("unsafe surface path in continuity state")
        if record["owner"] != "consumer-repository" or record[
            "adapter_owner"
        ] != "egohygiene/holon":
            raise MaterializationError("invalid surface ownership in continuity state")
        if not isinstance(record["strategy"], str) or record["strategy"] not in {
            "evidence-grounded-template",
            "managed-block",
            "preserve-repository-owned",
        }:
            raise MaterializationError("invalid surface strategy in continuity state")
        if not isinstance(record["applied_file_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", record["applied_file_sha256"]
        ):
            raise MaterializationError(
                "invalid surface applied_file_sha256 in continuity state"
            )
        managed_digest = record["managed_block_sha256"]
        if managed_digest is not None and (
            not isinstance(managed_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", managed_digest)
        ):
            raise MaterializationError(
                "invalid surface managed_block_sha256 in continuity state"
            )
        source = record["source"]
        provenance_keys = {
            "role",
            "artifact",
            "repository",
            "revision",
            "version",
            "lifecycle",
            "release_included",
            "path",
            "sha256",
        }
        if (
            not isinstance(source, dict)
            or set(source) != provenance_keys
            or source["role"] != "portable-contract"
            or source["repository"] != "egohygiene/aether"
            or not isinstance(source["revision"], str)
            or not re.fullmatch(r"[0-9a-f]{40}", source["revision"])
            or not isinstance(source["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"])
            or not isinstance(source["version"], str)
            or not source["version"].strip()
            or not isinstance(source["lifecycle"], str)
            or not source["lifecycle"].strip()
            or not isinstance(source["release_included"], bool)
            or not isinstance(source["path"], str)
            or not source["path"].strip()
        ):
            raise MaterializationError("invalid surface source in continuity state")
        expected_artifacts = {
            "CONTINUITY.md": "continuity-template",
            "AGENTS.md": "codex-repository-instructions",
            ".github/copilot-instructions.md": "github-copilot-instructions",
            "CLAUDE.md": "claude-repository-instructions",
        }
        if source["artifact"] != expected_artifacts[path]:
            raise MaterializationError("surface source does not match its path")
        source_artifact = next(
            (
                artifact
                for artifact in portable_contract["artifacts"]
                if artifact["id"] == source["artifact"]
            ),
            None,
        )
        expected_source = (
            {
                "role": portable_contract["role"],
                "artifact": source_artifact["id"],
                "repository": portable_contract["repository"],
                "revision": portable_contract["revision"],
                "version": portable_contract["version"],
                "lifecycle": portable_contract["lifecycle"],
                "release_included": portable_contract["release_included"],
                "path": source_artifact["path"],
                "sha256": source_artifact["sha256"],
            }
            if source_artifact is not None
            else None
        )
        if source != expected_source:
            raise MaterializationError(
                "surface source does not match pinned source_contracts"
            )
        if path == "CONTINUITY.md":
            if record["managed_block_sha256"] is not None or record["strategy"] not in {
                "evidence-grounded-template",
                "preserve-repository-owned",
            }:
                raise MaterializationError("invalid CONTINUITY.md ownership state")
            expected_usage = (
                "consulted-contract"
                if record["strategy"] == "preserve-repository-owned"
                else "evidence-grounded-template"
            )
        elif record["managed_block_sha256"] is None or record["strategy"] != "managed-block":
            raise MaterializationError("invalid managed instruction ownership state")
        else:
            expected_usage = "managed-block"
        if record["source_usage"] != expected_usage:
            raise MaterializationError("invalid surface source_usage in continuity state")
        if path in result:
            raise MaterializationError(f"duplicate surface in continuity state: {path}")
        result[path] = record
    if not {"CONTINUITY.md", "AGENTS.md"} <= set(result):
        raise MaterializationError("continuity state is missing a required surface")
    return result


def _unsafe_path_component(target: Path, relative: str) -> str | None:
    normalized = safe_relative_path(relative, allow_internal=True)
    candidate = target
    parts = normalized.split("/")
    for index, part in enumerate(parts):
        candidate = candidate / part
        if candidate.is_symlink():
            return "symlink"
        if index < len(parts) - 1 and candidate.exists() and not candidate.is_dir():
            return "non-directory parent"
    return None


def _secure_target_path(target: Path, relative: str) -> Path:
    issue = _unsafe_path_component(target, relative)
    if issue is not None:
        raise MaterializationError(
            f"repository path contains an unsupported {issue}: {relative}"
        )
    return target_path(target, relative)


@contextmanager
def _continuity_lock(target: Path) -> Iterator[None]:
    internal_root = _secure_target_path(target, ".holon")
    internal_root_existed = internal_root.exists()
    try:
        internal_root.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise MaterializationError(
            f"unable to prepare repository-continuity lock: {error}"
        ) from error
    lock_path = _secure_target_path(target, LOCK_RELATIVE_PATH)
    try:
        lock_path.mkdir()
    except FileExistsError as error:
        raise MaterializationError(
            "another repository-continuity apply or rollback is active; "
            f"remove stale {LOCK_RELATIVE_PATH} only after confirming no operation is running"
        ) from error
    except OSError as error:
        raise MaterializationError(
            f"unable to acquire repository-continuity lock: {error}"
        ) from error
    try:
        yield
    finally:
        try:
            lock_path.rmdir()
        except OSError as error:
            raise MaterializationError(
                f"unable to release repository-continuity lock: {error}"
            ) from error
        if not internal_root_existed:
            try:
                internal_root.rmdir()
            except OSError:
                # Successful materialization leaves state/backups beneath this root.
                pass


def _read_target_file(target: Path, relative: str) -> tuple[str, bytes | None]:
    if _unsafe_path_component(target, relative) is not None:
        return "non-regular", None
    path = _secure_target_path(target, relative)
    if not path.exists():
        return "missing", None
    if not path.is_file():
        return "non-regular", None
    try:
        return "file", path.read_bytes()
    except OSError as error:
        raise MaterializationError(
            f"unable to read repository-owned path {relative}: {error}"
        ) from error


def _decode_target(content: bytes, relative: str) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MaterializationError(f"repository-owned Markdown is not UTF-8: {relative}") from error


def _inside_markdown_fence(text: str, position: int) -> bool:
    fence_character: str | None = None
    fence_length = 0
    offset = 0
    for line in text.splitlines(keepends=True):
        if offset >= position:
            break
        indentation = len(line) - len(line.lstrip(" "))
        stripped = line[indentation:] if indentation <= 3 else ""
        match = re.match(r"(`{3,}|~{3,})", stripped)
        if match:
            marker = match.group(1)
            remainder = stripped[len(marker):].rstrip("\r\n")
            if fence_character is None:
                if marker[0] == "`" and "`" in remainder:
                    offset += len(line)
                    continue
                fence_character = marker[0]
                fence_length = len(marker)
            elif (
                marker[0] == fence_character
                and len(marker) >= fence_length
                and not remainder.strip(" \t")
            ):
                fence_character = None
                fence_length = 0
        offset += len(line)
    return fence_character is not None


def _canonical_marker_region(text: str) -> tuple[int, int, str] | None:
    if text.count(MANAGED_BEGIN) != 1 or text.count(MANAGED_END) != 1:
        return None
    begin_matches = list(
        re.finditer(rf"^{re.escape(MANAGED_BEGIN)}\r?$", text, flags=re.MULTILINE)
    )
    end_matches = list(
        re.finditer(rf"^{re.escape(MANAGED_END)}\r?$", text, flags=re.MULTILINE)
    )
    if len(begin_matches) != 1 or len(end_matches) != 1:
        return None
    begin = begin_matches[0]
    end = end_matches[0]
    if end.start() <= begin.end() or _inside_markdown_fence(
        text, begin.start()
    ) or _inside_markdown_fence(text, end.start()):
        return None
    start = begin.start()
    finish = end.end()
    if finish < len(text) and text[finish] == "\n":
        finish += 1
    return start, finish, text[start:finish]


def _find_block(text: str) -> tuple[int, int, str] | None:
    return _canonical_marker_region(text)


def _new_instruction_content(relative: str, block: bytes) -> bytes:
    headings = {
        "AGENTS.md": "# AGENTS.md",
        ".github/copilot-instructions.md": "# GitHub Copilot repository instructions",
        "CLAUDE.md": "# CLAUDE.md",
    }
    return f"{headings[relative]}\n\n".encode("utf-8") + block


def _append_block(current: bytes, block: bytes) -> bytes:
    if not current:
        return block
    separator = b"\n" if current.endswith(b"\n") else b"\n\n"
    if current.endswith(b"\n\n"):
        separator = b""
    return current + separator + block


def _diff(relative: str, before: bytes | None, after: bytes | None) -> str:
    try:
        before_text = "" if before is None else _decode_target(before, relative)
        after_text = "" if after is None else _decode_target(after, relative)
    except MaterializationError:
        return ""
    def lf_records(text: str) -> list[str]:
        parts = text.split("\n")
        records = [part + "\n" for part in parts[:-1]]
        if parts[-1]:
            records.append(parts[-1])
        return records

    records = difflib.unified_diff(
        lf_records(before_text),
        lf_records(after_text),
        fromfile="/dev/null" if before is None else f"a/{relative}",
        tofile="/dev/null" if after is None else f"b/{relative}",
        lineterm="\n",
    )
    rendered: list[str] = []
    for record in records:
        if record.endswith("\n"):
            rendered.append(record)
            continue
        rendered.append(record + "\n")
        rendered.append("\\ No newline at end of file\n")
    if not rendered:
        return ""
    return "".join(rendered)


def _operation(
    *,
    action: str,
    path: str,
    reason: str,
    before: bytes | None,
    after: bytes | None,
    source: dict[str, Any] | None,
    managed_block_sha256: str | None = None,
) -> dict[str, Any]:
    if action in {"conflict", "opt-out", "unsupported", "preserve"}:
        source_usage = "consulted-contract"
    elif path == "CONTINUITY.md":
        source_usage = "evidence-grounded-template"
    else:
        source_usage = "managed-block"
    return {
        "action": action,
        "path": path,
        "owner": "consumer-repository",
        "adapter_owner": "egohygiene/holon",
        "source": source,
        "source_usage": source_usage,
        "previous_sha256": sha256_bytes(before) if before is not None else None,
        "proposed_sha256": sha256_bytes(after) if after is not None else None,
        "managed_block_sha256": managed_block_sha256,
        "proposed_content": after.decode("utf-8") if after is not None else None,
        "diff": (
            ""
            if action in {"conflict", "opt-out", "unsupported"}
            else _diff(path, before, after)
        ),
        "reason": reason,
    }


def _source_for_path(inputs: dict[str, Any], path: str) -> dict[str, Any] | None:
    artifact_ids = {
        "CONTINUITY.md": "continuity-template",
        "AGENTS.md": "codex-repository-instructions",
        ".github/copilot-instructions.md": "github-copilot-instructions",
        "CLAUDE.md": "claude-repository-instructions",
    }
    artifact_id = artifact_ids.get(path)
    return next(
        (
            record
            for record in inputs["artifacts"]
            if record["artifact"] == artifact_id
        ),
        None,
    )


def _plan_continuity_surface(
    target: Path,
    desired: bytes,
    state_record: dict[str, Any] | None,
    source: dict[str, Any],
    migration: dict[str, Any] | None,
) -> dict[str, Any]:
    kind, current = _read_target_file(target, "CONTINUITY.md")
    if kind == "non-regular":
        return _operation(
            action="conflict",
            path="CONTINUITY.md",
            reason="continuity destination exists but is a symlink or non-regular file",
            before=None,
            after=None,
            source=source,
        )
    if kind == "missing":
        if migration is not None:
            return _operation(
                action="conflict",
                path="CONTINUITY.md",
                reason="continuity migration expected an existing file",
                before=None,
                after=None,
                source=source,
            )
        if state_record is not None and state_record.get(
            "strategy"
        ) != "preserve-repository-owned":
            return _operation(
                action="conflict",
                path="CONTINUITY.md",
                reason="previously materialized continuity file is missing",
                before=None,
                after=None,
                source=source,
            )
        return _operation(
            action="create",
            path="CONTINUITY.md",
            reason="evidence-grounded continuity file does not exist",
            before=None,
            after=desired,
            source=source,
        )
    assert current is not None
    try:
        _decode_target(current, "CONTINUITY.md")
    except MaterializationError:
        return _operation(
            action="conflict",
            path="CONTINUITY.md",
            reason="existing CONTINUITY.md is not UTF-8 Markdown",
            before=current,
            after=None,
            source=source,
        )
    if migration is not None:
        current_sha = sha256_bytes(current)
        if current == desired:
            return _operation(
                action="noop",
                path="CONTINUITY.md",
                reason="reviewed continuity migration already matches proposed bytes",
                before=current,
                after=current,
                source=source,
            )
        if current_sha != migration["expected_sha256"]:
            return _operation(
                action="conflict",
                path="CONTINUITY.md",
                reason="existing continuity file does not match the reviewed migration SHA-256",
                before=current,
                after=current,
                source=source,
            )
        action = "update"
        reason = (
            "replace the exact reviewed continuity revision: "
            + migration["reason"]
            + f" ({migration['evidence_url']})"
        )
        return _operation(
            action=action,
            path="CONTINUITY.md",
            reason=reason,
            before=current,
            after=desired,
            source=source,
        )
    if current == desired:
        action = "noop"
        reason = "existing repository-owned continuity file already matches proposed bytes"
    else:
        action = "preserve"
        reason = "existing CONTINUITY.md is repository-owned and is never overwritten by scaffolding"
    return _operation(
        action=action,
        path="CONTINUITY.md",
        reason=reason,
        before=current,
        after=current,
        source=source,
    )


def _plan_instruction_surface(
    target: Path,
    relative: str,
    desired_block: bytes,
    state_record: dict[str, Any] | None,
    source: dict[str, Any],
) -> dict[str, Any]:
    kind, current = _read_target_file(target, relative)
    desired_block_sha = sha256_bytes(desired_block)
    if kind == "non-regular":
        return _operation(
            action="conflict",
            path=relative,
            reason="instruction destination exists but is a symlink or non-regular file",
            before=None,
            after=None,
            source=source,
            managed_block_sha256=desired_block_sha,
        )
    if kind == "missing":
        if state_record is not None:
            return _operation(
                action="conflict",
                path=relative,
                reason="previously reconciled instruction surface is missing",
                before=None,
                after=None,
                source=source,
                managed_block_sha256=desired_block_sha,
            )
        proposed = _new_instruction_content(relative, desired_block)
        return _operation(
            action="create",
            path=relative,
            reason="instruction surface does not exist",
            before=None,
            after=proposed,
            source=source,
            managed_block_sha256=desired_block_sha,
        )

    assert current is not None
    try:
        text = _decode_target(current, relative)
    except MaterializationError:
        return _operation(
            action="conflict",
            path=relative,
            reason="existing instruction surface is not UTF-8 Markdown",
            before=current,
            after=None,
            source=source,
            managed_block_sha256=desired_block_sha,
        )
    begin_count = text.count(MANAGED_BEGIN)
    end_count = text.count(MANAGED_END)
    if begin_count == 0 and end_count == 0:
        proposed = _append_block(current, desired_block)
        return _operation(
            action="update",
            path=relative,
            reason="append one canonical managed block while preserving authored bytes",
            before=current,
            after=proposed,
            source=source,
            managed_block_sha256=desired_block_sha,
        )
    region = _find_block(text)
    if region is None:
        return _operation(
            action="conflict",
            path=relative,
            reason="managed block markers are duplicated, missing, unbalanced, or malformed",
            before=current,
            after=current,
            source=source,
            managed_block_sha256=desired_block_sha,
        )
    start, finish, current_block = region
    current_block_bytes = current_block.encode("utf-8")
    current_block_sha = sha256_bytes(current_block_bytes)
    if current_block_bytes == desired_block:
        return _operation(
            action="noop",
            path=relative,
            reason="canonical managed block already matches the pinned projection",
            before=current,
            after=current,
            source=source,
            managed_block_sha256=desired_block_sha,
        )
    if state_record is None:
        return _operation(
            action="conflict",
            path=relative,
            reason="existing noncanonical managed block has no trusted Holon state",
            before=current,
            after=current,
            source=source,
            managed_block_sha256=desired_block_sha,
        )
    if state_record.get("managed_block_sha256") != current_block_sha:
        return _operation(
            action="conflict",
            path=relative,
            reason="managed block differs from the last applied checksum",
            before=current,
            after=current,
            source=source,
            managed_block_sha256=desired_block_sha,
        )
    proposed_text = text[:start] + desired_block.decode("utf-8") + text[finish:]
    proposed = proposed_text.encode("utf-8")
    return _operation(
        action="update",
        path=relative,
        reason="replace only the verified managed block and preserve surrounding prose",
        before=current,
        after=proposed,
        source=source,
        managed_block_sha256=desired_block_sha,
    )


def _no_write_operations(
    request: dict[str, Any],
    inputs: dict[str, Any],
) -> list[dict[str, Any]]:
    paths = ["CONTINUITY.md", "AGENTS.md"]
    if "github-copilot" in request["providers"]:
        paths.append(".github/copilot-instructions.md")
    if "claude-code" in request["providers"]:
        paths.append("CLAUDE.md")
    mode = request["mode"]
    if mode == "opt-out":
        action = "opt-out"
        reason = "explicit repository opt-out: " + request["opt_out"]["reason"]
    elif mode == "unsupported":
        action = "unsupported"
        reason = "unsupported repository profile: " + request["unsupported_reason"]
    else:
        action = "conflict"
        reason = "parallel candidates require semantic reconciliation before any write"
    return [
        _operation(
            action=action,
            path=path,
            reason=reason,
            before=None,
            after=None,
            source=_source_for_path(inputs, path),
        )
        for path in sorted(paths)
    ]


def _next_state(
    request: dict[str, Any],
    inputs: dict[str, Any],
    operations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if request["mode"] in {"opt-out", "unsupported", "parallel-conflict"} or any(
        operation["action"] == "conflict" for operation in operations
    ):
        return None
    surfaces = []
    for operation in operations:
        if operation["action"] in {"conflict", "opt-out", "unsupported"}:
            continue
        if operation["path"] == "CONTINUITY.md":
            strategy = (
                "preserve-repository-owned"
                if operation["action"] == "preserve"
                else "evidence-grounded-template"
            )
        else:
            strategy = "managed-block"
        surfaces.append(
            {
                "path": operation["path"],
                "owner": operation["owner"],
                "adapter_owner": operation["adapter_owner"],
                "strategy": strategy,
                "applied_file_sha256": operation["proposed_sha256"],
                "managed_block_sha256": operation["managed_block_sha256"],
                "source": operation["source"],
                "source_usage": operation["source_usage"],
            }
        )
    return {
        "schema_version": STATE_SCHEMA,
        "adapter_version": ADAPTER_VERSION,
        "repository": request["repository"]["id"],
        "repository_profile": request["repository_profile"],
        "mode": request["mode"],
        "request_sha256": sha256_bytes(canonical_bytes(request)),
        "profile_sha256": inputs["profile_sha256"],
        "profile_version": inputs["profile_version"],
        "rollout_stage": inputs["rollout_stage"],
        "source_contracts": inputs["source_contracts"],
        "surfaces": surfaces,
    }


def build_continuity_plan(
    request: dict[str, Any],
    target: Path,
    *,
    profile_path: Path,
    aether_source: Path,
) -> dict[str, Any]:
    """Build a deterministic, exact-byte repository-continuity preview."""
    target = validate_target_root(target)
    profile, projection_blocks, template_sections, inputs = _load_inputs(
        profile_path,
        aether_source,
    )
    errors = validate_continuity_request(request, profile)
    if errors:
        raise MaterializationError("continuity request is invalid: " + "; ".join(errors))

    state, prior_state_bytes = _load_state_snapshot(target)
    prior_state_sha256 = (
        sha256_bytes(prior_state_bytes) if prior_state_bytes is not None else None
    )
    prior_surfaces = _state_surfaces(state)
    if request["mode"] in {"opt-out", "unsupported", "parallel-conflict"}:
        operations = _no_write_operations(request, inputs)
    else:
        desired_continuity = render_continuity(request, template_sections)
        operations = [
            _plan_continuity_surface(
                target,
                desired_continuity,
                prior_surfaces.get("CONTINUITY.md"),
                _source_for_path(inputs, "CONTINUITY.md"),
                request["continuity_migration"],
            ),
            _plan_instruction_surface(
                target,
                "AGENTS.md",
                projection_blocks["AGENTS.md"],
                prior_surfaces.get("AGENTS.md"),
                _source_for_path(inputs, "AGENTS.md"),
            ),
        ]
        if "github-copilot" in request["providers"]:
            operations.append(
                _plan_instruction_surface(
                    target,
                    ".github/copilot-instructions.md",
                    projection_blocks[".github/copilot-instructions.md"],
                    prior_surfaces.get(".github/copilot-instructions.md"),
                    _source_for_path(inputs, ".github/copilot-instructions.md"),
                )
            )
        if "claude-code" in request["providers"]:
            operations.append(
                _plan_instruction_surface(
                    target,
                    "CLAUDE.md",
                    projection_blocks["CLAUDE.md"],
                    prior_surfaces.get("CLAUDE.md"),
                    _source_for_path(inputs, "CLAUDE.md"),
                )
            )
        operations.sort(key=lambda item: item["path"])

    summary: dict[str, int] = {}
    for operation in operations:
        summary[operation["action"]] = summary.get(operation["action"], 0) + 1
    next_state = _next_state(request, inputs, operations)
    payload = {
        "schema_version": PLAN_SCHEMA,
        "adapter_version": ADAPTER_VERSION,
        "repository": request["repository"]["id"],
        "repository_profile": request["repository_profile"],
        "mode": request["mode"],
        "request_sha256": sha256_bytes(canonical_bytes(request)),
        "prior_state_sha256": prior_state_sha256,
        "request": request,
        "inputs": inputs,
        "operations": operations,
        "summary": {key: summary[key] for key in sorted(summary)},
        "next_state": next_state,
        "authority": {
            "credentials": False,
            "external_write": False,
            "merge": False,
            "publish": False,
        },
    }
    plan = dict(payload)
    plan["plan_id"] = sha256_bytes(canonical_bytes(payload))
    return plan


def validate_continuity_plan(plan: dict[str, Any]) -> None:
    """Reject malformed or modified continuity plans before application."""
    if not isinstance(plan, dict) or plan.get("schema_version") != PLAN_SCHEMA:
        raise MaterializationError("unsupported continuity plan schema")
    expected_keys = {
        "schema_version",
        "adapter_version",
        "repository",
        "repository_profile",
        "mode",
        "request_sha256",
        "prior_state_sha256",
        "request",
        "inputs",
        "operations",
        "summary",
        "next_state",
        "authority",
        "plan_id",
    }
    if set(plan) != expected_keys:
        raise MaterializationError("continuity plan has unsupported or missing fields")
    if plan["adapter_version"] != ADAPTER_VERSION:
        raise MaterializationError("continuity plan has an unsupported adapter_version")
    if not isinstance(plan["repository"], str) or not re.fullmatch(
        r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", plan["repository"]
    ):
        raise MaterializationError("continuity plan has an invalid repository")
    if not isinstance(plan["repository_profile"], str) or not plan[
        "repository_profile"
    ].strip():
        raise MaterializationError("continuity plan has an invalid repository_profile")
    if not isinstance(plan["mode"], str) or plan["mode"] not in MODES:
        raise MaterializationError("continuity plan has an unsupported mode")

    def valid_sha256(value: Any, *, nullable: bool = False) -> bool:
        return (nullable and value is None) or (
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
        )

    if not valid_sha256(plan["request_sha256"]):
        raise MaterializationError("continuity plan has an invalid request_sha256")
    if not valid_sha256(plan["prior_state_sha256"], nullable=True):
        raise MaterializationError("continuity plan has an invalid prior_state_sha256")

    request = plan["request"]
    validation_profile = {
        "repository_profiles": [
            {
                "id": profile_id,
                "repository_classes": sorted(PROFILE_CLASSES[profile_id]),
                "visibilities": sorted(PROFILE_VISIBILITIES[profile_id]),
            }
            for profile_id in sorted(PROFILE_CLASSES)
        ]
    }
    if not isinstance(request, dict):
        raise MaterializationError("continuity plan request is malformed")
    request_errors = validate_continuity_request(request, validation_profile)
    if request_errors:
        raise MaterializationError(
            "continuity plan request is invalid: " + "; ".join(request_errors)
        )
    request_sha256 = sha256_bytes(canonical_bytes(request))
    if request_sha256 != plan["request_sha256"]:
        raise MaterializationError("continuity plan request digest is invalid")
    if (
        plan["repository"] != request["repository"]["id"]
        or plan["repository_profile"] != request["repository_profile"]
        or plan["mode"] != request["mode"]
    ):
        raise MaterializationError("continuity plan identity does not match its request")

    inputs = plan["inputs"]
    input_keys = {
        "profile_sha256",
        "profile_version",
        "rollout_stage",
        "source_contracts",
        "artifacts",
    }
    if not isinstance(inputs, dict) or set(inputs) != input_keys:
        raise MaterializationError("continuity plan inputs are malformed")
    if not valid_sha256(inputs["profile_sha256"]):
        raise MaterializationError("continuity plan has an invalid profile_sha256")
    if not isinstance(inputs["profile_version"], str) or not inputs[
        "profile_version"
    ].strip():
        raise MaterializationError("continuity plan has an invalid profile_version")
    if not isinstance(inputs["rollout_stage"], str) or inputs[
        "rollout_stage"
    ] not in {"observe", "ratchet", "enforce"}:
        raise MaterializationError("continuity plan has an invalid rollout_stage")
    _validate_state_source_contracts(inputs["source_contracts"])

    artifact_keys = {
        "role",
        "artifact",
        "repository",
        "revision",
        "version",
        "lifecycle",
        "release_included",
        "path",
        "sha256",
    }
    artifacts = inputs["artifacts"]
    expected_artifact_ids = {
        "continuity-template",
        "codex-repository-instructions",
        "github-copilot-instructions",
        "claude-repository-instructions",
    }
    if not isinstance(artifacts, list) or len(artifacts) != 4:
        raise MaterializationError("continuity plan must pin four Aether artifacts")
    portable_contract = next(
        source
        for source in inputs["source_contracts"]
        if source["role"] == "portable-contract"
    )
    artifact_ids: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != artifact_keys:
            raise MaterializationError("continuity plan contains malformed artifact provenance")
        artifact_id = artifact["artifact"]
        if not isinstance(artifact_id, str):
            raise MaterializationError("continuity plan artifact provenance is inconsistent")
        source_artifact = next(
            (
                candidate
                for candidate in portable_contract["artifacts"]
                if candidate["id"] == artifact_id
            ),
            None,
        )
        expected_provenance = (
            {
                "role": portable_contract["role"],
                "artifact": source_artifact["id"],
                "repository": portable_contract["repository"],
                "revision": portable_contract["revision"],
                "version": portable_contract["version"],
                "lifecycle": portable_contract["lifecycle"],
                "release_included": portable_contract["release_included"],
                "path": source_artifact["path"],
                "sha256": source_artifact["sha256"],
            }
            if source_artifact is not None
            else None
        )
        if artifact != expected_provenance or artifact_id in artifact_ids:
            raise MaterializationError("continuity plan artifact provenance is inconsistent")
        artifact_ids.add(artifact_id)
    if artifact_ids != expected_artifact_ids or artifacts != sorted(
        artifacts, key=lambda item: item["artifact"]
    ):
        raise MaterializationError("continuity plan artifact pins are incomplete or unordered")

    operations = plan["operations"]
    operation_keys = {
        "action",
        "path",
        "owner",
        "adapter_owner",
        "source",
        "source_usage",
        "previous_sha256",
        "proposed_sha256",
        "managed_block_sha256",
        "proposed_content",
        "diff",
        "reason",
    }
    expected_paths = {"CONTINUITY.md", "AGENTS.md"}
    if "github-copilot" in request["providers"]:
        expected_paths.add(".github/copilot-instructions.md")
    if "claude-code" in request["providers"]:
        expected_paths.add("CLAUDE.md")
    if not isinstance(operations, list) or not 2 <= len(operations) <= 4:
        raise MaterializationError("continuity plan must contain two to four operations")
    seen_paths: set[str] = set()
    actions: list[str] = []
    allowed_actions = {
        "create",
        "update",
        "noop",
        "preserve",
        "conflict",
        "opt-out",
        "unsupported",
    }
    for operation in operations:
        if not isinstance(operation, dict) or set(operation) != operation_keys:
            raise MaterializationError("continuity plan contains a malformed operation")
        path = operation["path"]
        action = operation["action"]
        if (
            not isinstance(path, str)
            or not isinstance(action, str)
            or path not in SURFACE_PATHS
            or path in seen_paths
            or action not in allowed_actions
        ):
            raise MaterializationError("continuity plan contains an unsupported operation")
        if operation["owner"] != "consumer-repository" or operation[
            "adapter_owner"
        ] != "egohygiene/holon":
            raise MaterializationError("continuity plan contains invalid operation ownership")
        if operation["source"] != _source_for_path(inputs, path):
            raise MaterializationError("continuity plan operation source does not match its path")
        expected_usage = (
            "consulted-contract"
            if action in {"conflict", "opt-out", "unsupported", "preserve"}
            else "evidence-grounded-template"
            if path == "CONTINUITY.md"
            else "managed-block"
        )
        if operation["source_usage"] != expected_usage:
            raise MaterializationError("continuity plan contains invalid source_usage")
        for key in ("previous_sha256", "proposed_sha256", "managed_block_sha256"):
            if not valid_sha256(operation[key], nullable=True):
                raise MaterializationError(f"continuity plan operation has an invalid {key}")
        content = operation["proposed_content"]
        if content is not None and not isinstance(content, str):
            raise MaterializationError("continuity plan proposed_content must be text or null")
        if (content is None) != (operation["proposed_sha256"] is None):
            raise MaterializationError("continuity plan proposed content and digest disagree")
        if content is not None and sha256_bytes(content.encode("utf-8")) != operation[
            "proposed_sha256"
        ]:
            raise MaterializationError("continuity plan proposed content digest is invalid")
        if not isinstance(operation["diff"], str) or not isinstance(
            operation["reason"], str
        ) or not operation["reason"].strip():
            raise MaterializationError("continuity plan operation explanation is malformed")
        if path == "CONTINUITY.md" and operation["managed_block_sha256"] is not None:
            raise MaterializationError("CONTINUITY.md cannot claim managed-block ownership")
        if path != "CONTINUITY.md":
            expected_managed_digest = request["mode"] in {"materialize", "provisional"}
            if expected_managed_digest != (operation["managed_block_sha256"] is not None):
                raise MaterializationError("continuity plan managed-block digest is inconsistent")
        if action == "create" and operation["previous_sha256"] is not None:
            raise MaterializationError("continuity create operation cannot have a preimage digest")
        if action in {"create", "update"} and (
            content is None or not operation["diff"]
        ):
            raise MaterializationError("continuity write operation lacks exact preview bytes")
        if action in {"update", "noop", "preserve"} and operation[
            "previous_sha256"
        ] is None:
            raise MaterializationError("continuity operation lacks its preimage digest")
        if action in {"noop", "preserve"} and (
            operation["previous_sha256"] != operation["proposed_sha256"]
            or operation["diff"]
        ):
            raise MaterializationError("continuity no-write operation changes bytes")
        if action in {"conflict", "opt-out", "unsupported"} and operation["diff"]:
            raise MaterializationError("continuity no-write disposition cannot contain a diff")
        if action in {"opt-out", "unsupported"} and any(
            operation[key] is not None
            for key in (
                "previous_sha256",
                "proposed_sha256",
                "managed_block_sha256",
                "proposed_content",
            )
        ):
            raise MaterializationError("continuity disposition operation cannot carry write bytes")
        seen_paths.add(path)
        actions.append(action)
    if seen_paths != expected_paths or operations != sorted(
        operations, key=lambda item: item["path"]
    ):
        raise MaterializationError("continuity plan operations do not match selected surfaces")

    mode_actions = {
        "opt-out": {"opt-out"},
        "unsupported": {"unsupported"},
        "parallel-conflict": {"conflict"},
    }
    if plan["mode"] in mode_actions and set(actions) != mode_actions[plan["mode"]]:
        raise MaterializationError("continuity plan actions do not match its disposition")
    if plan["mode"] in {"materialize", "provisional"} and not set(actions) <= {
        "create",
        "update",
        "noop",
        "preserve",
        "conflict",
    }:
        raise MaterializationError("continuity plan has an invalid materialization action")
    expected_summary = {
        action: actions.count(action) for action in sorted(set(actions))
    }
    if plan["summary"] != expected_summary:
        raise MaterializationError("continuity plan summary does not match its operations")
    try:
        expected_next_state = _next_state(request, inputs, operations)
    except (KeyError, TypeError, ValueError) as error:
        raise MaterializationError("continuity plan next state inputs are malformed") from error
    if plan["next_state"] != expected_next_state:
        raise MaterializationError("continuity plan next_state does not match its operations")

    plan_id = plan.get("plan_id")
    if not isinstance(plan_id, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_id):
        raise MaterializationError("continuity plan is missing a valid plan_id")
    payload = {key: value for key, value in plan.items() if key != "plan_id"}
    try:
        payload_sha256 = sha256_bytes(canonical_bytes(payload))
    except (TypeError, ValueError) as error:
        raise MaterializationError("continuity plan is not canonical JSON") from error
    if payload_sha256 != plan_id:
        raise MaterializationError("continuity plan content does not match its plan_id")
    if plan.get("authority") != {
        "credentials": False,
        "external_write": False,
        "merge": False,
        "publish": False,
    }:
        raise MaterializationError("continuity plan cannot grant external authority")


def _next_backup(target: Path, plan_id: str) -> tuple[str, Path]:
    parent_relative = f"{BACKUPS_RELATIVE_PATH}/{plan_id}"
    parent = _secure_target_path(target, parent_relative)
    parent.mkdir(parents=True, exist_ok=True)
    attempt = 1
    while (parent / f"attempt-{attempt:03d}").exists():
        attempt += 1
    relative = f"{parent_relative}/attempt-{attempt:03d}"
    root = target / relative
    root.mkdir(parents=True, exist_ok=False)
    return relative, root


def _assert_operation_preimage(
    target: Path,
    operation: dict[str, Any],
) -> bytes | None:
    kind, content = _read_target_file(target, operation["path"])
    action = operation["action"]
    if action == "create":
        if kind != "missing" or operation["previous_sha256"] is not None:
            raise MaterializationError(
                f"continuity target changed after preview: {operation['path']}"
            )
        return None
    if action in {"update", "noop", "preserve"}:
        if (
            kind != "file"
            or content is None
            or sha256_bytes(content) != operation["previous_sha256"]
        ):
            raise MaterializationError(
                f"continuity target changed after preview: {operation['path']}"
            )
        return content
    raise MaterializationError(
        f"unsupported continuity operation during apply: {action}"
    )


def _assert_operation_postimage(
    target: Path,
    operation: dict[str, Any],
) -> None:
    kind, content = _read_target_file(target, operation["path"])
    if (
        kind != "file"
        or content is None
        or sha256_bytes(content) != operation["proposed_sha256"]
    ):
        raise MaterializationError(
            f"continuity target changed during apply: {operation['path']}"
        )


def apply_continuity_plan(
    plan: dict[str, Any],
    target: Path,
    *,
    profile_path: Path,
    aether_source: Path,
) -> dict[str, Any]:
    """Apply one reviewed plan under a repository-local fail-closed lock."""
    target = validate_target_root(target)
    with _continuity_lock(target):
        return _apply_continuity_plan_locked(
            plan,
            target,
            profile_path=profile_path,
            aether_source=aether_source,
        )


def _apply_continuity_plan_locked(
    plan: dict[str, Any],
    target: Path,
    *,
    profile_path: Path,
    aether_source: Path,
) -> dict[str, Any]:
    """Recompute and atomically apply an exact reviewed continuity plan."""
    validate_continuity_plan(plan)
    target = validate_target_root(target)
    current_plan = build_continuity_plan(
        plan["request"],
        target,
        profile_path=profile_path,
        aether_source=aether_source,
    )
    if current_plan["plan_id"] != plan["plan_id"]:
        raise MaterializationError(
            "target, request, profile, or source changed after preview; create a new plan"
        )
    non_materializable = {
        operation["action"]
        for operation in plan["operations"]
        if operation["action"] in {"conflict", "opt-out", "unsupported"}
    }
    if non_materializable:
        raise MaterializationError(
            "continuity plan is not materializable: "
            + ", ".join(sorted(non_materializable))
        )

    prior_state, prior_state_bytes = _load_state_snapshot(target)
    actual_prior_state_sha256 = (
        sha256_bytes(prior_state_bytes) if prior_state_bytes is not None else None
    )
    if actual_prior_state_sha256 != plan["prior_state_sha256"]:
        raise MaterializationError(
            "continuity state changed after preview; create a new plan"
        )
    preimages = {
        operation["path"]: _assert_operation_preimage(target, operation)
        for operation in plan["operations"]
    }
    if prior_state is not None and all(
        operation["action"] in {"noop", "preserve"}
        for operation in plan["operations"]
    ):
        if not isinstance(plan["next_state"], dict):
            raise MaterializationError("continuity plan has no materializable next state")
        prior_contract = {
            key: prior_state.get(key) for key in plan["next_state"]
        }
        if prior_contract == plan["next_state"]:
            for operation in plan["operations"]:
                _assert_operation_postimage(target, operation)
            return prior_state
    backup_relative, backup_root = _next_backup(target, plan["plan_id"])
    if prior_state_bytes is not None:
        atomic_write(backup_root / "state-before.json", prior_state_bytes)

    rollback_operations = []
    for operation in plan["operations"]:
        if operation["action"] not in {"create", "update"}:
            continue
        backup_path: str | None = None
        if operation["action"] == "update":
            backup_path = f"files/{operation['path']}"
            backup_destination = _secure_target_path(backup_root, backup_path)
            backup_destination.parent.mkdir(parents=True, exist_ok=True)
            preimage = preimages[operation["path"]]
            if preimage is None:
                raise MaterializationError(
                    f"continuity update has no preimage: {operation['path']}"
                )
            atomic_write(backup_destination, preimage)
        rollback_operations.append(
            {
                "action": operation["action"],
                "path": operation["path"],
                "expected_after_sha256": operation["proposed_sha256"],
                "previous_sha256": operation["previous_sha256"],
                "backup_path": backup_path,
            }
        )
    rollback = {
        "schema_version": ROLLBACK_SCHEMA,
        "plan_id": plan["plan_id"],
        "repository": plan["repository"],
        "prior_state_present": prior_state is not None,
        "prior_state_sha256": (
            sha256_bytes(prior_state_bytes) if prior_state_bytes is not None else None
        ),
        "operations": rollback_operations,
    }
    rollback_bytes = pretty_json_bytes(rollback)
    atomic_write(backup_root / "rollback.v1.json", rollback_bytes)

    applied: list[dict[str, Any]] = []
    proposed_state_bytes: bytes | None = None
    try:
        for operation in plan["operations"]:
            if operation["action"] not in {"create", "update"}:
                continue
            content = operation["proposed_content"]
            if not isinstance(content, str):
                raise MaterializationError(
                    f"continuity plan has no proposed content for {operation['path']}"
                )
            encoded = content.encode("utf-8")
            if sha256_bytes(encoded) != operation["proposed_sha256"]:
                raise MaterializationError(
                    f"continuity proposed content changed for {operation['path']}"
                )
            _assert_operation_preimage(target, operation)
            atomic_write(_secure_target_path(target, operation["path"]), encoded)
            applied.append(operation)

        for operation in plan["operations"]:
            _assert_operation_postimage(target, operation)

        if not isinstance(plan["next_state"], dict):
            raise MaterializationError("continuity plan has no materializable next state")
        state = dict(plan["next_state"])
        state["plan_id"] = plan["plan_id"]
        state["rollback_manifest"] = f"{backup_relative}/rollback.v1.json"
        state["rollback_sha256"] = sha256_bytes(rollback_bytes)
        proposed_state_bytes = pretty_json_bytes(state)
        atomic_write(
            _secure_target_path(target, STATE_RELATIVE_PATH),
            proposed_state_bytes,
        )
        return state
    except Exception as error:
        compensation_errors: list[str] = []
        for operation in reversed(applied):
            try:
                kind, content = _read_target_file(target, operation["path"])
                if operation["action"] == "create":
                    if kind == "missing":
                        continue
                    if (
                        kind == "file"
                        and content is not None
                        and sha256_bytes(content) == operation["proposed_sha256"]
                    ):
                        _secure_target_path(target, operation["path"]).unlink()
                        continue
                    compensation_errors.append(operation["path"])
                    continue
                preimage = preimages[operation["path"]]
                assert preimage is not None
                if (
                    kind == "file"
                    and content is not None
                    and sha256_bytes(content) == operation["previous_sha256"]
                ):
                    continue
                if (
                    kind == "file"
                    and content is not None
                    and sha256_bytes(content) == operation["proposed_sha256"]
                ):
                    atomic_write(
                        _secure_target_path(target, operation["path"]),
                        preimage,
                    )
                    continue
                compensation_errors.append(operation["path"])
            except (OSError, MaterializationError):
                compensation_errors.append(operation["path"])
        try:
            state_path = _secure_target_path(target, STATE_RELATIVE_PATH)
            if not state_path.exists():
                if prior_state is not None:
                    compensation_errors.append(STATE_RELATIVE_PATH)
            elif not state_path.is_file():
                compensation_errors.append(STATE_RELATIVE_PATH)
            else:
                current_state_bytes = state_path.read_bytes()
                if prior_state is None:
                    if (
                        proposed_state_bytes is not None
                        and current_state_bytes == proposed_state_bytes
                    ):
                        state_path.unlink()
                    else:
                        compensation_errors.append(STATE_RELATIVE_PATH)
                elif current_state_bytes == prior_state_bytes:
                    pass
                elif (
                    proposed_state_bytes is not None
                    and current_state_bytes == proposed_state_bytes
                ):
                    assert prior_state_bytes is not None
                    atomic_write(state_path, prior_state_bytes)
                else:
                    compensation_errors.append(STATE_RELATIVE_PATH)
        except (OSError, MaterializationError):
            compensation_errors.append(STATE_RELATIVE_PATH)
        if compensation_errors:
            raise MaterializationError(
                "continuity apply failed and automatic recovery refused concurrent edits: "
                + ", ".join(sorted(set(compensation_errors)))
            ) from error
        raise


def verify_continuity_target(target: Path) -> list[str]:
    """Verify continuity structure and managed-block ownership without owning prose."""
    target = validate_target_root(target)
    try:
        state = _load_state(target)
        surfaces = _state_surfaces(state)
    except MaterializationError as error:
        return [str(error)]
    if state is None:
        return ["no repository-continuity materialization state exists"]
    errors: list[str] = []
    for path in sorted(surfaces):
        record = surfaces[path]
        path = record["path"]
        kind, content = _read_target_file(target, path)
        if kind != "file" or content is None:
            errors.append(f"continuity surface is missing or non-regular: {path}")
            continue
        try:
            text = _decode_target(content, path)
        except MaterializationError as error:
            errors.append(str(error))
            continue
        if path == "CONTINUITY.md":
            if record["strategy"] != "preserve-repository-owned":
                errors.extend(_continuity_structure_errors(content))
            continue
        region = _find_block(text)
        if region is None:
            errors.append(f"managed continuity block is missing or malformed: {path}")
            continue
        digest = sha256_bytes(region[2].encode("utf-8"))
        if digest != record.get("managed_block_sha256"):
            errors.append(f"managed continuity block drift: {path}")
    return sorted(set(errors))


def rollback_continuity_target(
    target: Path,
    *,
    expected_state_sha256: str | None = None,
) -> None:
    """Roll back the latest adapter apply under a repository-local lock."""
    target = validate_target_root(target)
    with _continuity_lock(target):
        _rollback_continuity_target_locked(
            target,
            expected_state_sha256=expected_state_sha256,
        )


def _rollback_continuity_target_locked(
    target: Path,
    *,
    expected_state_sha256: str | None = None,
) -> None:
    """Roll back only after every applied byte and recovery input is verified."""
    target = validate_target_root(target)
    state, applied_state_bytes = _load_state_snapshot(target)
    if state is None:
        raise MaterializationError("no repository-continuity state exists to roll back")
    assert applied_state_bytes is not None
    if expected_state_sha256 is not None:
        if not isinstance(expected_state_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_state_sha256
        ):
            raise MaterializationError(
                "expected continuity state SHA-256 must be 64 lowercase hexadecimal characters"
            )
        if sha256_bytes(applied_state_bytes) != expected_state_sha256:
            raise MaterializationError(
                "continuity state changed after rollback approval; verify it and approve its current SHA-256"
            )
    rollback_relative = state.get("rollback_manifest")
    if not isinstance(rollback_relative, str):
        raise MaterializationError("continuity state does not reference rollback metadata")
    rollback_path = _secure_target_path(target, rollback_relative)
    if not rollback_path.is_file():
        raise MaterializationError(f"continuity rollback metadata is missing: {rollback_relative}")
    try:
        rollback_bytes = rollback_path.read_bytes()
    except OSError as error:
        raise MaterializationError(
            f"unable to read continuity rollback metadata: {error}"
        ) from error
    if sha256_bytes(rollback_bytes) != state["rollback_sha256"]:
        raise MaterializationError("continuity rollback metadata digest does not match state")
    try:
        rollback = json.loads(rollback_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MaterializationError(f"invalid continuity rollback metadata: {error}") from error
    if not isinstance(rollback, dict):
        raise MaterializationError("continuity rollback metadata is malformed")
    if rollback.get("schema_version") != ROLLBACK_SCHEMA or rollback.get(
        "plan_id"
    ) != state.get("plan_id"):
        raise MaterializationError("continuity rollback metadata does not match current state")

    expected_keys = {
        "schema_version",
        "plan_id",
        "repository",
        "prior_state_present",
        "prior_state_sha256",
        "operations",
    }
    if set(rollback) != expected_keys or rollback.get("repository") != state.get(
        "repository"
    ):
        raise MaterializationError("continuity rollback metadata is malformed")
    if not isinstance(rollback.get("prior_state_present"), bool) or not isinstance(
        rollback.get("operations"), list
    ):
        raise MaterializationError("continuity rollback metadata is malformed")
    if rollback["prior_state_present"]:
        if not isinstance(rollback["prior_state_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", rollback["prior_state_sha256"]
        ):
            raise MaterializationError("continuity rollback prior state digest is invalid")
    elif rollback["prior_state_sha256"] is not None:
        raise MaterializationError("continuity rollback unexpectedly records prior state")
    seen_paths: set[str] = set()
    operation_keys = {
        "action",
        "path",
        "expected_after_sha256",
        "previous_sha256",
        "backup_path",
    }
    for operation in rollback["operations"]:
        if not isinstance(operation, dict) or set(operation) != operation_keys:
            raise MaterializationError("continuity rollback operation is malformed")
        action = operation["action"]
        path = operation["path"]
        if (
            not isinstance(action, str)
            or action not in {"create", "update"}
            or not isinstance(path, str)
            or path not in SURFACE_PATHS
        ):
            raise MaterializationError("continuity rollback operation is unsupported")
        if path in seen_paths:
            raise MaterializationError("continuity rollback contains a duplicate surface")
        seen_paths.add(path)
        if not isinstance(operation["expected_after_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", operation["expected_after_sha256"]
        ):
            raise MaterializationError("continuity rollback has an invalid applied digest")
        if action == "create":
            if operation["previous_sha256"] is not None or operation["backup_path"] is not None:
                raise MaterializationError("continuity create rollback metadata is malformed")
        else:
            if not isinstance(operation["previous_sha256"], str) or not re.fullmatch(
                r"[0-9a-f]{64}", operation["previous_sha256"]
            ):
                raise MaterializationError("continuity update rollback has an invalid digest")
            if operation["backup_path"] != f"files/{path}":
                raise MaterializationError("continuity update rollback has an unsafe backup path")

    applied_surface_bytes: dict[str, bytes] = {}
    for operation in rollback["operations"]:
        kind, content = _read_target_file(target, operation["path"])
        if kind != "file" or content is None:
            raise MaterializationError(
                f"rollback blocked because continuity surface is missing: {operation['path']}"
            )
        if sha256_bytes(content) != operation["expected_after_sha256"]:
            raise MaterializationError(
                "rollback blocked because continuity surface changed after apply: "
                + operation["path"]
            )
        applied_surface_bytes[operation["path"]] = content

    backup_root = rollback_path.parent
    restore_bytes: dict[str, bytes] = {}
    for operation in rollback["operations"]:
        if operation["action"] != "update":
            continue
        backup_path = operation["backup_path"]
        backup = _secure_target_path(backup_root, backup_path)
        if not backup.is_file():
            raise MaterializationError(
                f"continuity rollback backup is missing or invalid for {operation['path']}"
            )
        try:
            content = backup.read_bytes()
        except OSError as error:
            raise MaterializationError(
                f"unable to read continuity rollback backup for {operation['path']}: {error}"
            ) from error
        if sha256_bytes(content) != operation["previous_sha256"]:
            raise MaterializationError(
                f"continuity rollback backup is missing or invalid for {operation['path']}"
            )
        restore_bytes[operation["path"]] = content

    state_before = _secure_target_path(backup_root, "state-before.json")
    state_before_bytes: bytes | None = None
    if rollback["prior_state_present"]:
        if not state_before.is_file():
            raise MaterializationError(
                "continuity rollback expected prior state but its backup is missing"
            )
        try:
            state_before_bytes = state_before.read_bytes()
        except OSError as error:
            raise MaterializationError(
                f"unable to read continuity rollback prior state: {error}"
            ) from error
        if sha256_bytes(state_before_bytes) != rollback["prior_state_sha256"]:
            raise MaterializationError(
                "continuity rollback prior state backup is invalid"
            )

    state_path = _secure_target_path(target, STATE_RELATIVE_PATH)
    try:
        for operation in reversed(rollback["operations"]):
            destination = _secure_target_path(target, operation["path"])
            if operation["action"] == "create":
                destination.unlink()
                continue
            atomic_write(destination, restore_bytes[operation["path"]])

        if rollback.get("prior_state_present"):
            assert state_before_bytes is not None
            atomic_write(state_path, state_before_bytes)
        else:
            state_path.unlink(missing_ok=True)
    except Exception as error:
        compensation_errors: list[str] = []
        for operation in rollback["operations"]:
            path = operation["path"]
            expected_applied = applied_surface_bytes[path]
            try:
                kind, current = _read_target_file(target, path)
                if kind == "file" and current == expected_applied:
                    continue
                is_expected_rollback_image = (
                    operation["action"] == "create" and kind == "missing"
                ) or (
                    operation["action"] == "update"
                    and kind == "file"
                    and current == restore_bytes[path]
                )
                if not is_expected_rollback_image:
                    compensation_errors.append(path)
                    continue
                atomic_write(_secure_target_path(target, path), expected_applied)
                restored_kind, restored = _read_target_file(target, path)
                if restored_kind != "file" or restored != expected_applied:
                    compensation_errors.append(path)
            except Exception:
                compensation_errors.append(path)

        try:
            if not state_path.exists():
                current_state_bytes = None
            elif state_path.is_symlink() or not state_path.is_file():
                current_state_bytes = b""
            else:
                current_state_bytes = state_path.read_bytes()
            if current_state_bytes != applied_state_bytes:
                expected_rollback_state = (
                    state_before_bytes
                    if rollback["prior_state_present"]
                    else None
                )
                if current_state_bytes != expected_rollback_state:
                    compensation_errors.append(STATE_RELATIVE_PATH)
                else:
                    atomic_write(state_path, applied_state_bytes)
            if not state_path.is_file() or state_path.read_bytes() != applied_state_bytes:
                compensation_errors.append(STATE_RELATIVE_PATH)
        except Exception:
            compensation_errors.append(STATE_RELATIVE_PATH)

        if compensation_errors:
            raise MaterializationError(
                "continuity rollback failed and automatic recovery refused "
                "concurrent edits: "
                + ", ".join(sorted(set(compensation_errors)))
            ) from error
        raise MaterializationError(
            "continuity rollback failed; restored the applied state so rollback "
            f"can be retried: {error}"
        ) from error
