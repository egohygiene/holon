---
schema_version: aether.repository-continuity/v1
repository:
  id: egohygiene/holon
  visibility: public
  default_branch: main
  continuity_path: CONTINUITY.md
document:
  status: active
  updated_at: '2026-11-14T22:49:48Z'
  max_bytes: 16384
  max_lines: 240
  stale_reason: null
  superseded_by: null
scope:
  purpose: Make repeated native site-suite checks ignore renderer-owned cache while retaining authored
    formatting, deterministic artifacts and guarded recovery.
  includes:
  - The site-suite Biome profile excludes only renderer-owned site-docs/.cache alongside existing generated
    outputs. The source inventory is refreshed; no renderer/cache bytes are rewritten to make validation
    pass.
  - The canonical fixture runner now repeats the complete quality/build path and deliberately rejects
    malformed authored formatting, retaining cache and matching existing public artifact snapshots.
  - Actual generic and LaunchKit site-only consumers use frozen Node/hash-pinned Python graphs, pass two
    consecutive native checks, preserve the exact original autorefs cache bytes and public artifact trees,
    and verify preview, ownership/no-op and guarded disposable recovery.
  excludes: &id001
  - All native targets were disposable generated consumers. No live repository, public deployment, stable
    release, browser/accessibility or cross-platform support is inferred.
  - The canonical legacy fixture uses a labeled synthetic Aether unit input; the independent actual site-only
    proof uses no Aether artifact and does not qualify a complete foundation. Existing Aether release/install
    gates remain separate.
  - Historical Empathy source, canary bytes and proof clocks remain unchanged. This owner repair requires
    explicit later consumer pin adoption; it does not rewrite already accepted evidence.
  canonical_sources:
  - AGENTS.md
  - ROADMAP.md
  - blueprints/site-suite/blueprint.json
  - blueprints/site-suite/files/biome.json
  - tools/check_site_suite_fixtures.py
  - docs/site-suite-blueprint.md
  - docs/evidence/2026-11-14-site-suite-repeat-checks.json
  - tests/fixtures/site-suite/artifact-contracts.json
  - https://github.com/egohygiene/holon/issues/109
  precedence:
  - user-and-runtime-instructions
  - scoped-repository-instructions
  - live-repository-and-work-tracker-state
  - canonical-repository-sources
  - continuity-checkpoint
work:
  objective: Make repeated native site-suite checks ignore renderer-owned cache while retaining authored
    formatting, deterministic artifacts and guarded recovery.
  success_conditions:
  - Generic and LaunchKit consumers pass two full native checks with normal renderer cache present.
  - The previous formatter boundary fails on the exact retained cache; authored-format failure still gates;
    no cache deletion/reformatting hides a failure.
  - Both public artifact trees match reviewed snapshots and source ownership/no-op/guarded recovery remain
    valid.
  active_issue:
    provider: github
    id: egohygiene/holon#109
    url: https://github.com/egohygiene/holon/issues/109
  next:
    kind: issue
    id: egohygiene/holon#32
    description: After reviewing this repair, select the bounded orientation-card source/pilot checkpoint;
      preserve existing source-only versus complete-foundation and release acceptance boundaries.
    readiness: ready
    references:
    - https://github.com/egohygiene/holon/issues/32
    - https://github.com/egohygiene/holon/issues/66
    depends_on: []
state:
  base:
    revision: fc3c20ce7ec9dbdfae7828f82bc6102c639e43e0
    ref: refs/heads/main
    verified_at: '2026-11-14T22:49:48Z'
  candidate:
    branch: codex/site-suite-cache-boundary
    revision: null
    pull_request: null
    handoff_state: ready-for-review
  live:
    status: verified
    observed_at: '2026-11-14T22:49:48Z'
    default_branch_revision: fc3c20ce7ec9dbdfae7828f82bc6102c639e43e0
    issue_state: open
    pull_request_state: not-applicable
    notes: Observed main fc3c20c includes the merged finite distribution candidate and82 is closed;109
      is open as its independent newly discovered cache follow-up. No PR yet exists for this local candidate.
  parallel_changes: []
review:
  status: partial
  reviewed_at: '2026-11-14T22:49:48Z'
  reviewed_by: Codex
  evidence:
  - command: python -m unittest discover -s tests -p test_*.py -v; focused site-suite tests and compileall
    outcome: passed
    notes: 272 full tests pass with no failures/errors/skips. Relevant source/profile compilation and
      focused blueprint/projection controls pass.
    observed_at: '2026-11-14T22:49:48Z'
  - command: Actual generic/LaunchKit site-only qualification using frozen graphs, two complete checks
      and negative/recovery controls
    outcome: passed
    notes: Python3.12.14, Node24.19.0, pnpm11.24.0 and Zensical0.0.57. Both old cache-rule and authored-format
      controls fail as expected; cache remains byte-identical, no-op/ownership/preview and guarded recovery
      pass.
    observed_at: '2026-11-14T22:49:48Z'
  - command: python tools/check_site_suite_fixtures.py; python tools/site_suite_blueprint.py
    outcome: passed
    notes: Both existing fixture variants repeat full checks and reject authored-format errors; dist/Zensical
      hashes match unchanged reviewed snapshots. Refreshed canonical profile/file inventory validates.
    observed_at: '2026-11-14T22:49:48Z'
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

# holon continuity

## Purpose and precedence

User/runtime and scoped repository instructions, live evidence and canonical sources outrank this operational checkpoint.

## Resume protocol

Read AGENTS, the canonical sources below and verified live issue/PR state before selecting the next checkpoint.

## Current objective and success conditions

Make repeated native site-suite checks ignore renderer-owned cache while retaining authored formatting, deterministic artifacts and guarded recovery.

- Generic and LaunchKit consumers pass two full native checks with normal renderer cache present.
- The previous formatter boundary fails on the exact retained cache; authored-format failure still gates; no cache deletion/reformatting hides a failure.
- Both public artifact trees match reviewed snapshots and source ownership/no-op/guarded recovery remain valid.

## State snapshot

Observed default source `fc3c20ce7ec9dbdfae7828f82bc6102c639e43e0`. Candidate `codex/site-suite-cache-boundary` is a review checkpoint; its containing revision remains null intentionally.

## Completed and material changes

The site-suite Biome profile excludes only renderer-owned site-docs/.cache alongside existing generated outputs. The source inventory is refreshed; no renderer/cache bytes are rewritten to make validation pass.

The canonical fixture runner now repeats the complete quality/build path and deliberately rejects malformed authored formatting, retaining cache and matching existing public artifact snapshots.

Actual generic and LaunchKit site-only consumers use frozen Node/hash-pinned Python graphs, pass two consecutive native checks, preserve the exact original autorefs cache bytes and public artifact trees, and verify preview, ownership/no-op and guarded disposable recovery.

## Validation and review evidence

`python -m unittest discover -s tests -p test_*.py -v; focused site-suite tests and compileall` — passed: 272 full tests pass with no failures/errors/skips. Relevant source/profile compilation and focused blueprint/projection controls pass.

`Actual generic/LaunchKit site-only qualification using frozen graphs, two complete checks and negative/recovery controls` — passed: Python3.12.14, Node24.19.0, pnpm11.24.0 and Zensical0.0.57. Both old cache-rule and authored-format controls fail as expected; cache remains byte-identical, no-op/ownership/preview and guarded recovery pass.

`python tools/check_site_suite_fixtures.py; python tools/site_suite_blueprint.py` — passed: Both existing fixture variants repeat full checks and reject authored-format errors; dist/Zensical hashes match unchanged reviewed snapshots. Refreshed canonical profile/file inventory validates.

ADR not required: a localized formatter input-ownership bug fix restores the existing authored-versus-generated boundary without changing renderer, source ownership, policy or publication authority.

## Blockers, risks, unknowns, and deferred work

All native targets were disposable generated consumers. No live repository, public deployment, stable release, browser/accessibility or cross-platform support is inferred.

The canonical legacy fixture uses a labeled synthetic Aether unit input; the independent actual site-only proof uses no Aether artifact and does not qualify a complete foundation. Existing Aether release/install gates remain separate.

Historical Empathy source, canary bytes and proof clocks remain unchanged. This owner repair requires explicit later consumer pin adoption; it does not rewrite already accepted evidence.

## Next dependency-ready work

After reviewing this repair, select the bounded orientation-card source/pilot checkpoint; preserve existing source-only versus complete-foundation and release acceptance boundaries.

## Parallel changes and reconciliation

Preserve finite distribution82 acceptance and all Empathy website receipts. Consumer adoption of the new exact owner pin is separate from the source repair. Hygiene59 reference qualification is independent.

## Privacy and redaction

Public-safe source facts and synthetic fixtures only. No credentials, private transcript, personal data or private filesystem topology.

## Handoff update protocol

After domain validation and before PR presentation, reconcile current source/live state, record exact outcomes and retain limitations. Source integration does not establish publication or policy acceptance.

## Compaction and supersession

Git and linked work records retain history. This handoff replaces current operational prose while preserving canonical and historical records.
