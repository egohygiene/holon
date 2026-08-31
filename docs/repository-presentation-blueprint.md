# Repository-presentation blueprint

Holon's repository-presentation blueprint projects repository-owned facts into one
checksum-bound README region. It implements the proposed Hygiene
repository-presentation 1.0.0-alpha.1 contract with Identity's immutable v1
banner and evidence-badge package. It does not activate the proposed Hygiene
profile, evaluate evidence, fetch CI state, or synchronize repositories.

## Contract pins

| Contract | Immutable revision |
| --- | --- |
| Hygiene repository-presentation 1.0.0-alpha.1 (proposed) | cb2ed63425d29abada2d2bbb43a3b3e59d11aeb8 |
| Identity repository-presentation package 1.0.0 | 3c2fd3141371b355628e81f66f63159f19d63338 |
| Egolint 0.1.0-alpha.1 repository-presentation validator | 4efe92a2609b3384fcf3b5cda343a4f64d108824 |

The blueprint supports minimal, library, CLI, application, publication, private,
archived, and incubating projections. Each maps to Hygiene repository type,
visibility, and lifecycle axes; it does not create new policy semantics.

## Ownership boundary

The consumer source document owns purpose, maturity, commands, links, support,
security, license, exceptions, and opt-out decisions. Identity owns local banner
and badge bytes plus their manifests. Holon owns only deterministic composition,
preview, conflict detection, and rollback. Pace can transport the source and
plan without organization credentials.

The generated region begins with:

    <!-- repository-presentation:begin owner=egohygiene/identity profile=1.0.0-alpha.1 -->

and ends with:

    <!-- repository-presentation:end -->

Everything outside those markers remains byte-for-byte repository-authored.
Do not edit inside the region. Change the source document and regenerate it.

## Preview and initialize

Copy a source object from examples/repository-presentation-fixtures.json and
customize only with facts reviewed by that repository. Then create an exact
plan:

    python3 tools/repository_presentation_blueprint.py preview \
      --source .config/holon/repository-presentation.json \
      --readme README.md \
      --state .holon/repository-presentation.state.json \
      --plan .holon/repository-presentation.plan.json

Preview prints the exact unified diff. Missing required facts remain visible as
TODO(blocker) diagnostics and the plan action is blocked. Holon never invents a
command, status, link, license, support promise, or evidence state.

After review, apply the exact plan:

    python3 tools/repository_presentation_blueprint.py apply \
      --source .config/holon/repository-presentation.json \
      --readme README.md \
      --state .holon/repository-presentation.state.json \
      --plan .holon/repository-presentation.plan.json

Apply rechecks the plan checksum, source checksum, and current README checksum.
Initialization prepends the managed region and leaves the complete prior README
below it.

## Upgrade and conflicts

Run preview again after source, Identity package, or reviewed contract changes.
Holon upgrades only when the existing generated block matches the checksum in
state. Authored edits elsewhere in README are preserved. A missing state,
unbalanced or duplicate marker, manual edit inside the block, changed source
after preview, or changed README after preview fails closed.

To adopt a pre-existing region, review it and initialize trusted state through a
repository-specific migration. The generic command deliberately does not guess
whether unknown generated-looking content is safe.

## Exceptions and opt-out

A slot exception requires a known slot, durable reason, and safe local or HTTPS
evidence destination. It does not alter Hygiene policy or turn non-passing
evidence into passing evidence. The generated region identifies an applied
exception without copying its private reason or destination into README.

An explicit opt-out requires a reason. Preview then returns an opt-out action and
an empty diff. Keep the source in version control so Pace and reviewers can
distinguish a deliberate exception from missing adoption.

## Rollback

State retains the immediately previous README as a one-level rollback snapshot.
Rollback is checksum-bound and refuses to overwrite any README changed since
apply:

    python3 tools/repository_presentation_blueprint.py rollback \
      --readme README.md \
      --state .holon/repository-presentation.state.json

Review and commit state according to the consumer repository's rollout policy.
Do not store credentials or private evidence prose in the presentation source.

## Accessibility and evidence

The managed region uses the Identity light, dark, and high-contrast local banner
variants with a 640-pixel intrinsic narrow baseline, meaningful alt text, and a
visible textual fallback. Each badge carries text as well as color and links to
the supplied evidence destination and full represented commit. Hosted image or
badge services are unnecessary.

Holon validates the same deterministic marker, slot, banner, badge, destination,
state-message, and prohibited-claim boundaries consumed by the pinned Egolint
rule pack. Run the pinned Egolint validator in the consumer repository for the
authoritative conformance report; Holon does not reclassify evidence.

## Fixture proof

Run:

    python3 tools/repository_presentation_blueprint.py validate-fixtures
    python3 -m unittest tests.test_repository_presentation_blueprint -v

The suite renders every profile and the representative Mantle CLI source,
checks deterministic preview, verifies Egolint-compatible structures, proves
authored prose preservation, exercises conflicts and opt-out, and performs a
checksum-bound apply/rollback cycle.
