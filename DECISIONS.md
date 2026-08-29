---
schema: aether.architecture-document/v1
id: holon-decisions
title: Holon Decisions
kind: architecture-document
version: 0.6.0
status: provisional
owners:
  - egohygiene
created: 2026-08-19
updated: 2026-08-29
governed_by:
  - architecture-decisions
depends_on:
  - holon-principles
  - holon-epistemology
  - holon-foundations
  - holon-system
  - holon-architecture
related:
  - holon-purpose
  - holon-vision
  - holon-pillars
  - holon-manifesto
supersedes: []
---

# Holon Decisions

## Purpose

This document preserves significant accepted architectural choices and their rationale. Issues coordinate work, proposals explore alternatives, and this file records decisions that constrain future implementation.

## Governance

Do not rewrite historical context to fit current understanding. Amend a record for corrections that do not change meaning; supersede it with a new record when the decision changes materially.

## Index

- ADR-001: Model repository classes as manifests
- ADR-002: Stop the initial implementation at deterministic resolution
- ADR-003: Separate planning from external application
- ADR-004: Keep React/Vite utility dependencies platform-first and capability-gated
- ADR-005: Advance from resolution to explicit reversible local materialization
- ADR-006: Render Repository Intelligence through a static-first framework-neutral boundary
- ADR-007: Ship React/Vite as a generic versioned rendered pack
- ADR-008: Derive LaunchKit through an ordered manifest-driven overlay

## ADR-001: Model repository classes as manifests

- **Status:** Accepted as the current architectural direction
- **Date:** 2026-08-19
- **Context:** Repository evidence and ecosystem ownership require an explicit durable boundary.
- **Decision:** Model repository classes as manifests.
- **Consequences:** The choice improves ownership and predictability while requiring maintained contracts, validation, and migration discipline.
- **Reconsider when:** New evidence shows that the boundary prevents standalone usefulness, safety, portability, or maintainability.

## ADR-002: Stop the initial implementation at deterministic resolution

- **Status:** Accepted as the current architectural direction
- **Date:** 2026-08-19
- **Context:** Repository evidence and ecosystem ownership require an explicit durable boundary.
- **Decision:** Stop the initial implementation at deterministic resolution.
- **Consequences:** The choice improves ownership and predictability while requiring maintained contracts, validation, and migration discipline.
- **Reconsider when:** New evidence shows that the boundary prevents standalone usefulness, safety, portability, or maintainability.

## ADR-003: Separate planning from external application

- **Status:** Accepted as the current architectural direction
- **Date:** 2026-08-19
- **Context:** Repository evidence and ecosystem ownership require an explicit durable boundary.
- **Decision:** Separate planning from external application.
- **Consequences:** The choice improves ownership and predictability while requiring maintained contracts, validation, and migration discipline.
- **Reconsider when:** New evidence shows that the boundary prevents standalone usefulness, safety, portability, or maintainability.

## ADR-004: Keep React/Vite utility dependencies platform-first and capability-gated

- **Status:** Accepted as the current architectural direction
- **Date:** 2026-08-23
- **Context:** The React/Vite foundation needs a small, explainable dependency surface and must not inherit compatibility wrappers or Node-only utilities merely because upstream templates use them.
- **Decision:** Use [`catalog/react-vite-dependencies.json`](catalog/react-vite-dependencies.json) as the versioned utility policy. Keep Chalk optional for an explicit Node CLI rich-output capability, reject `source-map-support` in favor of modern Node source-map support, and reject Visibility.js in favor of the standard Page Visibility API. None of the three is a default React/Vite dependency.
- **Consequences:** Browser and Node dependencies remain separated; future blueprints can resolve reviewed decisions deterministically; optional packages require a real capability and fixture before installation; native platform improvements can remove dependencies instead of being hidden behind permanent wrappers.
- **Reconsider when:** The supported Node/browser floor changes, a concrete source-map compatibility gap is proven, a generated CLI needs styled terminal output, or material maintenance/security evidence changes a candidate's fit.

## ADR-005: Advance from resolution to explicit reversible local materialization

- **Status:** Accepted as the current architectural direction
- **Date:** 2026-08-23
- **Supersedes:** ADR-002 only with respect to the earlier implementation stopping point; deterministic resolution remains the required first phase.
- **Context:** HOL-01 established deterministic manifest resolution but intentionally stopped before filesystem generation. With the Hygiene repository-context contract and Aether provider-projection contract now available as sibling boundaries, Holon can advance to materialization without copying their internals or making mutable default branches runtime dependencies.
- **Decision:** Materialization is a four-boundary local workflow: `plan`, `render`, `verify`, and `rollback`. Planning is dry-run and timestamp-free. Rendering must recompute the plan immediately before mutation and apply only the exact reviewed plan. Holon owns generated-file state and SHA-256 evidence under `.holon/`, but that ownership never authorizes overwriting a file that is unowned or has changed since the prior render. Rollback is fail-closed and must not erase post-render user edits. Pinned provider artifacts are supplied to Holon as local inputs and verified before projection; the core engine performs no provider fetches. There is no v1 force-overwrite switch.
- **Consequences:** Repository generation becomes useful while remaining reviewable and reversible; idempotent re-renders produce no-op plans; user edits create explicit conflicts; removed generated files can be deleted safely only while unchanged; future React/Vite, LaunchKit, Hygiene, Relay, Realm, and other packs can plug into a stable rendered-source/application boundary; remote repository mutation and fleet reconciliation remain separate concerns.
- **Reconsider when:** A proven consumer requires controlled adoption of pre-existing files, multi-repository atomicity, content-addressed external storage for large plans/backups, or another recovery model that preserves the same no-clobber safety guarantees.

## ADR-006: Render Repository Intelligence through a static-first framework-neutral boundary

- **Status:** Accepted as the current architectural direction
- **Date:** 2026-08-25
- **Context:** Relay needs scrollable roadmap, ADR, Git journey, and evidence pages that share a coherent visual language. Observatory now owns a versioned public-safe Repository Intelligence read model. Coupling the visual primitives to Relay, a specific framework, or provider collection would force other repositories to copy the experience and would blur ownership between normalization, presentation, and publication.
- **Decision:** Holon owns a zero-runtime-dependency Repository Intelligence presentation package. Pure functions validate and render Observatory's repository and compare query views into semantic static HTML; an optional DOM controller adds search, filters, time controls, keyboard navigation, Identity token projection, active-section orientation, and fixed-row virtualization for long journey chapters. The same renderer serves Relay, framework wrappers, a custom-element adapter, an independent fixture lab, and a complete no-JavaScript exporter. The Observatory source contract is pinned to immutable commit and fixture hashes. Holon derives display-only progress from explicit states and exit criteria, but never collects provider data, infers roadmap readiness, redacts visibility, creates semantic epochs, or owns route publication.
- **Consequences:** Roadmap, decision, journey, evidence, comparison, and cognitive-state components share navigation and styling; consumers can adopt them without forking internals or accepting a framework; long histories remain bounded in interactive DOM size; static exports remain complete and inspectable; Identity can change expression without changing meaning. Holon must maintain HTML/CSS compatibility, safe escaping, accessibility behavior, fixture coverage, and explicit review when the Observatory contract changes.
- **Reconsider when:** A platform limitation makes semantic static HTML insufficient, a proven consumer needs a different virtualization geometry, the Observatory contract reaches a breaking version, or a framework adapter can add value without becoming the canonical implementation.

## ADR-007: Ship React/Vite as a generic versioned rendered pack

- **Status:** Accepted as the current architectural direction
- **Date:** 2026-08-29
- **Context:** Ego Hygiene sites need one clean, current React/Vite application foundation, but coupling React to the materialization engine or making LaunchKit universal would blur framework, product-presentation, and ownership boundaries.
- **Decision:** Holon exposes `site-react-vite` as an opt-in capability backed by `holon.react-vite-blueprint/v1`. The exact Node, pnpm, React, Vite, TypeScript, Vitest, and quality-adapter versions, required scalar parameters, template-file hashes, Identity token seam, static-host behavior, and canonical `pnpm check` command are governed in the profile. The blueprint remains a neutral rendered pack consumed by the existing plan/render/verify/rollback engine. LaunchKit, Storybook, and publishable-package behavior are separate opt-in profiles. Egolint policy, Identity truth, and Relay deployment remain externally owned contracts.
- **Consequences:** A clean directory can become a tested application without manual repair; consumers customize through manifests and governed source instead of template forks; deterministic builds and static preview are executable acceptance evidence; framework upgrades require profile/inventory/lockfile review; the baseline retains a real but intentionally small toolchain.
- **Reconsider when:** A proven non-React consumer shows the capability name is too broad, the static-host fallback cannot preserve required routes, the exact toolchain reaches end of support, or multiple derived profiles require a more general inheritance contract.

## ADR-008: Derive LaunchKit through an ordered manifest-driven overlay

- **Status:** Accepted as the current architectural direction
- **Date:** 2026-08-29
- **Context:** Evil Martians LaunchKit provides a strong developer-tool landing-page reference, while Holon's generic React/Vite foundation already owns the application toolchain and safety gates. Copying either tree into each product or turning LaunchKit into the universal site would create drift and blur ownership. Static content also should not depend on client JavaScript merely because React is the implementation language.
- **Decision:** Holon exposes `landing-launchkit` as a distinct profile that transitively requires `site-react-vite`. Materialization accepts a base rendered source plus ordered, digest-recorded overlays; the LaunchKit overlay may replace reviewed base paths without mutating or duplicating the canonical base pack. Product sections come from one schema-versioned manifest object serialized as canonical JSON into typed React source. The build pre-renders the complete page, progressively hydrates it, uses native disclosure/wrapping where possible, and enforces output budgets. The exact LaunchKit reference commit and MIT notice remain generated provenance. Identity, Egolint, Relay, Zensical, policy, Agent-Ready Web, and Pace retain their separate ownership contracts.
- **Consequences:** Consumers change content and selected sections without maintaining template internals; generic React/Vite upgrades remain independently reviewable; plan identity covers overlay order and bytes; two different products exercise the same components; static HTML remains useful without JavaScript. Overlay replacements and upstream intake now require explicit inventory, provenance, visual-contract, deterministic-build, and reconciliation review.
- **Reconsider when:** More than ordered file replacement is needed for safe composition, a non-React static renderer offers materially lower cost without losing the shared foundation, content requirements exceed the bounded v1 schema, or upstream LaunchKit changes invalidate the adapted information architecture.

## Open decisions

- Release and compatibility policy for the first stable version.
- Exact self-hosted, managed, and organization-integrated deployment boundaries.
- Whether a future reviewed adoption workflow should permit Holon to take ownership of pre-existing matching files.
- Which target systems must exist before the architecture status may become active.
- Packaging and compatibility policy for the first stable Repository Intelligence component release.

## Evidence and uncertainty

- **Observed:** The foundation catalog and resolver are implemented and validated with repository-class fixtures.
- **Observed:** The materialization engine now has deterministic planning, state/provenance tracking, pinned Aether projection consumption, generated ownership checks, and rollback fixtures.
- **Observed:** The generic React/Vite blueprint is versioned, inventory-locked, dependency-pinned, independently materializable, and executable through one clean-room fixture.
- **Observed:** The LaunchKit blueprint pins upstream commit/license evidence, composes through a 21-file overlay without new dependencies, and passes full OptiFlow and Mantle clean-room builds with different selected sections.
- **Observed:** The Repository Intelligence package renders Observatory-compatible small, large, stale, blocked, and partial fixtures; interactive histories virtualize while static exports remain complete.
- **Decided:** Network fetching, GitHub repository mutation, and fleet rollout remain outside local materialization.
- **Proposed:** Zensical, other specialized capability packs, downstream adoption, and organization-wide orchestration remain proposals until accepted and implemented.
