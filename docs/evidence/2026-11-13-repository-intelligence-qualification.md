# Repository Intelligence local qualification — 2026-11-13

This checkpoint qualifies the existing implementations for [#77](https://github.com/egohygiene/holon/issues/77), [#78](https://github.com/egohygiene/holon/issues/78) and [#79](https://github.com/egohygiene/holon/issues/79). It does not replace the immutable 2026-10-20 audit or add another renderer.

`node --test tests/javascript/repository-intelligence.test.mjs` passed **32 tests, zero failures/skips** with Node **24.19.0** on Linux. The public static CLI ran only against disposable synthetic/owner fixtures. The mounted adapter checks use the existing minimal DOM seam, which does not emulate HTML parsing, layout or certify browser accessibility.

## #77 — consumed health counters

The public validator rejects strings, markup, booleans, null, objects, arrays, negatives, fractional/nonfinite values and unsafe integers. Zero through MAX_SAFE_INTEGER, empty/absent counter maps and partial owner views remain compatible. Defensive lower-level text escaping remains independent of shape admission. The actual static CLI rejects the inert markup fixture without creating output, and the public mount now explicitly proves denial before existing consumer markup/listeners change. Tests: `health counters reject malformed types and numbers`, `health counter boundaries`, `details rendering escapes counter text`, `static CLI rejects an inert markup counter`, `public mount rejects malformed counters`.

## #78 — optional theme and custom-element lifecycle

Existing public adapter tests cover absent/null/empty theme forms, supported token overrides, prior consumer-owned inline style restoration, direct mount/update/destroy, snapshot-only custom element connection, controls/listeners/navigation, snapshot/theme changes, disconnect and reconnect. They execute the public adapter through the DOM seam; pure string rendering alone is not used as lifecycle proof. No framework or mandatory runtime dependency was added. Tests: `optional theme forms`, `direct mounting accepts absent/null/empty themes`, `snapshot-only custom element initializes controls and survives reconnect`.

## #79 — display-only release chronology

Tests cover both v9/v10 permutations, missing/invalid/calendar/offset timestamps, epoch zero, fractional precision and deterministic equal-time entity-ID ties. The owner array is unchanged. Static and interactive pure output agree, the public mounted adapter now explicitly agrees with the static summary/link, and the actual static CLI preserves the selected release URL. No semantic-version priority, provider readiness or release-policy inference is added. Tests: `latest release follows publication time`, `latest release preserves unknown`, `publication offsets`, `static CLI retains the selected publication link`, `mounted release summary agrees`.

## Exact upstream compatibility

`tests/fixtures/repository-intelligence/observatory-3cb3555-relay.repository.json` is copied byte-for-byte from Observatory **3cb3555f56b9b110e98e295c1201e8d9af641297**, path `fixtures/expected/egohygiene--relay.repository.json`. SHA256 is **5cf5bae721381ae5f011262a885bd264f767dc39cd859123903fab80afec8a5d**, matching the existing sibling lock. The new acceptance test checks that hash, validates this actual owner golden view and exercises pure rendering, mounted controls/summary and the public static CLI. Existing lock, dependency budget, timezone determinism and markup/CSS regressions also pass.

Local source/DOM/CLI evidence does not establish a real browser/site, provider freshness, hosted CI, fleet adoption, publication or human approval. Identity/Observatory contract pins and all existing ADR dispositions remain unchanged.
