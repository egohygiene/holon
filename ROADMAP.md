---
schema: aether.architecture-document/v1
id: holon-roadmap
title: Holon Roadmap
kind: architecture-document
version: 0.5.1
status: provisional
owners:
  - egohygiene
created: 2026-08-19
updated: 2026-11-13
governed_by:
  - architecture-roadmap
depends_on:
  - holon-vision
  - holon-pillars
  - holon-architecture
  - holon-decisions
related:
  - holon-purpose
  - holon-principles
  - holon-manifesto
  - holon-epistemology
supersedes: []
---

# Holon Roadmap

## Current work — 2026-11-13

The [repository execution ledger (#66)](https://github.com/egohygiene/holon/issues/66)
owns the ordered inventory of all 45 work items. Eight selected scopes are now
closed after six ordinary merges, with independent source review and focused
acceptance evidence at main `94a6ccc27a2d6bd4d18c603be9135ae1b935de1e`:

| Completed scope | Merged PR and immutable merge | Recorded focused evidence |
| --- | --- | --- |
| #68 — presentation path safety | [#94](https://github.com/egohygiene/holon/pull/94), [4b38713](https://github.com/egohygiene/holon/commit/4b387139350a1413adf2b046164f2f001ead64b7) | 15 presentation tests and fixture validation; aliases and failed paired writes. |
| #74 — presentation recovery and bytes | [#95](https://github.com/egohygiene/holon/pull/95), [6ecb181](https://github.com/egohygiene/holon/commit/6ecb181731d7b05c4c9fb12447421e7b05b020dc) | 20 presentation tests and fixtures; no-op, prior ownership, legacy state and LF/CRLF/mixed-newline CLI lifecycle. |
| #71 — ordered-overlay schema parity | [#96](https://github.com/egohygiene/holon/pull/96), [5362bbb](https://github.com/egohygiene/holon/commit/5362bbb21eed8927ce6a2fd481d2b5303a84759f) | 31 materialization tests, including emitted plan/state/rollback instances through Draft 2020-12. |
| #69 — complete recovery and compensation | [#97](https://github.com/egohygiene/holon/pull/97), [18751c7](https://github.com/egohygiene/holon/commit/18751c7768d5b1e440657e6c9b03f15e581a4d88) | 34 integrated materialization tests; transient failure compensation, retry and persistent-failure limits. Closure also records four final-main missing/corrupt recovery controls. |
| #63 — ADR provenance and compatible upgrade | [#98](https://github.com/egohygiene/holon/pull/98), [7d4b461](https://github.com/egohygiene/holon/commit/7d4b46137de8ff93ef14a7c108728032eca22719) | 9 ADR tests and blueprint validation; exact legacy upgrade/rollback and two pinned native ordinary-consumer cases. |
| #77 / #78 / #79 — counters, optional theme and release chronology | [#99](https://github.com/egohygiene/holon/pull/99), [94a6ccc](https://github.com/egohygiene/holon/commit/94a6ccc27a2d6bd4d18c603be9135ae1b935de1e) | 32 Node tests; actual static CLI, public adapter DOM seam and exact pinned Observatory golden bytes. |

These are recorded checks on their stated source boundaries, not new runs by
this documentation closeout. The [native ADR evidence](docs/evidence/2026-11-13-adr-native.json)
retains actual report bytes and source/binary/policy hashes: both ordinary
consumer cases are valid with zero Repository Intelligence diagnostics. The
separate release declaration remains unavailable/advisory. The
[component checkpoint](docs/evidence/2026-11-13-repository-intelligence-qualification.md)
does not claim a real-browser accessibility certification. Hosted CI, released
distribution, deployment, fleet adoption and human approval remain separate.

**Next acceptance checkpoint:** [#67](https://github.com/egohygiene/holon/issues/67)
is open, and its implementation is already merged through PR #93. Review its
remaining acceptance and specialized continuity/gitignore regression evidence;
do not rebuild the generic path guards. Source-delivered #70 and #73 likewise
retain their own open acceptance. #80 is already closed (2026-11-12); #81 owns
the broader navigation reconciliation, and #82 owns distribution/clean-room
qualification. Follow their live child records before choosing further work.

The dated execution snapshot below preserves stable HOL-Q identities, strategy
and historical observations; it is not a current merge queue. In particular,
the #6/#58 scaffolding and gitignore work is already delivered. Continuity stays
at `observe` under #42, and #56's historical ADR/human gates remain unchanged.

<!-- BEGIN ROADMAP EXECUTION SNAPSHOT -->
<!-- roadmap-manifest
schema: hygiene.roadmap/v1alpha1
repository: egohygiene/holon
visibility: public
publication: central
route: /roadmap/holon/
updated: 2026-09-09
-->
## 2026-09-09 execution snapshot

> This evidence-reconciled snapshot is the issue-generation and visual-roadmap handoff. The longer-horizon strategy below remains canonical context; generated HTML, JSON, progress, issue plans, and commit lists are projections.

**Lifecycle:** early implementation, pre-release  
**Current gate:** Keep repository-continuity rollout at `observe`; issue #42 remains blocked until the pinned Aether, Hygiene, and EgoLint inputs are released and a maintainer explicitly promotes the Holon profile.
**North-star outcome:** Deterministic, reversible blueprints that can materialize repositories and explain every resulting change.

**2026-09-18 file-contract update:** Independent layered gitignore work in #58
can proceed from the accepted Empathy source and Filament pilot. It does not
depend on promoting the repository-continuity profile.

### Visual roadmap publication

**Mode:** `central`  
**Route:** `/roadmap/holon/`  
**Current publication evidence:** Source and validation workflow; no verified release publication observed.

Publish the public-safe projection through egohygiene.io at /roadmap/holon/. This repository owns intent and acceptance evidence; it does not add a second site deployment.

### Quest line

<!-- roadmap-step
id: HOL-Q01
status: complete
depends_on: []
issues: []
-->
#### HOL-Q01 — Implement deterministic materialization

**State:** `complete`  
**Depends on:** None

**Outcome:** Holon can materialize its initial blueprint representation deterministically.

**Exit criteria:**

- [x] Repeated materialization from the same inputs is stable.
- [x] The implementation is present with validation configuration.

**Current evidence:**

- PR #20 merged at c62d57afed86.
- Materialization code and a validate workflow were observed.

<!-- roadmap-step
id: HOL-Q02
status: complete
depends_on: [HOL-Q01]
issues: []
-->
#### HOL-Q02 — Prove CI on the default branch

**State:** `complete`
**Depends on:** `HOL-Q01`

**Outcome:** Materialization and contract validation have durable workflow evidence.

**Exit criteria:**

- [x] The default-branch validation run is green.
- [x] A failing fixture demonstrates that invalid output is rejected.

**Current evidence:**

- The merged React/Vite blueprint ran `Validate Holon` successfully on the default branch.
- Negative materialization, dependency-policy, circular-import, ownership, and rollback fixtures prove invalid output is rejected.

<!-- roadmap-step
id: HOL-Q03
status: complete
depends_on: [HOL-Q02]
issues: [14, 15]
-->
#### HOL-Q03 — Ship React/Vite and its first derived profile

**State:** `complete`
**Depends on:** `HOL-Q02`

**Outcome:** Issues #14 and #15 produce an independently useful React/Vite foundation and one tested derived LaunchKit profile.

**Exit criteria:**

- [x] A clean directory materializes into a working React/Vite project.
- [x] The generated project builds and tests without manual repair.
- [x] A specialized landing profile composes without turning its presentation into the generic baseline.

**Current evidence:**

- `blueprints/react-vite/blueprint.json` owns the v1 profile and exact file inventory.
- `examples/react-vite-site.manifest.json` resolves the generic capability while explicitly excluding LaunchKit.
- `tools/check_react_vite_fixture.py` proves clean materialization, no-op replanning, frozen installation, formatting, lint, strict types, tests, byte-reproducible builds, static references, and live preview.
- `blueprints/launchkit/blueprint.json` pins the derived profile, base digest, upstream commit/license, overlay inventory, section contract, and byte budgets.
- OptiFlow and Mantle fixtures prove full and compact content models with pre-rendered HTML, progressive hydration, visual contracts, and deterministic builds.

<!-- roadmap-step
id: HOL-Q04
status: complete
depends_on: [HOL-Q03]
issues: [4]
-->
#### HOL-Q04 — Compose the public site suite

**State:** `complete`
**Depends on:** `HOL-Q03`

**Outcome:** One manifest composes a selectable landing with documentation, architecture, and legal surfaces without copying sibling ownership.

**Exit criteria:**

- [x] Generic React/Vite and LaunchKit landings remain distinct selectable profiles.
- [x] Zensical renders documentation, architecture, and legal routes from a closed reviewed content contract.
- [x] Both variants build byte-reproducibly and serve `/`, `/docs/`, `/architecture/`, and `/legal/` from one local artifact.
- [x] The issue #4 pull request is merged and its default-branch validation is green.

**Current evidence:**

- `blueprints/zensical/` pins the upstream release, license, hash-locked Python dependency graph, and exact rendered inventory.
- `blueprints/site-suite/` composes either landing choice without changing the profile ownership graph.
- Holon and OptiFlow fixtures prove generic and LaunchKit variants from empty directories through deterministic build and live preview.
- PR #27 merged the site-suite implementation and its default-branch validation passed.
- Identity #56/#57 and Antidote migration remain explicit downstream work.

<!-- roadmap-step
id: HOL-Q05
status: planned
depends_on: [HOL-Q02, HOL-Q04]
issues: []
-->
#### HOL-Q05 — Release and prove a clean-room consumer

**State:** `planned`  
**Depends on:** `HOL-Q02`, `HOL-Q04`

**Outcome:** A tagged Holon release creates and validates a real consumer from pinned inputs.

**Exit criteria:**

- [ ] Immutable release artifacts are published.
- [ ] A clean-room consumer build is linked as acceptance evidence.

**Current evidence:**

- No release or clean-room consumer proof was observed.

<!-- roadmap-step
id: HOL-Q06
status: active
depends_on: [HOL-Q03, HYG-Q06, IDN-Q06]
issues: [22]
-->
#### HOL-Q06 — Ship the accessible quest-line renderer

**State:** `active`
**Depends on:** `HOL-Q03`, `HYG-Q06`, `IDN-Q06`

**Outcome:** A versioned Holon blueprint renders a responsive visual quest line with expandable roadmap evidence and a no-JavaScript fallback.

**Exit criteria:**

- [ ] The renderer passes keyboard, WCAG 2.2 AA, reduced-motion, mobile, link, visual-regression, and bundle-size gates.
- [ ] It accepts deterministic manifest/evidence inputs and a configurable base path without owning deployment.
- [x] Framework-neutral roadmap, decision, journey, evidence, comparison, and cognitive-state primitives consume the pinned Observatory read model.
- [x] Interactive histories virtualize and the static exporter remains complete without JavaScript.
- [x] Small, large, stale, blocked, and partially adopted fixture stories are independently runnable outside Relay.

**Current evidence:**

- Issue #22 and merged PR #23 established the reusable renderer foundation.
- `packages/repository-intelligence/` implements the static-first component kit and independent fixture lab.
- The 640-event large fixture, accessibility/responsive contract tests, and deterministic visual snapshots provide local evidence; adoption by the React/Vite blueprint and full publication gates remain open.

<!-- roadmap-step
id: HOL-Q08
status: blocked
depends_on: [HOL-Q02]
issues: [42, 43, 44, 45, 46]
-->
#### HOL-Q08 — Materialize repository continuity safely

**State:** `blocked`
**Depends on:** `HOL-Q02`, released Aether/Hygiene/EgoLint continuity inputs, and explicit maintainer promotion

**Outcome:** Holon can scaffold, reconcile, verify, and recover repository-owned continuity surfaces through a reviewed local workflow without acquiring Git, GitHub, publication, or fleet authority.

**Exit criteria:**

- [x] A versioned `observe`-stage profile pins immutable Aether, Hygiene, and EgoLint inputs with verified artifact digests.
- [x] Block-scoped planning, preview, apply, verification, rollback, and conflict handling preserve repository-authored content.
- [x] Five repository classes, adversarial states, and the Antidote prototype migration pass deterministic fixture proof.
- [x] The canonical nested CLI requires an exact preview receipt before apply, and Holon dogfoods the same contract with durable local state.
- [ ] The pinned Aether contract and skill, Hygiene policy, and EgoLint rule/report contract are stable and included in immutable releases.
- [ ] A maintainer reviews the released-input fixture evidence, repins the profile, and explicitly promotes rollout beyond `observe`.

**Current evidence:**

- Issues #43 through #46 are closed through merged PRs #47 through #49 and #51.
- PR #51 added the bounded CLI, documentation, and Holon dogfood closeout without promoting the profile or closing parent issue #42.
- The profile still records Aether as `draft` and Hygiene/EgoLint as `proposed`, with `release_included: false` for all three sources.
- No GitHub releases were observed for Aether, Hygiene, or EgoLint on 2026-09-09, and EgoLint issue #55 remains open on the released-contract gate.
- Relay still owns reusable pull-request preflight, and Pace still owns fleet convergence.

<!-- roadmap-step
id: HOL-Q09
status: active
depends_on: [HOL-Q01]
issues: [6]
-->
#### HOL-Q09 — Materialize inherited ADR foundations

**State:** `active`
**Depends on:** `HOL-Q01` and the accepted Hygiene ADR policy from issue #15

**Outcome:** Every repository class can initialize or review-migrate a standard ADR foundation without copying organization policy or transferring ownership of repository decisions.

**Exit criteria:**

- [x] The foundation catalog requires one versioned architecture-decision capability for every repository class.
- [x] Consumer manifests pin Hygiene policy v1.2.0 at the exact approved commit.
- [x] The blueprint emits a policy reference, standard template, and deterministic numeric index while ADR records remain repository-owned.
- [x] Synthetic fixtures prove empty initialization, existing-record preservation, local extension bounds, stable ordering, and no-write conflicts.
- [x] Issue #6 scaffold and #64 policy-selection repair are merged.
- [ ] Current default-branch CI qualification remains a separate provider receipt.

**Current evidence:**

- Hygiene issue #15 and PR #48 accepted and activated the organization policy before this implementation began.
- `blueprints/architecture-decisions/` and `tools/architecture_decision_blueprint.py` contain the merged 1.1.0 owner blueprint and offline renderer, selecting accepted Hygiene policy 1.2.0 at `a05b14f8b9e2772124f879f818e09a911e996ad8`.
- Fleet-specific history extraction and repository migrations remain deferred to the dedicated per-repository issues.

<!-- roadmap-step
id: HOL-Q10
status: active
depends_on: [HOL-Q01]
issues: [58]
-->
#### HOL-Q10 — Materialize the accepted layered gitignore contract

**State:** `active`
**Depends on:** `HOL-Q01`, accepted Empathy foundation 1.1.0, and Filament PR #6

**Outcome:** Repositories can review, adopt, update, verify, and recover the
Empathy-owned ignore composition while retaining repository-owned local rules.

**Exit criteria:**

- [x] The pinned source adapter and deterministic read-only plan are reviewed and merged (PR #59).
- [ ] Reviewed creation and explicit exact-byte adoption preserve unrelated files and Git metadata.
- [ ] No-op reapplication, local-rule-preserving upgrades, drift detection, and guarded rollback pass disposable fixtures.

**Current evidence:**

- PR #59 merged at `72aabf834ff541a272624382079df359037764fa` with the pinned
  planner and accepted Filament/scoped Rust fixtures.
- The next #58 candidate adds reviewed apply/adoption, dedicated state and
  recovery, no-op reruns, updates preserving local selections, drift checks,
  scope release, and guarded rollback. Disposable fixtures cover the public CLI,
  a synthetic baseline upgrade, real Git behavior, and interrupted writes.
- Remaining checkboxes await maintainer review and merge of that lifecycle PR;
  local proof alone does not declare HOL-Q10 accepted.
- Source semantics remain in Empathy; EgoLint #61 owns reusable conformance,
  Relay execution, and Pace #30 later reviewed rollout under egohygiene/.github#32.

### Roadmap-to-issue handoff

- A step is complete only when its exit criteria and required evidence are satisfied; commit count never determines progress.
- Ready steps without an issue are candidates for the private, duplicate-aware roadmap.issue-plan.json dry run. Planned steps remain preview-only unless a reviewer explicitly opts them in with issue_policy: propose.
- Issue creation or reconciliation requires human approval or an explicitly authorized Pace operation and returns issue references through a reviewable roadmap pull request.
- Pull requests and commits should include Roadmap-Step: <ID>; historical evidence may be linked through existing issue and pull-request relationships.
- Public rendering uses only allowlisted build-time evidence and never places a GitHub token or private issue plan in the browser artifact.

<!-- END ROADMAP EXECUTION SNAPSHOT -->

## Strategic context

This roadmap describes capability evolution, not promised dates or an issue queue. Sequence follows architecture dependencies and may change when evidence or risk changes.

## Phase 1: Stabilize foundation resolution

**Outcome:** A bounded capability advances from documented intent to validated, independently usable behavior.

**Exit signals:**

- The owning contract and acceptance criteria are versioned.
- Implementation and documentation agree.
- Relevant tests and safety checks pass.
- Downstream consumers and migration impact are understood.
- Remaining uncertainty is visible.

## Phase 2: Render repository instances

**Outcome:** A bounded capability advances from documented intent to validated, independently usable behavior.

**Exit signals:**

- The owning contract and acceptance criteria are versioned.
- Implementation and documentation agree.
- Relevant tests and safety checks pass.
- Downstream consumers and migration impact are understood.
- Remaining uncertainty is visible.

## Phase 3: Implement safe upgrades

**Outcome:** A bounded capability advances from documented intent to validated, independently usable behavior.

**Exit signals:**

- The owning contract and acceptance criteria are versioned.
- Implementation and documentation agree.
- Relevant tests and safety checks pass.
- Downstream consumers and migration impact are understood.
- Remaining uncertainty is visible.

## Phase 4: Compose multi-repository organizations

**Outcome:** A bounded capability advances from documented intent to validated, independently usable behavior.

**Exit signals:**

- The owning contract and acceptance criteria are versioned.
- Implementation and documentation agree.
- Relevant tests and safety checks pass.
- Downstream consumers and migration impact are understood.
- Remaining uncertainty is visible.

## Phase 5: Expose a conversational visual organization compiler

**Outcome:** A bounded capability advances from documented intent to validated, independently usable behavior.

**Exit signals:**

- The owning contract and acceptance criteria are versioned.
- Implementation and documentation agree.
- Relevant tests and safety checks pass.
- Downstream consumers and migration impact are understood.
- Remaining uncertainty is visible.

## Cross-cutting tracks

- Security, privacy, accessibility, licensing, and provenance.
- Documentation, architecture portals, examples, and onboarding.
- Packaging, release, compatibility, and self-hosting.
- Organization integration through explicit contracts.
- Observatory evidence and Pace conformance when those systems exist.

## Deferred direction

Optional managed services, enterprise controls, marketplaces, and the conversational organization compiler remain later architecture work. Current choices should preserve portability and avoid foreclosing them.

## Evidence and uncertainty

- **Observed:** The repository README establishes the intended boundary as an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; significant implementation remains incomplete.
- **Decided for this draft:** The repository owns the bounded concern described here and participates through versioned contracts.
- **Proposed:** Target systems and later roadmap phases remain proposals until accepted and implemented.
- **Open question:** Which parts of this draft should become active in the first independently versioned release?
