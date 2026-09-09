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
The caller gathers and reviews mutable facts; Holon validates, renders, previews,
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
backups before changing any consumer file. The final state binds the rollback
manifest digest, and the manifest binds the exact prior-state digest. Rollback
restores that byte-exact preceding state when one existed and otherwise removes
the adapter state after recovery.

A process or power loss can interrupt the bounded multi-file apply before final
state is committed. The content-addressed backup attempt and its digest-bearing
rollback manifest remain the manual recovery anchor; automatic crash journaling
is deliberately deferred until the ADR-010 reconsideration trigger is met.

## Deferred implementation boundary

The adapter deliberately does not install hooks, edit workflows, fetch provider
state, open pull requests, or perform fleet rollout. Cross-repository fixture
proof and the reviewed Antidote prototype migration are implemented by the
offline harness above. Holon CLI/CI dogfood belongs to issue #46; Relay preflight
and Pace fleet reconciliation remain external ownership boundaries.
