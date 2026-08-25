export const REPOSITORY_INTELLIGENCE_SCHEMA =
  "egohygiene.observatory.repository-intelligence-read-model/v1";

export const COMPARISON_SCHEMA =
  "egohygiene.observatory.repository-intelligence-compare/v1";

export const REQUIRED_VIEWS = Object.freeze([
  "roadmap",
  "decisions",
  "journey",
  "now",
  "dependencies",
  "health",
  "releases",
  "work",
  "search",
]);

export const STATE_ORDER = Object.freeze([
  "active",
  "blocked",
  "ready",
  "planned",
  "complete",
  "accepted",
  "proposed",
  "superseded",
  "deprecated",
  "rejected",
  "partial",
  "stale",
  "unknown",
  "not_applicable",
]);

const COMPLETE_STATES = new Set([
  "complete",
  "completed",
  "accepted",
  "closed",
  "merged",
  "published",
  "success",
  "verified",
]);

const BLOCKED_STATES = new Set(["blocked", "failed", "failure"]);

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requireArray(errors, value, label) {
  if (!Array.isArray(value)) {
    errors.push(`${label} must be an array`);
  }
}

export function validateRepositoryIntelligence(snapshot) {
  const errors = [];
  if (!isObject(snapshot)) {
    return ["snapshot must be an object"];
  }
  if (snapshot.schema !== REPOSITORY_INTELLIGENCE_SCHEMA) {
    errors.push(`schema must be ${REPOSITORY_INTELLIGENCE_SCHEMA}`);
  }
  if (!isObject(snapshot.repository)) {
    errors.push("repository must be an entity reference");
  } else {
    for (const key of ["id", "key", "title", "state"]) {
      if (typeof snapshot.repository[key] !== "string" || !snapshot.repository[key]) {
        errors.push(`repository.${key} must be a non-empty string`);
      }
    }
  }
  if (!isObject(snapshot.views)) {
    errors.push("views must be an object");
    return errors;
  }
  for (const name of REQUIRED_VIEWS) {
    if (!isObject(snapshot.views[name])) {
      errors.push(`views.${name} must be an object`);
    }
  }
  if (isObject(snapshot.views.roadmap)) {
    requireArray(errors, snapshot.views.roadmap.steps, "views.roadmap.steps");
    requireArray(errors, snapshot.views.roadmap.roots, "views.roadmap.roots");
  }
  if (isObject(snapshot.views.decisions)) {
    requireArray(
      errors,
      snapshot.views.decisions.decisions,
      "views.decisions.decisions",
    );
  }
  if (isObject(snapshot.views.journey)) {
    requireArray(errors, snapshot.views.journey.chapters, "views.journey.chapters");
    requireArray(errors, snapshot.views.journey.events, "views.journey.events");
  }
  return errors;
}

export function assertRepositoryIntelligence(snapshot) {
  const errors = validateRepositoryIntelligence(snapshot);
  if (errors.length > 0) {
    throw new TypeError(`Invalid Repository Intelligence snapshot:\n- ${errors.join("\n- ")}`);
  }
  return snapshot;
}

export function validateComparison(comparison, repository) {
  if (comparison === null || comparison === undefined) {
    return [];
  }
  const errors = [];
  if (!isObject(comparison)) {
    return ["comparison must be an object"];
  }
  if (comparison.schema !== COMPARISON_SCHEMA) {
    errors.push(`comparison.schema must be ${COMPARISON_SCHEMA}`);
  }
  if (comparison.repository !== repository) {
    errors.push("comparison must represent the rendered repository");
  }
  for (const boundary of ["before", "after"]) {
    if (!isObject(comparison[boundary])) {
      errors.push(`comparison.${boundary} must be an object`);
    }
  }
  for (const delta of ["entities", "relationships", "events"]) {
    if (!isObject(comparison[delta])) {
      errors.push(`comparison.${delta} must be an object`);
      continue;
    }
    for (const key of ["added", "removed", "changed"]) {
      if (!Array.isArray(comparison[delta][key])) {
        errors.push(`comparison.${delta}.${key} must be an array`);
      }
    }
  }
  return errors;
}

export function normalizeState(value) {
  if (typeof value !== "string" || value.trim() === "") {
    return "unknown";
  }
  return value.trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
}

export function stateLabel(value) {
  return normalizeState(value)
    .split("_")
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

export function isCompleteState(value) {
  return COMPLETE_STATES.has(normalizeState(value));
}

export function isBlockedState(value) {
  return BLOCKED_STATES.has(normalizeState(value));
}

export function roadmapProgress(snapshot) {
  const steps = snapshot.views.roadmap.steps;
  const complete = steps.filter((step) =>
    isCompleteState(step?.entity?.state ?? step?.readiness?.value),
  ).length;
  const blocked = steps.filter(
    (step) =>
      isBlockedState(step?.entity?.state ?? step?.readiness?.value) ||
      (Array.isArray(step?.blocked_by) && step.blocked_by.length > 0),
  ).length;
  const active = steps.filter(
    (step) => normalizeState(step?.entity?.state) === "active",
  ).length;
  return {
    total: steps.length,
    complete,
    blocked,
    active,
    ratio: steps.length === 0 ? 0 : complete / steps.length,
    percentage: steps.length === 0 ? 0 : Math.round((complete / steps.length) * 100),
  };
}

export function collectEvidence(record) {
  const groups = [
    ["blocked by", record?.blocked_by],
    ["evidence", record?.evidence],
    ["tracked by", record?.tracked_by],
    ["verified by", record?.verified_by],
    ["informed by", record?.informed_by],
    ["depends on", record?.dependencies],
    ["supersedes", record?.supersedes],
    ["superseded by", record?.superseded_by],
    ["informs", record?.informs],
  ];
  const seen = new Set();
  const items = [];
  for (const [relationship, values] of groups) {
    if (!Array.isArray(values)) continue;
    for (const entity of values) {
      if (!isObject(entity) || typeof entity.id !== "string" || seen.has(entity.id)) {
        continue;
      }
      seen.add(entity.id);
      items.push({ relationship, entity });
    }
  }
  return items;
}

export function createEntityIndex(snapshot) {
  const index = new Map();
  for (const entity of snapshot?.graph?.entities ?? []) {
    if (isObject(entity) && typeof entity.id === "string") {
      index.set(entity.id, entity);
    }
  }
  for (const record of snapshot?.views?.search?.records ?? []) {
    if (isObject(record) && typeof record.id === "string" && !index.has(record.id)) {
      index.set(record.id, record);
    }
  }
  return index;
}

export function eventsByChapter(snapshot) {
  const events = new Map(
    snapshot.views.journey.events.map((event) => [event.id, event]),
  );
  const chapters = snapshot.views.journey.chapters.map((chapter) => ({
    ...chapter,
    events: (chapter.event_ids ?? [])
      .map((id) => events.get(id))
      .filter(Boolean),
  }));
  const assigned = new Set(chapters.flatMap((chapter) => chapter.event_ids ?? []));
  const unassigned = snapshot.views.journey.events.filter(
    (event) => !assigned.has(event.id),
  );
  if (unassigned.length > 0) {
    chapters.push({
      id: "chapter:unassigned",
      title: "Other recorded events",
      start_at: unassigned[0]?.occurred_at ?? null,
      end_at: unassigned.at(-1)?.occurred_at ?? null,
      boundary: null,
      event_ids: unassigned.map((event) => event.id),
      events: unassigned,
    });
  }
  return chapters;
}

export function filterEvents(events, filters = {}) {
  const query = String(filters.query ?? "").trim().toLowerCase();
  const kind = normalizeState(filters.kind ?? "all");
  const state = normalizeState(filters.state ?? "all");
  const from = filters.from ? Date.parse(filters.from) : Number.NEGATIVE_INFINITY;
  const to = filters.to ? Date.parse(filters.to) + 86_399_999 : Number.POSITIVE_INFINITY;
  return events.filter((event) => {
    const occurred = Date.parse(event.occurred_at ?? "");
    const searchable = [
      event.type,
      event.subject_entity?.title,
      event.subject_entity?.key,
      event.subject_entity?.kind,
      event.subject_entity?.state,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    const eventKind = normalizeState(event.subject_entity?.kind ?? event.type?.split(".")[0]);
    const eventState = normalizeState(event.subject_entity?.state);
    return (
      (!query || searchable.includes(query)) &&
      (kind === "all" || eventKind === kind) &&
      (state === "all" || eventState === state) &&
      (!Number.isFinite(occurred) || (occurred >= from && occurred <= to))
    );
  });
}

export function computeVirtualWindow(
  items,
  {
    scrollTop = 0,
    viewportHeight = 560,
    rowHeight = 132,
    overscan = 4,
  } = {},
) {
  const count = items.length;
  const safeRowHeight = Math.max(1, Number(rowHeight) || 132);
  const safeViewport = Math.max(safeRowHeight, Number(viewportHeight) || 560);
  const safeScroll = Math.max(0, Number(scrollTop) || 0);
  const safeOverscan = Math.max(0, Math.floor(Number(overscan) || 0));
  const visibleStart = Math.floor(safeScroll / safeRowHeight);
  const visibleCount = Math.ceil(safeViewport / safeRowHeight);
  const start = Math.max(0, visibleStart - safeOverscan);
  const end = Math.min(count, visibleStart + visibleCount + safeOverscan);
  return {
    start,
    end,
    before: start * safeRowHeight,
    after: Math.max(0, (count - end) * safeRowHeight),
    totalHeight: count * safeRowHeight,
    items: items.slice(start, end),
  };
}

export function searchRecords(snapshot, query, { state = "all", kind = "all" } = {}) {
  const normalizedQuery = String(query ?? "").trim().toLowerCase();
  const normalizedState = normalizeState(state);
  const normalizedKind = normalizeState(kind);
  return (snapshot.views.search.records ?? []).filter((record) => {
    const haystack = String(record.search_text ?? `${record.title} ${record.key}`)
      .toLowerCase();
    return (
      (!normalizedQuery || haystack.includes(normalizedQuery)) &&
      (normalizedState === "all" || normalizeState(record.state) === normalizedState) &&
      (normalizedKind === "all" || normalizeState(record.kind) === normalizedKind)
    );
  });
}
