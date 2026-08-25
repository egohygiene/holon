const REPOSITORY = "egohygiene/relay";
const COMMIT = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

function entity(kind, key, title, state, freshness = "current") {
  const paths = {
    architecture_decision: `blob/${COMMIT}/DECISIONS.md#${key.toLowerCase()}`,
    check: "actions/runs/812",
    commit: `commit/${key}`,
    deployment: "deployments/1842",
    file: `blob/${COMMIT}/${key}`,
    issue: `issues/${key}`,
    pull_request: `pull/${key}`,
    release: `releases/tag/${key}`,
    repository: "",
    roadmap_step: `blob/${COMMIT}/ROADMAP.md#${key.toLowerCase()}`,
  };
  return {
    id: `ri:${REPOSITORY}:${kind}:${key}`,
    kind,
    repository: REPOSITORY,
    key,
    title,
    canonical_url: `https://github.com/${REPOSITORY}/${paths[kind] ?? ""}`.replace(/\/$/, ""),
    visibility: "public",
    state,
    assertion: "authoritative",
    confidence: "authoritative",
    freshness,
  };
}

const issue22 = entity("issue", "22", "Create reusable Repository Intelligence visualization components", "open");
const pull28 = entity("pull_request", "28", "Build the shared intelligence shell", "merged");
const check812 = entity("check", "repository-intelligence-812", "Repository Intelligence validation", "success");
const commitOne = entity("commit", COMMIT, "feat(intelligence): publish the normalized graph", "recorded", "not_applicable");
const release = entity("release", "v0.4.0", "Repository Intelligence v0.4.0", "published");
const deployment = entity("deployment", "github-pages-1842", "GitHub Pages production deployment", "success");

const questEntities = [
  entity("roadmap_step", "REL-Q01", "Name the repository story", "complete"),
  entity("roadmap_step", "REL-Q02", "Normalize public-safe evidence", "complete"),
  entity("roadmap_step", "REL-Q03", "Build the shared visual language", "active"),
  entity("roadmap_step", "REL-Q04", "Publish ADR lineage", "blocked", "stale"),
  entity("roadmap_step", "REL-Q05", "Turn Git history into epochs", "ready"),
  entity("roadmap_step", "REL-Q06", "Ship the repository route", "planned"),
  entity("roadmap_step", "REL-Q07", "Prove fleet-wide comparison", "unknown", "unknown"),
];

const decisionEntities = [
  entity("architecture_decision", "ADR-001", "Use a framework-neutral view model", "accepted"),
  entity("architecture_decision", "ADR-002", "Render static HTML before enhancement", "accepted"),
  entity("architecture_decision", "ADR-003", "Adopt a raw commit graph", "rejected"),
  entity("architecture_decision", "ADR-004", "Group delivery into meaningful epochs", "proposed"),
  entity("architecture_decision", "ADR-005", "Replace raw history with evidence journeys", "superseded"),
];

function quest(entityRef, index) {
  const dependencies = index > 0 ? [questEntities[index - 1]] : [];
  const blocked = entityRef.state === "blocked" ? [issue22] : [];
  const complete = entityRef.state === "complete";
  return structuredClone({
    entity: entityRef,
    outcome: [
      "The repository can explain its purpose in one durable narrative.",
      "Collectors emit one deterministic, public-safe Repository Intelligence snapshot.",
      "Roadmap, decisions, journey, and evidence share one navigable visual language.",
      "Accepted and superseded choices remain traceable without rewriting history.",
      "Commits, issues, checks, releases, and deployments read as a delivery story.",
      "The visual story publishes at a configurable repository route.",
      "People can compare represented states without invented causal claims.",
    ][index],
    exit_criteria: [
      { complete, text: "The owning contract and acceptance evidence are versioned." },
      { complete: complete || entityRef.state === "active", text: "The experience works with keyboard and mobile layouts." },
      { complete: false, text: "A clean-room consumer proves the integration boundary." },
    ],
    dependencies,
    blocked_by: blocked,
    tracked_by: index >= 2 ? [issue22] : [],
    informed_by: index >= 2 ? [decisionEntities[0], decisionEntities[1]] : [],
    evidence: complete ? [commitOne, pull28] : [],
    verified_by: complete ? [check812] : [],
    readiness: {
      assertion: "inferred",
      confidence: "inferred",
      reasons: blocked.length ? ["A stale open issue blocks the next verified transition."] : [],
      value: entityRef.state,
    },
  });
}

function event(id, type, occurredAt, subject, freshness = "current") {
  return {
    id,
    type,
    occurred_at: occurredAt,
    recorded_at: "2026-08-25T18:00:00Z",
    subject: subject.id,
    subject_entity: subject,
    actor: null,
    changes: [],
    provenance: [`source:${subject.key}`],
    visibility: "public",
    assertion: "authoritative",
    freshness,
    extensions: {},
  };
}

const events = [
  event("event:q1-created", "roadmap_step.created", "2026-07-01T09:00:00Z", questEntities[0]),
  event("event:adr1-proposed", "architecture_decision.proposed", "2026-07-02T09:00:00Z", decisionEntities[0]),
  event("event:adr1-accepted", "architecture_decision.accepted", "2026-07-03T09:00:00Z", decisionEntities[0]),
  event("event:q1-complete", "roadmap_step.status_changed", "2026-07-05T10:00:00Z", questEntities[0]),
  event("event:q2-created", "roadmap_step.created", "2026-07-06T09:00:00Z", questEntities[1]),
  event("event:issue-opened", "issue.opened", "2026-07-08T09:00:00Z", issue22),
  event("event:pr-opened", "pull_request.opened", "2026-07-12T09:00:00Z", pull28),
  event("event:commit-created", "commit.created", "2026-07-14T10:00:00Z", commitOne, "not_applicable"),
  event("event:check-completed", "check.completed", "2026-07-14T10:05:00Z", check812),
  event("event:pr-merged", "pull_request.merged", "2026-07-14T10:10:00Z", pull28),
  event("event:q2-complete", "roadmap_step.status_changed", "2026-07-15T10:00:00Z", questEntities[1]),
  event("event:q3-active", "roadmap_step.status_changed", "2026-07-16T09:00:00Z", questEntities[2]),
  event("event:adr3-rejected", "architecture_decision.rejected", "2026-07-18T09:00:00Z", decisionEntities[2]),
  event("event:adr4-proposed", "architecture_decision.proposed", "2026-07-20T09:00:00Z", decisionEntities[3]),
  event("event:release-published", "release.published", "2026-08-01T09:00:00Z", release),
  event("event:deployment-completed", "deployment.completed", "2026-08-01T10:00:00Z", deployment),
  event("event:q4-blocked", "roadmap_step.status_changed", "2026-08-04T09:00:00Z", questEntities[3], "stale"),
  event("event:q5-ready", "roadmap_step.status_changed", "2026-08-05T09:00:00Z", questEntities[4]),
];

function searchRecord(reference) {
  return {
    ...reference,
    search_text: `${reference.title} ${reference.key} ${reference.kind} ${reference.state} ${reference.repository}`.toLowerCase(),
  };
}

function baseSnapshot() {
  const steps = questEntities.map(quest);
  const decisions = decisionEntities.map((entityRef, index) => ({
    entity: entityRef,
    decision_scope: "repository",
    implementation_status: index < 2 ? "verified" : index === 3 ? "planned" : "not_applicable",
    evidence: index < 2 ? [commitOne] : [],
    tracked_by: index === 3 ? [issue22] : [],
    verified_by: index < 2 ? [check812] : [],
    informs: index < 2 ? [questEntities[2], questEntities[4]] : [],
    supersedes: index === 4 ? [decisionEntities[2]] : [],
    superseded_by: index === 2 ? [decisionEntities[4]] : [],
  }));
  const graphEntities = [
    ...questEntities,
    ...decisionEntities,
    issue22,
    pull28,
    check812,
    commitOne,
    release,
    deployment,
  ];
  return structuredClone({
    schema: "egohygiene.observatory.repository-intelligence-read-model/v1",
    contract_version: "1.0.0-alpha.1",
    snapshot_id: "relay:demo:2026-08-25",
    observed_at: "2026-08-25T18:00:00Z",
    represented_commit: COMMIT,
    visibility: "public",
    repository: entity("repository", REPOSITORY, "Relay", "active"),
    generator: { name: "egohygiene/holon:fixture-app", version: "0.1.0" },
    upstream: [],
    coverage: {
      status: "partial",
      freshness: { current: 48, stale: 3, unknown: 2, not_applicable: 1 },
      assertions: { authoritative: 51, inferred: 3 },
      counts: { entities: graphEntities.length, relationships: 12, events: events.length, sources: 10, redactions: 0 },
    },
    graph: { entities: graphEntities, relationships: [], events, sources: [] },
    views: {
      roadmap: { roots: [questEntities[0].id], steps },
      decisions: { decisions },
      journey: {
        chapters: [
          { id: "chapter:foundation", title: "The foundation", start_at: "2026-07-01T09:00:00Z", end_at: "2026-07-15T10:00:00Z", boundary: null, event_ids: events.slice(0, 11).map(({ id }) => id) },
          { id: "chapter:visual-language", title: "A language for repository truth", start_at: "2026-07-16T09:00:00Z", end_at: "2026-07-20T09:00:00Z", boundary: null, event_ids: events.slice(11, 14).map(({ id }) => id) },
          { id: "chapter:publication", title: "From code to public evidence", start_at: "2026-08-01T09:00:00Z", end_at: "2026-08-05T09:00:00Z", boundary: release, event_ids: events.slice(14).map(({ id }) => id) },
        ],
        events,
      },
      now: {
        coverage_status: "partial",
        current_focus: [questEntities[2]],
        blockers: [{ id: "relationship:issue-blocks-q4", type: "blocks", source: issue22, target: questEntities[3], assertion: "authoritative", confidence: "authoritative", freshness: "stale", provenance: ["source:22"] }],
        next_ready: [questEntities[4]],
        recent_events: events.slice(-5).reverse(),
      },
      dependencies: {
        external_repositories: [entity("repository", "egohygiene/observatory", "Observatory", "active")],
        relationships: steps.slice(1).map((step, index) => ({ id: `relationship:q${index + 2}-depends-q${index + 1}`, type: "depends-on", source: step.entity, target: step.dependencies[0], assertion: "authoritative", confidence: "authoritative", freshness: "current", provenance: ["source:roadmap"] })),
      },
      health: {
        score: null,
        score_reason: "Evidence states stay primary; no synthetic roll-up score is asserted.",
        checks: [check812],
        check_states: { success: 1 },
        freshness: { current: 48, stale: 3, unknown: 2, not_applicable: 1 },
        assertions: { authoritative: 51, inferred: 3 },
        stale_ids: [questEntities[3].id, issue22.id],
        unknown_ids: [questEntities[6].id],
      },
      releases: { releases: [{ entity: release, published_at: "2026-08-01T09:00:00Z", includes: [commitOne, pull28], deployments: [deployment], boundary_event_ids: ["event:release-published"] }] },
      work: {
        open_issues: [issue22],
        open_pull_requests: [],
        roadmap_queues: { active: [questEntities[2]], blocked: [questEntities[3]], ready: [questEntities[4]], waiting: [questEntities[5]], unknown: [questEntities[6]] },
      },
      search: { records: graphEntities.map(searchRecord) },
    },
    extensions: {},
  });
}

function makeSmall() {
  const snapshot = baseSnapshot();
  snapshot.snapshot_id = "relay:small";
  snapshot.views.roadmap.steps = snapshot.views.roadmap.steps.slice(0, 1);
  snapshot.views.decisions.decisions = snapshot.views.decisions.decisions.slice(0, 1);
  snapshot.views.journey.events = snapshot.views.journey.events.slice(0, 2);
  snapshot.views.journey.chapters = [{ ...snapshot.views.journey.chapters[0], event_ids: snapshot.views.journey.events.map(({ id }) => id), end_at: snapshot.views.journey.events.at(-1).occurred_at }];
  snapshot.coverage.status = "current";
  snapshot.views.now.coverage_status = "current";
  snapshot.views.now.blockers = [];
  return snapshot;
}

function makeStale() {
  const snapshot = baseSnapshot();
  snapshot.snapshot_id = "relay:stale";
  snapshot.observed_at = "2026-06-01T09:00:00Z";
  snapshot.coverage.status = "stale";
  snapshot.repository.freshness = "stale";
  snapshot.views.now.coverage_status = "stale";
  snapshot.views.health.stale_ids = snapshot.graph.entities.slice(0, 8).map(({ id }) => id);
  for (const step of snapshot.views.roadmap.steps.slice(2)) step.entity.freshness = "stale";
  return snapshot;
}

function makeBlocked() {
  const snapshot = baseSnapshot();
  snapshot.snapshot_id = "relay:blocked";
  snapshot.views.roadmap.steps[2].entity.state = "blocked";
  snapshot.views.roadmap.steps[2].blocked_by = [issue22];
  snapshot.views.roadmap.steps[2].readiness.value = "blocked";
  snapshot.views.now.current_focus = [];
  snapshot.views.now.blockers.push({ id: "relationship:issue-blocks-q3", type: "blocks", source: issue22, target: questEntities[2], assertion: "authoritative", confidence: "authoritative", freshness: "current", provenance: ["source:22"] });
  return snapshot;
}

function makePartial() {
  const snapshot = baseSnapshot();
  snapshot.snapshot_id = "relay:partially-adopted";
  snapshot.coverage.status = "unknown";
  snapshot.views.decisions.decisions = [];
  snapshot.views.releases.releases = [];
  snapshot.views.health.checks = [];
  snapshot.views.health.check_states = {};
  snapshot.views.now.coverage_status = "unknown";
  return snapshot;
}

function makeLarge() {
  const snapshot = baseSnapshot();
  snapshot.snapshot_id = "relay:large-history";
  const kinds = ["commit", "pull_request", "check", "issue", "roadmap_step", "architecture_decision", "release", "deployment"];
  const states = ["recorded", "merged", "success", "closed", "complete", "accepted", "published", "success"];
  const largeEvents = Array.from({ length: 640 }, (_, index) => {
    const kind = kinds[index % kinds.length];
    const key = kind === "commit" ? index.toString(16).padStart(40, "a").slice(-40) : `demo-${index + 1}`;
    const reference = entity(kind, key, `Journey evidence ${String(index + 1).padStart(3, "0")}`, states[index % states.length]);
    const occurred = new Date(Date.UTC(2025, 0, 1, 9 + index * 6));
    return event(`event:large-${String(index + 1).padStart(3, "0")}`, `${kind}.recorded`, occurred.toISOString(), reference);
  });
  snapshot.views.journey.events = largeEvents;
  snapshot.views.journey.chapters = Array.from({ length: 8 }, (_, index) => {
    const chapterEvents = largeEvents.slice(index * 80, (index + 1) * 80);
    return {
      id: `chapter:epoch-${index + 1}`,
      title: `Epoch ${index + 1} · ${["Foundation", "Contracts", "First consumers", "Evidence", "Publication", "Hardening", "Adoption", "Next horizon"][index]}`,
      start_at: chapterEvents[0].occurred_at,
      end_at: chapterEvents.at(-1).occurred_at,
      boundary: index === 4 ? release : null,
      event_ids: chapterEvents.map(({ id }) => id),
    };
  });
  snapshot.coverage.counts.events = largeEvents.length;
  return snapshot;
}

export const scenarioNames = Object.freeze(["small", "large", "stale", "blocked", "partial"]);

export function createScenario(name = "blocked") {
  const factories = { small: makeSmall, large: makeLarge, stale: makeStale, blocked: makeBlocked, partial: makePartial };
  if (!factories[name]) throw new RangeError(`Unknown fixture scenario: ${name}`);
  return factories[name]();
}

export function createComparison(snapshot) {
  return {
    schema: "egohygiene.observatory.repository-intelligence-compare/v1",
    contract_version: "1.0.0-alpha.1",
    repository: snapshot.repository.key,
    before: { snapshot_id: "relay:before", represented_commit: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", observed_at: "2026-08-01T09:00:00Z" },
    after: { snapshot_id: snapshot.snapshot_id, represented_commit: snapshot.represented_commit, observed_at: snapshot.observed_at },
    entities: { added: [questEntities[6].id], removed: [], changed: [{ id: questEntities[2].id, fields: ["state"] }] },
    relationships: { added: ["relationship:q7-depends-q6"], removed: [], changed: [] },
    events: { added: ["event:q5-ready"], removed: [], changed: [] },
    views: [],
  };
}
