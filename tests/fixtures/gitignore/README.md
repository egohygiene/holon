# Pinned ignore consumer fixtures

`empathy/` contains test-only copies of the catalog and both registered ignore
fragments from `egohygiene/empathy@b44f798bb49259f9f48416b4ffebde1103e135c0`.
Production reads caller-supplied, digest-verified data. These copies keep tests
offline; they are not a second source of policy or an installed baseline.

`filament/manifest.json` is the accepted Filament manifest from PR #6, merged as
`c3eb64b8087face7504e7571dc8396c19525649f`. Its `composition.json` is byte-identical
to `foundation/contracts/filament.gitignore-plan.json` in that pilot.

`scoped-rust/` adds one explicit Rust scope at `crates/widget`. Its local text
reopens `target/keep.txt` after the scoped `/target/` overlay and ignores a local
scratch directory. The universal baseline remains last in both scopes. Root
and sibling `target/` directories remain visible.

Both compositions were generated with the pinned upstream CLI:

```sh
python3 -B /path/to/pinned-empathy/tools/foundation.py \
  --catalog /path/to/pinned-empathy/foundation/catalog.json \
  plan-gitignore --manifest tests/fixtures/gitignore/filament/manifest.json \
  --source-root /path/to/pinned-empathy \
  --output tests/fixtures/gitignore/filament/composition.json
```

Repeat with `scoped-rust` for that fixture. Requests carry the resolved profile
list, explicit scope selection, upstream composition's canonical JSON digest,
and empty initial adoption lists. Tests add explicit approvals only when testing
the adoption proposal. No test runs the upstream generator or accesses a network.
