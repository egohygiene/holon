# Layered gitignore materialization

Issue [#58](https://github.com/egohygiene/holon/issues/58) gives Empathy's accepted
layered ignore contract a reusable local materialization path: read-only planning,
explicit reviewed creation/adoption, tracked updates, verification, and guarded
rollback. Filament and scoped Rust fixtures exercise that complete local lifecycle.
The interface does not run Git, create a PR, execute Relay, or reconcile a fleet.

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
To adopt the existing Filament pilot, record its current `.gitignore` digest
`3637ea33004215037e745cf898f59e7c2a3195f8b66df5bae0921186ec731373` in `adopt`
after checking it against the accepted composition. Holon checks it again before
tracking the file and does not rewrite those existing bytes or permissions.

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

Plans use `holon.gitignore-plan/v2`. The planning-only v1 format is rejected by
both `check-plan` and `apply`; regenerate and review it with this CLI. Request
and source formats remain v1. A v2 plan binds the exact previous gitignore state
and generic ownership-state digests as well as all source and consumer inputs.

Inspect each operation's before/proposed bytes, permission modes, and digests, exact unified diff,
ownership, explicit scope/local text, layer provenance, and reason. Non-UTF-8 or
unsafe targets cannot have a textual diff and remain conflicts. Plans are
timestamp-free and omit machine-local paths. Their `plan_id` hashes the complete
canonical payload excluding `plan_id` itself.

| Action | Meaning |
| --- | --- |
| `create` | The output is absent and has no stale adoption approval. |
| `adopt` | Explicit approval binds current, exact composed bytes; apply records tracking without rewriting. |
| `update` | Tracked bytes and mode are unchanged; a new explicit composition changes content. |
| `noop` | Tracked bytes already match the desired composition. |
| `release` | An omitted or preserved scope loses tracking; its unchanged file remains in place. |
| `preserve` | Empathy explicitly protects the path; proposed content is informational. |
| `conflict` | Reconcile unknown edits, missing tracked files, mode drift, generic ownership, stale adoption, or unsafe paths. |

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
byte-identical; choose a new output path after changing inputs. The same failure
and usage exit codes apply to the remaining commands.

## Reviewed apply and repeat use

After reviewing the complete plan, pass its exact `plan_id` explicitly:

```sh
python3 tools/holon_materialize.py gitignore apply \
  --request /path/to/gitignore.request.json \
  --composition /tmp/consumer.empathy-gitignore.json \
  --empathy-source /path/to/pinned-empathy \
  --target /path/to/consumer \
  --plan /tmp/consumer.holon-gitignore.json \
  --reviewed-plan-id REVIEWED_PLAN_SHA256
```

The token identifies reviewed evidence; it is not proof of a human review or a
permission grant. The caller remains responsible for authorization. Apply
rebuilds the complete plan before taking a local lock and again under that lock.
It rejects changed evidence and conflicts before creating recovery data or
writing consumer files. Existing generic Holon ownership cannot be adopted by
this adapter. This plan is not a generic `render` input.

The result is `holon.gitignore-apply-result/v1`, with status `applied` or `noop`,
tracked-file count, state path, and exact state digest. For repeated use, generate
and review a **fresh plan against the current state**. Applying that unchanged
selection is a no-op: consumer bytes, modes, state, and recovery records remain
unchanged. Replaying an already-consumed plan fails its stale-state check.
Changing provenance or selection can record a new state even when file bytes
stay the same. A preserve-only request without prior ownership writes nothing.

## State, updates, and local rules

The dedicated state is `.holon/gitignore-state.v1.json`
(`holon.gitignore-state/v1`). It records the explicit request, pinned source,
composition provenance, scope/layer selections, exact tracked bytes and modes,
plan ID, and checksum-bound recovery reference. Repository ownership of local
rules remains distinct from Holon's permission to update an unchanged tracked
composition. ADR-011 defines this exception to generic first-adoption behavior;
ADR-005 still governs generic packs.

To update local rules, edit the explicit Empathy selection, regenerate and check
the composition with Empathy, update the request digest, then plan/review/apply.
Holon does not extract, guess, or merge additions from manually edited files.
Unrecorded edits must be preserved and reconciled before automation resumes;
adding an adoption approval never overrides tracked drift.

A baseline upgrade additionally requires a reviewed update to Holon's accepted
source profile and the new immutable source export. Recompose the same explicit
local additions and overlays against that pin. The new plan shows changed
baseline bytes and retained local text; removed local rules must be an explicit
selection change. There is no arbitrary source-pin override flag.

Omitting a previously tracked scope or selecting `preserve` releases tracking
without deleting its file. Even release refuses edited or missing tracked files.
Later re-adoption requires explicit exact-byte approval. Combining preserve and
adoption is a conflict. Generic and gitignore state cannot own the same path.

## Verify and recover

```sh
python3 tools/holon_materialize.py gitignore verify --target /path/to/consumer
```

Verification checks saved provenance consistency, state and recovery checksums,
ownership inventory, and every tracked file's exact bytes and mode. Its
`holon.gitignore-verification/v1` result supplies the `state_sha256` for reviewed
recovery. It requires local state, not Empathy source access. It does not replace
Empathy's original manifest validation or EgoLint's semantic conformance checks.
Checksums detect drift; they do not authenticate deliberately rewritten local
state and recovery records.

Each changed application retains immutable recovery evidence at
`.holon/gitignore-backups/<plan-id>/attempt-NNN/rollback.v1.json`
(`holon.gitignore-rollback/v1`). It includes exact prior state bytes, file
preimages/postimages and modes, and the directories created for new scopes.
Review this record and the current verification result, then run:

```sh
python3 tools/holon_materialize.py gitignore rollback \
  --target /path/to/consumer \
  --expected-state-sha256 REVIEWED_CURRENT_STATE_SHA256
```

Rollback prevalidates the complete transition before any write, including
released files and the preceding recovery anchor. An intervening file edit,
ownership conflict, stale state digest, missing backup, or corrupted record
stops recovery. Created files are removed; updated files and the previous state
are restored exactly. Adopted files remain untouched. Only empty directories
created for scopes are removed. Unrelated work and Git metadata are preserved.
Successive rollbacks may follow the retained state chain; each requires a fresh
verification and review. Recovery records remain after rollback, and a repeated
application creates a new attempt rather than overwriting earlier evidence.

Apply and rollback serialize cooperating operations using
`.holon/gitignore.lock`. A busy/stale lock fails closed; inspect the operation
and recovery evidence before manually removing an abandoned lock. Consumer
files and state are checked again around writes, and state is published last.
Ordinary write failures attempt restoration only while files still match known
operation images; intervening edits are preserved and reported with the recovery
path. Run with other filesystem writers quiescent: individual replacements are
atomic, but this is not an atomic multi-file transaction or protection against
an adversarial concurrent writer. Process/power-loss recovery remains manual
using retained evidence. The adapter does not provide automatic journal replay.

## Downstream work

Source semantics remain in Empathy. EgoLint #61 owns reusable conformance,
Empathy #92 consumes it, Relay executes it, and Pace #30 owns later reviewed
rollout. Direct MegaLinter repairs and the queued `.gitattributes` iteration
remain separate under the file-contract epic.

## Proof

```sh
python3 -B -m unittest discover --start-directory tests \
  --pattern "test_gitignore*.py"
```

The disposable fixtures prove accepted Filament creation and adoption through
the public CLI, no-op reruns, exact provenance, scoped Rust/local exceptions with
real Git, source drift, stale/forged plans, path/ownership conflicts, updates,
release, complete rollback chains, recovery corruption, and injected write
failures. A synthetic source-profile repin proves local-rule preservation across
a baseline upgrade; it does not introduce a new production Empathy baseline.
