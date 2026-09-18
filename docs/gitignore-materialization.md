# Layered gitignore adoption planning

Issue [#58](https://github.com/egohygiene/holon/issues/58) gives Empathy's accepted
layered ignore contract a reusable local materialization path. This first slice
implements **read-only initial creation/adoption planning and stale-plan checks**.
It does not apply changes, record ownership, upgrade files, or roll back anything.
Those lifecycle steps remain open in #58 for the next reviewed PR.

## Ownership and inputs

Empathy owns profile resolution, rules, composition, and foundation `1.1.0`.
Holon consumes an already-composed `empathy.gitignore/v1` artifact and an explicit
consumer request. No network requests or external generator execution occur.

[`catalog/gitignore-materialization.json`](../catalog/gitignore-materialization.json)
records the accepted Empathy revision `b44f798bb49259f9f48416b4ffebde1103e135c0`
and canonical catalog digest. Holon checks the supplied catalog against that
pin and every registered fragment against the catalog, including unselected
overlays. The source directory may be an artifact-only export: content digests,
not its directory name or mutable Git HEAD, establish the accepted input identity.
Changing the accepted source requires a reviewed Holon source-pin change.

The request binds the exact composition by canonical JSON SHA-256. Holon checks
repository, resolved profile IDs, scope paths, source provenance, layer hashes,
exact local text, content hashes, and v1 framing/order: overlays, local additions,
then the universal baseline. Rules are read from the verified Empathy fragments;
Holon does not maintain a production copy of the baseline.

The upstream `resolved_manifest_sha256` is retained as provenance. Holon does not
re-resolve the full foundation manifest or validate its unrelated required files.
Use Empathy's `check-gitignore-plan` with the original manifest for that proof.
EgoLint #61 owns reusable semantic conformance beyond this adapter's checks.

## Request contract

`holon.gitignore-request/v1` is a closed JSON object with these required fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Exactly `holon.gitignore-request/v1`. |
| `repository` | The composition's `owner/name`. |
| `source_revision` | The accepted 40-character Empathy revision above. |
| `profiles` | Empathy's resolved profile IDs, in the composition's order. |
| `scopes` | Explicit `{root, overlays, local_additions}` records in composition order. |
| `composition_sha256` | SHA-256 of canonical JSON: sorted keys, compact separators, UTF-8, no trailing newline. |
| `adopt` | Explicit `{path, before_sha256}` approvals; use `[]` for greenfield planning. |

The root scope `.` is required. Additional scopes are normalized relative
directories; Git/Holon metadata, symlinks, case-insensitive collisions, traversal,
and globs are rejected. Local additions must be empty or LF-terminated text with
no CR or NUL. They are never inferred from an existing file. An adoption record
must name a selected output and bind current bytes that exactly match the verified
composition. Matching bytes without that record still produce a conflict.

The [Filament request](../tests/fixtures/gitignore/filament/request.json) and
[scoped Rust request](../tests/fixtures/gitignore/scoped-rust/request.json) are
complete examples. The former uses the accepted Filament pilot's exact output.

## Prepare and inspect

Acquire the pinned Empathy source separately. After reviewing the consumer
manifest, run Empathy's public CLI explicitly to compose it:

```sh
python3 -B /path/to/pinned-empathy/tools/foundation.py \
  --catalog /path/to/pinned-empathy/foundation/catalog.json \
  plan-gitignore --manifest /path/to/gitignore.manifest.json \
  --source-root /path/to/pinned-empathy \
  --output /tmp/consumer.empathy-gitignore.json
```

Populate the request from the reviewed selection and resolved profile IDs, then
build a Holon plan outside the consumer and source directories:

```sh
python3 tools/holon_materialize.py gitignore plan \
  --request /path/to/gitignore.request.json \
  --composition /tmp/consumer.empathy-gitignore.json \
  --empathy-source /path/to/pinned-empathy \
  --target /path/to/consumer \
  --output /tmp/consumer.holon-gitignore.json
```

Inspect each operation's before/proposed bytes and digests, exact unified diff,
ownership, explicit scope/local text, layer provenance, and reason. Non-UTF-8 or
unsafe targets cannot have a textual diff and remain conflicts. Plans are
timestamp-free and omit machine-local paths. Their `plan_id` hashes the complete
canonical payload excluding `plan_id` itself.

| Action | Meaning |
| --- | --- |
| `create` | The output is absent and has no stale adoption approval. |
| `adopt` | Explicit approval binds the current, exact composed bytes. No ownership is granted yet. |
| `preserve` | Empathy explicitly protects the path; proposed content is informational. |
| `conflict` | Reconcile unknown text, stale adoption evidence, or unsafe paths before continuing. |

Check that the same request, source, composition, and target still reproduce the
reviewed artifact:

```sh
python3 tools/holon_materialize.py gitignore check-plan \
  --request /path/to/gitignore.request.json \
  --composition /tmp/consumer.empathy-gitignore.json \
  --empathy-source /path/to/pinned-empathy \
  --target /path/to/consumer \
  --plan /tmp/consumer.holon-gitignore.json
```

`plan` returns 0 for conflict-free inspection or 1 with a written conflict plan.
Invalid inputs return 1 without a plan. `check-plan` returns 1 for changed inputs,
stale/tampered plans, or conflicts; 0 means only that the read-only comparison
passes. Usage errors return 2. An existing output artifact is reused only when
byte-identical; choose a new output path after changing inputs.

## Review boundary and continuation

Repository ownership of local rules remains distinct from Holon's future
application/provenance state. This initial planner does not consume generic
whole-file state or authorize its adoption. Existing state reconciliation,
reviewed apply, no-op reapplication, source upgrades, drift verification, and
guarded recovery are the next #58 slice. A future apply must re-read all inputs
and target bytes immediately before mutation, retain prior evidence, and reject
conflicts. This plan is not accepted by the generic `render` command.

ADR-005 still governs the generic engine's no-clobber rule. This read-only slice
does not change that decision or claim the complete upgrade milestone. Shared
hashing/path/target primitives are reused from the materialization engine;
gitignore-specific planning retains repository ownership. Relay execution and
Pace rollout remain downstream. MegaLinter repairs and the queued `.gitattributes`
iteration remain outside this PR.

## Proof

```sh
python3 -B -m unittest discover --start-directory tests \
  --pattern test_gitignore_materialization.py
```

The disposable fixtures prove accepted Filament bytes, explicit adoption,
scoped Rust/local exceptions using real Git, byte-preserved consumer/Git metadata,
source drift, changed rules/order, stale plans, unsafe paths, and output isolation.
They do not claim apply, upgrade, or rollback acceptance.
