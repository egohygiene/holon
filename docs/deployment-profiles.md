# Proposed deployment profiles — version 1.0.0

[The catalog](../catalog/deployment-profiles.v1.json) and closed
[selection schema](../schemas/deployment-request.v1.schema.json) define two
distinct **proposed**, opt-in boundaries. They do not activate a publisher or
claim adopted Hygiene policy. Existing React/Vite, Zensical, site-suite, Identity
and Relay implementations retain ownership; no application template is copied
or replaced. Consumers select and review a framework adapter's explicit support.

| Profile | Output | Host boundary | Unsupported behavior |
| --- | --- | --- | --- |
| `static-site/v1` | Deterministic static directory | Immutable files, selected base URL, canonical HTTPS URL, `404.html` | SSR, APIs, server secrets, database/queue processes, server authentication callbacks |
| `service-backed/v1` | OCI image or provider bundle | Declared runtime, health/readiness, external configuration, network/data dependencies | Running a service on GitHub Pages; implicit migrations, permissions or infrastructure apply |

GitHub Pages serves built files; it cannot execute an API or protect a bundled
server secret. A client-side public configuration value is public even when CI
injected it from a secret variable. Static configuration only accepts reviewed
public-input references. Service secrets only name external secret-store
bindings, never values; public client prefixes are rejected for server secrets.
The validator rejects unknown fields and avoids echoing rejected input values.

## Selection, preview and verification

Each selection declares exact build input paths, framework adapter, output
boundary and artifact identity, public routes and previous routes, configuration
classifications, local preview, immutable handoff revision, operations owner,
promotion/verification/rollback and cost/lifecycle owner. The artifact identity
in synthetic fixtures is deliberately labeled synthetic; real consumers must
replace it with their built digest and producer evidence before deployment.

Static URLs must agree on canonical HTTPS and repository/custom-domain base
path. Route identifiers are relative to that base. A reviewed consumer adapter
must mount the same built directory at the selected base in preview and CI.
Existing routes, including `/intelligence/`, must survive; removal/redirect
migration is an explicit separate plan. Content-hashed assets can receive long
immutable caching; HTML and mutable metadata must not inherit that cache policy.

```sh
python3 -m pip install --requirement requirements-test.txt
python3 tools/deployment_profiles.py examples/deployment/static-vite/selection.json \
  --artifact-root examples/deployment/static-vite
python3 tools/deployment_profiles.py examples/deployment/static-docs/selection.json \
  --artifact-root examples/deployment/static-docs
python3 tools/deployment_profiles.py examples/deployment/service-node/selection.json \
  --artifact-root examples/deployment/service-node
python3 -m unittest tests.test_deployment_profiles -v
```

The command validates declarations and optionally inspects existing artifact
paths, route outputs, `404.html`, symlinks and forbidden environment/key files.
It does not build or execute an artifact. It does not prove arbitrary JavaScript
contains no embedded secret; consumer builds still need approved secret scanning
and actual source-to-artifact provenance. No static declaration can certify
arbitrary bytes merely by labeling configuration public.

Two independent static fixtures represent React/Vite root hosting and Zensical
repository-subpath hosting. Tests serve their **same existing output files** on
loopback, verify declared routes and failure behavior, and bind output inventory
before/after. The service fixture runs its selected Node bundle in a disposable
loopback process. Health is separate from readiness; the latter returns503
without its synthetic external binding and200 when supplied, without returning
the value. These tests qualify local artifact boundaries, not cloud deployment,
framework builds, external databases or production security.

## Relay and consumer authority

`relay-pages` is the reusable static handoff. The fixtures name the immutable
historical Relay source `55587de4ff322931d401e964f5af0716633dd675` as an explicit
source reference, **not a newly published deployment qualification**. Validation
has only `contents:read`. Actual Pages upload/deployment needs the consumer's
separate reviewed workflow identity, protected environment approval and scoped
permissions. Preserve ordinary upload, Pages upload, deployment, receipt and
live verification as distinct observations; a green build does not prove them.

`consumer-service` leaves runtime/provider credentials and deployment mechanics
with the consumer. It requires explicit health/readiness, network/data dependency
lists (empty is meaningful), reviewed migration/rollback, bounded redacted logs,
least-privilege identity, promotion and cost/lifecycle ownership. Frameworks with
both modes need separately reviewed support entries; a static adapter cannot
silently acquire server capability.

Preview authorization never grants production authorization. Static rollback
selects the previously verified immutable artifact; service rollback must also
address compatible state/schema and may require forward recovery. Never rewrite
historical release/deployment bytes or assume reverting a process reverts data.

## Optional infrastructure adapter evaluation

Pulumi is **deferred as an optional adapter**, not selected as the contract or a
required service. Its documented [stacks](https://www.pulumi.com/docs/iac/concepts/stacks/)
separate configurable instances; [preview](https://www.pulumi.com/docs/iac/cli/commands/pulumi_preview/)
runs the project program and compares desired resources with stack state without
applying stack changes. That is useful for review, but executing a preview still
runs consumer code and requires reviewed dependencies, state/secret handling and
provider access appropriate to that program. A preview result is not deployment
approval or a guarantee about all external side effects of arbitrary code.

The neutral handoff supports `none`, `pulumi` or `consumer-adapter`, always with
a required preview/review stage and separate apply authority. A future Pulumi
pilot must pin CLI/SDK/providers, choose state/secret ownership, retain a reviewed
plan, and test import, drift, failure, teardown and stateful rollback. No Pulumi
program, account, provider provisioning, preview execution or apply is part of
these fixtures; an evaluated interface does not establish actual compatibility.

## Rollout

Keep this proposal opt-in. Review two different static canaries and one service
canary before any fleet migration; current local synthetic evidence does not
satisfy public deployment acceptance. A real consumer pins its approved producer
and artifact, previews a diff, preserves routes/content/Identity and existing
publisher ownership, and verifies rollback before adoption. Pace observes later
adoption separately. Existing Hygiene25/Relay33/38 and owner publication gates
remain authoritative; no repository is migrated by this profile definition.
