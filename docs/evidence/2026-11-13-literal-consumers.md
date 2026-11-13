# Literal consumer qualification — 2026-11-13 UTC

Issue: [#73](https://github.com/egohygiene/holon/issues/73), parent [#66](https://github.com/egohygiene/holon/issues/66).
The [machine-readable evidence](2026-11-13-literal-consumers.json) preserves exact
sources, tool versions, commands, hashes, criteria and the clean browser receipt.

The existing serialization/static-insertion fixes preserve the accepted values.
Actual generated-consumer execution exposed one remaining production defect:
LaunchKit rendered with `renderToStaticMarkup`, while its browser client calls
`hydrateRoot`. Adjacent server text lacks the boundaries required for hydration,
and a real production browser reported React error 418 on first load and reload.
Changing only the actual generated server entry to `renderToString` eliminated
the mismatch. The canonical template now makes that correction.

This candidate also adds the opt-in
[`check_literal_consumer_fixtures.py`](../../tools/check_literal_consumer_fixtures.py)
qualification command. It uses real generated applications and React's real
serializer and bundles. Its optional browser mode requires an existing Python
Playwright/Chromium installation; neither enters generated dependencies.

## Acceptance mapping

| #73 criterion | Actual evidence |
| --- | --- |
| JSON serialization/value roundtrip | Both built web manifests parse back to the exact title and description. |
| Literal HTML text and attributes | Parsed emitted HTML and actual browser DOM preserve quotes, apostrophes, ampersands, angle brackets, backslashes and Unicode; injected-looking text produces no `x-lit` element. |
| Exact static insertion | Real LaunchKit SSR preserves `$&`, dollar-backtick, dollar-apostrophe and `$$`; exactly one root/main remains and the old fallback is absent. |
| Real consumers/build/serve/hydration/determinism | Generic and two canonical LaunchKit pilots pass their required full checks, previews and repeat builds. The two literal variants additionally pass actual Chromium React attachment, reload, no-JS content and LaunchKit hydration, with two byte-identical builds each. |
| Coherent inventories and dependent hashes | LaunchKit overlay inventory, dependent site-suite profile digest and actual OptiFlow HTML snapshot are refreshed and validated. Generic source, stylesheets and Mantle output are unchanged. |

The final literal run starts from clean functional source
`298e26ad13339e678eee9b40e1179d1c25fb8148` after rebasing onto actual main
`bfa61f74a491cb621953d38b03da5bdc46da3e28`. Its original UTC clocks remain
`23:45:08.662535`–`23:45:29.665498`. Later evidence/continuity edits do not change
the qualified runtime, template, inventories, snapshots or qualifier.

## Reproduce

Use Node 24.21.0 and the declared pnpm 11.24.0. Browser qualification here used
Python Playwright 1.62.0 and installed Chromium 151.0.7922.173. Existing helpers
use frozen locks and ignore install scripts; generated `pnpm check` remains
format, lint, types, unit tests and production build, with strict budgets.

```sh
python3 tools/react_vite_blueprint.py
python3 tools/launchkit_blueprint.py
python3 tools/site_suite_blueprint.py
python3 -m unittest discover --start-directory tests --pattern 'test_*blueprint.py' --verbose
python3 tools/check_react_vite_fixture.py
python3 tools/check_launchkit_fixtures.py

literal_workspace=$(mktemp -d)
python3 tools/check_literal_consumer_fixtures.py \
  --work-directory "${literal_workspace}/consumers" \
  --receipt "${literal_workspace}/receipt.json" --browser
```

All 45 focused blueprint tests pass. Existing canonical helpers ran at the
source boundaries stated in the JSON; the final literal receipt binds its exact
clean functional source. The opt-in tool retains generated consumers for review
and refuses to overwrite an existing working directory. An omitted `--browser`
records browser checks as not run.

## Findings and scope

The generic browser's automatic, undeclared `/favicon.ico` request returns 404.
The first local harness treated it as gating; the final qualifier retains only
that exact request as a finding and still fails every application runtime or
other console error. LaunchKit's local consumer-owned icon avoids unrelated
external identity requests. Final application/hydration errors are empty; no
request interception or certificate bypass is used.

This is local HTTP preview and Chromium/Linux fixture qualification. It grants
no public deployment, release/distribution, full accessibility, physical-device
or other-browser acceptance. Minimal Aether projection fixtures isolate the
materializer path and do not establish released/native Aether qualification.
Issue disposition remains with root after peer and integration. Issues #67/#70
are already closed; broader navigation is #81 and parent #66 stays open.

ADR not required: this repairs hydration within the existing LaunchKit React
rendering design and adds a bounded qualification command; no ownership,
dependency or architecture boundary changes.
