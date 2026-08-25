---
schema: aether.architecture-document/v1
id: holon-architecture
title: Holon Architecture
kind: architecture-document
version: 0.2.0
status: provisional
owners:
  - egohygiene
created: 2026-08-19
updated: 2026-08-25
governed_by:
  - architecture-architecture
depends_on:
  - holon-foundations
  - holon-system
related:
  - holon-purpose
  - holon-vision
  - holon-principles
  - holon-pillars
supersedes: []
---

# Holon Architecture

## Purpose and scope

Holon uses a layered, contract-driven architecture. This document owns structural boundaries, dependency direction, integration rules, and current-to-target evolution. Logical responsibilities remain canonical in [SYSTEM.md](SYSTEM.md).

## Layer model

1. **Intent and contracts** — identity, policy, specifications, schemas, and accepted decisions.
2. **Domain** — canonical concepts and pure domain behavior.
3. **Application** — planning, orchestration, use cases, and state transitions.
4. **Adapters** — filesystems, providers, frameworks, renderers, and external tools.
5. **Interfaces** — CLI, library, site, reports, generated artifacts, and automation contracts.
6. **Evidence** — tests, diagnostics, provenance, manifests, and health projections.

Dependencies point inward toward stable contracts and domain behavior. External details do not become canonical domain truth.

## Structural view

```mermaid
flowchart TB
  subgraph Materialization
  S1[Foundation catalog]
  S2[Manifest schema]
  S3[Resolver]
  S4[Template adapter]
  S5[Generation planner]
  S6[Renderer]
  S7[State and provenance]
  S1 --> S2
  S2 --> S3
  S3 --> S4
  S4 --> S5
  S5 --> S6
  S6 --> S7
  end
  subgraph Repository Intelligence presentation
  O1[Observatory read model]
  O2[Pure semantic renderers]
  O3[DOM enhancement controller]
  O4[Static HTML exporter]
  O5[Relay or independent host]
  O1 --> O2
  O2 --> O3
  O2 --> O4
  O3 --> O5
  O4 --> O5
  end
```

The diagram is conceptual. [SYSTEM.md](SYSTEM.md) remains authoritative for responsibilities and implementation evidence determines current availability.

## Dependency rules

- Sibling domain capabilities integrate through versioned public contracts, not direct access to internals.
- Generated artifacts never become the canonical source unless an accepted decision explicitly changes ownership.
- Provider and platform adapters depend on application ports; core behavior does not depend on a provider implementation.
- Read, plan, apply, verify, publish, and recover remain separate authority boundaries when consequential.
- Cross-repository references use releases, immutable commits, schemas, packages, or documented APIs rather than mutable default-branch assumptions.
- Repository Intelligence rendering consumes Observatory query views through a pinned versioned contract. Renderers may derive display-only progress from those views, but they do not collect provider data, infer readiness, redact visibility, or become a second query engine.
- Pure semantic rendering precedes optional DOM enhancement so static exports, framework adapters, and interactive hosts share one HTML contract.

## Ecosystem interfaces

- Hygiene ontology
- Empathy templates
- Aether bundles
- Realm profiles
- Relay actions
- Pace reconciliation
- future web frontend
- Observatory Repository Intelligence read model
- Relay Repository Intelligence routes

## Deployment and portability

The architecture favors independently usable local and self-hosted operation. Optional managed services may add availability, collaboration, support, and hosted infrastructure without becoming the canonical holder of portable state.

## Evidence and uncertainty

- **Observed:** Foundation resolution, reversible local materialization, and the static-first Repository Intelligence component package are implemented with contract fixtures and tests.
- **Decided:** Repository Intelligence visuals remain framework-neutral projections over Observatory's versioned public-safe view model; publication stays with Relay or another host.
- **Proposed:** Target systems and later roadmap phases remain proposals until accepted and implemented.
- **Open question:** Which parts of this draft should become active in the first independently versioned release?
