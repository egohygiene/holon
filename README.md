# Holon

🌀 An architecture-driven bootstrapper for creating coherent organizations,
repositories, and software ecosystems.

This repository now defines the first executable foundation contract for the Ego
Hygiene organization. It turns four repository classes—library, tool, product,
and publication—into versioned, testable manifests rather than copied template
folders.

## Contract preview

- [`catalog/foundation.json`](catalog/foundation.json) defines capabilities,
  ownership, dependencies, conflicts, and class policy.
- [`schemas/`](schemas/) provides the machine-readable catalog and manifest
  contracts.
- [`examples/`](examples/) contains a valid manifest for every repository class.
- [`tools/holon_contract.py`](tools/holon_contract.py) validates and resolves the
  contract without third-party dependencies.
- [`docs/foundation-contract.md`](docs/foundation-contract.md) documents
  generation boundaries, immutable pins, and idempotent update behavior.

Validate the catalog and all examples:

```bash
python3 tools/holon_contract.py validate-catalog
for manifest in examples/*.manifest.json; do
  python3 tools/holon_contract.py validate --manifest "${manifest}"
done
python3 -m unittest discover --start-directory tests --verbose
```

Resolve a manifest to the deterministic input a future generator will consume:

```bash
python3 tools/holon_contract.py resolve \
  --manifest "examples/tool.manifest.json" \
  --output "/tmp/holon-tool.resolved.json"
```

The CLI in this change intentionally stops at contract resolution. File
rendering and update application come later, after this policy layer is stable.
