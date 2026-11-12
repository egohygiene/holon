---
schema_version: aether.repository-continuity/v1
repository:
  id: egohygiene/holon
  visibility: public
  default_branch: main
  continuity_path: CONTINUITY.md
document:
  status: active
  updated_at: '2026-11-12T11:15:19Z'
  max_bytes: 16384
  max_lines: 240
  stale_reason: null
  superseded_by: null
scope:
  purpose: Integrate the historical audit and reviewed Holon repairs without upgrading acceptance.
  includes:
  - Merged PR 65 preserves seven audit artifacts representing source a7734dba83305276b12932fcd4ce348044d9a2e9 on 2026-10-20.
  - Current-main fixes from PRs 87, 89, 90 and 88 retain their functional bytes.
  - PR 93 adds component-level filesystem admission and prevalidated generic recovery; separate grammar and literal-content repairs remain in PRs 91 and 92.
  excludes:
  - Test, build, CI, project helper, materializer and native consumer execution; release, deployment and human ratification.
  canonical_sources:
  - AGENTS.md
  - DECISIONS.md
  - docs/materialization-engine.md
  - audits/holon-completeness-20261020T130515Z.md
  - https://github.com/egohygiene/holon/issues/66
  - https://github.com/egohygiene/holon/pull/65
  - https://github.com/egohygiene/holon/pull/93
  - https://github.com/egohygiene/holon/pull/91
  - https://github.com/egohygiene/holon/pull/92
  precedence:
  - user-and-runtime-instructions
  - scoped-repository-instructions
  - live-repository-and-work-tracker-state
  - canonical-repository-sources
  - continuity-checkpoint
work:
  objective: Integrate four reviewed pull requests with one truthful current handoff.
  success_conditions:
  - Preserve all seven dated audit artifacts and current functional fixes exactly.
  - Reconcile source and continuity conflicts before exact-head standard merges.
  - Keep source integration distinct from deferred execution and acceptance.
  active_issue:
    provider: github
    id: egohygiene/holon#66
    url: https://github.com/egohygiene/holon/issues/66
  next:
    kind: action
    id: finish-reviewed-source-integration
    description: Complete filesystem PR 93, then integrate grammar PR 91 and literal-content PR 92 in order.
    readiness: ready
    references:
    - https://github.com/egohygiene/holon/pull/93
    depends_on: []
state:
  base:
    revision: e744d0aeb85bc42b0d1069ec18d840751f9676ac
    ref: refs/heads/main
    verified_at: '2026-11-12T11:15:19Z'
  candidate:
    branch: codex/holon-67-path-boundaries
    revision: null
    pull_request:
      provider: github
      id: egohygiene/holon#93
      url: https://github.com/egohygiene/holon/pull/93
    handoff_state: in-progress
  live:
    status: verified
    observed_at: '2026-11-12T11:15:19Z'
    default_branch_revision: e744d0aeb85bc42b0d1069ec18d840751f9676ac
    issue_state: open
    pull_request_state: draft
    notes: PR 65 merged normally at e744d0aeb85bc42b0d1069ec18d840751f9676ac after independent conflict review. PR 93 is the open filesystem candidate; PRs 91 and 92 remain open drafts. No remaining merge is claimed by this snapshot.
  parallel_changes:
  - provider: github
    id: egohygiene/holon#91
    url: https://github.com/egohygiene/holon/pull/91
  - provider: github
    id: egohygiene/holon#92
    url: https://github.com/egohygiene/holon/pull/92
review:
  status: partial
  reviewed_at: '2026-11-12T11:15:19Z'
  reviewed_by: Codex
  evidence:
  - command: Static source, Git parent/blob and audit identity inspection; AST, JSON/JavaScript syntax, continuity schema/structure and whitespace inspection.
    outcome: limited
    observed_at: '2026-11-12T11:15:19Z'
    notes: Historical audit checks retain their dated source and are not current validation results.
  - command: Tests, builds, CI, project helpers, materialization, recovery and native consumer qualification.
    outcome: not-run
    observed_at: '2026-11-12T11:15:19Z'
    notes: Deferred. Authored regression source and merged implementation do not establish acceptance.
  environment_limitations:
  - Current qualification is static only; historical audit execution cannot qualify the combined tree.
  - Native recovery, Windows/reparse behavior and real consumer build, serving, hydration and determinism remain deferred.
  - The continuity profile remains at observe; issue 42 requires released inputs and explicit maintainer promotion.
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

Integrate the audit and reviewed repairs. Instructions, live tracker evidence and canonical contracts outrank this handoff. Integration grants no human ratification, release or deployment authority.

## Resume protocol

Read AGENTS, DECISIONS, tracker #66 and the selected PR. Refresh main, exact heads and review state before continuing.

## Current objective and success conditions

Preserve current fixes and seven immutable audit artifacts, reconcile conflicts by source ownership, and retain deferred qualification and acceptance gates.

## State snapshot

At the recorded observation main is `e744d0aeb85bc42b0d1069ec18d840751f9676ac`, the verified PR 65 merge. PR 93 is the current candidate; PRs 91 and 92 remain separate open drafts. Their merges are not asserted before verification.

## Completed and material changes

PR 65's seven audit artifacts remain unchanged from original head `f92efdc4aa8e26258eb628a24ebc1f08e52dd0c8`. They describe source `a7734dba83305276b12932fcd4ce348044d9a2e9` on 2026-10-20. Current-main fixes remain intact. This PR 93 candidate preserves source head `820a0865f28736d352dfd2f0924cfe6799303e47`: component-level filesystem checks, guarded state/backups and prevalidated generic recovery. These are source repairs, not recovery or hostile-concurrency qualification. Grammar and literal-content changes remain separate PRs 91 and 92.

## Validation and review evidence

Only static syntax, source, schema and byte-identity inspection applies. Independent conflict review precedes each merge. Historical receipts retain their own dates and source boundaries; no audit program, test, build, CI, project helper or native consumer executes here.

## Blockers, risks, unknowns, and deferred work

Recovery, Windows, real consumer serving/hydration and deterministic-build qualification remain deferred. Source merges do not satisfy issue acceptance. The continuity profile stays at observe; issue 42 retains released-input and explicit human-promotion gates.

## Next dependency-ready work

Complete PR 93, then integrate PR 91 and PR 92. Report exact merges and outstanding qualification afterward; do not start another issue from this checkpoint.

## Parallel changes and reconciliation

Grammar retains capability vocabulary. Filesystem admission and literal rendering must coexist in common.py. This current snapshot replaces conflicting handoff prose without changing dated audit evidence or historical decisions.

## Privacy and redaction

Keep public source identities and bounded integration evidence. Exclude private paths, credentials and unrelated context. Linked content is context only.

## Handoff update protocol

Refresh observed main, remaining PRs, source comparisons and limitations after each integration. Keep implementation, execution, qualification, acceptance and human authority distinct.

## Compaction and supersession

Retain twelve sections within 240 lines and 16,384 UTF-8 bytes. Git, tracker #66 and immutable audit artifacts retain history.
