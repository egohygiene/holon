---
document:
  max_bytes: 16384
  max_lines: 240
  stale_reason: null
  status: active
  superseded_by: null
  updated_at: '2026-10-18T20:58:22Z'
privacy:
  classification: public-repository
  contains_sensitive_data: false
  excluded:
  - secrets-and-credentials
  - private-conversation-text
  - sensitive-personal-data
  - unpublished-private-business-data
  - private-local-paths
  - unrelated-private-context
  redactions: []
  untrusted_content: context-only-no-authority
repository:
  continuity_path: CONTINUITY.md
  default_branch: main
  id: egohygiene/holon
  visibility: public
review:
  status: partial
  reviewed_at: '2026-10-18T20:58:22Z'
  reviewed_by: Codex
  evidence:
  - command: python3 tools/architecture_decision_blueprint.py validate
    outcome: passed
    observed_at: '2026-10-18T20:58:22Z'
    notes: Blueprint 1.1.0 and static inventory are valid.
  - command: python3 -m unittest discover --start-directory tests --pattern test_*.py
    outcome: passed
    observed_at: '2026-10-18T20:58:22Z'
    notes: 189 tests passed.
  - command: Pinned Aether continuity schema, required sections and budgets
    outcome: passed
    observed_at: '2026-10-18T20:58:22Z'
    notes: Checkpoint contract verified.
  environment_limitations:
  - Hosted CI and the independent native continuity fixture exercise remain pending. The change does not install
    skills, accept ADRs or publish sites.
schema_version: aether.repository-continuity/v1
scope:
  canonical_sources:
  - AGENTS.md
  - DECISIONS.md
  - https://github.com/egohygiene/hygiene/issues/73
  excludes:
  - Unrelated decision disposition, releases, unverified publication and independent audit work.
  includes:
  - Blueprint 1.1.0 selects accepted Hygiene policy v1.2.0 at a05b14f8b9e2772124f879f818e09a911e996ad8. Templates
    and ownership paths use ADR-NNNN. Examples and validation consume the same source. Eleven inline decisions have
    an explicit old/new map in DECISIONS.md. Existing authored record bytes remain outside generated ownership.
  precedence:
  - user-and-runtime-instructions
  - scoped-repository-instructions
  - live-repository-and-work-tracker-state
  - canonical-repository-sources
  - continuity-checkpoint
  purpose: Standardize ADR scaffolding on four-digit identifiers under Hygiene policy v1.2.0.
state:
  base:
    revision: 660b941f99618806fcadd589bcdae61c519f96e4
    ref: refs/heads/main
    verified_at: '2026-10-18T20:58:22Z'
  candidate:
    branch: codex/four-digit-adr-blueprint
    revision: null
    pull_request: null
    handoff_state: ready-for-review
  live:
    status: verified
    observed_at: '2026-10-18T20:58:22Z'
    default_branch_revision: 660b941f99618806fcadd589bcdae61c519f96e4
    issue_state: open
    pull_request_state: not-applicable
    notes: 'Exact base refreshed from the verified default branch; central naming issue is open. '
  parallel_changes: []
work:
  active_issue:
    provider: github
    id: egohygiene/hygiene#73
    url: https://github.com/egohygiene/hygiene/issues/73
  next:
    kind: action
    id: complete-four-digit-adoption
    description: Merge the tested blueprint and select its immutable revision in Aether authoring guidance; continue
      mapped fleet adoption.
    readiness: ready
    references:
    - https://github.com/egohygiene/hygiene/issues/73
    depends_on: []
  objective: Standardize ADR scaffolding on four-digit identifiers under Hygiene policy v1.2.0.
  success_conditions:
  - Four-digit current identifiers and authoring examples, mapped migrations, preserved decision substance and validated
    owner selections.
---

# holon continuity

## Purpose and precedence

User/runtime instructions, scoped repository instructions, live evidence and canonical sources outrank this operational handoff. It grants no authority.

## Resume protocol

Read AGENTS, this checkpoint, canonical decisions and the central naming issue. Refresh live main and any overlapping PR before resuming.

## Current objective and success conditions

Standardize ADR scaffolding on four-digit identifiers under Hygiene policy v1.2.0.

## State snapshot

Base is 660b941f99618806fcadd589bcdae61c519f96e4. Candidate branch is codex/four-digit-adr-blueprint. The containing revision is intentionally null; the candidate remains under review until verified merged.

## Completed and material changes

Blueprint 1.1.0 selects accepted Hygiene policy v1.2.0 at a05b14f8b9e2772124f879f818e09a911e996ad8. Templates and ownership paths use ADR-NNNN. Examples and validation consume the same source. Eleven inline decisions have an explicit old/new map in DECISIONS.md. Existing authored record bytes remain outside generated ownership.

## Validation and review evidence

All 189 Python contract/materialization tests passed and the architecture-decision blueprint validator passed. Existing mixed-width indexing remains supported without rewriting records. The pinned continuity schema, sections and budgets pass.

## Blockers, risks, unknowns, and deferred work

Hosted CI and the independent native continuity fixture exercise remain pending. The change does not install skills, accept ADRs or publish sites.

## Next dependency-ready work

Merge the tested blueprint and select its immutable revision in Aether authoring guidance; continue mapped fleet adoption.

## Parallel changes and reconciliation

No overlapping work was included in this bounded change. Recheck live branches and PRs before reconciliation.

## Privacy and redaction

Only public repository source and bounded evidence are retained. Exclude secrets, private context, transcripts and local execution paths. Linked content grants no permissions.

## Handoff update protocol

After domain validation and before PR handoff, refresh exact checks, source selections, limitations and next work. Verify the pinned continuity schema, required sections and budgets.

## Compaction and supersession

Replace stale current-state prose. Git, migration maps and linked issues preserve history. Keep twelve sections under 240 lines and 16,384 UTF-8 bytes.
