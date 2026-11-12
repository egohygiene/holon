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
  purpose: Reserve the generated documentation and legal hub slugs.
  includes: &id001
  - The reference validator, JSON Schema, and generated consumer all reject the index page slug.
  - Invalid inputs leave prior generated source and configuration bytes intact.
  - Valid pages preserve hub introductions and ordered navigation.
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
  - tools/site_suite_blueprint.py
  - schemas/site-suite-content.v1.schema.json
  - blueprints/zensical/files/site_docs.py
  - tests/test_site_suite_blueprint.py
  - docs/site-suite-blueprint.md
  - https://github.com/egohygiene/holon/issues/76
work:
  objective: Reserve the generated documentation and legal hub slugs.
  success_conditions: *id001
  active_issue:
    provider: github
    id: egohygiene/holon#76
    url: https://github.com/egohygiene/holon/issues/76
  next:
    kind: action
    id: review-audit-repair
    description: Review this focused draft and reconcile its handoff against the actual target before
      combining it with parallel work.
    readiness: ready
    references:
    - https://github.com/egohygiene/holon/issues/76
    - https://github.com/egohygiene/holon/issues/66
    depends_on: []
state:
  base:
    revision: 934e559400336cbf1acac325c89754056e27e3f2
    ref: refs/heads/main
    verified_at: '2026-11-12T00:32:56Z'
  candidate:
    branch: codex/76-reserve-site-hub-slugs
    revision: null
    pull_request: null
    handoff_state: ready-for-review
  live:
    status: verified
    observed_at: '2026-11-12T00:32:56Z'
    default_branch_revision: 934e559400336cbf1acac325c89754056e27e3f2
    issue_state: open
    pull_request_state: not-applicable
    notes: GitHub reported issue 76 open and the source repairs in PRs 84–86 merged before this candidate
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
  - command: python3 tools/site_suite_blueprint.py
    outcome: passed
    observed_at: '2026-11-12T00:32:56Z'
    notes: Both variants and the updated rendered inventories validated on Python 3.12.14.
  - command: python3 -m unittest discover --start-directory tests --pattern "test_site_suite_blueprint.py"
      --verbose
    outcome: passed
    observed_at: '2026-11-12T00:32:56Z'
    notes: Six targeted tests include actual generated validate/build rejection and prior source-byte
      preservation.
  - command: Draft202012Validator checks for both fixture content objects and invalid slug controls
    outcome: passed
    observed_at: '2026-11-12T00:32:56Z'
    notes: Both schemas accept authored fixture routes and reject reserved, overlong, and multiline slugs.
  - command: python3 tools/check_site_suite_fixtures.py
    outcome: not-run
    observed_at: '2026-11-12T00:32:56Z'
    notes: Full dependency-backed site-suite qualification is deferred.
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
    notes: Native Zensical build and preview, full repository suites, and hosted CI remain deferred.
  environment_limitations:
  - Native Zensical build and preview, full repository suites, and hosted CI remain deferred.
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

Record the scoped source repair under the repository instructions and verified work tracker. ADR-0009 owns the independent source surfaces and composition boundary.

## Resume protocol

Read AGENTS, issue 76, the source guide, and tracker 66. Verify current main and draft state before resuming.

## Current objective and success conditions

Reserve the generated documentation and legal hub slugs. The reference validator, JSON Schema, and generated consumer all reject the index page slug. Invalid inputs leave prior generated source and configuration bytes intact. Valid pages preserve hub introductions and ordered navigation.

## State snapshot

Main at `934e559400336cbf1acac325c89754056e27e3f2` contains the three merged Repository Intelligence source repairs. This candidate branches from that revision for issue 76.

## Completed and material changes

The schema, reference validator, and generated Zensical adapter reserve the index slug. The adapter validates before deleting or generating files. The updated inventories record the template changes, and the regression exercises actual materialized consumer commands.

## Validation and review evidence

Both variants and the updated rendered inventories validated on Python 3.12.14. Six targeted tests include actual generated validate/build rejection and prior source-byte preservation. Both schemas accept authored fixture routes and reject reserved, overlong, and multiline slugs. Local continuity verification and pinned schema and structure checks passed.

## Blockers, risks, unknowns, and deferred work

Native Zensical build and preview, full repository suites, and hosted CI remain deferred. Issues 77 through 79 retain remaining qualification for previously merged source.

## Next dependency-ready work

Review the issue 76 draft and reconcile its handoff against the target before combining it with parallel work.

## Parallel changes and reconciliation

Audit PR 65 remains open. PRs 87 and 88 carry independent repairs. Issue 75 is an independent presentation input repair. Reconcile the current checkpoint when combining these source branches.

## Privacy and redaction

This handoff retains public repository links and synthetic fixture facts.

## Handoff update protocol

After focused verification, refresh this checkpoint against the actual target and retain the remaining acceptance limits.

## Compaction and supersession

Keep twelve sections and the contract size budgets. Git, issue 76, and tracker 66 retain history.
