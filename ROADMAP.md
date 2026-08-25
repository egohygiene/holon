---
schema: aether.architecture-document/v1
id: holon-roadmap
title: Holon Roadmap
kind: architecture-document
version: 0.1.0
status: provisional
owners:
  - egohygiene
created: 2026-08-19
updated: 2026-08-25
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

<!-- BEGIN ROADMAP EXECUTION SNAPSHOT -->
<!-- roadmap-manifest
schema: hygiene.roadmap/v1alpha1
repository: egohygiene/holon
visibility: public
publication: central
route: /roadmap/holon/
updated: 2026-08-25
-->
## 2026-08-24 execution snapshot

> This evidence-reconciled snapshot is the issue-generation and visual-roadmap handoff. The longer-horizon strategy below remains canonical context; generated HTML, JSON, progress, issue plans, and commit lists are projections.

**Lifecycle:** early implementation, pre-release  
**Current gate:** Produce default-branch CI and release evidence, then complete the React/Vite blueprint in issue #14.  
**North-star outcome:** Deterministic, reversible blueprints that can materialize repositories and explain every resulting change.

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
status: active
depends_on: [HOL-Q01]
issues: []
-->
#### HOL-Q02 — Prove CI on the default branch

**State:** `active`  
**Depends on:** `HOL-Q01`

**Outcome:** Materialization and contract validation have durable workflow evidence.

**Exit criteria:**

- [ ] The default-branch validation run is green.
- [ ] A failing fixture demonstrates that invalid output is rejected.

**Current evidence:**

- A validate workflow exists, but no run evidence was observed.

<!-- roadmap-step
id: HOL-Q03
status: planned
depends_on: [HOL-Q02]
issues: [14]
-->
#### HOL-Q03 — Ship the React and Vite blueprint

**State:** `planned`  
**Depends on:** `HOL-Q02`

**Outcome:** Issue #14 produces a tested blueprint suitable for the roadmap-site pilot.

**Exit criteria:**

- [ ] A clean directory materializes into a working React/Vite project.
- [ ] The generated project builds and tests without manual repair.

**Current evidence:**

- Issue #14 tracks the React/Vite blueprint.

<!-- roadmap-step
id: HOL-Q04
status: planned
depends_on: [HOL-Q03]
issues: []
-->
#### HOL-Q04 — Prove reversibility and reviewable diffs

**State:** `planned`  
**Depends on:** `HOL-Q03`

**Outcome:** Operators can preview, apply, and safely reverse blueprint-owned changes.

**Exit criteria:**

- [ ] Preview identifies every planned file change.
- [ ] Removal or rollback preserves consumer-owned data.

**Current evidence:**

- Reversible, reviewable materialization is the north-star gap.

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

- Issue #22 tracks the reusable renderer foundation.
- `packages/repository-intelligence/` implements the static-first component kit and independent fixture lab.
- The 640-event large fixture, accessibility/responsive contract tests, and deterministic visual snapshots provide local evidence; React/Vite blueprint integration and full publication gates remain open.

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
