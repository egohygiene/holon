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
  applyRepositoryTheme,
  collectEvidence,
  computeVirtualWindow,
  defineRepositoryIntelligenceElement,
  escapeHtml,
  eventsByChapter,
  filterEvents,
  mountRepositoryIntelligence,
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
import { withRepositoryIntelligenceDOM } from "./helpers/repository-intelligence-dom.mjs";

const ROOT = resolve(import.meta.dirname, "../..");
const CSS_PATH = resolve(
  ROOT,
  "packages/repository-intelligence/src/repository-intelligence.css",
);

test("optional theme forms restore only adapter-owned inline overrides", () => {
  withRepositoryIntelligenceDOM(({ Element }) => {
    const root = new Element();
    root.style.setProperty("--ehri-primary", "original", "important");
    root.style.setProperty("--consumer-token", "untouched");
    for (const theme of [undefined, null, {}, { tokens: {} }]) {
      applyRepositoryTheme(root, { tokens: { primary: "#123456", accent: "#654321" } });
      assert.equal(root.style.getPropertyValue("--ehri-primary"), "#123456");
      applyRepositoryTheme(root, theme);
      assert.equal(root.style.getPropertyValue("--ehri-primary"), "original");
      assert.equal(root.style.getPropertyPriority("--ehri-primary"), "important");
      assert.equal(root.style.getPropertyValue("--ehri-accent"), "");
      assert.equal(root.style.getPropertyValue("--consumer-token"), "untouched");
    }
    applyRepositoryTheme(root, { primary: "#123456" });
    root.style.setProperty("--ehri-primary", "consumer-edit");
    applyRepositoryTheme(root, null);
    assert.equal(root.style.getPropertyValue("--ehri-primary"), "consumer-edit");
    applyRepositoryTheme(root, { primary: "bad;value", unknown: "ignored" });
    assert.equal(root.style.getPropertyValue("--ehri-primary"), "consumer-edit");
    assert.equal(root.style.getPropertyValue("unknown"), "");
  });
});

test("direct mounting accepts absent/null/empty themes and cleans up on update", () => {
  withRepositoryIntelligenceDOM(({ Element }) => {
    for (const theme of [undefined, null, {}, { tokens: { primary: "#123456" } }]) {
      const root = new Element();
      const options = { snapshot: createScenario("small") };
      if (theme !== undefined) options.theme = theme;
      const controller = mountRepositoryIntelligence(root, options);
      const oldSearch = root.querySelector("[data-intelligence-search]");
      assert.equal(oldSearch.listenerCount("input"), 1);
      const next = controller.update({ snapshot: createScenario("blocked"), theme: null });
      assert.equal(oldSearch.listenerCount("input"), 0);
      assert.equal(root.listenerCount("keydown"), 1);
      assert.equal(root.style.getPropertyValue("--ehri-primary"), "");
      next.destroy();
      assert.equal(root.listenerCount("keydown"), 0);
      assert.equal(root.dataset.ehriEnhanced, undefined);
    }
  });
});

test("snapshot-only custom element initializes controls and survives reconnect", () => {
  withRepositoryIntelligenceDOM(({ connect, disconnect }) => {
    const Component = defineRepositoryIntelligenceElement();
    const element = new Component();
    element.style.setProperty("--ehri-primary", "consumer-inline");
    element.snapshot = createScenario("small");
    assert.doesNotThrow(() => connect(element));
    assert.equal(element.dataset.ehriEnhanced, "true");
    const search = element.querySelector("[data-intelligence-search]");
    assert.equal(search.listenerCount("input"), 1);
    search.value = "missing";
    search.emit("input");
    assert.match(element.querySelector("[data-filter-results]").value, /matching records/);
    element.links[0].emit("keydown", { key: "ArrowRight" });
    assert.equal(document.activeElement, element.links[1]);

    element.theme = { tokens: { primary: "#123456" } };
    assert.equal(search.listenerCount("input"), 0);
    assert.equal(element.style.getPropertyValue("--ehri-primary"), "#123456");
    element.snapshot = createScenario("blocked");
    assert.equal(element.listenerCount("keydown"), 1);
    element.theme = null;
    assert.equal(element.style.getPropertyValue("--ehri-primary"), "consumer-inline");
    const beforeDisconnect = element.querySelector("[data-intelligence-search]");
    disconnect(element);
    assert.equal(element.listenerCount("keydown"), 0);
    assert.equal(beforeDisconnect.listenerCount("input"), 0);
    assert.equal(element.dataset.ehriEnhanced, undefined);
    connect(element);
    assert.equal(element.listenerCount("keydown"), 1);
    assert.equal(element.querySelector("[data-intelligence-search]").listenerCount("input"), 1);
    assert.equal(defineRepositoryIntelligenceElement(), Component);
    disconnect(element);
  });
});

function releaseRecord(key, publishedAt) {
  const record = createScenario("small").views.releases.releases[0];
  return {
    ...record,
    published_at: publishedAt,
    entity: {
      ...record.entity,
      id: `release:${key}`,
      key,
      title: `${key} publication`,
      canonical_url: `https://example.invalid/releases/${key}`,
    },
  };
}

function latestReleaseMetric(html) {
  const metric = html.match(/<article class="ehri-metric"[^>]*>\s*<span class="ehri-metric__label">Latest release<\/span>[\s\S]*?<\/article>/u)?.[0];
  assert.ok(metric, "latest-release metric exists");
  return metric;
}

test("latest release follows publication time across v9/v10 and array permutations", () => {
  const v10 = releaseRecord("v10", "2026-10-02T00:00:00Z");
  const v9 = releaseRecord("v9", "2026-10-01T00:00:00Z");
  for (const records of [[v10, v9], [v9, v10]]) {
    const snapshot = createScenario("small");
    snapshot.views.releases.releases = records;
    const before = JSON.stringify(records);
    for (const mode of ["static", "interactive"]) {
      const metric = latestReleaseMetric(renderRepositoryIntelligence(snapshot, { mode }));
      assert.match(metric, /<a href="https:\/\/example\.invalid\/releases\/v10">v10<\/a>/);
      assert.doesNotMatch(metric, />v9</);
    }
    assert.equal(JSON.stringify(records), before, "selection does not reorder or mutate owner data");
  }
});

test("latest release preserves unknown and undated states without coercing invalid dates", () => {
  const snapshot = createScenario("small");
  for (const date of [null, undefined, "invalid", "2026-02-30T00:00:00Z", "2026-01-01", "2026-01-01T00:00:00", "2026-01-01T00:00:00-00:00"]) {
    snapshot.views.releases.releases = [releaseRecord("undated", date)];
    const html = renderRepositoryIntelligence(snapshot);
    assert.match(latestReleaseMetric(html), /<strong>Unknown<\/strong>/);
    assert.match(latestReleaseMetric(html), /No valid publication time observed/);
    assert.match(html, /undated publication/, "full release record remains visible");
  }
  snapshot.views.releases.releases = [];
  assert.match(latestReleaseMetric(renderRepositoryIntelligence(snapshot)), /<strong>None<\/strong>/);
});

test("publication offsets, submillisecond precision, epoch zero and equal-time ties are deterministic", () => {
  const snapshot = createScenario("small");
  const cases = [
    [releaseRecord("newer", "2026-10-01T00:00:00.000000002Z"), releaseRecord("older", "2026-10-01T00:00:00.000000001Z"), "newer"],
    [releaseRecord("utc", "2026-10-01T00:00:01Z"), releaseRecord("offset", "2026-10-01T02:00:00+02:00"), "utc"],
    [releaseRecord("alpha", "2026-10-01T00:00:00Z"), releaseRecord("beta", "2026-10-01T02:00:00+02:00"), "alpha"],
    [releaseRecord("epoch", "1970-01-01T00:00:00Z"), releaseRecord("before", "1969-12-31T23:59:59Z"), "epoch"],
  ];
  for (const [first, second, expected] of cases) {
    for (const records of [[first, second], [second, first]]) {
      snapshot.views.releases.releases = records;
      const metric = latestReleaseMetric(renderRepositoryIntelligence(snapshot));
      assert.ok(metric.includes(`>${expected}</a>`));
    }
  }
  snapshot.views.releases.releases = [releaseRecord("unsafe-link", "2026-10-01T00:00:00Z")];
  snapshot.views.releases.releases[0].entity.canonical_url = "javascript:example";
  assert.doesNotMatch(latestReleaseMetric(renderRepositoryIntelligence(snapshot)), /<a /);
});

test("static CLI retains the selected publication link for nonchronological owner arrays", async () => {
  const directory = await mkdtemp(join(tmpdir(), "ehri-latest-"));
  try {
    const snapshot = createScenario("small");
    snapshot.views.releases.releases = [
      releaseRecord("v10", "2026-10-02T00:00:00Z"),
      releaseRecord("v9", "2026-10-01T00:00:00Z"),
    ];
    const input = join(directory, "input.json");
    const output = join(directory, "output.html");
    await writeFile(input, JSON.stringify(snapshot), "utf8");
    const result = spawnSync(process.execPath, [
      resolve(ROOT, "packages/repository-intelligence/bin/render-static.mjs"),
      "--input", input, "--output", output,
    ], { cwd: ROOT, encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
    const metric = latestReleaseMetric(await readFile(output, "utf8"));
    assert.match(metric, /href="https:\/\/example\.invalid\/releases\/v10"/);
    assert.match(metric, />v10<\/a>/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

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

test("public mount rejects malformed counters before inserting any markup", () => {
  withRepositoryIntelligenceDOM(({ Element }) => {
    const root = new Element();
    root.innerHTML = "existing consumer content";
    const snapshot = createScenario("small");
    snapshot.views.health.check_states = { success: '<span data-counter="inert">example</span>' };
    assert.throws(() => mountRepositoryIntelligence(root, { snapshot }), /nonnegative safe integer/);
    assert.equal(root.innerHTML, "existing consumer content");
    assert.equal(root.listenerCount("keydown"), 0);
  });
});

test("mounted release summary agrees with static publication evidence and links", () => {
  withRepositoryIntelligenceDOM(({ Element }) => {
    const root = new Element();
    const snapshot = createScenario("small");
    snapshot.views.releases.releases = [releaseRecord("v10", "2026-10-02T00:00:00Z"), releaseRecord("v9", "2026-10-01T00:00:00Z")];
    const controller = mountRepositoryIntelligence(root, { snapshot });
    assert.equal(latestReleaseMetric(root.innerHTML), latestReleaseMetric(renderRepositoryIntelligence(snapshot)));
    assert.match(latestReleaseMetric(root.innerHTML), /releases\/v10/);
    controller.destroy();
  });
});

test("exact pinned Observatory golden bytes retain pure mounted and public CLI compatibility", async () => {
  const bytes = await readFile(resolve(ROOT, "tests/fixtures/repository-intelligence/observatory-3cb3555-relay.repository.json"));
  const lock = JSON.parse(await readFile(resolve(ROOT, "contracts/observatory-repository-intelligence.v1.lock.json"), "utf8"));
  const expected = lock.golden_fixture_evidence.find((item) => item.path === "fixtures/expected/egohygiene--relay.repository.json");
  assert.equal(createHash("sha256").update(bytes).digest("hex"), expected.sha256);
  const snapshot = JSON.parse(bytes);
  assert.deepEqual(validateRepositoryIntelligence(snapshot), []);
  const html = renderRepositoryIntelligence(snapshot);
  withRepositoryIntelligenceDOM(({ Element }) => {
    const root = new Element();
    const controller = mountRepositoryIntelligence(root, { snapshot });
    assert.equal(latestReleaseMetric(root.innerHTML), latestReleaseMetric(html));
    assert.equal(root.querySelector("[data-intelligence-search]").listenerCount("input"), 1);
    controller.destroy();
  });
  const directory = await mkdtemp(join(tmpdir(), "ehri-owner-golden-"));
  try {
    const output = join(directory, "output.html");
    const result = spawnSync(process.execPath, [resolve(ROOT, "packages/repository-intelligence/bin/render-static.mjs"),
      "--input", resolve(ROOT, "tests/fixtures/repository-intelligence/observatory-3cb3555-relay.repository.json"), "--output", output], { cwd: ROOT, encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(latestReleaseMetric(await readFile(output, "utf8")), latestReleaseMetric(html));
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

test("small fixture markup and component CSS retain recorded regression snapshots", async () => {
  const html = renderRepositoryIntelligence(createScenario("small"));
  const css = await readFile(CSS_PATH, "utf8");
  const digest = (value) => createHash("sha256").update(value).digest("hex");
  // The candidate adds only the selected release link; visual/browser review remains pending.
  assert.equal(digest(html), "e723f04b1678ae6cfdb861e33f61a74e55d70d4a1ff348675755ee108adf7948");
  assert.equal(digest(css), "ebc865cb28edc74f924ce597355c3c3814361e57efd11796e8a8ff57afd51ab9");
});
