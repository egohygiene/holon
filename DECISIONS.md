---
schema: aether.architecture-document/v1
id: holon-decisions
title: Holon Decisions
kind: architecture-document
version: 0.3.0
status: provisional
owners:
  - egohygiene
created: 2026-08-19
updated: 2026-08-23
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

## Open decisions

- Release and compatibility policy for the first stable version.
- Exact self-hosted, managed, and organization-integrated deployment boundaries.
- Whether a future reviewed adoption workflow should permit Holon to take ownership of pre-existing matching files.
- Which target systems must exist before the architecture status may become active.

## Evidence and uncertainty

- **Observed:** The foundation catalog and resolver are implemented and validated with repository-class fixtures.
- **Observed:** The materialization engine now has deterministic planning, state/provenance tracking, pinned Aether projection consumption, generated ownership checks, and rollback fixtures.
- **Decided:** Network fetching, GitHub repository mutation, and fleet rollout remain outside local materialization.
- **Proposed:** Specialized capability packs and organization-wide orchestration remain proposals until accepted and implemented.
