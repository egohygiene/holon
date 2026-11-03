import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

import {
  COMPARISON_SCHEMA,
  REPOSITORY_INTELLIGENCE_SCHEMA,
  collectEvidence,
  computeVirtualWindow,
  escapeHtml,
  eventsByChapter,
  filterEvents,
  renderEvidenceDrawer,
  renderDetails,
  renderRepositoryIntelligence,
  renderStatePanel,
  roadmapProgress,
  safeHref,
  validateComparison,
  validateRepositoryIntelligence,
} from "../../packages/repository-intelligence/src/index.js";
import {
  createComparison,
  createScenario,
  scenarioNames,
} from "../../examples/repository-intelligence/fixtures.mjs";

const ROOT = resolve(import.meta.dirname, "../..");
const CSS_PATH = resolve(
  ROOT,
  "packages/repository-intelligence/src/repository-intelligence.css",
);

test("all story fixtures satisfy the framework-neutral view boundary", () => {
  assert.deepEqual(scenarioNames, ["small", "large", "stale", "blocked", "partial"]);
  for (const name of scenarioNames) {
    const snapshot = createScenario(name);
    assert.equal(snapshot.schema, REPOSITORY_INTELLIGENCE_SCHEMA);
    assert.deepEqual(validateRepositoryIntelligence(snapshot), [], name);
  }
});

test("health counters reject malformed types and numbers at the public boundary", () => {
  for (const value of [
    '<span data-counter="inert">example</span>', "1", true, null, {}, [],
    -1, 0.5, NaN, Infinity, -Infinity, Number.MAX_SAFE_INTEGER + 1,
  ]) {
    const snapshot = createScenario("small");
    snapshot.views.health.check_states = { success: value };
    assert.deepEqual(validateRepositoryIntelligence(snapshot), [
      'views.health.check_states["success"] must be a nonnegative safe integer',
    ]);
    assert.throws(() => renderRepositoryIntelligence(snapshot), /nonnegative safe integer/);
  }
  for (const value of [null, [], "invalid"]) {
    const snapshot = createScenario("small");
    snapshot.views.health.check_states = value;
    assert.deepEqual(validateRepositoryIntelligence(snapshot), [
      "views.health.check_states must be an object of counters",
    ]);
  }
});

test("health counter boundaries and partial views preserve numeric output", () => {
  for (const count of [0, 1, Number.MAX_SAFE_INTEGER]) {
    const snapshot = createScenario("small");
    snapshot.views.health.check_states = { success: count };
    assert.deepEqual(validateRepositoryIntelligence(snapshot), []);
    assert.ok(renderRepositoryIntelligence(snapshot).includes(`<strong>${count}</strong>`));
  }
  const partial = createScenario("partial");
  delete partial.views.health.check_states;
  assert.deepEqual(validateRepositoryIntelligence(partial), []);
  assert.doesNotThrow(() => renderRepositoryIntelligence(partial));
});

test("details rendering escapes counter text even without the high-level validator", () => {
  const snapshot = createScenario("small");
  snapshot.views.health.check_states = { unknown: '<span data-counter="inert">example</span>' };
  const html = renderDetails(snapshot);
  assert.doesNotMatch(html, /<span data-counter="inert">/);
  assert.match(html, /&lt;span data-counter=&quot;inert&quot;&gt;example&lt;\/span&gt;/);
});

test("static CLI rejects an inert markup counter without producing an output file", async () => {
  const directory = await mkdtemp(join(tmpdir(), "ehri-counter-"));
  try {
    const snapshot = createScenario("small");
    snapshot.views.health.check_states = { success: '<span data-counter="inert">example</span>' };
    const input = join(directory, "input.json");
    const output = join(directory, "output.html");
    await writeFile(input, JSON.stringify(snapshot), "utf8");
    const result = spawnSync(process.execPath, [
      resolve(ROOT, "packages/repository-intelligence/bin/render-static.mjs"),
      "--input", input, "--output", output,
    ], { cwd: ROOT, encoding: "utf8" });
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /views\.health\.check_states/);
    assert.doesNotMatch(result.stdout + result.stderr, /data-counter="inert"/);
    await assert.rejects(readFile(output), { code: "ENOENT" });
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("fixture creation is isolated across stories", () => {
  const blocked = createScenario("blocked");
  const small = createScenario("small");
  assert.equal(blocked.views.roadmap.steps[2].entity.state, "blocked");
  assert.equal(small.views.roadmap.steps[0].entity.state, "complete");
  assert.equal(createScenario("blocked").views.roadmap.steps[2].entity.state, "blocked");
});

test("roadmap progress uses explicit completion instead of commit volume", () => {
  const snapshot = createScenario("blocked");
  const progress = roadmapProgress(snapshot);
  assert.deepEqual(progress, {
    total: 7,
    complete: 2,
    blocked: 2,
    active: 0,
    ratio: 2 / 7,
    percentage: 29,
  });
});

test("quest evidence deduplicates shared records and preserves relationships", () => {
  const step = createScenario("blocked").views.roadmap.steps[2];
  step.evidence.push(step.tracked_by[0]);
  const evidence = collectEvidence(step);
  assert.equal(evidence.filter(({ entity }) => entity.key === "22").length, 1);
  assert.deepEqual(
    evidence.map(({ relationship }) => relationship),
    ["blocked by", "informed by", "informed by", "depends on"],
  );
});

test("static rendering emits the complete accessible repository story", () => {
  const snapshot = createScenario("blocked");
  const html = renderRepositoryIntelligence(snapshot);
  assert.match(html, /<main id="ehri-main">/);
  assert.match(html, /aria-label="Roadmap minimap"/);
  assert.match(html, /<section[^>]+id="roadmap"/);
  assert.match(html, /<section[^>]+id="decisions"/);
  assert.match(html, /<section[^>]+id="journey"/);
  assert.match(html, /<details class="ehri-evidence"/);
  assert.match(html, /data-state="rejected"/);
  assert.match(html, /data-state="superseded"/);
  assert.match(html, /data-state="blocked"/);
  assert.doesNotMatch(html, /data-intelligence-search/);
  assert.equal((html.match(/class="ehri-event"/g) ?? []).length, 18);

  const interactive = renderRepositoryIntelligence(snapshot, { mode: "interactive" });
  assert.match(interactive, /<label class="ehri-search">/);
  assert.match(interactive, /aria-live="polite"/);
});

test("interactive rendering virtualizes long chapters while static output is complete", () => {
  const snapshot = createScenario("large");
  const interactive = renderRepositoryIntelligence(snapshot, { mode: "interactive" });
  const staticHtml = renderRepositoryIntelligence(snapshot, { mode: "static" });
  const interactiveEvents = (interactive.match(/class="ehri-event"/g) ?? []).length;
  const staticEvents = (staticHtml.match(/class="ehri-event"/g) ?? []).length;
  assert.equal(staticEvents, 640);
  assert.ok(interactiveEvents < 100, `expected fewer than 100 rows, got ${interactiveEvents}`);
  assert.equal((interactive.match(/data-virtual-chapter=/g) ?? []).length, 8);
  assert.match(interactive, /class="ehri-virtual-space"/);
});

test("virtual windows preserve stable scroll geometry", () => {
  const items = Array.from({ length: 10_000 }, (_, index) => index);
  const first = computeVirtualWindow(items, {
    scrollTop: 132 * 500,
    viewportHeight: 528,
    rowHeight: 132,
    overscan: 4,
  });
  const next = computeVirtualWindow(items, {
    scrollTop: 132 * 501,
    viewportHeight: 528,
    rowHeight: 132,
    overscan: 4,
  });
  assert.deepEqual(
    { start: first.start, end: first.end, before: first.before, total: first.totalHeight },
    { start: 496, end: 508, before: 65_472, total: 1_320_000 },
  );
  assert.equal(next.start, first.start + 1);
  assert.equal(next.before - first.before, 132);
  assert.equal(first.items.length, 12);
});

test("journey filtering preserves semantic chapters and explicit time controls", () => {
  const snapshot = createScenario("blocked");
  const chapters = eventsByChapter(snapshot);
  assert.equal(chapters.length, 3);
  const commits = filterEvents(snapshot.views.journey.events, { kind: "commit" });
  assert.equal(commits.length, 1);
  const afterAugust = filterEvents(snapshot.views.journey.events, { from: "2026-08-01" });
  assert.equal(afterAugust.length, 4);
});

test("comparison rendering validates Observatory compare state", () => {
  const snapshot = createScenario("small");
  const comparison = createComparison(snapshot);
  assert.equal(comparison.schema, COMPARISON_SCHEMA);
  assert.deepEqual(validateComparison(comparison, snapshot.repository.key), []);
  const html = renderRepositoryIntelligence(snapshot, { comparison });
  assert.match(html, /Compare state/);
  assert.match(html, /<strong>4<\/strong> total deltas/);
});

test("all cognitive state panels share one semantic primitive", () => {
  for (const state of [
    "empty",
    "stale",
    "unknown",
    "loading",
    "error",
    "not_applicable",
    "partial",
  ]) {
    const html = renderStatePanel(state);
    assert.match(html, new RegExp(`data-state="${state}"`));
    assert.match(html, /role="status"/);
    assert.match(html, /<h3>/);
  }
});

test("renderers escape model content and URLs", () => {
  assert.equal(escapeHtml('<script src="x">&'), "&lt;script src=&quot;x&quot;&gt;&amp;");
  const drawer = renderEvidenceDrawer([
    {
      relationship: "evidence",
      entity: {
        id: "danger",
        kind: "file",
        key: "x",
        title: "<img src=x onerror=alert(1)>",
        state: "unknown",
        canonical_url: 'https://example.test/\" onmouseover=\"alert(1)',
      },
    },
  ]);
  assert.doesNotMatch(drawer, /<img/);
  assert.doesNotMatch(drawer, /onmouseover="alert/);
  assert.match(drawer, /&lt;img/);
  assert.equal(safeHref("javascript:alert(1)"), null);
  assert.equal(safeHref("https://github.com/egohygiene/holon"), "https://github.com/egohygiene/holon");
});

test("rendered fragment links and public evidence links are valid", () => {
  const html = renderRepositoryIntelligence(createScenario("blocked"));
  const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]));
  const fragments = [...html.matchAll(/\shref="#([^"]+)"/g)].map((match) => match[1]);
  for (const fragment of fragments) {
    assert.ok(ids.has(fragment), `missing fragment target: ${fragment}`);
  }
  const hrefs = [...html.matchAll(/\shref="([^"]+)"/g)].map((match) => match[1]);
  for (const href of hrefs) {
    assert.ok(
      href.startsWith("#") || href.startsWith("./") || href.startsWith("/") || href.startsWith("https://"),
      `unsafe or unresolved href: ${href}`,
    );
  }
});

test("responsive and accessibility CSS regressions remain covered", async () => {
  const css = await readFile(CSS_PATH, "utf8");
  for (const contract of [
    "@media (max-width: 58rem)",
    "@media (max-width: 42rem)",
    "@media (prefers-reduced-motion: reduce)",
    "@media (prefers-contrast: more)",
    "@media (forced-colors: active)",
    "@media print",
    ".ehri-minimap",
    ".ehri-journey-track--virtual",
    ":focus-visible",
  ]) {
    assert.ok(css.includes(contract), `missing CSS contract: ${contract}`);
  }
  assert.doesNotMatch(css, /scroll-behavior:\s*smooth/);
});

test("the dependency-free browser package stays inside its reviewed size budget", async () => {
  const files = [
    "controller.js",
    "index.js",
    "model.js",
    "render.js",
    "repository-intelligence.css",
  ];
  const bytes = (
    await Promise.all(
      files.map((file) =>
        readFile(resolve(ROOT, "packages/repository-intelligence/src", file)),
      ),
    )
  ).reduce((total, content) => total + content.byteLength, 0);
  assert.ok(bytes <= 96 * 1024, `package is ${bytes} bytes; budget is 98304 bytes`);
});

test("Identity theme and Observatory locks are explicit and immutable", async () => {
  const theme = JSON.parse(
    await readFile(resolve(ROOT, "catalog/repository-intelligence-theme.json"), "utf8"),
  );
  const lock = JSON.parse(
    await readFile(
      resolve(ROOT, "contracts/observatory-repository-intelligence.v1.lock.json"),
      "utf8",
    ),
  );
  assert.equal(theme.schema, "egohygiene.holon.repository-intelligence-theme/v1");
  assert.equal(lock.source_commit, "3cb3555f56b9b110e98e295c1201e8d9af641297");
  assert.equal(lock.golden_fixture_evidence.length, 3);
  assert.deepEqual(lock.consumed_schemas, [
    REPOSITORY_INTELLIGENCE_SCHEMA,
    COMPARISON_SCHEMA,
  ]);
});

test("static CLI produces a complete self-contained HTML page", async () => {
  const snapshot = createScenario("small");
  const input = join(tmpdir(), `ehri-${process.pid}-input.json`);
  const output = join(tmpdir(), `ehri-${process.pid}-output.html`);
  await writeFile(input, `${JSON.stringify(snapshot)}\n`, "utf8");
  const result = spawnSync(
    process.execPath,
    [
      resolve(ROOT, "packages/repository-intelligence/bin/render-static.mjs"),
      "--input",
      input,
      "--output",
      output,
      "--home-url",
      "/intelligence/",
    ],
    { cwd: ROOT, encoding: "utf8" },
  );
  assert.equal(result.status, 0, result.stderr);
  const html = await readFile(output, "utf8");
  assert.match(html, /^<!doctype html>/);
  assert.match(html, /<style>@layer ehri\.reset/);
  assert.match(html, /href="\/intelligence\/"/);
  assert.match(html, /The quest line/);
  assert.doesNotMatch(html, /<script/);
});

test("static rendering is byte-stable across host timezones", async () => {
  const snapshot = createScenario("small");
  const input = join(tmpdir(), `ehri-${process.pid}-timezone-input.json`);
  const utcOutput = join(tmpdir(), `ehri-${process.pid}-utc.html`);
  const honoluluOutput = join(tmpdir(), `ehri-${process.pid}-honolulu.html`);
  const renderer = resolve(ROOT, "packages/repository-intelligence/bin/render-static.mjs");
  await writeFile(input, `${JSON.stringify(snapshot)}\n`, "utf8");
  for (const [timezone, output] of [
    ["UTC", utcOutput],
    ["Pacific/Honolulu", honoluluOutput],
  ]) {
    const result = spawnSync(
      process.execPath,
      [renderer, "--input", input, "--output", output],
      { cwd: ROOT, encoding: "utf8", env: { ...process.env, TZ: timezone } },
    );
    assert.equal(result.status, 0, result.stderr);
  }
  assert.equal(
    await readFile(utcOutput, "utf8"),
    await readFile(honoluluOutput, "utf8"),
  );
});

test("small fixture markup and component CSS retain reviewed visual snapshots", async () => {
  const html = renderRepositoryIntelligence(createScenario("small"));
  const css = await readFile(CSS_PATH, "utf8");
  const digest = (value) => createHash("sha256").update(value).digest("hex");
  assert.equal(digest(html), "ce389480af6b63898f48b0746cf51d291fed51ec9bdf3ed0b4fe5505ffd91dee");
  assert.equal(digest(css), "ebc865cb28edc74f924ce597355c3c3814361e57efd11796e8a8ff57afd51ab9");
});
