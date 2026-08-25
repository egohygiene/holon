#!/usr/bin/env node

import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

import { escapeHtml, renderRepositoryIntelligence } from "../src/render.js";

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function usage() {
  return `Usage: eh-repository-intelligence-render --input <snapshot.json> --output <index.html> [options]

Options:
  --input       Observatory repository read-model JSON
  --output      Static HTML destination
  --title       Optional document title
  --home-url    Breadcrumb destination (default: ./)
  --help        Show this help
`;
}

const { values } = parseArgs({
  options: {
    input: { type: "string" },
    output: { type: "string" },
    title: { type: "string" },
    "home-url": { type: "string", default: "./" },
    help: { type: "boolean", short: "h" },
  },
  strict: true,
});

if (values.help) {
  process.stdout.write(usage());
  process.exit(0);
}
if (!values.input || !values.output) {
  process.stderr.write(usage());
  process.exit(2);
}

const inputPath = resolve(values.input);
const outputPath = resolve(values.output);
const snapshot = JSON.parse(await readFile(inputPath, "utf8"));
const css = await readFile(resolve(PACKAGE_ROOT, "src/repository-intelligence.css"), "utf8");
const documentTitle = values.title ?? `${snapshot.repository?.title ?? "Repository"} · Intelligence`;
const body = renderRepositoryIntelligence(snapshot, {
  title: values.title,
  homeUrl: values["home-url"],
  mode: "static",
});
const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark light">
  <title>${escapeHtml(documentTitle)}</title>
  <style>${css}</style>
</head>
<body>${body}</body>
</html>
`;
await writeFile(outputPath, html, "utf8");
process.stdout.write(`Rendered ${inputPath} to ${outputPath}\n`);
