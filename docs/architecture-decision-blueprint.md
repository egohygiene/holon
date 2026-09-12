# Architecture-decision blueprint

Holon's `architecture-decisions` capability gives every applicable repository
the same local ADR foundation while keeping organization policy canonical in
`egohygiene/hygiene`. The blueprint pins policy v1.1.0 at commit
`f598ed659a43dd759d4ede41c27f9e5daf991aa7`; it does not copy or reinterpret
that policy.

## Contract and ownership

| Surface | Authority | Behavior |
| --- | --- | --- |
| `docs/decisions/policy-reference.json` | Holon-generated | Records the exact Hygiene contract, version, source revision, local paths, extensions, and exceptions. |
| `docs/decisions/ADR-TEMPLATE.md` | Holon-generated | Supplies the standard front matter and seven-section record anatomy with the consumer repository identity. |
| `docs/decisions/README.md` | Holon-generated | Projects repository-owned ADR metadata in stable numeric order. |
| `docs/decisions/ADR-NNN-short-slug.md` | Repository-owned | Preserves decision rationale, human disposition, lineage, and evidence. Holon reads these records for the index but never materializes or edits them. |
| Organization policy and schemas | Hygiene-owned | Remain canonical at the pinned revision. Local settings cannot override their fields, lifecycle, ownership, or approval rules. |

The review pack contains only the three generated files. The ordinary Holon
materialization state records their exact bytes and ownership. ADR documents
themselves never enter that state.

## Initialize a repository

Add the immutable policy input to the foundation manifest:

```json
{
  "pins": {
    "adr_policy": "egohygiene/hygiene@f598ed659a43dd759d4ede41c27f9e5daf991aa7"
  }
}
```

All four v1 repository classes require `architecture-decisions`, so the
resolver fails closed if this pin is missing or mutable. Render the ADR
capability to a disposable directory outside the target:

```bash
adr_pack="$(mktemp -d)"
python3 tools/architecture_decision_blueprint.py render-pack \
  --manifest "/path/to/foundation.manifest.json" \
  --repository-root "/path/to/repository" \
  --output "${adr_pack}"
```

Compose that reviewed pack with the repository's other selected blueprint
packs. Use it as the base `--render-source` when it is the only pack, or as an
ordered `--render-overlay` when another blueprint supplies the base:

```bash
python3 tools/holon_materialize.py plan \
  --manifest "/path/to/foundation.manifest.json" \
  --target "/path/to/repository" \
  --aether-source "/path/to/aether-at-the-pinned-revision" \
  --render-source "/path/to/base-rendered-pack" \
  --render-overlay "${adr_pack}" \
  --output "/tmp/repository.plan.json"
```

Inspect every operation before running `render` with the same ordered inputs. A
new repository creates the policy reference, template, and empty index. The
render-pack command itself is read-only with respect to the target and does not
fetch policy or provider content.

## Add and re-index a decision

Copy `ADR-TEMPLATE.md` to the next unused three-digit ID, complete the record,
and leave it `proposed` until durable human approval exists. Re-run
`render-pack`, review the new index bytes, then plan and render with the same
inputs. Index order uses the numeric ID, not filename or filesystem order.
Missing IDs, legacy four-or-more-digit IDs, and established uppercase prefixes
are preserved; IDs are never renumbered or reused.

The indexer reads only `id`, `title`, `status`, and `date` from each record. A
malformed filename, mismatched ID, duplicate numeric identity, invalid status,
or invalid date stops pack generation instead of emitting a misleading index.

## Adopt an existing ADR corpus

Existing `ADR-*.md` files and established-prefix records remain outside the
desired materialization set and are byte-preserved. They are indexed when their
existing filename and four index fields are valid.

If any generated destination already exists without Holon ownership—even when
it looks similar—the generic planner reports a conflict and render performs no
writes. Reconcile that path in a dedicated migration review: compare the
generated pack with the existing file, move unique authored guidance to a
repository-owned document or ADR, and deliberately establish the generated
surface. There is no force-overwrite or silent ownership-adoption flag.

An existing `DECISIONS.md` may remain as a compatibility entrypoint that links
to `docs/decisions/README.md`. Historical records and IDs stay unchanged.
Backfilling rationale from Git history is separate repository-owned work, not
part of scaffold initialization.

## Register local extensions or exceptions

The optional manifest parameters project directly into the policy reference:

```json
{
  "parameters": {
    "adr_extensions": [
      {
        "id": "egohygiene.example.decision-impact/v1",
        "kind": "metadata",
        "schema": "schemas/example-decision-impact.v1.schema.json",
        "required": false
      }
    ],
    "adr_exceptions": []
  }
}
```

Extensions are limited to a versioned Ego Hygiene ID, `metadata` or
`validation` kind, a safe repository-local `schemas/*.json` path, and a
required flag. Exceptions use the exact Hygiene reference shape; approved
exceptions require HTTP(S) approval evidence. Unknown keys fail closed, so
neither mechanism can redirect the policy source or redefine global fields.

## Upgrade or replace the policy

A future upgrade is a reviewed Holon blueprint revision plus a consumer
manifest-pin change. Before changing the source revision or semantic version,
validate every existing ADR against the target Hygiene contracts and review
any migration notes. The current v1 tool accepts only the approved v1.1.0
revision, preventing a consumer from silently selecting different policy
bytes.

Rollback uses the generic materialization engine. It can restore prior
generated surfaces only while their recorded bytes remain unchanged; it never
removes or rewrites repository-owned ADRs.

## Validate

```bash
python3 tools/architecture_decision_blueprint.py validate
python3 -m unittest tests.test_architecture_decision_blueprint --verbose
```

The fixture suite proves empty initialization, deterministic numeric indexing,
legacy-width preservation, extension bounds, missing-pin rejection,
byte-preservation of existing ADRs, and fail-closed handling of an unmanaged
generated path.
