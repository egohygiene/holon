---
schema: aether.architecture-document/v1
id: holon-system
title: Holon System
kind: architecture-document
version: 0.8.0
status: provisional
owners:
  - egohygiene
created: 2026-08-19
updated: 2026-09-09
governed_by:
  - architecture-system
depends_on:
  - holon-foundations
  - holon-ontology
related:
  - holon-purpose
  - holon-vision
  - holon-principles
  - holon-pillars
supersedes: []
---

# Holon System

## Purpose and scope

This document identifies Holon's logical systems and responsibilities. It answers what the major systems do; [ARCHITECTURE.md](ARCHITECTURE.md) owns their structural organization and dependency rules.

## System inventory

| System | State | Responsibility |
| --- | --- | --- |
| Foundation catalog | Implemented | Defines repository classes, capability ownership, dependency edges, conflicts, security floors, and default/allowed capability sets. |
| Manifest schema | Implemented | Validates repository intent, immutable sibling pins, requested capabilities, site selection, preserve boundaries, and parameters. |
| Resolver | Implemented | Produces one deterministic dependency-ordered resolved manifest and rejects mutable pins, weakened security floors, missing transitive pins, cycles, and conflicts. |
| Template and overlay adapter | Implemented | Accepts a base rendered pack plus ordered overlays, performs bounded scalar/canonical-JSON manifest substitution, records every tree digest and file source, copies binary content, and rejects symlinks plus reserved/escaping paths. |
| Generation planner | Implemented | Converts resolved intent and verified inputs into a timestamp-free `holon.materialization-plan/v1` with create/update/delete/noop/preserve/conflict operations and a content-derived plan ID. |
| Renderer | Implemented | Recomputes the reviewed plan before mutation, applies only conflict-free operations, uses atomic file replacement, and records reversible backup evidence. |
| State and provenance | Implemented | Records generated ownership, per-file SHA-256 provenance, resolved input identity, verification state, and fail-closed rollback metadata under `.holon/`. |
| Aether projection adapter | Implemented | Consumes a caller-supplied pinned Aether release distribution, verifies release/projection provenance, and materializes approved native provider projections without fetching mutable branches. |
| Repository-continuity adapter | Implemented | Produces exact local plans for a repository-owned checkpoint and one canonical instruction block per selected provider, preserves authored prose, requires digest-bound migration for an existing checkpoint, and records reversible state without acquiring external authority. |
| Repository-continuity fixture harness | Implemented | Proves deterministic and reversible behavior across five repository profiles and a reviewed Antidote legacy migration, then validates each target with a contract-fingerprinted EgoLint binary and caller-supplied immutable sources; CI builds that binary from the exact pinned validator revision. |
| React/Vite blueprint | Implemented | Provides a versioned, inventory-locked generic site pack with exact React/Vite/TypeScript/pnpm dependencies, strict checks, Identity token injection, accessible route/error states, deterministic static output, and a clean-room executable fixture. |
| LaunchKit blueprint | Implemented | Derives a typed, manifest-driven developer-product landing profile from React/Vite through one inventory-locked overlay, pinned upstream intake, Identity seams, pre-rendered HTML, progressive hydration, optional sections, byte budgets, and two different clean-room pilots. |
| Zensical blueprint | Implemented | Provides an independently selectable, inventory-locked documentation pack with a pinned alpha upstream release, universal hash-locked Python graph, reviewed content contract, isolated documentation/architecture/legal builds, and local preview. |
| Public site-suite composer | Implemented | Combines either landing profile with Zensical surfaces into one deterministic four-route `dist` artifact, verifies static references and accessibility structure, and preserves Relay, Identity, policy, Pace, and Observatory ownership seams. |
| Repository Intelligence model adapter | Implemented | Validates Observatory repository and compare view-model boundaries, preserves explicit state semantics, groups semantic chapters, and calculates deterministic virtual windows without collecting or querying provider data. |
| Repository Intelligence renderers | Implemented | Emit semantic static HTML for roadmap quests, decision lineage, delivery epochs, evidence drawers, summary matrices, comparison, and shared cognitive states. |
| Repository Intelligence controller | Implemented | Adds Identity token projection, search, filters, time controls, keyboard navigation, active-section orientation, and stable long-history virtualization to the same static markup. |
| Repository Intelligence static exporter | Implemented | Produces a complete self-contained HTML document for no-JavaScript publication at a host-owned route. |
| Organization compiler API | Target | Will compose multiple repository/site manifests and bounded adapters into organization-wide plans after the repository materialization contract stabilizes. |

## External systems

- Hygiene ontology and repository-context contract
- Empathy templates
- Aether release bundles and provider projections
- Realm profiles
- Relay actions
- Pace reconciliation
- versioned Identity, Egolint, Relay, LaunchKit, and Zensical site integrations
- Observatory Repository Intelligence snapshots

External systems are integrations, not hidden implementation units. Each requires version, authentication, availability, data, error, and replacement boundaries appropriate to its risk.

## System interactions

The current repository pipeline is:

```text
foundation catalog + manifest
        ↓
resolver
        ↓
resolved manifest
        ↓
rendered packs + pinned provider artifacts
        ↓
generation planner
        ↓ reviewed plan
renderer
        ↓
managed files + state + rollback evidence
        ↓
verify / rollback

explicit repository facts + pinned continuity contracts + verified Aether bytes
        ↓
repository-continuity plan
        ↓ reviewed exact bytes
block-aware apply + state + rollback evidence
        ↓
verify / rollback

selected React/Vite or LaunchKit landing + Zensical surfaces
        ↓
site-suite composer
        ↓
four-route dist artifact for Relay

Observatory public-safe Repository Intelligence snapshot
        ↓
pure semantic renderer
        ├── complete static HTML export
        └── DOM enhancement controller
                  ↓
          Relay or independent host
```

The materialization engine does not claim that every selected capability already has a native adapter. Capability ownership remains explicit: Aether is supported through a pinned release adapter, repository continuity has a bounded specialized adapter, and other capabilities use a rendered pack or a future specialized adapter owned by the corresponding Holon/sibling issue.

## Failure model

Systems fail closed at destructive, publication, privacy, and security boundaries. In particular:

- an unowned pre-existing target file is a conflict in the generic whole-file engine; the continuity adapter's ADR-010 exception may append or adopt exactly one canonical instruction block while preserving surrounding prose;
- a managed file whose current digest differs from recorded state is a conflict;
- a reviewed plan is invalidated when the target or its input artifacts change before render;
- rollback refuses to erase post-render user edits;
- no v1 force-overwrite path exists;
- provider artifacts are accepted only after immutable pin and digest/provenance checks.

Partial results identify coverage and remain distinguishable from complete success.

## Evidence and uncertainty

- **Observed:** HOL-01 implemented the versioned foundation catalog, manifest schema, deterministic resolver, and negative/positive contract tests.
- **Observed:** HOL-02 implements local plan/render/verify/rollback materialization, generated ownership state, reversible backups, generic rendered-pack input, and pinned Aether projection consumption.
- **Observed:** HOL-Q08 implements local repository-continuity plan/preview/apply/verify/rollback, exact source and preimage binding, block-scoped instruction reconciliation, repository-owned checkpoint preservation, and explicit no-write dispositions.
- **Observed:** The repository-continuity fixture harness covers new, existing, provisional, opt-out, unsupported, conflict, upgrade, parallel-reconciliation, no-op, and rollback paths across all five profiles; it also proves lossless useful-state mapping from the pinned Antidote prototype and requires a semantic pass from a contract-fingerprinted EgoLint validator. Canonical CI builds that validator from the exact pinned revision.
- **Observed:** HOL-Q03 provides the independently useful `site-react-vite` capability, a 25-file governed rendered pack, a frozen package graph, and a clean consumer that installs, checks, builds reproducibly, and serves through Vite preview without manual repair.
- **Observed:** The `landing-launchkit` capability composes that base with a 21-file overlay, canonical typed content, pre-rendered output, pinned Evil Martians provenance, and distinct OptiFlow/Mantle executable fixtures.
- **Observed:** The `docs-zensical` capability pins Zensical `0.0.57` and a hash-locked Python graph, then produces isolated documentation, architecture, and legal surfaces from a closed content contract.
- **Observed:** The public site-suite composer proves generic and LaunchKit landing variants from empty directories through no-op replanning, frozen installs, byte-reproducible builds, live four-route preview, and reviewed artifact-tree digests.
- **Observed:** HOL-Q06 implements a zero-runtime-dependency Repository Intelligence component package, an independent five-state fixture lab, 640-event virtualization evidence, a static exporter, and Identity-compatible theming.
- **Decided:** Materialization remains a local deterministic application boundary; provider fetching, GitHub repository mutation, and fleet reconciliation stay outside the engine.
- **Decided:** Repository Intelligence presentation consumes the pinned Observatory view boundary and does not duplicate collection, normalization, query, redaction, or publication ownership.
- **Proposed:** Other specialized capability packs, downstream Identity/Antidote adoption, and the organization compiler API remain roadmap work until their own contracts and fixtures land.
