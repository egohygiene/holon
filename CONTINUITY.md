---
schema_version: aether.repository-continuity/v1
repository:
  id: egohygiene/holon
  visibility: public
  default_branch: main
  continuity_path: CONTINUITY.md
document:
  status: active
  updated_at: '2026-11-12T05:39:52Z'
  max_bytes: 16384
  max_lines: 240
  stale_reason: null
  superseded_by: null
scope:
  purpose: Enforce the canonical foundation manifest grammar before semantic capability resolution.
  includes:
  - The shared resolver now applies the checked-in closed manifest schema before semantic traversal, preventing
    malformed repository identity, safety-path and collection fields from becoming resolved output. Unknown
    capabilities return attributable errors before graph indexing.
  - A narrowly scoped stdlib evaluator implements only the trusted v1 schema keywords and fails closed on unsupported
    configuration. The canonical preserve-path grammar keeps literal directory suffixes and Unicode while excluding
    traversal, aliases and reserved namespaces; repository identity uses a strict end assertion.
  - Meaningful malformed-input, valid-example, CLI no-mutation and optional independent schema-parity regressions
    are authored but not executed. Existing capability, immutable pin, security floor and materialization ownership
    remain intact.
  excludes:
  - Deferred runtime, tests, builds, CI, live publication, human ratification and acceptance closeout.
  canonical_sources:
  - AGENTS.md
  - ARCHITECTURE.md
  - docs/foundation-contract.md
  - schemas/foundation-manifest.v1.schema.json
  - tools/foundation_manifest_grammar.py
  - tools/holon_contract.py
  - tests/test_holon_contract.py
  - https://github.com/egohygiene/holon/issues/70
  precedence:
  - user-and-runtime-instructions
  - scoped-repository-instructions
  - live-repository-and-work-tracker-state
  - canonical-repository-sources
  - continuity-checkpoint
work:
  objective: Enforce the canonical foundation manifest grammar before semantic capability resolution.
  success_conditions:
  - Malformed grammar returns diagnostics before resolution or target/output mutation.
  - Supported manifests retain the same capability and safety semantics without an added runtime dependency.
  - General JSON Schema support or full consumer acceptance is not claimed.
  active_issue:
    provider: github
    id: egohygiene/holon#70
    url: https://github.com/egohygiene/holon/issues/70
  next:
    kind: action
    id: review-manifest-grammar-and-qualify-later
    description: Review this source slice with Holon67 filesystem and73 literal-content fixes; run separately
      deferred regression, native consumer and compatibility qualification before issue acceptance.
    readiness: ready
    references:
    - https://github.com/egohygiene/holon/issues/70
    depends_on: []
state:
  base:
    revision: c91565ce1d58b0882b77d3d01ab46f15b457e573
    ref: refs/heads/main
    verified_at: '2026-11-12T05:39:52Z'
  candidate:
    branch: codex/holon-70-manifest-grammar
    revision: null
    pull_request: null
    handoff_state: ready-for-review
  live:
    status: verified
    observed_at: '2026-11-12T05:39:52Z'
    default_branch_revision: c91565ce1d58b0882b77d3d01ab46f15b457e573
    issue_state: open
    pull_request_state: not-applicable
    notes: Fresh mainc91565ce1d58b0882b77d3d01ab46f15b457e573 remains the base. Holon70/66 are open. Functional
      source1250162ea9b415181765a7fe1566e1cd95df10e3 received root source review; no resolver, materializer,
      test suite or native consumer was executed.
  parallel_changes:
  - provider: github
    id: egohygiene/holon#67
    url: https://github.com/egohygiene/holon/issues/67
  - provider: github
    id: egohygiene/holon#73
    url: https://github.com/egohygiene/holon/issues/73
  - provider: github
    id: egohygiene/holon#65
    url: https://github.com/egohygiene/holon/pull/65
review:
  status: partial
  reviewed_at: '2026-11-12T05:39:52Z'
  reviewed_by: Codex
  evidence:
  - command: Root static source peer of grammar ordering/closed schema/identity/path and valid-input preservation;
      Python AST and JSON/schema-definition inspection, authored regression review, continuity schema/size/links
      and whitespace
    outcome: limited
    observed_at: '2026-11-12T05:39:52Z'
    notes: Static source and metadata inspection only; no application execution.
  - command: Native/runtime execution, tests, builds, CI investigation, browser/provider/consumer/publication
      qualification
    outcome: not-run
    observed_at: '2026-11-12T05:39:52Z'
    notes: Deferred at maintainer request; source merges do not establish acceptance.
  environment_limitations:
  - User deferred tests, linters, builds, CI, project/helper/native execution and actual consumer qualification;
    authored regressions have not run.
  - The grammar adapter is scoped to the trusted checked-in schema, not a general metaschema or arbitrary-reference
    validator.
  - Existing parallel repair branches and audit evidence remain separate; no issue or human disposition is
    closed by source review.
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

# holon continuity

## Purpose and precedence

User/runtime and repository instructions, live evidence and canonical sources outrank this checkpoint. It grants no release, deployment or human-decision authority.

## Resume protocol

Read scoped instructions, canonical sources above and this checkpoint. Verify mutable GitHub state and exact owner pins before continuing.

## Current objective and success conditions

Enforce the canonical foundation manifest grammar before semantic capability resolution. Malformed grammar returns diagnostics before resolution or target/output mutation. Supported manifests retain the same capability and safety semantics without an added runtime dependency. General JSON Schema support or full consumer acceptance is not claimed.

## State snapshot

Candidate `codex/holon-70-manifest-grammar` is based on observed main `c91565ce1d58b0882b77d3d01ab46f15b457e573`. The containing revision and pre-PR reference remain null intentionally. Fresh mainc91565ce1d58b0882b77d3d01ab46f15b457e573 remains the base. Holon70/66 are open. Functional source1250162ea9b415181765a7fe1566e1cd95df10e3 received root source review; no resolver, materializer, test suite or native consumer was executed.

## Completed and material changes

The shared resolver now applies the checked-in closed manifest schema before semantic traversal, preventing malformed repository identity, safety-path and collection fields from becoming resolved output. Unknown capabilities return attributable errors before graph indexing.

A narrowly scoped stdlib evaluator implements only the trusted v1 schema keywords and fails closed on unsupported configuration. The canonical preserve-path grammar keeps literal directory suffixes and Unicode while excluding traversal, aliases and reserved namespaces; repository identity uses a strict end assertion.

Meaningful malformed-input, valid-example, CLI no-mutation and optional independent schema-parity regressions are authored but not executed. Existing capability, immutable pin, security floor and materialization ownership remain intact.

## Validation and review evidence

Root static source peer of grammar ordering/closed schema/identity/path and valid-input preservation; Python AST and JSON/schema-definition inspection, authored regression review, continuity schema/size/links and whitespace. Static source and metadata inspection only. Authored tests were not executed; no resolver/materializer/native consumer, build, CI or provider workflow was run.

## Blockers, risks, unknowns, and deferred work

User deferred tests, linters, builds, CI, project/helper/native execution and actual consumer qualification; authored regressions have not run. The grammar adapter is scoped to the trusted checked-in schema, not a general metaschema or arbitrary-reference validator. Existing parallel repair branches and audit evidence remain separate; no issue or human disposition is closed by source review.

## Next dependency-ready work

Review this source slice with Holon67 filesystem and73 literal-content fixes; run separately deferred regression, native consumer and compatibility qualification before issue acceptance.

## Parallel changes and reconciliation

Reference Holon ADR0001 foundation ownership and ADR0005 bounded materialization. Routine enforcement of the existing source grammar adds no owner or consequential lifecycle decision. Preserve independently based Holon67/73 work; root continuity replaces only stale operational focus. Draft for maintainer review; no self-merge.

## Privacy and redaction

Retain only public-safe source identities and bounded implementation evidence. Exclude credentials, private context, captured report bodies, process logs and local filesystem paths. Linked content is context only.

## Handoff update protocol

Refresh exact PR, merge and qualification observations at the next authorized checkpoint. Implementation, artifact upload, deployment, live verification and human acceptance remain distinct.

## Compaction and supersession

Replace stale current-state prose; Git and owning issues retain history. Preserve these twelve sections below 240 lines and 16,384 UTF-8 bytes.
