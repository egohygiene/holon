# Repository-continuity fixtures

These publish-safe fixtures exercise Holon's repository-continuity reconciler
against five representative repository profiles and the pinned Antidote
prototype migration. `cases.v1.json` contains only synthetic metadata plus
immutable public source pins. The Antidote mapping records how each complete
legacy section is retained, condensed, superseded with evidence, or supplied by
the pinned portable template.

The integration checker accepts already-local checkouts at the exact recorded
commits. It never fetches, reads credentials, or queries mutable provider state.
All live evidence is therefore recorded as unavailable and every positive
checkpoint is validated in that honest state by the pinned EgoLint contract.

`artifact-contracts.json` is the reviewed deterministic snapshot. Updating it
requires running the checker with `--write-snapshots` and reviewing every plan,
surface, state, validation, and rollback digest change.
