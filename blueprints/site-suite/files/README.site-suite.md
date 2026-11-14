# Holon site-suite composition

This repository composes one independently selectable landing profile with
Zensical documentation, architecture, and legal surfaces. Product teams own
the reviewed manifest content; Holon owns composition and generated internals.

Install the pinned Node and Python graphs, then run the canonical suite check:

```sh
pnpm install --frozen-lockfile --ignore-scripts
python3 -m venv ".venv"
".venv/bin/python" -m pip install \
  --require-hashes \
  --requirement "site-docs/requirements.lock.txt"
".venv/bin/python" site_suite.py check
```

Preview the complete GitHub Pages artifact locally:

The check is repeatable after a build. Renderer-owned `site-docs/.cache` is
excluded from authored-source formatting alongside generated content and build
output; no command reformats or deletes that cache to make a check pass.
Authored source remains subject to the normal formatter and quality gates.

```sh
".venv/bin/python" site_suite.py preview --port 8000
```

Routes are stable: `/` is the selected React/Vite or LaunchKit landing,
`/docs/` is durable documentation, `/architecture/` explains the current
system and decisions, and `/legal/` projects reviewed legal content.

Relay owns publication and rollback. Identity, Hygiene, policy owners,
Egolint, and Pace retain their canonical ecosystem responsibilities.
