# Documentation surfaces

Holon owns this Zensical configuration and rendering adapter. Repository owners
provide `site_suite_content`, product metadata, and reviewed Identity inputs in
their foundation manifest; they do not fork the generated theme internals.

Create an isolated environment and install the reviewed lock:

```sh
python3 -m venv ".venv"
".venv/bin/python" -m pip install \
  --require-hashes \
  --requirement "site-docs/requirements.lock.txt"
```

Validate or build all three durable surfaces:

```sh
".venv/bin/python" site_docs.py validate
".venv/bin/python" site_docs.py build
```

Preview the standalone documentation artifact:

```sh
".venv/bin/python" site_docs.py preview --port 8000
```

Zensical renders documentation. Identity remains canonical for tokens/assets,
Hygiene and the consumer remain canonical for architecture, legal sources stay
with their policy owners, and Relay owns publication and rollback.
