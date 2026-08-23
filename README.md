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
- [`docs/foundation-contract.md`](docs/foundation-contract.md) documents
  repository-class policy and immutable pins.
- [`docs/materialization-engine.md`](docs/materialization-engine.md) documents
  generated ownership, conflict handling, Aether projection consumption, and
  rollback safety.

## Validate the foundation

```bash
python3 tools/holon_contract.py validate-catalog
for manifest in examples/*.manifest.json; do
  python3 tools/holon_contract.py validate --manifest "${manifest}"
done
python3 -m unittest discover --start-directory tests --pattern "test_*.py" --verbose
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
