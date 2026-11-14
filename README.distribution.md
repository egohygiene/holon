# Holon source archive candidate

This is an **unreleased 1.0.0-rc.0 candidate**, not published v1 availability or
a stable support promise. Its version authority is
`catalog/distribution-candidate.json`; the root npm metadata remains a private
workspace and the Repository Intelligence package retains its separate alpha
lifecycle. `DISTRIBUTION.json` in a prepared archive identifies the exact source
commit and every selected payload byte. The separately retained candidate
receipt identifies the complete compressed archive digest.

## Finite compatibility boundary

The selected interfaces are foundation catalog validation, manifest validation
and resolution, and explicit `site-suite plan`, `render`, `verify` and guarded
`rollback`. Both canonical generic and LaunchKit site packs are included. The
qualified runtime is Linux x86_64 with Python 3.12.14 and its standard library.
No pip dependency, workspace install, Node module or credential is required for
these interfaces. Keep the archive contents together; installing individual
scripts is unsupported.

Source materialization does not qualify a frontend dependency install, build,
browser, deployment or every optional blueprint. Existing frontend/native safety
records retain their stated sources; `docs/evidence/2026-11-13-adr-native.json`
in the source repository owns #63's ordinary-consumer ADR compatibility.
Windows, macOS, concurrent-writer guarantees, the npm workspace, alpha component
package, full-foundation Aether adoption and continuity promotion are outside
this candidate. Full-foundation admission still requires a genuine pinned
Aether distribution. Site-only projection leaves every omitted capability
explicitly unqualified.

## Prepare from one immutable producer source

The producer must use a full reviewed commit that contains the exact running
preparer. It reads Git objects, never uncommitted source or local dependency
caches. Output must be a new directory outside the producer checkout.

```bash
python3 tools/distribution_candidate.py prepare \
  --source-commit FULL_REVIEWED_COMMIT --output /tmp/holon-candidate
```

The archive has canonical file order, owner IDs, modes, source-commit epoch and
gzip time zero. Repeated preparation under the declared runtime must produce
identical complete archive and manifest digests. The file inventory excludes
its containing generated manifest; archive identity lives in the external
receipt, avoiding self-containing hashes. Symlinks, submodules, unsafe paths,
missing selected files and oversized input are refused. Existing output is
never overwritten.

Release policy and declaration validation compose Aether's existing
`prepare-repository-release` reference tool. The exact public revision and file
digests are locked in `catalog/distribution-candidate.json`. Acquire that exact
Aether source separately, then verify its bytes before executing the reference
validator:

```bash
python3 tools/distribution_candidate.py verify-inputs --aether-source /path/to/pinned-aether
python3 /path/to/pinned-aether/library/organization/specs/release/validate.py \
  --repository . --format json
```

This is a draft reference contract, not a released Aether agent distribution.
The standard Taskfile names delegate `release:plan` to that owner and expose
candidate preparation/verification. `release:publish` fails explicitly. The
manual read-only workflow prepares local evidence only; it has no tag, Release,
registry, signature or deployment adapter. Its hosted execution remains
unobserved until separately run. No second release/versioning engine exists.

## Verify, extract and use outside the producer

Obtain the archive and its digest from the reviewed candidate receipt. Verify
the digest independently before executing extracted code. The verifier admits
every bounded regular-file member and complete inventory before extraction;
it never follows tar links or writes over an existing destination.

```bash
python3 tools/distribution_candidate.py verify --archive /path/to/candidate.tar.gz \
  --sha256 RETAINED_ARCHIVE_SHA256 --extract /tmp/holon-extracted
cd /tmp/holon-extracted/holon
python3 -B -S tools/holon_contract.py validate-catalog
python3 -B -S tools/holon_materialize.py site-suite plan \
  --manifest examples/site-suite-generic.manifest.json --variant generic \
  --target /tmp/holon-consumer --output /tmp/holon-consumer.plan.json
# Review the plan, including site_suite_projection and omitted capabilities.
python3 -B -S tools/holon_materialize.py site-suite render \
  --target /tmp/holon-consumer --plan /tmp/holon-consumer.plan.json
python3 -B -S tools/holon_materialize.py site-suite verify --target /tmp/holon-consumer
python3 -B -S tools/holon_materialize.py site-suite rollback --target /tmp/holon-consumer
```

Ordinary generated-file conflicts, exact-plan replay and recovery guards remain
unchanged. Rollback refuses post-render edits; retain and reconcile those
consumer changes instead of deleting them. Never replace an immutable artifact
or exact published tag. Prepare a reviewed successor if a candidate is wrong.
SBOM, signing, actual release channels, tags and registry publication remain
unavailable/separate actions.

For repeatable clean-room evidence, the producer verifier extracts into a new
external temporary directory and starts the **extracted** qualifier under
`python -B -S` with only PATH and locale environment keys:

```bash
python3 tools/qualify_distribution_candidate.py \
  --candidate /tmp/holon-candidate/candidate.json --result /tmp/holon-clean-room.json
```

The child uses only the archive and the declared Python runtime. It validates
the catalog and manifests; proves two differently named targets have equal
plans and managed bytes; performs both actual variant updates, no-op checks,
exact managed-output/state rollback, edited-file refusal and unowned conflicts;
and confirms the ordinary full-foundation Aether gate still refuses. It does
not fetch provider input, access a source checkout, install packages or build a
frontend. The receipt records candidate status and exact limits, not published
availability. A clean-room candidate result does not close broader #82 or
HOL-Q05 publication criteria by itself.
