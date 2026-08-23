# React/Vite dependency policy

Status: accepted  
Contract: [`catalog/react-vite-dependencies.json`](../catalog/react-vite-dependencies.json)  
Schema: [`schemas/react-vite-dependency-policy.v1.schema.json`](../schemas/react-vite-dependency-policy.v1.schema.json)  
Last verified: 2026-08-23

## Purpose

Holon's React/Vite foundation should begin with platform capabilities and add dependencies only when a declared capability has a concrete use case. A package appearing in an upstream template is not sufficient reason to put it into every generated site.

The canonical machine-readable policy separates browser runtime dependencies from Node-side build and CLI dependencies, records reviewed versions and evidence, and gives future blueprints a deterministic input rather than a copied package list.

## Decisions

| Candidate | Boundary | Decision | Baseline replacement |
| --- | --- | --- | --- |
| Chalk | Node CLI/build tooling | Optional | Plain output or minimal project-owned ANSI formatting |
| source-map-support | Node runtime | Reject | Native Node source-map support |
| Visibility.js | Browser runtime | Reject | Native Page Visibility API plus a small React hook when useful |

None of these candidates is a default React/Vite dependency.

### Chalk

**Decision: optional, capability-gated.**

Chalk is a good fit when a Holon-generated Node CLI genuinely benefits from styled terminal diagnostics. The current reviewed release is Chalk `6.0.0`; upstream declares it ESM, MIT licensed, zero-runtime-dependency, and compatible with Node `>=22`.

It must not be imported into browser runtime code and it must not become default weight merely because a site blueprint has Node-based tooling. A future `node-cli-rich-output` consumer may add the exact reviewed version only when it has a focused fixture covering color-enabled, color-disabled, and non-interactive output.

Supply-chain history matters here. Upstream release notes identify Chalk `5.6.1` as vulnerable and `5.6.2` as the fix. This is not a reason to reject Chalk permanently; it is evidence for exact reviewed versions, frozen lockfiles, dependency review, and explicit major-version revalidation.

Sources:

- https://github.com/chalk/chalk
- https://github.com/chalk/chalk/releases
- https://www.npmjs.com/package/chalk

### source-map-support

**Decision: reject for the modern Node baseline.**

The upstream project itself documents that Node `>=12.12.0` normally does not require the package because Node provides `--enable-source-maps`. Current Node also exposes `module.setSourceMapsSupport()` for programmatic control; Node documentation recommends the CLI flag when source maps should be enabled before modules load.

The reviewed npm version is `0.5.21`, MIT licensed, with two runtime dependencies, and the package has not needed a normal npm release in several years. Adding it to a modern React/Vite foundation would therefore duplicate a platform capability.

A future exception may reopen the decision only for a demonstrated compatibility gap, such as a required `vm.runInThisContext` path that the supported Node version cannot satisfy natively. The exception must remain capability-specific instead of changing the universal baseline.

Sources:

- https://github.com/evanw/node-source-map-support
- https://www.npmjs.com/package/source-map-support
- https://nodejs.org/api/cli.html#--enable-source-maps
- https://nodejs.org/api/module.html

### Visibility.js

**Decision: reject for modern browser targets.**

Visibility.js `2.0.2` is an MIT-licensed wrapper from the browser-prefix/polyfill era. The repository's release is from 2018; the most recent later repository change observed during this review was a typings fix in 2024.

The underlying Page Visibility API is now a standard web-platform capability. MDN classifies it as Baseline Widely available and notes cross-browser availability since July 2015. The platform exposes `document.visibilityState`, `document.hidden`, and the `visibilitychange` event directly.

When React ergonomics benefit from an abstraction, prefer a tiny project-owned hook around those primitives. That keeps behavior testable without adding a compatibility library whose legacy-browser purpose is outside the intended baseline.

Sources:

- https://github.com/ai/visibilityjs
- https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API
- https://developer.mozilla.org/en-US/docs/Web/API/Document/visibilityState

## Blueprint integration

Issue #14 should consume the policy contract rather than copying this prose into a package manifest.

The initial React/Vite foundation should therefore resolve these candidate groups as:

```text
browser runtime:
  no dependency from this candidate set

Node runtime/build:
  no dependency from this candidate set

optional capability:
  node-cli-rich-output -> Chalk only after the capability is implemented and tested
```

The policy does not choose the complete Node, pnpm, React, Vite, testing, linting, or Storybook stack. Those remain owned by their corresponding blueprint and Egolint decisions. This contract only prevents these evaluated utilities from becoming unexplained baseline weight.

## Supply-chain rules

For any package admitted by this or a later revision:

1. Record the reviewed version and license.
2. Keep browser and Node dependency classes separate.
3. Use an exact reviewed version in the generated dependency manifest and a frozen lockfile for installation.
4. Review transitive dependencies and material security history.
5. Revalidate a candidate before a major-version upgrade.
6. Keep rejected or optional packages out of the default dependency sets.
7. Require a concrete fixture/use case before changing an optional package to adopted baseline status.

## Validation

Run the policy validator directly:

```bash
python3 tools/react_vite_dependency_policy.py \
  --policy "catalog/react-vite-dependencies.json"
```

Run the repository's standard-library test suite:

```bash
python3 -m unittest discover \
  --start-directory "tests" \
  --pattern "test_*.py" \
  --verbose
```

The tests protect the candidate set, platform-first alternatives, Node/browser separation, Chalk's capability gate, and the reviewed supply-chain policy.

## Reconsideration triggers

Revisit this decision when any of the following becomes true:

- the supported Node floor changes materially;
- a candidate publishes a major version that changes its architecture or dependency footprint;
- the supported browser policy intentionally includes targets without the standard Page Visibility API;
- a real generated Node CLI needs terminal styling;
- a reproducible source-map defect demonstrates that native Node support is insufficient;
- security or maintenance evidence materially changes a candidate's risk profile.

Until one of those conditions is demonstrated, the smallest correct baseline is the preferred baseline.
