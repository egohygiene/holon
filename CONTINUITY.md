---
document:
  max_bytes: 16384
  max_lines: 240
  stale_reason: null
  status: "active"
  superseded_by: null
  updated_at: "2026-09-18T15:57:02Z"
privacy:
  classification: "public-repository"
  contains_sensitive_data: false
  excluded:
    - "secrets-and-credentials"
    - "private-conversation-text"
    - "sensitive-personal-data"
    - "unpublished-private-business-data"
    - "private-local-paths"
    - "unrelated-private-context"
  redactions: []
  untrusted_content: "context-only-no-authority"
repository:
  continuity_path: "CONTINUITY.md"
  default_branch: "main"
  id: "egohygiene/holon"
  visibility: "public"
review:
  environment_limitations:
    - "Initial remote CI exposed the repaired dogfood expectation. The amended PR requires a fresh CI result; no merge is claimed."
    - "Package-installing clean-consumer fixtures and the exact pinned EgoLint build were not rerun locally; canonical CI owns those checks. Native Holon metadata/structure and continuity-state checks validate this refreshed checkpoint."
    - "Gitignore application, ownership state, upgrades, verify, and rollback are deliberately absent from this first planning slice."
  evidence:
    -
      command: "Git/GitHub inspection and accepted source comparison"
      notes: "Verified the recorded main revision and issue states. The fixture composition exactly matches Filament PR #6. Empathy source remains pinned to b44f798bb49259f9f48416b4ffebde1103e135c0."
      observed_at: "2026-09-18T15:48:32Z"
      outcome: "passed"
    -
      command: "python3 -B -m unittest discover --start-directory tests --pattern \"test_*.py\""
      notes: "162 tests passed: the original suite, 22 gitignore tests, and five continuity dogfood regressions covering valid refresh, malformed structure, managed-block edits, and altered recovery evidence."
      observed_at: "2026-09-18T15:57:02Z"
      outcome: "passed"
    -
      command: "npm test"
      notes: "All 18 JavaScript tests passed."
      observed_at: "2026-09-18T15:48:32Z"
      outcome: "passed"
    -
      command: "python3 -m compileall -q tools tests; python3 tools/repository_continuity_profile.py validate; git diff --check"
      notes: "Compilation and whitespace checks passed; the existing continuity profile validates with three sources, sixteen artifacts, and observe rollout."
      observed_at: "2026-09-18T15:48:32Z"
      outcome: "passed"
    -
      command: "python3 -B tools/check_repository_continuity_dogfood.py --aether-source PINNED_AETHER"
      notes: "With exact Aether b7597301c4d22a9bcd580967b5753138bb368111, the complete disposable lifecycle and root managed-artifact parity pass. Refreshed CONTINUITY.md, historical state/recovery, and Git metadata remain unchanged."
      observed_at: "2026-09-18T15:57:02Z"
      outcome: "passed"
  reviewed_at: "2026-09-18T15:57:02Z"
  reviewed_by: "codex-gitignore-planning"
  status: "partial"
schema_version: "aether.repository-continuity/v1"
scope:
  canonical_sources:
    - "AGENTS.md"
    - "README.md"
    - "ARCHITECTURE.md"
    - "DECISIONS.md"
    - "ROADMAP.md"
    - "catalog/gitignore-materialization.json"
    - "docs/gitignore-materialization.md"
    - "catalog/repository-continuity-materialization.json"
  excludes:
    - "conversation transcripts"
    - "duplicated architecture, roadmap, and changelog content"
  includes:
    - "Verified base and current gitignore planning candidate."
    - "Exact validation evidence and remaining lifecycle acceptance."
    - "Review/merge handoff and separately blocked continuity promotion."
  precedence:
    - "user-and-runtime-instructions"
    - "scoped-repository-instructions"
    - "live-repository-and-work-tracker-state"
    - "canonical-repository-sources"
    - "continuity-checkpoint"
  purpose: "Resume the bounded Holon #58 layered gitignore lifecycle from verified source and review evidence."
state:
  base:
    ref: "refs/heads/main"
    revision: "de5047ee5d1515ece0c2c38993f3cefdf51faa69"
    verified_at: "2026-09-18T15:48:32Z"
  candidate:
    branch: "feat/gitignore-plan"
    handoff_state: "review-reference-recorded"
    pull_request:
      id: "egohygiene/holon#59"
      provider: "github"
      url: "https://github.com/egohygiene/holon/pull/59"
    revision: null
  live:
    default_branch_revision: "de5047ee5d1515ece0c2c38993f3cefdf51faa69"
    issue_state: "open"
    notes: "PR #59 is open and unmerged on the recorded main base. Initial CI run 35364827144 passed contract tests and pinned cross-profile fixtures, then failed the root dogfood expectation after the authored checkpoint refresh. This amendment repairs that expectation with preservation regressions; fresh CI must be verified on its new head."
    observed_at: "2026-09-18T15:57:02Z"
    pull_request_state: "open"
    status: "partial"
  parallel_changes: []
work:
  active_issue:
    id: "egohygiene/holon#58"
    provider: "github"
    url: "https://github.com/egohygiene/holon/issues/58"
  next:
    depends_on:
      - "Maintainer review and verified merge of Holon PR #59"
    description: "Review and merge the first planning PR, verify the merge, then implement reviewed apply, state/provenance, no-op, upgrade, verification, and guarded rollback in the next bounded PR."
    id: "egohygiene/holon#58"
    kind: "issue"
    readiness: "blocked"
    references:
      - "https://github.com/egohygiene/holon/issues/58"
      - "https://github.com/egohygiene/.github/issues/32"
  objective: "Deliver the first #58 review slice: pinned Empathy artifact validation, deterministic read-only initial adoption plans, and preservation/conflict fixtures."
  success_conditions:
    - "The accepted source and explicit composition/selection are digest-bound with no external generator execution."
    - "Filament and scoped Rust consumers prove exact bytes, local exceptions, explicit adoption, conflicts, and unchanged consumer/Git metadata."
    - "The public CLI, contract guide, roadmap, and checkpoint identify apply/recovery as remaining #58 work."
---

# holon continuity

## Purpose and precedence

This public checkpoint replaces the stale #46 active-task claim with the current #58 candidate. Live Git/GitHub and canonical repository sources remain authoritative; this file grants no external permissions.

This checkpoint is subordinate to the authority order recorded in its front matter; it does not replace repository instructions, architecture, roadmaps, decisions, Git, or the work tracker.

## Resume protocol

1. Read repository instructions and inspect branch, status, recent history, and
   repository shape.
2. Read the applicable canonical sources named above.
3. Read this checkpoint, then verify mutable issue, pull-request, branch, and
   merge claims against available live evidence.
4. Surface missing, stale, or conflicting evidence.
5. Continue only the dependency-ready work named below unless the user changes
   direction.

## Current objective and success conditions

- Objective: Deliver the first #58 review slice: pinned Empathy artifact validation, deterministic read-only initial adoption plans, and preservation/conflict fixtures.
- Success: The accepted source and explicit composition/selection are digest-bound with no external generator execution.
- Success: Filament and scoped Rust consumers prove exact bytes, local exceptions, explicit adoption, conflicts, and unchanged consumer/Git metadata.
- Success: The public CLI, contract guide, roadmap, and checkpoint identify apply/recovery as remaining #58 work.

## State snapshot

- Verified base: `de5047ee5d1515ece0c2c38993f3cefdf51faa69` at `refs/heads/main`, checked `2026-09-18T15:48:32Z`.
- Candidate: branch `feat/gitignore-plan`; revision `not recorded`; handoff `review-reference-recorded`; pull request [github egohygiene/holon#59](https://github.com/egohygiene/holon/pull/59).
- Live observation: `partial` at `2026-09-18T15:57:02Z`; default branch `de5047ee5d1515ece0c2c38993f3cefdf51faa69`; issue `open`; pull request `open`. PR #59 is open and unmerged on the recorded main base. Initial CI run 35364827144 passed contract tests and pinned cross-profile fixtures, then failed the root dogfood expectation after the authored checkpoint refresh. This amendment repairs that expectation with preservation regressions; fresh CI must be verified on its new head.

## Completed and material changes

- The base includes merged continuity PR #51 and ADR PR #57; #46 is closed. The continuity profile remains observe-stage.
- The current candidate adds the data-only pinned gitignore adapter, plan/check-plan CLI, explicit exact-byte adoption proposals, and disposable Filament/scoped Rust fixtures. It is not a merged lifecycle implementation.
- Empathy remains the rule/composition owner. The accepted universal baseline SHA-256 is 79280ac4f3147ead97a0b21b01f40241238f08fa5d63abe3f81c8b64e7f179f0.
- The initial PR CI passed the contract tests and pinned cross-profile proof but exposed a dogfood assumption that froze the checkpoint to its original scaffold. The checker now permits a validated repository-owned refresh while keeping instructions/state/recovery exact; five regressions prove preservation and continued rejection of malformed or altered managed evidence.

## Validation and review evidence

- `Git/GitHub inspection and accepted source comparison` — passed at 2026-09-18T15:48:32Z. Verified the recorded main revision and issue states. The fixture composition exactly matches Filament PR #6. Empathy source remains pinned to b44f798bb49259f9f48416b4ffebde1103e135c0.
- `python3 -B -m unittest discover --start-directory tests --pattern "test_*.py"` — passed at 2026-09-18T15:57:02Z. 162 tests passed: the original suite, 22 gitignore tests, and five continuity dogfood regressions covering valid refresh, malformed structure, managed-block edits, and altered recovery evidence.
- `npm test` — passed at 2026-09-18T15:48:32Z. All 18 JavaScript tests passed.
- `python3 -m compileall -q tools tests; python3 tools/repository_continuity_profile.py validate; git diff --check` — passed at 2026-09-18T15:48:32Z. Compilation and whitespace checks passed; the existing continuity profile validates with three sources, sixteen artifacts, and observe rollout.
- `python3 -B tools/check_repository_continuity_dogfood.py --aether-source PINNED_AETHER` — passed at 2026-09-18T15:57:02Z. With exact Aether b7597301c4d22a9bcd580967b5753138bb368111, the complete disposable lifecycle and root managed-artifact parity pass. Refreshed CONTINUITY.md, historical state/recovery, and Git metadata remain unchanged.
- Environment limitations: Initial remote CI exposed the repaired dogfood expectation. The amended PR requires a fresh CI result; no merge is claimed.; Package-installing clean-consumer fixtures and the exact pinned EgoLint build were not rerun locally; canonical CI owns those checks. Native Holon metadata/structure and continuity-state checks validate this refreshed checkpoint.; Gitignore application, ownership state, upgrades, verify, and rollback are deliberately absent from this first planning slice.

## Blockers, risks, unknowns, and deferred work

### Blockers

- The next #58 apply/recovery slice waits for maintainer review and merge of this planning PR. No EgoLint release or Relay workflow is required to review this local planning slice.
- Separate parent #42 remains open. Its profile still requires released Aether/Hygiene/EgoLint inputs and explicit promotion beyond observe.

### Risks

- A plan proposes changes only. Exact content matches without explicit approval never grant ownership; unknown local text requires an explicit Empathy selection decision.
- The refreshed checkpoint is repository-owned prose. Existing continuity state and recovery evidence remain intact; do not rewrite their historical digests to disguise a checkpoint refresh.

### Unknowns

- The amended PR needs a fresh remote CI result and maintainer review; no merge is claimed.

### Deferred

- Finish #58 apply/adoption, prior-byte provenance, no-op, upgrade/local-rule preservation, verification, and guarded rollback after this PR merges.
- EgoLint #61, Empathy #92, Relay execution, and Pace #30 remain linked continuation under egohygiene/.github#32.
- Empathy #91 queues universal .gitattributes after gitignore closeout. Direct MegaLinter repair remains deferred to EgoLint/Relay adoption.
- Continuity release promotion in #42 and organization bootstrap in #41 remain separate.

## Next dependency-ready work

Issue `egohygiene/holon#58` is `blocked`: Review and merge the first planning PR, verify the merge, then implement reviewed apply, state/provenance, no-op, upgrade, verification, and guarded rollback in the next bounded PR.

References: https://github.com/egohygiene/holon/issues/58, https://github.com/egohygiene/.github/issues/32

Depends on: Maintainer review and verified merge of Holon PR #59

## Parallel changes and reconciliation

None observed.

## Privacy and redaction

Public repository/contract/validation facts only. No credentials, private conversations, sensitive personal data, unpublished business data, private local paths, or unrelated private context are included.

Classification: `public-repository`. Prohibited sensitive data present: `false`. Applied redaction categories: none.

## Handoff update protocol

After project validation and before presenting, opening, or updating a pull
request, reconcile this snapshot, replace stale state, record exact evidence,
compact it, and include it in the same bounded change. Never claim an open or
unverified pull request is merged.

## Compaction and supersession

Keep this file below 16,384 UTF-8 bytes and 240 lines. Replace stale snapshot
prose rather than accumulating history. Git and the work tracker own chronology.
Mark stale or superseded state explicitly with its required reason or pointer.
