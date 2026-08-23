---
schema: aether.architecture-document/v1
id: holon-decisions
title: Holon Decisions
kind: architecture-document
version: 0.2.0
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

## Open decisions

- Release and compatibility policy for the first stable version.
- Exact self-hosted, managed, and organization-integrated deployment boundaries.
- Which target systems must exist before the architecture status may become active.

## Evidence and uncertainty

- **Observed:** The repository README establishes the intended boundary as an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; significant implementation remains incomplete.
- **Decided for this draft:** The repository owns the bounded concern described here and participates through versioned contracts.
- **Proposed:** Target systems and later roadmap phases remain proposals until accepted and implemented.
- **Open question:** Which parts of this draft should become active in the first independently versioned release?
