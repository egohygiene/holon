# Repository Intelligence components

`@egohygiene/repository-intelligence` turns Observatory's versioned repository
read model into a navigable roadmap, decision lineage, delivery journey, and
evidence surface. It has no runtime dependencies and owns no provider or query
logic.

## Consume from a browser surface

Load the stylesheet once, then mount the component into any DOM element:

```js
import {
  mountRepositoryIntelligence,
} from "@egohygiene/repository-intelligence";
import "@egohygiene/repository-intelligence/styles.css";

const controller = mountRepositoryIntelligence(
  document.querySelector("#intelligence"),
  {
    snapshot,
    comparison,
    theme: identityTheme,
    homeUrl: "/intelligence/",
  },
);
```

The same API can be wrapped by React, Vue, Svelte, or another framework. A
custom-element adapter is available through
`defineRepositoryIntelligenceElement()` when property-based integration is a
better fit.

```js
import { defineRepositoryIntelligenceElement } from "@egohygiene/repository-intelligence";

defineRepositoryIntelligenceElement();
const element = document.createElement("eh-repository-intelligence");
element.snapshot = snapshot;
document.querySelector("#intelligence").append(element);
```

No theme property is required. Snapshot/theme changes rerender while connected;
disconnect removes listeners and adapter-owned theme overrides, and reconnect
mounts the current properties again.

## Render a no-JavaScript page

The static renderer emits one complete HTML document with the component CSS
inlined:

```bash
node packages/repository-intelligence/bin/render-static.mjs \
  --input "repository-intelligence.json" \
  --output "dist/roadmap/index.html" \
  --home-url "/intelligence/"
```

Static output keeps native links, headings, landmarks, lists, and expandable
`details` evidence. Interactive mounting adds search, filters, time controls,
active navigation, keyboard shortcuts, and virtualized long journey chapters.

## Contract boundary

The renderer consumes:

- `egohygiene.observatory.repository-intelligence-read-model/v1`; and
- optionally `egohygiene.observatory.repository-intelligence-compare/v1`.

The immutable source pin and golden-fixture hashes live in
`contracts/observatory-repository-intelligence.v1.lock.json`. A renderer change
must not infer provider state, calculate readiness, redact visibility, or replace
Observatory's normalized query views.

## Identity theming

CSS first resolves `--identity-*` semantic properties and then falls back to the
reference theme. JavaScript consumers may pass the allowlisted token object
defined by `schemas/repository-intelligence-theme.v1.schema.json`. State meaning
is never carried by color alone.

Omitted, `undefined`, `null` and empty `{}` themes all select the CSS fallback
without JavaScript overrides. A flat token map or a theme's `tokens` object
supplies allowlisted overrides; other names and unsafe CSS values are ignored.
Each application replaces the previous adapter-owned overrides, so clearing a
theme or omitting a previously selected token restores the prior inline value
or CSS cascade. Existing inline values/priorities and later consumer edits are
preserved when the adapter releases its own overrides. These runtime empty-theme
semantics do not change the schema for a named, nonempty theme artifact.

## Accessibility and performance

- Native landmarks, headings, links, lists, `details`, labels, and live output.
- Arrow, Home, and End navigation across the sticky view navigation; `/` focuses
  search and Escape clears it.
- Responsive single-column layouts, high-contrast and forced-color support,
  reduced-motion support, and print expansion.
- Interactive journey chapters virtualize above 60 events with stable fixed
  row geometry and overscan. Static rendering remains complete.
