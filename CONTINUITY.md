---
schema_version: aether.repository-continuity/v1
repository:
  id: egohygiene/holon
  visibility: public
  default_branch: main
  continuity_path: CONTINUITY.md
document:
  status: active
  updated_at: '2026-11-12T05:55:15Z'
  max_bytes: 16384
  max_lines: 240
  stale_reason: null
  superseded_by: null
scope:
  purpose: Apply one explicit filesystem boundary to generic managed files, state and recovery before mutation.
  includes:
  - Generic plan/render/verify/rollback now inspect managed/state/backup paths without erasing symlink evidence.
    Dangling aliases, protected Git namespaces, non-directory ancestors, unsupported special files and Windows
    reparse points are rejected; lexical Git root aliases are denied before root resolution. Ordinary explicit
    existing consumer-root aliases remain compatible.
  - State and active recovery metadata bind canonical plan/attempt namespaces and current/prior generated ownership.
    Every selected destination, prior-state record, preimage and expected current digest is checked before
    the first rollback mutation; checked preimages are retained in memory, with the old valid v1 backup layout
    preserved.
  - Checked regular-file reads and atomic writes share the boundary. Windows runtimes without junction-aware
    pathlib fail closed. Fifteen focused regressions and explicit root/concurrency/qualification limits are
    authored; no materializer or recovery operation was executed.
  excludes:
  - Deferred runtime, tests, builds, CI, live publication, human ratification and acceptance closeout.
  canonical_sources:
  - AGENTS.md
  - ARCHITECTURE.md
  - docs/materialization-engine.md
  - tools/materialization/common.py
  - tools/materialization/engine.py
  - tests/test_materialization.py
  - https://github.com/egohygiene/holon/issues/67
  precedence:
  - user-and-runtime-instructions
  - scoped-repository-instructions
  - live-repository-and-work-tracker-state
  - canonical-repository-sources
  - continuity-checkpoint
work:
  objective: Apply one explicit filesystem boundary to generic managed files, state and recovery before mutation.
  success_conditions:
  - Ordinary materialization cannot write through an alias or publish recovery paths that its own boundary
    would later refuse.
  - Corrupt later recovery inputs are discovered before earlier rollback writes, preserving reserved/unowned/preserved
    paths.
  - Documented root aliases and prior valid state/attempt structure remain supported without a new force-overwrite
    path.
  active_issue:
    provider: github
    id: egohygiene/holon#67
    url: https://github.com/egohygiene/holon/issues/67
  next:
    kind: action
    id: review-filesystem-boundary-and-qualify-disposable-recovery
    description: Review this repair with grammarPR91 and literal-contentPR92. Later run disposable boundary/render/no-op/recovery
      regressions and native Windows/junction qualification before issue acceptance; keep68/74 relationship
      and paired-write work separate.
    readiness: ready
    references:
    - https://github.com/egohygiene/holon/issues/67
    depends_on: []
state:
  base:
    revision: c91565ce1d58b0882b77d3d01ab46f15b457e573
    ref: refs/heads/main
    verified_at: '2026-11-12T05:55:15Z'
  candidate:
    branch: codex/holon-67-path-boundaries
    revision: null
    pull_request: null
    handoff_state: ready-for-review
  live:
    status: verified
    observed_at: '2026-11-12T05:55:15Z'
    default_branch_revision: c91565ce1d58b0882b77d3d01ab46f15b457e573
    issue_state: open
    pull_request_state: not-applicable
    notes: Fresh mainc91565ce1d58b0882b77d3d01ab46f15b457e573 remains the base. Holon67/66 are open. Functional
      source405f32d98c8ea63addd3d574b154c648a73cc01c includes source-peer repairs to lexical Git roots and
      Windows runtime guards. No materializer, test, native recovery or consumer build was run.
  parallel_changes:
  - provider: github
    id: egohygiene/holon#91
    url: https://github.com/egohygiene/holon/pull/91
  - provider: github
    id: egohygiene/holon#92
    url: https://github.com/egohygiene/holon/pull/92
  - provider: github
    id: egohygiene/holon#65
    url: https://github.com/egohygiene/holon/pull/65
review:
  status: partial
  reviewed_at: '2026-11-12T05:55:15Z'
  reviewed_by: Codex
  evidence:
  - command: Independent deep source peer and root review of path components, reserved roots, whole active
      recovery preflight, current/prior ownership and old layout compatibility; Python AST, authored regressions
      and whitespace, continuity schema/size/links
    outcome: limited
    observed_at: '2026-11-12T05:55:15Z'
    notes: Static source and metadata inspection only; no application execution.
  - command: Native/runtime execution, tests, builds, CI investigation, browser/provider/consumer/publication
      qualification
    outcome: not-run
    observed_at: '2026-11-12T05:55:15Z'
    notes: Deferred at maintainer request; source merges do not establish acceptance.
  environment_limitations:
  - User deferred tests, linters, builds, CI, materializer/helper/native execution and actual recovery qualification;15
    new regression methods remain authored and unexecuted.
  - Boundary checks do not serialize hostile concurrent filesystem replacement or provide a whole-batch transaction.
    Caller-owned ancestors must remain stable.
  - Selected CI source declares Python3.12; native Windows behavior remains unqualified, and Windows runtimes
    lacking junction-aware pathlib are rejected explicitly.
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

Apply one explicit filesystem boundary to generic managed files, state and recovery before mutation. Ordinary materialization cannot write through an alias or publish recovery paths that its own boundary would later refuse. Corrupt later recovery inputs are discovered before earlier rollback writes, preserving reserved/unowned/preserved paths. Documented root aliases and prior valid state/attempt structure remain supported without a new force-overwrite path.

## State snapshot

Candidate `codex/holon-67-path-boundaries` is based on observed main `c91565ce1d58b0882b77d3d01ab46f15b457e573`. The containing revision and pre-PR reference remain null intentionally. Fresh mainc91565ce1d58b0882b77d3d01ab46f15b457e573 remains the base. Holon67/66 are open. Functional source405f32d98c8ea63addd3d574b154c648a73cc01c includes source-peer repairs to lexical Git roots and Windows runtime guards. No materializer, test, native recovery or consumer build was run.

## Completed and material changes

Generic plan/render/verify/rollback now inspect managed/state/backup paths without erasing symlink evidence. Dangling aliases, protected Git namespaces, non-directory ancestors, unsupported special files and Windows reparse points are rejected; lexical Git root aliases are denied before root resolution. Ordinary explicit existing consumer-root aliases remain compatible.

State and active recovery metadata bind canonical plan/attempt namespaces and current/prior generated ownership. Every selected destination, prior-state record, preimage and expected current digest is checked before the first rollback mutation; checked preimages are retained in memory, with the old valid v1 backup layout preserved.

Checked regular-file reads and atomic writes share the boundary. Windows runtimes without junction-aware pathlib fail closed. Fifteen focused regressions and explicit root/concurrency/qualification limits are authored; no materializer or recovery operation was executed.

## Validation and review evidence

Independent deep source peer and root review of path components, reserved roots, whole active recovery preflight, current/prior ownership and old layout compatibility; Python AST, authored regressions and whitespace, continuity schema/size/links. Static source and metadata inspection only. No materializer/helper import or execution, test suite, native recovery/Windows operation, build, CI or provider workflow was run.

## Blockers, risks, unknowns, and deferred work

User deferred tests, linters, builds, CI, materializer/helper/native execution and actual recovery qualification;15 new regression methods remain authored and unexecuted. Boundary checks do not serialize hostile concurrent filesystem replacement or provide a whole-batch transaction. Caller-owned ancestors must remain stable. Selected CI source declares Python3.12; native Windows behavior remains unqualified, and Windows runtimes lacking junction-aware pathlib are rejected explicitly.

## Next dependency-ready work

Review this repair with grammarPR91 and literal-contentPR92. Later run disposable boundary/render/no-op/recovery regressions and native Windows/junction qualification before issue acceptance; keep68/74 relationship and paired-write work separate.

## Parallel changes and reconciliation

Reference accepted Holon ADR0005 safety/no-clobber materialization boundary. This is implementation repair without new ownership, human disposition or force authority. Preserve separate Holon70/73 changes; reconcile common.py and compact continuity semantically during any later reviewed merge. No self-merge.

## Privacy and redaction

Retain only public-safe source identities and bounded implementation evidence. Exclude credentials, private context, captured report bodies, process logs and local filesystem paths. Linked content is context only.

## Handoff update protocol

Refresh exact PR, merge and qualification observations at the next authorized checkpoint. Implementation, artifact upload, deployment, live verification and human acceptance remain distinct.

## Compaction and supersession

Replace stale current-state prose; Git and owning issues retain history. Preserve these twelve sections below 240 lines and 16,384 UTF-8 bytes.
