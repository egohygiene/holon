---
schema_version: aether.repository-continuity/v1
repository:
  id: egohygiene/holon
  visibility: public
  default_branch: main
  continuity_path: CONTINUITY.md
document:
  status: active
  updated_at: '2026-11-12T00:32:56Z'
  max_bytes: 16384
  max_lines: 240
  stale_reason: null
  superseded_by: null
scope:
  purpose: Validate and render complete HTTPS repository-presentation destinations.
  includes: &id001
  - All four presentation input groups accept complete HTTPS destinations.
  - Unsafe inputs produce field-specific diagnostics and no proposed README diff.
  - Existing local fixture rendering remains compatible.
  excludes:
  - Unrelated audit findings, publication, and fleet adoption.
  - Full repository suites and hosted CI.
  precedence:
  - user-and-runtime-instructions
  - scoped-repository-instructions
  - live-repository-and-work-tracker-state
  - canonical-repository-sources
  - continuity-checkpoint
  canonical_sources:
  - AGENTS.md
  - DECISIONS.md
  - tools/repository_presentation_blueprint.py
  - tests/test_repository_presentation_blueprint.py
  - docs/repository-presentation-blueprint.md
  - https://github.com/egohygiene/holon/issues/75
work:
  objective: Validate and render complete HTTPS repository-presentation destinations.
  success_conditions: *id001
  active_issue:
    provider: github
    id: egohygiene/holon#75
    url: https://github.com/egohygiene/holon/issues/75
  next:
    kind: action
    id: review-audit-repair
    description: Review this focused draft and reconcile its handoff against the actual target before
      combining it with parallel work.
    readiness: ready
    references:
    - https://github.com/egohygiene/holon/issues/75
    - https://github.com/egohygiene/holon/issues/66
    depends_on: []
state:
  base:
    revision: 934e559400336cbf1acac325c89754056e27e3f2
    ref: refs/heads/main
    verified_at: '2026-11-12T00:32:56Z'
  candidate:
    branch: codex/75-presentation-https-destinations
    revision: null
    pull_request: null
    handoff_state: ready-for-review
  live:
    status: verified
    observed_at: '2026-11-12T00:32:56Z'
    default_branch_revision: 934e559400336cbf1acac325c89754056e27e3f2
    issue_state: open
    pull_request_state: not-applicable
    notes: GitHub reported issue 75 open and the source repairs in PRs 84–86 merged before this candidate
      was published.
  parallel_changes:
  - provider: github
    id: egohygiene/holon#65
    url: https://github.com/egohygiene/holon/pull/65
  - provider: github
    id: egohygiene/holon#87
    url: https://github.com/egohygiene/holon/pull/87
  - provider: github
    id: egohygiene/holon#88
    url: https://github.com/egohygiene/holon/pull/88
review:
  status: partial
  reviewed_at: '2026-11-12T00:32:56Z'
  reviewed_by: Codex
  evidence:
  - command: python3 -m unittest discover --start-directory tests --pattern "test_repository_presentation_blueprint.py"
      --verbose
    outcome: passed
    observed_at: '2026-11-12T00:32:56Z'
    notes: 11 tests on Python 3.12.14, including actual preview CLI controls.
  - command: python3 tools/repository_presentation_blueprint.py validate-fixtures
    outcome: passed
    observed_at: '2026-11-12T00:32:56Z'
    notes: All local presentation fixtures validated.
  - command: python3 tools/holon_materialize.py continuity verify --target "."
    outcome: passed
    observed_at: '2026-11-12T00:32:56Z'
    notes: Local tracked continuity state and managed instruction block verified.
  - command: Pinned Aether continuity Draft 2020-12 schema, sections, and budget checks; git diff --check
    outcome: passed
    observed_at: '2026-11-12T00:32:56Z'
    notes: Branch handoff and focused diff passed local checks.
  - command: Released EgoLint conformance and hosted CI
    outcome: not-run
    observed_at: '2026-11-12T00:32:56Z'
    notes: Full repository suites, consumer Egolint validation, and hosted CI remain deferred.
  environment_limitations:
  - Full repository suites, consumer Egolint validation, and hosted CI remain deferred.
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
---

# Holon continuity

## Purpose and precedence

Record the scoped source repair under the repository instructions and verified work tracker. The repository-presentation blueprint guide owns the destination contract.

## Resume protocol

Read AGENTS, issue 75, the source guide, and tracker 66. Verify current main and draft state before resuming.

## Current objective and success conditions

Validate and render complete HTTPS repository-presentation destinations. All four presentation input groups accept complete HTTPS destinations. Unsafe inputs produce field-specific diagnostics and no proposed README diff. Existing local fixture rendering remains compatible.

## State snapshot

Main at `934e559400336cbf1acac325c89754056e27e3f2` contains the three merged Repository Intelligence source repairs. This candidate branches from that revision for issue 75.

## Completed and material changes

The presentation validator checks HTTPS host, port, and credentials, and preserves the local reference grammar while rejecting parent-directory segments. The preview suppresses a proposed diff for unsafe destinations. The public CLI regression checks exception, banner, badge, and navigation fields.

## Validation and review evidence

11 tests on Python 3.12.14, including actual preview CLI controls. All local presentation fixtures validated. Local continuity verification and pinned schema and structure checks passed.

## Blockers, risks, unknowns, and deferred work

Full repository suites, consumer Egolint validation, and hosted CI remain deferred. Issues 77 through 79 retain remaining qualification for previously merged source.

## Next dependency-ready work

Review the issue 75 draft and reconcile its handoff against the target before combining it with parallel work.

## Parallel changes and reconciliation

Audit PR 65 remains open. PRs 87 and 88 carry independent repairs. Issue 76 is an independent site-suite change. Reconcile the current checkpoint when combining these source branches.

## Privacy and redaction

This handoff retains public repository links and synthetic fixture facts.

## Handoff update protocol

After focused verification, refresh this checkpoint against the actual target and retain the remaining acceptance limits.

## Compaction and supersession

Keep twelve sections and the contract size budgets. Git, issue 75, and tracker 66 retain history.
