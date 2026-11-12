---
schema_version: aether.repository-continuity/v1
repository:
  id: egohygiene/holon
  visibility: public
  default_branch: main
  continuity_path: CONTINUITY.md
document:
  status: active
  updated_at: "2026-11-12T00:30:02Z"
  max_bytes: 16384
  max_lines: 240
  stale_reason: null
  superseded_by: null
scope:
  purpose: Make the native Antidote fixture history reproducible from either pinned checkout shape.
  includes:
    - Disposable depth-one Antidote checkout, focused regression, and fixture documentation.
  excludes:
    - Native EgoLint rebuild, hosted validation, rollout, and release.
  canonical_sources:
    - AGENTS.md
    - tools/check_repository_continuity_fixtures.py
    - tests/fixtures/repository-continuity/cases.v1.json
    - tests/fixtures/repository-continuity/artifact-contracts.json
    - docs/repository-continuity-materialization.md
    - https://github.com/egohygiene/holon/issues/80
  precedence:
    - user-and-runtime-instructions
    - scoped-repository-instructions
    - live-repository-and-work-tracker-state
    - canonical-repository-sources
    - continuity-checkpoint
work:
  objective: Stabilize native fixture history without rewriting the validator evidence.
  success_conditions:
    - Pinned full and shallow Antidote sources produce a depth-one disposable checkout at the same commit.
    - Native report bytes remain part of the strict reviewed artifact comparison.
  active_issue:
    provider: github
    id: egohygiene/holon#80
    url: https://github.com/egohygiene/holon/issues/80
  next:
    kind: action
    id: qualify-native-antidote-fixture
    description: Run the pinned native fixture command during the validation sweep and compare the reviewed artifacts.
    readiness: ready
    references:
      - https://github.com/egohygiene/holon/issues/80
    depends_on: []
state:
  base:
    revision: 934e559400336cbf1acac325c89754056e27e3f2
    ref: refs/heads/main
    verified_at: "2026-11-12T00:30:02Z"
  candidate:
    branch: codex/holon-80-native-fixture-depth
    revision: null
    pull_request: null
    handoff_state: in-progress
  live:
    status: verified
    observed_at: "2026-11-12T00:30:02Z"
    default_branch_revision: 934e559400336cbf1acac325c89754056e27e3f2
    issue_state: open
    pull_request_state: not-applicable
    notes: Main includes merged PR 86. No open PR for issue 80 was observed before this candidate.
  parallel_changes:
    - provider: github
      id: egohygiene/holon#65
      url: https://github.com/egohygiene/holon/pull/65
review:
  status: partial
  reviewed_at: "2026-11-12T00:30:02Z"
  reviewed_by: Codex
  evidence:
    - command: 'python3 -m unittest discover --start-directory tests --pattern "test_repository_continuity_fixtures.py" --verbose'
      outcome: passed
      observed_at: "2026-11-12T00:30:02Z"
      notes: Eight tests passed on Python 3.12.14 and Git 2.52.0, including the full/shallow and wrong-revision controls.
    - command: Pinned Antidote checkout comparison using clone_antidote_fixture, git rev-list and git cat-file
      outcome: passed
      observed_at: "2026-11-12T00:30:02Z"
      notes: Both source shapes at f9e23128a660066b3f64c73c4dd2d36554b6040a produced identical pinned commit and source bytes with one visible commit.
    - command: Native EgoLint integration, released continuity conformance, and hosted CI
      outcome: not-run
      observed_at: "2026-11-12T00:30:02Z"
      notes: Full fixture execution and hosted checks are deferred to the validation sweep.
  environment_limitations:
    - Native EgoLint integration was not run with the pinned binary.
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

Record the bounded fixture reproducibility repair from issue #80 under the
repository instructions, live tracker, and fixture contracts.

## Resume protocol

Read AGENTS, [issue #80](https://github.com/egohygiene/holon/issues/80),
[tracker #66](https://github.com/egohygiene/holon/issues/66), and the
[fixture guide](docs/repository-continuity-materialization.md). Recheck the
candidate and parallel work before updating the handoff.

## Current objective and success conditions

Use the same depth-one disposable Antidote checkout for either pinned source
shape. Keep Git's observed history evidence in the original validator report.

## State snapshot

The candidate starts at main `934e559400336cbf1acac325c89754056e27e3f2`,
which contains the merged publication-selection work from PR #86. Issue #80
was open at the recorded observation.

## Completed and material changes

The checker uses a depth-one local clone and verifies its pinned revision and
shallow state. The fixture tests exercise both source shapes and reject a
wrong mapped revision. The existing source locks and reviewed digests still
govern the full native check.

## Validation and review evidence

The focused fixture file passed all eight tests. Both full and shallow
checkouts of the real Antidote pin yielded the same depth-one commit object
and authored files. The native report and full suite remain unqualified.

## Blockers, risks, unknowns, and deferred work

Issue #80 retains the exact native validator and artifact comparison run.
Issues #77–#79 retain their broader rendering, accessibility, and owner
qualification work. The continuity profile remains at observe.

## Next dependency-ready work

Run the pinned native proof from the fixture guide during the validation
sweep and compare its exact outputs before accepting issue #80.

## Parallel changes and reconciliation

Audit PR #65 and work on issues #72, #75, and #76 are separate candidates.
Reconcile the repository-root checkpoint when combining same-repository drafts.

## Privacy and redaction

This checkpoint records public source facts and synthetic test evidence.

## Handoff update protocol

Record the reviewed head and full native outcomes when available. Check current
issue and pull-request state before asserting acceptance.

## Compaction and supersession

Use Git and the linked issues for history. Retain only the current candidate
and remaining checks in the next checkpoint.
