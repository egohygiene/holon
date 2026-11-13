# Materialization and manifest acceptance — 2026-11-13

Issues [#67](https://github.com/egohygiene/holon/issues/67) and
[#70](https://github.com/egohygiene/holon/issues/70) are qualified against the
already merged implementations from PRs #93 and #91. The runtime source is
`3eddaf17517ebcf8af78b9e0a69c10312f6ab84e`. This candidate changes no runtime,
schema, dependency, template, ownership rule or frozen audit.

The additional public CLI regression is committed at
`7847e1c16e62da4fc4921c697bc9b4c0f56e1955`. It extends the existing independent
schema corpus through both `validate` and `resolve`, without adding a runtime
dependency. The [machine-readable record](2026-11-13-materialization-contract.json)
contains exact commands, source/file/log hashes, counts and limitations. The
five complete command logs are retained beside it.

## Executed checks

Python **3.12.14**, test-only `jsonschema` **4.26.0**, Linux:

| Command | Result |
| --- | --- |
| `python3 -m unittest discover --start-directory tests --pattern "test_materialization.py" --verbose` | 34 passed, zero skipped |
| `python3 -m unittest discover --start-directory tests --pattern "test_continuity_materialization.py" --verbose` | 38 passed, zero skipped |
| `python3 -m unittest discover --start-directory tests --pattern "test_gitignore_materialization.py" --verbose` | 22 passed, zero skipped |
| `python3 -m unittest discover --start-directory tests --pattern "test_holon_contract.py" --verbose` | 17 passed, zero skipped |
| `python3 tools/holon_contract.py validate-catalog` | Four classes / fifteen capabilities valid |

That is **111 distinct suite tests**. The shared generic suite counts once.
The contract suite executes **63 independent Draft 2020-12 parity cases** and
**126 public CLI invocations**, including the original malformed identity and
preservation inputs. Separately, both public resolution runs for every one of
the **nine committed manifest examples** emitted identical bytes.

The first new CLI test assumed all rejection exits were 1. Non-object JSON
correctly takes the loader's existing exit 2. The final test instead checks
success against the independent schema and matching rejection code/diagnostics
between both entries. No implementation or policy was changed for that test
correction.

## Issue #67 acceptance

All five criteria are supported by the executed suites and reviewed guard
entry points in `tools/materialization/common.py` and `engine.py`:

| Criterion | Executed evidence |
| --- | --- |
| Check every managed/state/recovery component before use | Generic tests reject symlink and non-directory ancestors, nested Git namespaces, dangling state/internal aliases and FIFO state without reading it. |
| Reject Git, unowned, preserved, parent and external-backup aliases without sentinel changes | `test_plan_rejects_generated_alias_to_git_unowned_or_preserved_files`, `test_plan_rejects_symlink_and_non_directory_ancestors` and `test_render_rejects_backup_alias_inserted_after_planning` compare the disposable fixture snapshot before/after refusal. |
| Keep state, backup allocation and recovery containment consistent | Tests cover dangling attempt allocation, generated aliases during verify/rollback, every preimage and prior state before rollback mutation, and external/unowned recovery metadata. |
| Preserve valid directory, target-root, deterministic/no-op and rollback behavior | Explicit directory-root alias lifecycle, missing ordinary target creation, deterministic plans, rendered no-op, first/update rollback, compensation and retry controls pass. |
| Preserve specialized guards and no-force boundaries | All 38 continuity and 22 gitignore tests pass, including leaf/parent/internal aliases, non-directory parents, authored-content preservation, explicit adoption, drift refusal, byte-exact rollback and approval binding. No generic overwrite path was added. |

The [generic tests](../../tests/test_materialization.py),
[continuity tests](../../tests/test_continuity_materialization.py) and
[gitignore tests](../../tests/test_gitignore_materialization.py) retain the
individual regression names and assertions.

## Issue #70 acceptance

| Criterion | Executed evidence |
| --- | --- |
| Enforce complete grammar before semantic output | The 63-case corpus covers required/closed fields, identity syntax, collection/item types and preservation grammar; the resolver produces no result for malformed grammar. |
| Public CLI/schema parity, stable refusals and no mutation | The added public-entry regression compares both CLI outcomes with an independent Draft 2020-12 validator; invalid output sentinels and consumer bytes remain unchanged. The original combined missing-identity/string-preserve case also exercises materialization planning without creating a plan or changing its consumer. |
| Preserve valid examples and semantic constraints | All nine committed examples resolve byte-identically twice through the public CLI. Existing required-capability, ordering, conflict/cycle, security-floor and immutable/transitive/ADR-pin tests pass. |
| Do not reinterpret malformed safety fields | String/invalid preservation collections, unsafe path spellings and malformed identities remain rejected; accepted literal paths retain directory suffixes, spaces and Unicode. |
| Make the dependency strategy explicit | [The foundation contract](../foundation-contract.md#manifest-grammar) documents the schema-driven standard-library evaluator, supported-keyword boundary and fail-closed expansion rule. The unsupported-schema regression passes; `jsonschema` remains test-only. |

The [contract suite](../../tests/test_holon_contract.py) contains the corpus,
independent validator and public CLI assertions. Its successful log includes
the added case; the independent parity check was executed, not skipped.

## Scope and disposition

The local acceptance criteria for both issues are supported. Root review and
integration of this evidence candidate precede explicit issue disposition.
Parent #66, source-delivered #73, navigation #81, continuity activation #42 and
release/distribution #82 retain their separate scopes.

This is Linux local qualification. The Windows-runtime refusal is simulated;
native Windows/junction behavior was not qualified. There is no claim of a
hostile-concurrent-process lock, crash-atomic whole-batch transaction, hosted CI,
released availability, publication, fleet adoption or human ADR approval.

Decision impact: reference existing ADR-0001 manifest ownership and ADR-0005
reversible materialization. This change adds acceptance evidence and one public
CLI regression for their existing boundaries; no new architectural decision is
required. Specialized ADR-0010/ADR-0011 behavior is preserved by its suites.
