---
schema_version: aether.repository-continuity/v1
repository:
  id: egohygiene/holon
  visibility: public
  default_branch: main
  continuity_path: CONTINUITY.md
document:
  status: active
  updated_at: '2026-11-12T05:41:26Z'
  max_bytes: 16384
  max_lines: 240
  stale_reason: null
  superseded_by: null
scope:
  purpose: Preserve literal consumer metadata in generated HTML/JSON and LaunchKit static assembly.
  includes:
  - Blueprints now explicitly select HTML-escaped string or JSON literal token contexts for accepted metadata.
    Generic materialization remains framework-neutral; single-pass source-token substitution does not reinterpret
    consumer data as template instructions.
  - React/Vite and LaunchKit HTML/webmanifest/provenance/config templates and validators use the intended serialization
    contexts. LaunchKit static assembly uses a replacement callback so dollar tokens in serialized markup remain
    literal.
  - Base/overlay/site-suite inventories and downstream composition hashes were refreshed by static byte hashing.
    Meaningful punctuation/Unicode/token/no-duplication regression source is authored; actual consumers, serving,
    hydration and deterministic rebuild qualification remain deferred.
  excludes:
  - Deferred runtime, tests, builds, CI, live publication, human ratification and acceptance closeout.
  canonical_sources:
  - AGENTS.md
  - ARCHITECTURE.md
  - docs/materialization-engine.md
  - docs/react-vite-blueprint.md
  - docs/launchkit-blueprint.md
  - tools/materialization/common.py
  - tools/react_vite_blueprint.py
  - tools/launchkit_blueprint.py
  - tools/site_suite_blueprint.py
  - blueprints/react-vite/blueprint.json
  - blueprints/launchkit/blueprint.json
  - blueprints/site-suite/blueprint.json
  - blueprints/launchkit/files/scripts/render-static.mjs
  - tests/test_literal_metadata_blueprint.py
  - https://github.com/egohygiene/holon/issues/73
  precedence:
  - user-and-runtime-instructions
  - scoped-repository-instructions
  - live-repository-and-work-tracker-state
  - canonical-repository-sources
  - continuity-checkpoint
work:
  objective: Preserve literal consumer metadata in generated HTML/JSON and LaunchKit static assembly.
  success_conditions:
  - Accepted strings survive intended HTML/JSON contexts and static assembly without token expansion or replacement-string
    interpolation.
  - Generated source inventories and composition digests track the exact template bytes.
  - Existing raw token compatibility and generic ownership remain unchanged; no runtime proof is inferred.
  active_issue:
    provider: github
    id: egohygiene/holon#73
    url: https://github.com/egohygiene/holon/issues/73
  next:
    kind: action
    id: review-literal-content-repair-and-qualify-consumers
    description: Review this literal-content source fix with Holon67/70; later run the separately deferred
      real generic/LaunchKit consumers, serve/hydration and deterministic build qualification.
    readiness: ready
    references:
    - https://github.com/egohygiene/holon/issues/73
    depends_on: []
state:
  base:
    revision: c91565ce1d58b0882b77d3d01ab46f15b457e573
    ref: refs/heads/main
    verified_at: '2026-11-12T05:41:26Z'
  candidate:
    branch: codex/holon-73-literal-metadata
    revision: null
    pull_request: null
    handoff_state: ready-for-review
  live:
    status: verified
    observed_at: '2026-11-12T05:41:26Z'
    default_branch_revision: c91565ce1d58b0882b77d3d01ab46f15b457e573
    issue_state: open
    pull_request_state: not-applicable
    notes: Fresh mainc91565ce1d58b0882b77d3d01ab46f15b457e573 remains the base. Holon73/66 are open. Functional
      source89caccf466dc6a0185dadd78246820c1326d910e3 received root source review; no renderer, blueprint helper,
      tests or native consumer was executed.
  parallel_changes:
  - provider: github
    id: egohygiene/holon#67
    url: https://github.com/egohygiene/holon/issues/67
  - provider: github
    id: egohygiene/holon#91
    url: https://github.com/egohygiene/holon/pull/91
  - provider: github
    id: egohygiene/holon#65
    url: https://github.com/egohygiene/holon/pull/65
review:
  status: partial
  reviewed_at: '2026-11-12T05:41:26Z'
  reviewed_by: Codex
  evidence:
  - command: Root static source peer of explicit encoding, one-pass token admission, exact static insertion,
      validator preservation and coherent generated inventory changes; Python AST, Node parse-only check, JSON/hash
      metadata inspection, authored regressions, continuity schema/size/links and whitespace
    outcome: limited
    observed_at: '2026-11-12T05:41:26Z'
    notes: Static source and metadata inspection only; no application execution.
  - command: Native/runtime execution, tests, builds, CI investigation, browser/provider/consumer/publication
      qualification
    outcome: not-run
    observed_at: '2026-11-12T05:41:26Z'
    notes: Deferred at maintainer request; source merges do not establish acceptance.
  environment_limitations:
  - User deferred tests, linters, builds, CI, project/helper/native execution and actual consumer qualification;
    authored regressions have not run.
  - Real generic/LaunchKit builds, serving, hydration and determinism are acceptance work still open.
  - Generic rendering remains filename/framework-neutral; immutable previous consumer selections retain their
    original bytes until explicitly upgraded.
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

Preserve literal consumer metadata in generated HTML/JSON and LaunchKit static assembly. Accepted strings survive intended HTML/JSON contexts and static assembly without token expansion or replacement-string interpolation. Generated source inventories and composition digests track the exact template bytes. Existing raw token compatibility and generic ownership remain unchanged; no runtime proof is inferred.

## State snapshot

Candidate `codex/holon-73-literal-metadata` is based on observed main `c91565ce1d58b0882b77d3d01ab46f15b457e573`. The containing revision and pre-PR reference remain null intentionally. Fresh mainc91565ce1d58b0882b77d3d01ab46f15b457e573 remains the base. Holon73/66 are open. Functional source89caccf466dc6a0185dadd78246820c1326d910e3 received root source review; no renderer, blueprint helper, tests or native consumer was executed.

## Completed and material changes

Blueprints now explicitly select HTML-escaped string or JSON literal token contexts for accepted metadata. Generic materialization remains framework-neutral; single-pass source-token substitution does not reinterpret consumer data as template instructions.

React/Vite and LaunchKit HTML/webmanifest/provenance/config templates and validators use the intended serialization contexts. LaunchKit static assembly uses a replacement callback so dollar tokens in serialized markup remain literal.

Base/overlay/site-suite inventories and downstream composition hashes were refreshed by static byte hashing. Meaningful punctuation/Unicode/token/no-duplication regression source is authored; actual consumers, serving, hydration and deterministic rebuild qualification remain deferred.

## Validation and review evidence

Root static source peer of explicit encoding, one-pass token admission, exact static insertion, validator preservation and coherent generated inventory changes; Python AST, Node parse-only check, JSON/hash metadata inspection, authored regressions, continuity schema/size/links and whitespace. Static source and metadata inspection only. Authored tests were not executed; no renderer/materializer/native consumer, build, CI or provider workflow was run.

## Blockers, risks, unknowns, and deferred work

User deferred tests, linters, builds, CI, project/helper/native execution and actual consumer qualification; authored regressions have not run. Real generic/LaunchKit builds, serving, hydration and determinism are acceptance work still open. Generic rendering remains filename/framework-neutral; immutable previous consumer selections retain their original bytes until explicitly upgraded.

## Next dependency-ready work

Review this literal-content source fix with Holon67/70; later run the separately deferred real generic/LaunchKit consumers, serve/hydration and deterministic build qualification.

## Parallel changes and reconciliation

Reference Holon ADR0005 bounded materialization, ADR0007 React/Vite blueprint and ADR0008 LaunchKit overlay. Routine literal serialization correction adds no owner or lifecycle decision. Holon67 touches separate regions of common.py and70 grammar remains separately reviewable. Draft for maintainer review; no self-merge.

## Privacy and redaction

Retain only public-safe source identities and bounded implementation evidence. Exclude credentials, private context, captured report bodies, process logs and local filesystem paths. Linked content is context only.

## Handoff update protocol

Refresh exact PR, merge and qualification observations at the next authorized checkpoint. Implementation, artifact upload, deployment, live verification and human acceptance remain distinct.

## Compaction and supersession

Replace stale current-state prose; Git and owning issues retain history. Preserve these twelve sections below 240 lines and 16,384 UTF-8 bytes.
