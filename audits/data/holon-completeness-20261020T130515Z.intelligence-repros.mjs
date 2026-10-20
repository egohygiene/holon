#!/usr/bin/env node
// Synthetic, local-only audit reproductions. No network or repository mutation.
import { mkdtemp, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import { spawnSync } from "node:child_process";

const { values } = parseArgs({ options: { repository: { type: "string" } }, strict: true });
if (!values.repository) throw new Error("Pass --repository /path/to/holon-checkout");
const repository = resolve(values.repository);
const source = pathToFileURL(join(repository, "packages/repository-intelligence/src/index.js"));
const fixtures = pathToFileURL(join(repository, "examples/repository-intelligence/fixtures.mjs"));
const api = await import(source.href);
const { createScenario } = await import(fixtures.href);

const releaseSnapshot = createScenario("small");
const releasePrototype = releaseSnapshot.views.releases.releases[0];
releaseSnapshot.views.releases.releases = [
  ["v10.0.0", "2026-08-20T10:00:00Z"],
  ["v9.0.0", "2026-07-20T10:00:00Z"],
].map(([key, publishedAt]) => ({
  ...structuredClone(releasePrototype),
  entity: {
    ...structuredClone(releasePrototype.entity),
    id: `ri:egohygiene/relay:release:${key}`,
    key,
    title: `Synthetic release ${key}`,
    canonical_url: `https://github.com/egohygiene/relay/releases/tag/${key}`,
  },
  published_at: publishedAt,
}));
const releaseSummary = api.renderSummary(releaseSnapshot);
const releaseCard = releaseSummary
  .split('<span class="ehri-metric__label">Latest release</span>')[1]
  .split("</article>")[0];

const payload = '<span data-holon-audit="health-count">SYNTHETIC_AUDIT_MARKUP</span>';
const snapshot = createScenario("small");
const baselineErrors = api.validateRepositoryIntelligence(snapshot);
snapshot.views.health.check_states.success = payload;
const invalidCountErrors = api.validateRepositoryIntelligence(snapshot);
const html = api.renderRepositoryIntelligence(snapshot);
const tempRoot = await mkdtemp(join(tmpdir(), "holon-intelligence-audit-"));
let cli;
try {
  const input = join(tempRoot, "input.json");
  const output = join(tempRoot, "output.html");
  await writeFile(input, JSON.stringify(snapshot), "utf8");
  const result = spawnSync(process.execPath, [
    join(repository, "packages/repository-intelligence/bin/render-static.mjs"),
    "--input", input, "--output", output,
  ], { encoding: "utf8" });
  const resultHtml = result.status === 0 ? await readFile(output, "utf8") : "";
  cli = {
    exit_code: result.status,
    raw_synthetic_markup_in_output: resultHtml.includes(`<strong>${payload}</strong>`),
  };
} finally {
  await rm(tempRoot, { recursive: true, force: true });
}

// A minimal DOM seam, not a browser/layout/a11y test. The null-theme failure
// occurs before queries/listeners; the explicit-theme control completes mount.
class AuditElement {
  constructor() {
    this.dataset = {};
    this.style = { setProperty() {} };
    this.isConnected = false;
    this.innerHTML = "";
  }
  querySelectorAll() { return []; }
  querySelector() { return null; }
  addEventListener() {}
  removeEventListener() {}
  removeAttribute(name) { if (name === "data-ehri-enhanced") delete this.dataset.ehriEnhanced; }
}
globalThis.Element = AuditElement;
globalThis.HTMLElement = AuditElement;
globalThis.document = { activeElement: null };
const definitions = new Map();
globalThis.customElements = {
  get(name) { return definitions.get(name); },
  define(name, value) { definitions.set(name, value); },
};
const Adapter = api.defineRepositoryIntelligenceElement("holon-audit-intelligence");
const element = new Adapter();
element.snapshot = createScenario("small");
element.isConnected = true;
let defaultFailure = null;
try { element.connectedCallback(); } catch (error) {
  defaultFailure = { name: error.name, message: error.message };
}
let explicitThemeFailure = null;
try { element.theme = {}; } catch (error) {
  explicitThemeFailure = { name: error.name, message: error.message };
}

process.stdout.write(JSON.stringify({
  source_revision: "a7734dba83305276b12932fcd4ce348044d9a2e9",
  runtime: { node: process.version },
  latest_release: {
    input_release_order: releaseSnapshot.views.releases.releases.map((entry) => ({
      key: entry.entity.key,
      published_at: entry.published_at,
    })),
    validation_errors: api.validateRepositoryIntelligence(releaseSnapshot),
    expected_latest_key: "v10.0.0",
    rendered_latest_key: releaseCard.match(/<strong>(.*?)<\/strong>/)[1],
    limits: "Synthetic releases match the pinned producer's observed entity-ID sort, not publication-date order. Exact producer generation was separately qualified; this portable reproduction isolates Holon's rendering assumption.",
  },
  health_count_markup: {
    synthetic_case: "String-valued health.check_states.success passes public validation and enters raw HTML",
    baseline_validation_errors: baselineErrors,
    invalid_count_validation_errors: invalidCountErrors,
    raw_synthetic_markup_in_renderer: html.includes(`<strong>${payload}</strong>`),
    escaped_synthetic_markup_in_renderer: html.includes(api.escapeHtml(payload)),
    cli,
    limits: "No scripts were executed and no site was published. Payload is inert synthetic markup; malformed producer input is required.",
  },
  custom_element_default_theme: {
    default_theme_error: defaultFailure,
    explicit_empty_theme_error: explicitThemeFailure,
    explicit_empty_theme_mount_completed: explicitThemeFailure === null && element.dataset.ehriEnhanced === "true",
    limits: "Minimal DOM seam proves public adapter call path and optional-theme failure; it does not prove browser layout or assistive-technology behavior.",
  },
}, null, 2) + "\n");
