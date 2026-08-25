---
schema: aether.architecture-document/v1
id: holon-design-system
title: Holon Design System
kind: architecture-document
version: 0.2.0
status: provisional
owners:
  - egohygiene
created: 2026-08-19
updated: 2026-08-25
governed_by:
  - architecture-design-system
depends_on:
  - holon-personal-model
  - holon-design
related:
  - holon-purpose
  - holon-vision
  - holon-principles
  - holon-pillars
supersedes: []
---

# Holon Design System

## Purpose and scope

This document defines reusable semantic language for Holon's documentation, terminal output, diagrams, reports, sites, and future interactive surfaces. It does not freeze a framework, component library, or final visual identity.

## Semantic roles

| Role | Meaning |
| --- | --- |
| Canvas | Primary quiet background or base surface |
| Surface | Grouped content or bounded interaction area |
| Primary | Main action or navigational emphasis |
| Information | Neutral context or observation |
| Success | Completed and verified state |
| Caution | Review required; safe to pause |
| Danger | Destructive, security, privacy, or irreversible risk |
| Unknown | Missing, unavailable, partial, or unverified state |

## Status vocabulary

Use the states observed, planned, running, partial, verified, failed, blocked, and unknown consistently. Repository Intelligence additionally preserves decision lifecycle states—proposed, accepted, rejected, deprecated, and superseded—and evidence freshness states—current, stale, unknown, and not applicable. Never present partial, stale, or unknown as success.

## Content and interaction

- Use verbs that describe the actual operation.
- Put scope and consequence before confirmation.
- Keep destructive actions visually and textually distinct.
- Pair errors with recovery and evidence locations.
- Preserve stable identifiers in machine-readable output.
- Respect reduced-motion and no-color contexts.

## Components and projections

Canonical patterns include command help, progress state, evidence table, decision card, plan preview, validation summary, architecture node, recovery prompt, quest line, sticky minimap, decision chain, delivery epoch, evidence drawer, and cognitive state panel. Concrete tokens and components are downstream projections maintained by the owning surface.

The Repository Intelligence package resolves Identity semantic token properties
before using a neutral reference fallback. Canvas, surface, text, primary,
information, success, caution, danger, unknown, border, type, radius, and shadow
roles may vary by repository identity. State meaning remains present in labels,
structure, and text when color or motion is unavailable.

## Visual direction

The expression should remain architectural, visual, empowering, and explicit before consequential creation while allowing product-specific identity to vary inside Ego Hygiene's broader family.

## Evidence and uncertainty

- **Observed:** The Repository Intelligence component package implements the shared patterns and semantic tokens with responsive, reduced-motion, increased-contrast, forced-colors, and print projections.
- **Decided:** Visual identity may vary through semantic tokens while state vocabulary and accessibility behavior remain stable.
- **Proposed:** Target systems and later roadmap phases remain proposals until accepted and implemented.
- **Open question:** Which parts of this draft should become active in the first independently versioned release?
