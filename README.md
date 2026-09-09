# Holon

🌀 An architecture-driven bootstrapper for creating coherent organizations,
repositories, and software ecosystems.

Holon defines versioned repository-class manifests and a deterministic,
reversible materialization engine for the Ego Hygiene organization. The current
foundation models four repository classes—library, tool, product, and
publication—without treating copied template folders as canonical source.

## Contract preview

- [`catalog/foundation.json`](catalog/foundation.json) defines capabilities,
  ownership, dependencies, conflicts, and class policy.
- [`schemas/`](schemas/) provides machine-readable foundation, plan, state, and
  rollback contracts.
- [`examples/`](examples/) contains a valid manifest for every repository class.
- [`tools/holon_contract.py`](tools/holon_contract.py) validates and resolves the
  foundation contract without third-party dependencies.
- [`tools/holon_materialize.py`](tools/holon_materialize.py) exposes explicit
  `plan`, `render`, `verify`, and `rollback` boundaries.
- [`catalog/repository-continuity-materialization.json`](catalog/repository-continuity-materialization.json)
  pins the provisional Aether, Hygiene, and EgoLint continuity inputs, approved
  repository surfaces, rollout gates, and ownership seams. See
  [`docs/repository-continuity-materialization.md`](docs/repository-continuity-materialization.md).
- [`tools/repository_continuity_profile.py`](tools/repository_continuity_profile.py)
  validates that closed profile and verifies pinned source bytes without network
  access or repository mutation.
- [`tools/materialization/continuity.py`](tools/materialization/continuity.py)
  provides deterministic continuity validation, exact preview, block-scoped
  reconciliation, verification, and checksum-bound rollback. Its versioned
  request, plan, state, and rollback contracts live in [`schemas/`](schemas/).
- [`tools/check_repository_continuity_fixtures.py`](tools/check_repository_continuity_fixtures.py)
  proves new, existing, provisional, conflict, upgrade, no-op, EgoLint, and
  rollback behavior across five repository profiles plus the reviewed Antidote
  prototype migration, using only caller-supplied immutable local sources.
- [`blueprints/react-vite/`](blueprints/react-vite/) contains the versioned,
  inventory-locked generic React/Vite rendered pack.
- [`tools/react_vite_blueprint.py`](tools/react_vite_blueprint.py) validates the
  blueprint profile, exact toolchain, capability boundary, template inventory,
  dependency policy, Egolint consumer contract, and clean example parameters.
- [`blueprints/launchkit/`](blueprints/launchkit/) contains the versioned
  LaunchKit overlay, pinned Evil Martians intake, and typed landing components.
- [`tools/launchkit_blueprint.py`](tools/launchkit_blueprint.py) validates
  composition, upstream provenance, content contracts, inventory, and the two
  materially different pilot manifests.
- [`blueprints/repository-presentation/`](blueprints/repository-presentation/) contains the
  pinned, non-destructive README presentation contract and all eight repository profiles.
- [`tools/repository_presentation_blueprint.py`](tools/repository_presentation_blueprint.py)
  provides exact preview, checksum-bound apply, conflict detection, fixture validation,
  opt-out, and one-level rollback. See
  [`docs/repository-presentation-blueprint.md`](docs/repository-presentation-blueprint.md).
- [`blueprints/zensical/`](blueprints/zensical/) contains the versioned,
  hash-locked documentation, architecture, and legal rendered pack.
- [`blueprints/site-suite/`](blueprints/site-suite/) composes either landing
  profile with Zensical into one deterministic, Relay-ready `dist` artifact.
- [`tools/site_suite_blueprint.py`](tools/site_suite_blueprint.py) validates
  profile digests, content, provenance, ownership seams, and both variants.
- [`docs/foundation-contract.md`](docs/foundation-contract.md) documents
  repository-class policy and immutable pins.
- [`docs/materialization-engine.md`](docs/materialization-engine.md) documents
  generated ownership, conflict handling, Aether projection consumption, and
  rollback safety.
- [`docs/react-vite-blueprint.md`](docs/react-vite-blueprint.md) documents the
  generic site foundation and its Identity, Egolint, Relay, and LaunchKit
  boundaries.
- [`docs/launchkit-blueprint.md`](docs/launchkit-blueprint.md) documents the
  derived profile, declarative section model, static rendering, ownership
  seams, pilots, and upstream-reconciliation workflow.
- [`docs/site-suite-blueprint.md`](docs/site-suite-blueprint.md) documents the
  four-route composition, Zensical intake, consumer schema, pilots, and
  ecosystem ownership boundaries.
- [`packages/repository-intelligence/`](packages/repository-intelligence/)
  provides static-first roadmap, decision, journey, and evidence renderers for
  Observatory's versioned Repository Intelligence read model.

## Explore Repository Intelligence components

The component lab proves small, large, stale, blocked, and partially adopted
repositories without depending on Relay:

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000/examples/repository-intelligence/`. The large story
contains 640 events grouped into eight epochs and exercises the same virtual
window used by consumers.

Render a complete no-JavaScript page from an Observatory repository snapshot:

```bash
node packages/repository-intelligence/bin/render-static.mjs \
  --input "repository-intelligence.json" \
  --output "dist/roadmap/index.html" \
  --home-url "/intelligence/"
```

The renderers accept Identity-compatible semantic tokens, keep collection and
query behavior outside the package, and expose a direct DOM mount API plus a
custom-element adapter. See
[`docs/repository-intelligence-components.md`](docs/repository-intelligence-components.md)
for the integration boundary.

## Validate the foundation

```bash
python3 tools/holon_contract.py validate-catalog
python3 tools/repository_continuity_profile.py validate
python3 tools/react_vite_blueprint.py
python3 tools/launchkit_blueprint.py
python3 tools/repository_presentation_blueprint.py validate-fixtures
python3 tools/site_suite_blueprint.py
for manifest in examples/*.manifest.json; do
  python3 tools/holon_contract.py validate --manifest "${manifest}"
done
python3 -m unittest discover --start-directory tests --pattern "test_*.py" --verbose
node --test tests/javascript/*.test.mjs
```

Prove repository-continuity materialization against the exact Aether, Hygiene,
EgoLint, and Antidote revisions recorded by the fixture contract:

```bash
continuity_root="$(pwd)"
(
  cd ".continuity-sources/egolint"
  CARGO_TARGET_DIR="${continuity_root}/.continuity-build/egolint" \
    cargo build --locked --bin "egolint"
)

python3 tools/check_repository_continuity_fixtures.py \
  --aether-source .continuity-sources/aether \
  --hygiene-source .continuity-sources/hygiene \
  --egolint-source .continuity-sources/egolint \
  --egolint-binary .continuity-build/egolint/debug/egolint \
  --antidote-source .continuity-sources/antidote
```

The checker does not fetch sources or accept credentials. The validation
workflow acquires the exact commits separately, with credential persistence
disabled, before invoking the same local-only command.

Execute the disposable React/Vite consumer proof with the profile's pinned
package manager:

```bash
corepack_directory="$(mktemp -d)"
corepack prepare "pnpm@11.24.0" --activate
corepack enable --install-directory "$corepack_directory"
PATH="$corepack_directory:$PATH" python3 tools/check_react_vite_fixture.py
PATH="$corepack_directory:$PATH" python3 tools/check_launchkit_fixtures.py
PATH="$corepack_directory:$PATH" python3 tools/check_site_suite_fixtures.py
```

Resolve a manifest directly when only the contract output is needed:

```bash
python3 tools/holon_contract.py resolve \
  --manifest "examples/tool.manifest.json" \
  --output "/tmp/holon-tool.resolved.json"
```

## Plan and materialize a repository

Holon never jumps directly from intent to mutation. First create a dry-run plan.
Repositories selecting `aether-agents` must supply a previously acquired pinned
Aether distribution so Holon can verify the manifest pin, release provenance,
and provider-projection hashes without fetching a mutable branch.

```bash
python3 tools/holon_materialize.py plan \
  --manifest "examples/tool.manifest.json" \
  --target "/tmp/example-tool" \
  --aether-source "/path/to/pinned/aether/dist" \
  --render-source "/path/to/rendered-pack" \
  --output "/tmp/example-tool.plan.json"
```

Review the plan, then apply exactly that plan with the same immutable inputs:

```bash
python3 tools/holon_materialize.py render \
  --plan "/tmp/example-tool.plan.json" \
  --target "/tmp/example-tool" \
  --aether-source "/path/to/pinned/aether/dist" \
  --render-source "/path/to/rendered-pack"
```

Verify current generated ownership:

```bash
python3 tools/holon_materialize.py verify \
  --target "/tmp/example-tool"
```

Roll back the latest render when generated files have not been edited since the
render:

```bash
python3 tools/holon_materialize.py rollback \
  --target "/tmp/example-tool"
```

Holon fails closed around existing and modified files. An unowned target path is
a conflict; a managed path whose bytes no longer match recorded SHA-256 state is
a conflict; and rollback refuses to erase post-render edits. There is no v1
force-overwrite path.
