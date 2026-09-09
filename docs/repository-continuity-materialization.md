# Repository-continuity materialization

Holon owns deterministic materialization of the Ego Hygiene repository-continuity
contract. The versioned profile in
[`catalog/repository-continuity-materialization.json`](../catalog/repository-continuity-materialization.json)
defines the immutable inputs and approved output surfaces. It does not make the
repository-specific claims recorded in `CONTINUITY.md`; those remain owned by the
consumer repository.

The reconciler in
[`tools/materialization/continuity.py`](../tools/materialization/continuity.py)
turns caller-supplied facts into an exact plan without inventing a clock value. It has no provider
client, credential path, network fallback, merge authority, or fleet authority.
The caller gathers and reviews mutable facts; Holon validates, plans, previews,
applies, verifies, and can roll back only local repository files.

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
instruction files. The reconciler preserves every byte outside its managed block,
detects duplicate, reversed, or malformed markers, supports an explicit opt-out,
and refuses ambiguous writes. Symlinks, symlinked parents, and non-regular files
are conflicts. A canonical block can be adopted; a noncanonical block can be
upgraded only when its digest matches trusted prior Holon state.

An existing `CONTINUITY.md` is preserved by default. Replacement requires an
explicit reviewed migration with the expected current SHA-256, reason, and stable
HTTPS evidence URL. That compare-and-swap boundary makes legacy migrations
reviewable and prevents a stale plan from discarding repository-specific state.

Optional provider paths form an explicit allowlist. A deselected provider file is
not read or changed and is omitted from the next state. Re-enabling later adopts
an exact canonical block; a stale noncanonical block without retained ownership
state becomes a no-write conflict that requires review.

## Reconciliation lifecycle

The public adapter functions keep consequential boundaries separate:

1. `validate_continuity_request` checks the closed request, Aether metadata,
   selected repository profile, evidence dispositions, timestamps, references,
   and prohibited-data patterns.
2. `build_continuity_plan` resolves pinned bytes and returns exact proposed
   content, SHA-256 values, unified diffs, provenance, disposition counts, and a
   content-addressed `plan_id`.
3. The caller reviews or serializes that preview. Holon does not apply it as a
   side effect of planning.
4. `apply_continuity_plan` recomputes the plan, checks every target preimage, and
   applies only the exact reviewed bytes.
5. `verify_continuity_target` checks the required checkpoint structure and only
   the managed regions of instruction files, leaving surrounding prose owned by
   the repository.
6. `rollback_continuity_target` prevalidates all current bytes and backups before
   restoring the complete preimage.

The request, plan, state, and rollback shapes are public versioned schemas in
[`schemas/`](../schemas/). All three source contracts—including owner role,
version, immutable revision, lifecycle, release status, and every artifact
SHA-256—are copied into the plan and state. Each output operation also names the
exact locally verified Aether artifact consulted for that surface and records
whether the proposed bytes use its evidence-grounded template, its managed block,
or only its desired contract during a preserve/no-write disposition. The rendered
resume, handoff, and compaction protocols come from the pinned template rather
than an untracked copy in Holon. Hygiene and EgoLint entries are declared profile
pins here; their executable offline validation evidence belongs to issue #45.

Plans are deterministic across JSON object key order and contain no local source
paths. Identical requests, pinned inputs, prior state, and repository bytes yield
identical proposed bytes and the same `plan_id`.

## Canonical CLI and review receipt

The specialized adapter is exposed beneath Holon's existing materialization CLI:

```text
python3 tools/holon_materialize.py continuity <plan|preview|apply|verify|rollback>
```

This does not change the generic top-level `plan`, `render`, `verify`, and
`rollback` commands. Continuity uses `apply` because its block-scoped ownership
and repository-owned checkpoint contract are distinct from generic whole-file
rendering.

| Command | Required inputs | Successful result | Correct next action |
| --- | --- | --- | --- |
| `plan` | Closed request JSON, target, pinned profile, local pinned Aether checkout, external output path | Exact `holon.repository-continuity-plan/v1` plus a JSON result | Run `preview`; never apply the request directly |
| `preview` | Plan, target, external receipt path | Content-addressed `holon.repository-continuity-preview/v1` receipt plus a JSON result | Inspect every operation and copy its complete `plan_id` only if acceptable |
| `apply` | Plan, receipt, reviewed plan ID, target, pinned profile, and the same local Aether checkout | Recomputed/applied state plus its SHA-256 in a JSON result | Run `verify` before relying on or presenting the handoff |
| `verify` | Target | Read-only verification and current state SHA-256 | Retain that digest only if an explicit rollback is required |
| `rollback` | Target and reviewed current state SHA-256 | Restored preceding state in a JSON result | Create and preview a new plan before any later apply |

Plan and preview artifacts must be regular, non-symlinked paths outside the
target repository. This prevents a dry-run output from overwriting a target
surface or `.git` metadata. Repeating an identical artifact write is a no-op;
different existing bytes are never overwritten implicitly. The apply command
validates the receipt, compares the explicit reviewed plan ID, and then rebuilds
the plan from the current target and pinned inputs before entering the
repository lock. There is no plan-to-apply shortcut, `--force`, `--yes`, or
implicit confirmation.

One complete sequence is:

```bash
python3 tools/holon_materialize.py continuity plan \
  --request "/path/to/repository-continuity.request.json" \
  --target "/path/to/repository" \
  --aether-source "/path/to/aether-at-the-pinned-revision" \
  --output "/tmp/repository-continuity.plan.json"

python3 tools/holon_materialize.py continuity preview \
  --plan "/tmp/repository-continuity.plan.json" \
  --target "/path/to/repository" \
  --output "/tmp/repository-continuity.preview.json"

python3 tools/holon_materialize.py continuity apply \
  --plan "/tmp/repository-continuity.plan.json" \
  --preview-receipt "/tmp/repository-continuity.preview.json" \
  --reviewed-plan-id "<64-character-plan-id>" \
  --target "/path/to/repository" \
  --aether-source "/path/to/aether-at-the-pinned-revision"

python3 tools/holon_materialize.py continuity verify \
  --target "/path/to/repository"

python3 tools/holon_materialize.py continuity rollback \
  --target "/path/to/repository" \
  --expected-state-sha256 "<state_sha256-from-verify>"
```

The preview receipt has a closed public
[schema](../schemas/repository-continuity-preview.v1.schema.json). It binds the
plan schema and ID, repository and mode, operation summary, materializability,
closed no-authority flags, and each operation's action, path, reason, diff, and
previous, proposed, and managed-block digests into its `preview_id`. Every
runtime success emits exactly one
`holon.repository-continuity-cli-result/v1` object on standard output; every
runtime failure emits one on standard error and leaves standard output empty.
That result also has a closed public
[schema](../schemas/repository-continuity-cli-result.v1.schema.json) and always
includes the command, status, stable code, success flag, nullable plan, preview,
state, and reviewed-state identifiers, materializability, summary, errors, and
an exact `corrective_action`. Argument failures direct the caller to the
applicable `continuity <command> --help`. Within the continuity command group,
human-readable help is the only prose output.

The CLI accepts no credential or provider-client configuration and invokes no
Git, GitHub, network, merge, publication, deployment, hook-installation, or
fleet operation. A read-only CI check may reject stale state, but semantic
refresh remains an Aether skill and consumer-repository responsibility.

## Explicit dispositions

| Mode or condition | Plan result | Apply behavior |
| --- | --- | --- |
| `materialize` | Verified repository facts and exact proposed surfaces | Allowed after review when no conflict exists |
| `provisional` | Partial or unavailable live evidence plus explicit unknowns | Allowed, with limitations visible in `CONTINUITY.md` |
| `opt-out` | Recorded reason and no proposed content | Refused as non-materializable |
| `unsupported` | Recorded unsupported profile and no proposed content | Refused as non-materializable |
| `parallel-conflict` | At least two unreconciled candidates and no proposed content | Refused until semantic reconciliation is supplied |
| Malformed marker, drift, symlink, or stale migration digest | Exact no-write conflict | Refused |

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

## Executable fixture proof

[`tools/check_repository_continuity_fixtures.py`](../tools/check_repository_continuity_fixtures.py)
exercises the adapter in disposable repositories. The fixture corpus covers the
five repository profiles plus the pinned Antidote prototype migration:

| Fixture | Starting condition | Required evidence |
| --- | --- | --- |
| Research/publication | New continuity surfaces with public-safe local facts and explicitly unavailable provider state | Deterministic provisional create, verify, no-op replan, asserted EgoLint result, and exact rollback |
| Library/CLI | Existing repository-authored instructions | One canonical managed block without changing surrounding prose |
| Site/application | Test-only prior Holon profile and state-bound prior managed blocks, with the same immutable Aether source bytes | Profile/state and three managed-block upgrades with surrounding prose preserved |
| Organization/meta | Concurrent candidate checkpoints | Parallel conflict produces no writes; explicit reconciliation becomes materializable |
| Private creative | Incomplete private-repository evidence | Provisional checkpoint containing only synthetic, allowlisted, minimum-necessary metadata |
| Antidote prototype | Existing legacy checkpoint and agent instructions | Reviewed SHA-bound migration maps every useful legacy fact and preserves authored instruction prose |

The harness records mutable provider evidence as unavailable rather than
fabricating a successful live check. It plans each supported transition twice,
compares the complete plans,
applies and verifies the reviewed bytes, proves a byte-idempotent no-op apply, runs
a contract-fingerprinted EgoLint continuity validator with semantic report assertions,
and restores every approved surface and preceding state preimage byte-for-byte while
retaining the digest-bound recovery evidence. It also exercises opt-out, unsupported,
conflict, upgrade, and rollback paths. Canonical CI builds the validator binary
from the exact pinned source revision. Versioned output contracts and the Antidote
migration map make fixture
drift reviewable instead of silently updating expected results.

Private fixture content is synthetic and intentionally contains no private
conversation text, credentials, local paths, or real unpublished project state.
The Antidote source snapshot is accepted only at its recorded immutable revision;
the fixture maps useful checkpoint facts without carrying filler or treating the
snapshot as current mutable GitHub state.

## Holon dogfood

Holon consumes its own `library-cli` profile through the same canonical CLI. The
evidence-grounded input is
[`examples/holon-continuity.request.json`](../examples/holon-continuity.request.json).
It remains `provisional` because the pinned cross-repository contracts are not
released; dogfooding does not turn immutable merged revisions into release
evidence or promote rollout beyond `observe`.

The reviewed apply creates and commits these coupled artifacts:

- root [`CONTINUITY.md`](../CONTINUITY.md), whose semantic facts remain owned by
  this repository;
- root [`AGENTS.md`](../AGENTS.md), containing exactly one canonical Aether
  continuity block and no copied checkpoint body;
- `.holon/repository-continuity-state.v1.json`, containing exact provenance and
  managed-region ownership; and
- the referenced
  `.holon/repository-continuity-backups/<plan-id>/attempt-001/rollback.v1.json`,
  which the state digest binds.

The state and referenced rollback manifest must remain together. The first
application creates only new surfaces, so its recovery record needs no private
or repository-authored preimage blobs. Future semantic checkpoint updates still
require inspected evidence and a new reviewed request; the committed example is
not an authority to repeat stale live claims.

Dogfood validation verifies the committed target, replans the exact request into
an external temporary path, previews and applies the resulting all-no-op plan,
and proves that every repository byte—including `.git`—remains unchanged. A
separate disposable repository exercises create, verify, the same-request no-op
apply, and state-digest-approved rollback. Trap executables and byte snapshots
prove that no `git`, `gh`, `curl`, or `wget` process executes during that
lifecycle. CI performs only this deterministic verification; it never authors
semantic checkpoint prose.

Run the complete proof with the pinned local Aether checkout already acquired by
the caller or CI:

```bash
python3 tools/check_repository_continuity_dogfood.py \
  --aether-source ".continuity-sources/aether"
```

Before the root artifacts exist, `--lifecycle-only` runs only the disposable
portion. The canonical acceptance path omits that flag and requires exact parity
between the clean materialization and every committed dogfood artifact.

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

The adapter itself takes an already-local Aether checkout and verifies the four
bytes it consumes—the template plus the Codex, GitHub Copilot, and Claude
projections—even when only a subset of optional provider outputs is selected.

Run the cross-repository proof with caller-supplied checkouts at the exact
revisions recorded by the profile and fixture manifest:

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

The checker verifies each checkout revision and pinned artifact before using it.
It has no fetch implementation, provider client, credential input, or mutable
GitHub lookup. CI acquisition is separate orchestration: the workflow checks out
the four exact commits with credential persistence disabled, builds that EgoLint
source with its locked dependency graph, and passes only local paths to the
checker. A successful command requires the semantic EgoLint report to match the
fixture's declared expectation; an exit code alone is not fixture evidence.

## Release gate and released-input migration

Implementation and merge evidence do not make a contract released. The profile
therefore remains `proposed`, is capped at `observe`, and fails closed if a
caller attempts to promote it while any pinned source remains unreleased.

The following state was verified against the immutable profile and live GitHub
evidence on 2026-09-09:

| Source | Pinned profile state | Live release evidence | Remaining gate |
| --- | --- | --- | --- |
| [Aether](https://github.com/egohygiene/aether) | `b7597301c4d22a9bcd580967b5753138bb368111`; `draft`; `release_included: false` | Issues [#79](https://github.com/egohygiene/aether/issues/79) and [#80](https://github.com/egohygiene/aether/issues/80) are complete, but no GitHub release was observed | Mark the pinned contract and skill stable and include them in an immutable release |
| [Hygiene](https://github.com/egohygiene/hygiene) | `43386f5749116717585ead7459b4945e0ac50d06`; `proposed`; `release_included: false` | Issue [#45](https://github.com/egohygiene/hygiene/issues/45) is complete, but no GitHub release was observed | Accept and release the pinned organization policy |
| [EgoLint](https://github.com/egohygiene/egolint) | `786f1b3c59748a66bb092cad9589640f01c5b41d`; `proposed`; `release_included: false` | Issue [#55](https://github.com/egohygiene/egolint/issues/55) is open on the released-contract gate, and no GitHub release was observed | Consume released upstream projections and release the rule catalog and report contract |

Live issue and release state is mutable and must be rechecked before relying on
this observation. The immutable profile remains the authority for what this
Holon revision may consume.

When all three owners publish compatible releases:

1. acquire the exact released revisions without changing consumer files;
2. verify every declared artifact and release-provenance digest locally;
3. update the profile source versions, revisions, lifecycles, release flags, and
   hashes in one reviewable change;
4. regenerate and review the cross-repository fixture contracts;
5. run the profile verifier, canonical CLI dogfood, EgoLint proof, and full
   Python and JavaScript suites; and
6. require an explicit maintainer decision before changing the rollout stage.

No release event silently edits the profile or promotes enforcement.

## Acceptance traceability

The child sequence implements the local capability while keeping the released
input gate visible:

| Parent #42 criterion | Owning evidence | State after issue #46 |
| --- | --- | --- |
| Versioned profile consumes pinned Aether and Hygiene artifacts | [`catalog/repository-continuity-materialization.json`](../catalog/repository-continuity-materialization.json), its [schema](../schemas/repository-continuity-materialization-profile.v1.schema.json), and [profile tests](../tests/test_repository_continuity_profile.py) | Implemented at `observe` |
| Missing surfaces receive a repository-specific preview before mutation | [`continuity.py`](../tools/materialization/continuity.py), the canonical nested CLI, request/plan/preview schemas, and [CLI tests](../tests/test_continuity_cli.py) | Implemented |
| Authored content survives and managed blocks remain singular and idempotent | [Adapter unit tests](../tests/test_continuity_materialization.py), cross-profile fixtures, and Holon's [dogfood checker](../tools/check_repository_continuity_dogfood.py) | Implemented |
| Antidote migration retains useful state | [Migration map](../tests/fixtures/repository-continuity/antidote-migration-map.v1.json) and fixture artifact contract | Implemented |
| Five materially different repository profiles pass | [Fixture cases](../tests/fixtures/repository-continuity/cases.v1.json) and the [offline checker](../tools/check_repository_continuity_fixtures.py) | Implemented |
| Conflict, unsupported, provisional, opt-out, upgrade, parallel, and rollback states are tested | Adapter unit tests plus the [cross-profile contract tests](../tests/test_repository_continuity_fixtures.py) and checker | Implemented |
| Generated files record provenance and pass the released EgoLint validator | Pinned source/provenance checks and semantic EgoLint fixture reports pass against the pinned proposed validator | **Blocked:** the validator and its upstream inputs are not released |
| A second unchanged run produces no diff | Adapter no-op tests, cross-profile byte comparisons, and the dogfood checker's exact root-byte comparison | Implemented |
| Materialization grants no publish, merge, credential, or external-write authority | Profile, plan/state schemas, [CLI safety tests](../tests/test_continuity_cli.py), the dogfood command traps, [ADR-010](../DECISIONS.md#adr-010-reconcile-continuity-through-block-scoped-ownership-and-reviewed-migration), and workflow read-only permissions | Implemented |

Issue #46 can close after its bounded CLI, documentation, dogfood, and validation
evidence pass. [Parent issue #42](https://github.com/egohygiene/holon/issues/42)
must remain open until the released-validator row and every activation gate above
are satisfied. Relay preflight and Pace rollout are not hidden prerequisites for
the local adapter, but they remain the owners of their respective downstream
behaviors.

## State and recovery

Successful materialization writes its state to:

```text
.holon/repository-continuity-state.v1.json
```

Per-application rollback manifests and exact update preimages live under:

```text
.holon/repository-continuity-backups/<plan-id>/attempt-<number>/
```

Apply and rollback serialize through a fail-closed repository-local lock. Rollback
refuses missing, modified, symlinked, or mismatched targets, manifests, and
backups before changing any consumer file. The canonical CLI also binds rollback
approval to the exact current state digest and checks it under that lock. The
final state binds the rollback manifest digest, and the manifest binds the exact
prior-state digest. Rollback restores that byte-exact preceding state when one
existed and otherwise removes the adapter state after recovery. If a bounded
rollback write fails, the adapter restores the complete applied snapshot before
returning an error so the same reviewed rollback remains retryable.

A process or power loss can interrupt the bounded multi-file apply before final
state is committed. The content-addressed backup attempt and its digest-bearing
rollback manifest remain the manual recovery anchor; automatic crash journaling
is deliberately deferred until the ADR-010 reconsideration trigger is met.

## Deferred implementation boundary

The adapter deliberately does not install hooks, author semantic state in CI,
fetch provider state, open pull requests, or perform fleet rollout.
Cross-repository fixture proof and the reviewed Antidote prototype migration are
implemented by the offline harness above. The canonical CLI and Holon dogfood
expose and verify the same local adapter boundaries. Relay preflight and Pace
fleet reconciliation remain external ownership boundaries.
