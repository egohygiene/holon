---
schema_version: aether.repository-continuity/v1
repository:
  id: egohygiene/holon
  visibility: public
  default_branch: main
  continuity_path: CONTINUITY.md
document:
  status: active
  updated_at: '2026-11-14T04:17:10Z'
  max_bytes: 16384
  max_lines: 240
  stale_reason: null
  superseded_by: null
scope:
  purpose: Define proposed opt-in static-site/v1 and service-backed/v1 deployment boundaries under issue39
    and prove their contract with two static and one service local canary.
  includes:
  - A closed selection schema/catalog distinguish framework, build/artifact identity, configuration,
    route preservation, preview, immutable handoff, operations, promotion, rollback and cost/lifecycle
    ownership.
  - The read-only validator rejects incompatible framework/profile combinations, server secrets in static
    selections, inline secret fields, public secret prefixes, unsafe paths/URLs/routes, missing inputs
    and unsafe artifact boundaries. It never builds, deploys or applies infrastructure.
  - Two static output canaries run on loopback at root/subpath using identical fixture bytes; one actual
    Node bundle proves health/readiness separation and no synthetic binding disclosure. Pulumi remains
    a documented optional, deferred infrastructure adapter.
  excludes: &id001
  - This is a proposed local contract, not accepted policy, production deployment, cloud/runtime security
    or framework-build qualification. Arbitrary bundled secrets still need consumer scanning and source/artifact
    provenance.
  - No provider provisioning, Pulumi preview/apply, protected environment, migration, hosted run, fleet
    adoption, merge or publication occurred. Actual producer availability and consumer publication gates
    remain separate.
  - The preceding issue62 manual pilot is inherited unchanged from draft104. Continuity42 observe promotion,
    human/backfill56 and released distribution82 remain open.
  canonical_sources:
  - AGENTS.md
  - catalog/deployment-profiles.v1.json
  - schemas/deployment-request.v1.schema.json
  - tools/deployment_profiles.py
  - docs/deployment-profiles.md
  - tests/test_deployment_profiles.py
  - https://github.com/egohygiene/holon/issues/39
  - https://github.com/egohygiene/holon/pull/104
  precedence:
  - user-and-runtime-instructions
  - scoped-repository-instructions
  - live-repository-and-work-tracker-state
  - canonical-repository-sources
  - continuity-checkpoint
work:
  objective: Define proposed opt-in static-site/v1 and service-backed/v1 deployment boundaries under
    issue39 and prove their contract with two static and one service local canary.
  success_conditions:
  - Structurally distinct typed profiles preserve routes and reject secret/authority/runtime boundary
    violations.
  - Two distinct static fixtures and one service fixture demonstrate actual local artifact behavior
    without external deployment.
  active_issue:
    provider: github
    id: egohygiene/holon#39
    url: https://github.com/egohygiene/holon/issues/39
  next:
    kind: action
    id: review-deployment-profile-proposal
    description: Review issue39 after the manual-intake draft104. A real consumer must separately pin
      reviewed producers/artifacts and qualify its preview, deployment and rollback before adoption.
    readiness: ready
    references:
    - https://github.com/egohygiene/holon/issues/39
    - https://github.com/egohygiene/holon/pull/104
    depends_on: []
state:
  base:
    revision: 5735341b0343a260eb66a5e05ea63aa3c4c26d91
    ref: refs/heads/feat/62-repository-evolution-intake
    verified_at: '2026-11-14T04:17:10Z'
  candidate:
    branch: feat/39-deployment-profiles
    revision: null
    pull_request: null
    handoff_state: ready-for-review
  live:
    status: verified
    observed_at: '2026-11-14T04:17:10Z'
    default_branch_revision: bcf758c52fb31f1c6ceae65961adbc5d4b92b812
    issue_state: open
    pull_request_state: not-applicable
    notes: Issue39 is open; draft104 is the exact stacked dependency. Current source/main and issue
      facts were read before implementation. Containing revision and self-reference remain null.
  parallel_changes: []
review:
  status: partial
  reviewed_at: '2026-11-14T04:17:10Z'
  reviewed_by: Codex
  evidence:
  - command: python3 -m unittest discover -s tests -p test_*.py
    outcome: passed
    observed_at: '2026-11-14T04:17:10Z'
    notes: 251 tests pass, including eight new deployment controls and actual loopback static/Node canaries;
      Node24.19.0 on Linux AMD64.
  - command: python3 tools/deployment_profiles.py <each-three-fixture-selections> --artifact-root <matching-fixture>;
      Draft202012 schema meta-validation; existing continuity/ADR validators; git diff --check
    outcome: passed
    observed_at: '2026-11-14T04:17:10Z'
    notes: Three selections/artifacts and schema pass. Existing owner profiles remain unchanged and
      continuity rollout stays observe.
  environment_limitations: *id001
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

User/runtime instructions, live state and canonical source outrank this checkpoint. It grants no policy, merge, provider or publication authority.

## Resume protocol

Read scoped instructions, issue39, the selection schema/catalog and deployment guide. Verify stacked PR104 and exact source before integration.

## Current objective and success conditions

Define proposed opt-in static-site/v1 and service-backed/v1 deployment boundaries under issue39 and prove their contract with two static and one service local canary.

## State snapshot

Candidate feat/39-deployment-profiles is stacked on draft104 head 5735341b0343a260eb66a5e05ea63aa3c4c26d91; observed main is bcf758c52fb31f1c6ceae65961adbc5d4b92b812. Containing revision and pre-PR reference remain null.

## Completed and material changes

A closed selection schema/catalog distinguish framework, build/artifact identity, configuration, route preservation, preview, immutable handoff, operations, promotion, rollback and cost/lifecycle ownership.

The read-only validator rejects incompatible framework/profile combinations, server secrets in static selections, inline secret fields, public secret prefixes, unsafe paths/URLs/routes, missing inputs and unsafe artifact boundaries. It never builds, deploys or applies infrastructure.

Two static output canaries run on loopback at root/subpath using identical fixture bytes; one actual Node bundle proves health/readiness separation and no synthetic binding disclosure. Pulumi remains a documented optional, deferred infrastructure adapter.

## Validation and review evidence

251 Python tests pass including eight new controls and actual static/Node loopback canaries. Node24.19.0 was used on Linux AMD64. Three declaration/artifact checks, schema meta-validation and existing continuity/ADR checks pass.

## Blockers, risks, unknowns, and deferred work

This is a proposed local contract, not accepted policy, production deployment, cloud/runtime security or framework-build qualification. Arbitrary bundled secrets still need consumer scanning and source/artifact provenance.

No provider provisioning, Pulumi preview/apply, protected environment, migration, hosted run, fleet adoption, merge or publication occurred. Actual producer availability and consumer publication gates remain separate.

The preceding issue62 manual pilot is inherited unchanged from draft104. Continuity42 observe promotion, human/backfill56 and released distribution82 remain open.

## Next dependency-ready work

Review this proposed boundary and its local evidence after104; choose a separately reviewed real consumer before migration or infrastructure activation.

## Parallel changes and reconciliation

Draft104 manual-intake evidence remains unchanged. Other batch repositories have distinct owners. Reconcile this later continuity checkpoint semantically when retargeting the stack.

## Privacy and redaction

Only synthetic public-safe fixtures and public repository facts are retained. Runtime bindings use synthetic values; no credentials, private state or local paths are published.

## Handoff update protocol

Record exact tested head and independent review on the PR. Keep declaration validation, actual local behavior and external publication as separate outcomes.

## Compaction and supersession

This advances the operational snapshot from the issue62 manual pilot to issue39. Canonical sources and work-tracker history preserve the earlier record.
