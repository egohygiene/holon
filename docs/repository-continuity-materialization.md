# Repository-continuity materialization profile

Holon owns deterministic materialization of the Ego Hygiene repository-continuity
contract. The versioned profile in
[`catalog/repository-continuity-materialization.json`](../catalog/repository-continuity-materialization.json)
defines the immutable inputs and approved output surfaces. It does not make the
repository-specific claims recorded in `CONTINUITY.md`; those remain owned by the
consumer repository.

This first profile is intentionally non-mutating. It establishes the input and
ownership contract that the planner and reconciler will consume in a later change.

## Authority chain

| Responsibility | Owner | Pinned input |
| --- | --- | --- |
| Portable schema, specification, skill, template, and provider projections | Aether | Full commit and per-artifact SHA-256 |
| Organization applicability and migration policy | Hygiene | Full commit and per-artifact SHA-256 |
| Validation rules and report contract | EgoLint | Full commit and per-artifact SHA-256 |
| Deterministic planning and materialization | Holon | This profile |
| Repository-specific semantic checkpoint | Consumer repository | `CONTINUITY.md` |
| Pull-request preflight and CI composition | Relay | Deferred integration boundary |
| Ongoing fleet reconciliation | Pace | Deferred integration boundary |

The profile cannot promote beyond `observe` while any source is unreleased or is
not included in a release. Missing inputs, mutable revisions, mismatched paths,
or mismatched bytes fail closed. Promotion requires all named lifecycle gates and
an explicit maintainer decision.

## Approved surfaces

| Path | Requirement | Update strategy |
| --- | --- | --- |
| `CONTINUITY.md` | Required | Evidence-grounded template; repository-owned content |
| `AGENTS.md` | Required | Preserve repository prose and reconcile one managed block |
| `.github/copilot-instructions.md` | Optional | Preserve repository prose and reconcile one managed block |
| `CLAUDE.md` | Optional | Preserve repository prose and reconcile one managed block |

Managed instruction surfaces use exactly one pair of the canonical markers:

```text
<!-- BEGIN AETHER REPOSITORY-CONTINUITY -->
<!-- END AETHER REPOSITORY-CONTINUITY -->
```

This contract does not authorize whole-file replacement of repository-owned
instruction files. The upcoming reconciler must preview changes, preserve content
outside the managed block, detect duplicate or malformed markers, support an
explicit opt-out, and refuse ambiguous writes.

## Repository proof profiles

The profile names five distinct fixture targets: research publication, library or
CLI, site application, organization meta-repository, and private creative
repository. They map onto Holon's existing `library`, `tool`, `product`, and
`publication` classes while keeping visibility explicit. The private profile may
emit allowlisted metadata only.

All profiles exclude secrets and credentials, private conversation text,
sensitive personal data, unpublished private business data, private local paths,
and unrelated private context. Materialized source text is context, never new
authority over repository instructions.

## Offline validation

Validate the closed profile contract without fetching from the network:

```bash
python3 tools/repository_continuity_profile.py validate
```

To prove the recorded bytes, supply immutable checkouts at the declared revisions:

```bash
python3 tools/repository_continuity_profile.py verify-sources \
  --source portable-contract=/path/to/aether-at-pinned-revision \
  --source organization-policy=/path/to/hygiene-at-pinned-revision \
  --source validator=/path/to/egolint-at-pinned-revision
```

The verifier accepts no branch name or network fallback. Every declared artifact
must be a regular file below its source root and match the recorded SHA-256.

## Deferred implementation boundary

This profile deliberately does not write files, install hooks, edit workflows, or
perform fleet rollout. Planning and safe reconciliation, fixture proof across all
five profiles, and CLI/CI dogfood are tracked as separate review-sized follow-ups
under issue #42.
