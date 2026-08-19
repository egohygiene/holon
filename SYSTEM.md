---
schema: aether.architecture-document/v1
id: holon-system
title: Holon System
kind: architecture-document
version: 0.1.0
status: provisional
owners:
  - egohygiene
created: 2026-08-19
updated: 2026-08-19
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
| Foundation catalog | Target | Owns its bounded portion of an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; exposes explicit inputs, outputs, failure states, and evidence. |
| Manifest schema | Target | Owns its bounded portion of an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; exposes explicit inputs, outputs, failure states, and evidence. |
| Resolver | Target | Owns its bounded portion of an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; exposes explicit inputs, outputs, failure states, and evidence. |
| Template adapter | Target | Owns its bounded portion of an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; exposes explicit inputs, outputs, failure states, and evidence. |
| Generation planner | Target | Owns its bounded portion of an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; exposes explicit inputs, outputs, failure states, and evidence. |
| Renderer | Target | Owns its bounded portion of an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; exposes explicit inputs, outputs, failure states, and evidence. |
| State and provenance | Target | Owns its bounded portion of an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; exposes explicit inputs, outputs, failure states, and evidence. |
| Organization compiler API | Target | Owns its bounded portion of an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; exposes explicit inputs, outputs, failure states, and evidence. |

## External systems

- Hygiene ontology
- Empathy templates
- Aether bundles
- Realm profiles
- Relay actions
- Pace reconciliation
- future web frontend

External systems are integrations, not hidden implementation units. Each requires version, authentication, availability, data, error, and replacement boundaries appropriate to its risk.

## System interactions

Inputs enter through an adapter or validated contract, move through domain systems, produce artifacts and diagnostics, and leave through a stable interface. Evidence flows back to validation, review, and future decisions.

## Failure model

Systems fail closed at destructive, publication, privacy, and security boundaries. Partial results identify coverage and remain distinguishable from complete success.

## Evidence and uncertainty

- **Observed:** The repository README establishes the intended boundary as an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; significant implementation remains incomplete.
- **Decided for this draft:** The repository owns the bounded concern described here and participates through versioned contracts.
- **Proposed:** Target systems and later roadmap phases remain proposals until accepted and implemented.
- **Open question:** Which parts of this draft should become active in the first independently versioned release?
