---
schema: aether.architecture-document/v1
id: holon-ontology
title: Holon Ontology
kind: architecture-document
version: 0.1.0
status: provisional
owners:
  - egohygiene
created: 2026-08-19
updated: 2026-08-19
governed_by:
  - architecture-ontology
depends_on:
  - holon-purpose
  - holon-vision
  - holon-principles
  - holon-epistemology
related:
  - holon-pillars
  - holon-manifesto
  - holon-ai-constitution
  - holon-personal-model
supersedes: []
---

# Holon Ontology

## Domain scope

Holon models the concepts needed for instantiate governed repository and organization blueprints deterministically from composable, versioned manifests. The ontology names conceptual entities and relationships; it is not a source-code class model, API schema, or database design.

## Canonical concepts

| Concept | Meaning |
| --- | --- |
| Foundation | A canonical concept in the Holon domain whose exact fields belong to specifications or schemas, not this ontology. |
| Repository class | A canonical concept in the Holon domain whose exact fields belong to specifications or schemas, not this ontology. |
| Capability | A canonical concept in the Holon domain whose exact fields belong to specifications or schemas, not this ontology. |
| Manifest | A canonical concept in the Holon domain whose exact fields belong to specifications or schemas, not this ontology. |
| Catalog | A canonical concept in the Holon domain whose exact fields belong to specifications or schemas, not this ontology. |
| Resolution | A canonical concept in the Holon domain whose exact fields belong to specifications or schemas, not this ontology. |
| Projection | A canonical concept in the Holon domain whose exact fields belong to specifications or schemas, not this ontology. |
| Generation plan | A canonical concept in the Holon domain whose exact fields belong to specifications or schemas, not this ontology. |
| Instance | A canonical concept in the Holon domain whose exact fields belong to specifications or schemas, not this ontology. |
| Upgrade | A canonical concept in the Holon domain whose exact fields belong to specifications or schemas, not this ontology. |

## Core relationships

- A repository or person provides source context to one or more domain artifacts.
- A specification constrains how an artifact is interpreted or produced.
- A plan separates proposed action from execution.
- Evidence supports a claim; a decision authorizes a durable direction.
- Provenance connects derived artifacts to their inputs and processing context.
- A consumer integrates through an explicit interface rather than internal structure.

## Boundaries

- Conceptual identity is distinct from filesystem path, database identifier, or display label.
- Observed state is distinct from desired state.
- Proposed relationships are not accepted facts.
- Neighboring repositories retain ownership of their domain concepts.

## Evidence and uncertainty

- **Observed:** The repository README establishes the intended boundary as an architecture-driven bootstrapper for creating coherent organizations, repositories, and software ecosystems; significant implementation remains incomplete.
- **Decided for this draft:** The repository owns the bounded concern described here and participates through versioned contracts.
- **Proposed:** Target systems and later roadmap phases remain proposals until accepted and implemented.
- **Open question:** Which parts of this draft should become active in the first independently versioned release?
