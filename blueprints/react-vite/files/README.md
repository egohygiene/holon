# {{parameter.site_title}}

{{parameter.site_description}}

This site is materialized from the versioned Holon React/Vite foundation. Its
application shell is deliberately generic: product identity enters through
reviewed semantic tokens, and LaunchKit presentation remains a separate Holon
blueprint.

## Develop

Use the package-manager version declared in `package.json`:

```sh
corepack enable
pnpm install --frozen-lockfile
pnpm dev
```

Run the same bounded validation locally and in CI:

```sh
pnpm check
```

The command checks deterministic formatting/import organization, native
JavaScript/TypeScript lint diagnostics, strict TypeScript, unit and
accessibility smoke tests, and the production build. The
`egolint.javascript-package-quality.json` manifest also selects Egolint's
canonical React package-quality policy; Relay or another consumer should invoke
that Egolint contract rather than copying its rules into this repository.

## Publication boundary

- Vite emits static files beneath `dist/` using the configured base path.
- The build writes `dist/404.html` for static-host route fallback.
- Canonical URL and metadata are build-time source, not runtime mutation.
- Identity remains the source of brand tokens and assets.
- Agent-Ready Web, legal, documentation, and deployment capabilities compose
  through their owning Holon/Relay profiles.
- Storybook, package publication, and LaunchKit are not baseline dependencies.
