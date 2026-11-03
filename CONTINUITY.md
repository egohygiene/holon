---
document:
  max_bytes: 16384
  max_lines: 240
  stale_reason: null
  status: active
  superseded_by: null
  updated_at: '2026-11-03T04:51:18Z'
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
  reviewed_at: '2026-11-03T04:51:18Z'
  reviewed_by: Codex
  evidence:
  - command: node --check packages/repository-intelligence/src/render.js; node --check tests/javascript/repository-intelligence.test.mjs
    outcome: passed
    observed_at: '2026-11-03T04:51:18Z'
    notes: Both modified JavaScript files parse. Four new ordering/date/CLI regression cases are authored
      but unexecuted.
  - command: Generate the existing small fixture HTML from base and candidate; compare exact markup and
      SHA-256
    outcome: passed
    observed_at: '2026-11-03T04:51:18Z'
    notes: Base digest ce389480af6b63898f48b0746cf51d291fed51ec9bdf3ed0b4fe5505ffd91dee is reproduced.
      Candidate e723f04b1678ae6cfdb861e33f61a74e55d70d4a1ff348675755ee108adf7948 differs only by the selected
      release key gaining its supplied safe link. Record the intentional new markup digest; no visual
      approval is inferred.
  - command: git diff --check, unchanged owner lock/fixtures/CSS and continuity metadata/schema/structure/privacy/budget
      inspection
    outcome: passed
    observed_at: '2026-11-03T04:51:18Z'
    notes: Whitespace and checkpoint checks pass. Original fixture, owner-lock and CSS bytes/hashes are
      unchanged.
  - command: node --test tests/javascript/repository-intelligence.test.mjs; real mounted/browser/AX/owner
      compatibility and hosted CI
    outcome: not-run
    observed_at: '2026-11-03T04:51:18Z'
    notes: New regression cases and the existing suite remain unexecuted. Static example generation is
      narrower evidence.
  environment_limitations:
  - Ordering/date/precision/CLI regressions are authored but unexecuted; no full behavior or browser/AX
    qualification is claimed.
  - 'Publication syntax is explicit: zoned calendar-valid RFC3339, uppercase T/Z, up to nine fractional
    digits; leap seconds and unknown -00:00 are excluded from chronology.'
  - The intentional selected-link markup digest is recorded, with actual visual/browser review still pending.
  - Official released EgoLint continuity conformance and broader suites are unexecuted.
schema_version: aether.repository-continuity/v1
scope:
  canonical_sources:
  - AGENTS.md
  - packages/repository-intelligence/src/render.js
  - packages/repository-intelligence/README.md
  - tests/javascript/repository-intelligence.test.mjs
  - contracts/observatory-repository-intelligence.v1.lock.json
  - DECISIONS.md
  - https://github.com/egohygiene/holon/issues/79
  excludes:
  - Provider fetching/query normalization, release policy, schema/fixture lock changes and site publication.
  - Regression/browser/AX suites, hosted CI, merge and issue closure.
  includes: &id001
  - Select the greatest supported publication instant independent of array/semantic-version ordering,
    with deterministic ID ties and preserved source arrays.
  - Keep undated/invalid records visible, show Unknown when no usable dated entity exists and None for
    an empty view.
  - Use one static/mounted summary and safe selected-release link; preserve source state and provider/owner
    boundaries.
  precedence:
  - user-and-runtime-instructions
  - scoped-repository-instructions
  - live-repository-and-work-tracker-state
  - canonical-repository-sources
  - continuity-checkpoint
  purpose: Select the displayed latest release by valid publication evidence and retain a safe link to
    that release.
state:
  base:
    revision: a7734dba83305276b12932fcd4ce348044d9a2e9
    ref: refs/heads/main
    verified_at: '2026-11-03T04:51:18Z'
  candidate:
    branch: codex/79-latest-release-publication
    revision: null
    pull_request: null
    handoff_state: ready-for-review
  live:
    status: verified
    observed_at: '2026-11-03T04:51:18Z'
    default_branch_revision: a7734dba83305276b12932fcd4ce348044d9a2e9
    issue_state: open
    pull_request_state: not-applicable
    notes: Main a7734db and issue79 are current/open. Counter draft84, optional-theme draft85 and audit65
      remain open and separate. PR64 already merged. This candidate is not merged, released or browser-qualified.
  parallel_changes:
  - provider: github
    id: egohygiene/holon#65
    url: https://github.com/egohygiene/holon/pull/65
  - provider: github
    id: egohygiene/holon#84
    url: https://github.com/egohygiene/holon/pull/84
  - provider: github
    id: egohygiene/holon#85
    url: https://github.com/egohygiene/holon/pull/85
work:
  objective: Select the displayed latest release by valid publication evidence and retain a safe link
    to that release.
  success_conditions: *id001
  active_issue:
    provider: github
    id: egohygiene/holon#79
    url: https://github.com/egohygiene/holon/issues/79
  next:
    kind: action
    id: review-draft-and-qualify
    description: Review publication timestamp/tie/unknown semantics and the single-link markup change,
      run issue79 regressions during qualification, then reconcile peer drafts84/85 before any later merge.
    readiness: ready
    references:
    - https://github.com/egohygiene/holon/issues/79
    depends_on: []
---

# Holon continuity

## Purpose and precedence

Record only the bounded issue79 display-chronology draft. User/runtime and scoped instructions, live evidence and canonical sources outrank the checkpoint.

## Resume protocol

Read AGENTS, the component render/guide, owner lock, issue79 and peer drafts84/85. Verify main before resuming; PR64 is already merged.

## Current objective and success conditions

Use explicit valid publication timestamps for latest selection, preserve unknown/undated states, keep source order untouched and retain a safe link to the represented release.

## State snapshot

Base main a7734dba83305276b12932fcd4ce348044d9a2e9 is verified. Issue79 is open; candidate codex/79-latest-release-publication has null self-revision/PR before creation. Audit65 and drafts84/85 remain open.

## Completed and material changes

render.js selects the greatest supported zoned publication instant at nanosecond precision, then the smallest ID for equal instants. No valid dated entity yields Unknown; empty view yields None. The metric safely links the selected key. The package guide documents supported dates/ties. Four new regressions cover order, invalid/undated states, offsets/precision/ties and the public static CLI.

## Validation and review evidence

Two node --check commands and git diff --check pass. Existing small-fixture HTML generation reproduces the base digest and proves the candidate differs only by one selected-release link; its recorded markup digest is updated. Continuity metadata/schema/structure/budget checks pass.

## Blockers, risks, unknowns, and deferred work

Regression suites and real mounted/browser/AX/owner compatibility checks remain unexecuted. Static generation and an intentional markup digest are not visual approval or broad behavior qualification. No release/publication or owner-schema change occurs.

## Next dependency-ready work

Review date/tie/unknown behavior and the single-link markup, then run issue79 acceptance during qualification. Keep the issue open until actual required proof exists.

## Parallel changes and reconciliation

Counter draft84, theme draft85 and audit65 remain independent. Guide/test and root checkpoint edits can overlap; reconcile combined source and semantic continuity during later review, preserving each bounded fix and its evidence.

## Privacy and redaction

Only scoped public source facts and synthetic release fixture inputs are retained. Exclude private context, credentials, personal information and machine-local paths.

## Handoff update protocol

Refresh after review/actual qualification. ADR not required: local display chronology/link repair under the existing owner view boundary. Preserve all observe/proposed/release distinctions. No merge, closure or publication is authorized here.

## Compaction and supersession

Keep all twelve sections and current size limits. Canonical render code, owner lock, Git and issue79 retain the detailed implementation/history.
