# Repository Intelligence component architecture

## Outcome

Holon owns a reusable presentation boundary for repository plans, architectural
decisions, delivery history, current state, and linked evidence. Relay may
publish the resulting experience, but neither Relay nor this package must copy
Observatory's normalization or query logic.

```text
Hygiene / ADR / Git / issue / CI evidence
                  ↓
     Observatory normalized read model
                  ↓ immutable versioned contract
   Holon static-first component renderers
          ↙                 ↘
  Relay /intelligence        fixture or other host
  /roadmap /decisions        static HTML export
  /journey
```

## Package layers

| Layer | Responsibility |
| --- | --- |
| Model helpers | Validate the view boundary, preserve state vocabulary, derive display-only progress, group chapters, filter events, and calculate virtual windows. |
| Pure renderers | Escape untrusted content and emit semantic HTML for the shell, roadmap, decision chain, journey, evidence drawers, summary cards, comparison, and shared cognitive states. |
| DOM controller | Add search, state/kind filters, time controls, keyboard navigation, active-section state, long-history virtualization, and Identity token projection. |
| Static CLI | Combine the pure renderer and scoped stylesheet into a complete no-JavaScript HTML document. |
| Fixture lab | Prove small, large, stale, blocked, and partially adopted repositories without depending on Relay. |

The pure renderer is the stable integration seam. Framework adapters should
mount or wrap it rather than fork component internals.

## Navigation model

The shell keeps all primary views on one vertically scrollable page. A sticky
view bar moves among Now, Roadmap, Decisions, Journey, and Evidence. The roadmap
adds a sticky quest minimap on wide screens and a horizontally scrollable compact
map on small screens. Each quest and decision uses a stable fragment ID so the
dashboard, issues, and other intelligence pages can deep-link into the story.

## Evidence and cognition

- Roadmap progress is derived only from explicit complete states and exit
  criteria; commit count never determines completion.
- The decision chain is historical lineage, not a blockchain or an immutability
  claim. Accepted, proposed, rejected, deprecated, and superseded states stay
  visible.
- Git journey chapters are supplied by Observatory as semantic epochs. Commits
  appear alongside issues, pull requests, checks, releases, deployments, and
  roadmap transitions.
- Empty, loading, stale, unknown, error, partial, and not-applicable states use
  one shared component and never masquerade as success.

## Long-history behavior

Interactive chapters with more than 60 events render a fixed-row virtual window
with four rows of overscan. Spacer geometry preserves scroll height and position.
Time and evidence filters recompute the window without loading provider data.
Static export renders every event because completeness is more important than
browser optimization when JavaScript is absent.

## Accessibility contract

The DOM remains useful without enhancement. All controls have labels, evidence
drawers are native `details` elements, search result counts use a live `output`,
and virtual rows expose list position and size. Primary information is repeated
in text and structure rather than encoded by color, animation, or spatial
position. The stylesheet contains mobile, reduced-motion, increased-contrast,
forced-colors, and print projections.

## Sibling contract provenance

The renderer targets Observatory commit
`3cb3555f56b9b110e98e295c1201e8d9af641297`. The lock under `contracts/`
records the exact golden fixture hashes used while designing and testing this
package. Updating the pin requires fixture compatibility tests and an explicit
contract review.
