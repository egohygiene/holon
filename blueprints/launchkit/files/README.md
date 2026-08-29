# {{parameter.site_title}}

{{parameter.site_description}}

This landing site is materialized from Holon's LaunchKit profile, an ordered
overlay on the canonical React/Vite foundation. Product content comes from the
`launchkit_content` object in the foundation manifest; generated component and
style internals are not consumer-owned template forks.

## Develop

```sh
corepack enable
pnpm install --frozen-lockfile
pnpm dev
```

Run the same bounded quality sequence used by CI:

```sh
pnpm check
```

The build produces full semantic HTML before progressively hydrating it. It
also writes the static-host fallback, enforces JavaScript/CSS/HTML budgets, and
retains the generic foundation's format, lint, cycle, type, and test gates.

## Composition boundaries

- Identity owns the semantic stylesheet, favicon, social image, and optional
  project artwork supplied through the manifest.
- Zensical documentation remains a linked sibling surface rather than a React
  implementation copied into this landing profile.
- Policy, trust, and Agent-Ready Web routes enter through their dedicated Holon
  contracts as those issues land.
- Relay owns publication workflow behavior; Egolint owns quality policy.
- `THIRD_PARTY_NOTICES.md` records the exact Evil Martians LaunchKit reference.
