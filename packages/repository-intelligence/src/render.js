import {
  assertRepositoryIntelligence,
  collectEvidence,
  computeVirtualWindow,
  eventsByChapter,
  normalizeState,
  roadmapProgress,
  stateLabel,
  validateComparison,
} from "./model.js";

const STATE_MESSAGES = Object.freeze({
  empty: ["Nothing here yet", "The source model contains no records for this view."],
  stale: ["Evidence needs a refresh", "This view is preserved, but its source evidence is stale."],
  unknown: ["State is unknown", "The available evidence cannot support a stronger claim."],
  loading: ["Assembling evidence", "Repository Intelligence is loading its public-safe snapshot."],
  error: ["This view could not be rendered", "Inspect the validation evidence and try again."],
  not_applicable: ["Not applicable", "This capability does not apply to the repository profile."],
  partial: ["Partially adopted", "Some evidence is available; missing coverage remains explicit."],
});

const KIND_LABELS = Object.freeze({
  architecture_decision: "Decision",
  check: "Check",
  commit: "Commit",
  deployment: "Deployment",
  file: "File",
  issue: "Issue",
  pull_request: "Pull request",
  release: "Release",
  repository: "Repository",
  roadmap_step: "Quest",
});

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function safeHref(value) {
  if (typeof value !== "string") return null;
  const href = value.trim();
  if (!href || href.startsWith("//")) return null;
  if (href.startsWith("#") || href.startsWith("/") || href.startsWith("./") || href.startsWith("../")) {
    return href;
  }
  try {
    const parsed = new URL(href);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? href : null;
  } catch {
    return null;
  }
}

function safeId(value) {
  return String(value ?? "record")
    .toLowerCase()
    .replaceAll(/[^a-z0-9_-]+/g, "-")
    .replaceAll(/^-+|-+$/g, "") || "record";
}

function displayKind(kind) {
  return KIND_LABELS[normalizeState(kind)] ?? stateLabel(kind);
}

function formatDate(value, { dateOnly = false } = {}) {
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return String(value);
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...(dateOnly ? {} : { hour: "numeric", minute: "2-digit", timeZoneName: "short" }),
  }).format(date);
}

function statusPill(state, freshness) {
  const normalized = normalizeState(state);
  const stale = normalizeState(freshness) === "stale";
  return `<span class="ehri-status" data-state="${escapeHtml(normalized)}">
    <span class="ehri-status__dot" aria-hidden="true"></span>
    ${escapeHtml(stateLabel(normalized))}${stale ? " · stale" : ""}
  </span>`;
}

function recordSearchText(record) {
  return [
    record?.entity?.title,
    record?.entity?.key,
    record?.entity?.kind,
    record?.entity?.state,
    record?.title,
    record?.key,
    record?.kind,
    record?.state,
    record?.outcome,
    record?.implementation_status,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function entityLink(entity, { relationship = null, compact = false } = {}) {
  if (!entity) return "";
  const content = `<span class="ehri-evidence-card__kind">${escapeHtml(
    relationship ?? displayKind(entity.kind),
  )}</span>
    <span class="ehri-evidence-card__title">${escapeHtml(entity.title)}</span>
    <span class="ehri-evidence-card__meta">${escapeHtml(displayKind(entity.kind))} · ${escapeHtml(
      entity.key,
    )}</span>`;
  const attributes = `class="ehri-evidence-card${compact ? " ehri-evidence-card--compact" : ""}" data-kind="${escapeHtml(
    normalizeState(entity.kind),
  )}" data-state="${escapeHtml(normalizeState(entity.state))}"`;
  const href = safeHref(entity.canonical_url);
  if (href) {
    return `<a ${attributes} href="${escapeHtml(href)}">${content}<span class="ehri-evidence-card__arrow" aria-hidden="true">↗</span></a>`;
  }
  return `<div ${attributes}>${content}</div>`;
}

export function renderStatePanel(state, options = {}) {
  const normalized = normalizeState(state);
  const defaults = STATE_MESSAGES[normalized] ?? STATE_MESSAGES.unknown;
  const title = options.title ?? defaults[0];
  const message = options.message ?? defaults[1];
  const actionUrl = safeHref(options.actionUrl);
  const action = actionUrl
    ? `<a class="ehri-button ehri-button--quiet" href="${escapeHtml(actionUrl)}">${escapeHtml(
        options.actionLabel ?? "Inspect evidence",
      )}</a>`
    : "";
  return `<div class="ehri-state" data-state="${escapeHtml(normalized)}" role="status">
    <span class="ehri-state__mark" aria-hidden="true"></span>
    <div><h3>${escapeHtml(title)}</h3><p>${escapeHtml(message)}</p>${action}</div>
  </div>`;
}

export function renderEvidenceDrawer(items, options = {}) {
  const title = options.title ?? "Evidence";
  const id = safeId(options.id ?? title);
  if (!items || items.length === 0) {
    return `<div class="ehri-evidence-empty"><span aria-hidden="true">◇</span> No linked evidence yet</div>`;
  }
  return `<details class="ehri-evidence" id="${id}"${options.open ? " open" : ""}>
    <summary>
      <span>${escapeHtml(title)}</span>
      <span class="ehri-evidence__count">${items.length} ${items.length === 1 ? "record" : "records"}</span>
    </summary>
    <div class="ehri-evidence__grid">
      ${items
        .map(({ entity, relationship }) => entityLink(entity, { relationship }))
        .join("\n")}
    </div>
  </details>`;
}

function renderMetric(label, value, detail, state = "information") {
  return `<article class="ehri-metric" data-state="${escapeHtml(normalizeState(state))}">
    <span class="ehri-metric__label">${escapeHtml(label)}</span>
    <strong>${escapeHtml(value)}</strong>
    <span class="ehri-metric__detail">${escapeHtml(detail)}</span>
  </article>`;
}

export function renderSummary(snapshot) {
  const progress = roadmapProgress(snapshot);
  const now = snapshot.views.now;
  const health = snapshot.views.health;
  const releases = snapshot.views.releases.releases ?? [];
  const work = snapshot.views.work;
  const relationships = snapshot.views.dependencies.relationships ?? [];
  const release = releases.at(-1)?.entity;
  const focusCount = now.current_focus?.length ?? 0;
  const blockerCount = now.blockers?.length ?? 0;
  const workCount =
    (work.open_issues?.length ?? 0) +
    (work.open_pull_requests?.length ?? 0) +
    Object.values(work.roadmap_queues ?? {}).reduce(
      (sum, queue) => sum + (Array.isArray(queue) ? queue.length : 0),
      0,
    );
  return `<section class="ehri-section ehri-overview" id="overview" aria-labelledby="overview-title">
    <div class="ehri-section-heading">
      <div><span class="ehri-eyebrow">Current state</span><h2 id="overview-title">Read the room in one glance</h2></div>
      <p>Truthful signals stay separate. Unknown and stale evidence never become a green score.</p>
    </div>
    <div class="ehri-metrics">
      ${renderMetric("Roadmap", `${progress.complete} / ${progress.total}`, `${progress.percentage}% of quests verified`, progress.blocked ? "caution" : "success")}
      ${renderMetric("Now", focusCount || "—", focusCount ? `${focusCount} active focus ${focusCount === 1 ? "item" : "items"}` : "No current focus asserted", focusCount ? "active" : "unknown")}
      ${renderMetric("Blockers", blockerCount, blockerCount ? "Needs deliberate attention" : "No blockers asserted", blockerCount ? "blocked" : "success")}
      ${renderMetric("Health", health.checks?.length ?? 0, health.score_reason ?? "Evidence states preserved", snapshot.coverage?.status ?? "unknown")}
      ${renderMetric("Dependencies", relationships.length, `${snapshot.views.dependencies.external_repositories?.length ?? 0} external repositories`, relationships.length ? "information" : "unknown")}
      ${renderMetric("Latest release", release?.key ?? "None", release?.title ?? "No published boundary observed", release?.state ?? "unknown")}
      ${renderMetric("Work queue", workCount, `${work.open_pull_requests?.length ?? 0} open pull requests`, workCount ? "active" : "empty")}
      ${renderMetric("Observed", formatDate(snapshot.observed_at, { dateOnly: true }), `Commit ${String(snapshot.represented_commit ?? "unknown").slice(0, 8)}`, snapshot.coverage?.status ?? "unknown")}
    </div>
  </section>`;
}

function renderExitCriteria(criteria) {
  if (!criteria?.length) return "";
  return `<ul class="ehri-criteria" aria-label="Exit criteria">
    ${criteria
      .map(
        (criterion) => `<li data-complete="${criterion.complete ? "true" : "false"}">
          <span class="ehri-check" aria-hidden="true">${criterion.complete ? "✓" : ""}</span>
          <span>${escapeHtml(criterion.text)}</span>
        </li>`,
      )
      .join("\n")}
  </ul>`;
}

function renderQuestStep(step, index, total) {
  const entity = step.entity;
  const state = normalizeState(entity.state ?? step.readiness?.value);
  const evidence = collectEvidence(step);
  const dependencies = step.dependencies ?? [];
  const blockers = step.blocked_by ?? [];
  const progress = step.exit_criteria?.length
    ? Math.round(
        (step.exit_criteria.filter((criterion) => criterion.complete).length /
          step.exit_criteria.length) *
          100,
      )
    : state === "complete"
      ? 100
      : 0;
  return `<li class="ehri-quest" id="quest-${safeId(entity.key)}" data-filter-item data-state="${escapeHtml(
    state,
  )}" data-kind="roadmap_step" data-search="${escapeHtml(recordSearchText(step))}">
    <div class="ehri-quest__node" aria-hidden="true"><span>${String(index + 1).padStart(2, "0")}</span></div>
    <article class="ehri-quest__card">
      <header>
        <div>
          <span class="ehri-quest__sequence">Quest ${index + 1} of ${total} · ${escapeHtml(entity.key)}</span>
          <h3>${escapeHtml(entity.title)}</h3>
        </div>
        ${statusPill(state, entity.freshness)}
      </header>
      <p class="ehri-quest__outcome">${escapeHtml(step.outcome || "Outcome not yet described.")}</p>
      <div class="ehri-progress" aria-label="${progress}% of exit criteria complete">
        <span style="--ehri-progress:${progress}%"></span><strong>${progress}%</strong>
      </div>
      ${renderExitCriteria(step.exit_criteria)}
      ${
        blockers.length
          ? `<div class="ehri-callout" data-state="blocked"><strong>Blocked by</strong>${blockers
              .map((entity) => entityLink(entity, { compact: true }))
              .join("")}</div>`
          : ""
      }
      ${
        dependencies.length
          ? `<div class="ehri-dependency-row"><span>Unlocks after</span>${dependencies
              .map(
                (dependency) => `<a href="#quest-${safeId(dependency.key)}">${escapeHtml(
                  dependency.key,
                )}</a>`,
              )
              .join("")}</div>`
          : ""
      }
      ${renderEvidenceDrawer(evidence, { title: "Quest evidence", id: `${entity.key}-evidence` })}
    </article>
  </li>`;
}

export function renderRoadmap(snapshot) {
  const steps = snapshot.views.roadmap.steps;
  const progress = roadmapProgress(snapshot);
  if (steps.length === 0) {
    return `<section class="ehri-section" id="roadmap" aria-labelledby="roadmap-title">
      <div class="ehri-section-heading"><div><span class="ehri-eyebrow">Roadmap</span><h2 id="roadmap-title">Quest line</h2></div></div>
      ${renderStatePanel("empty")}
    </section>`;
  }
  return `<section class="ehri-section ehri-roadmap" id="roadmap" aria-labelledby="roadmap-title">
    <div class="ehri-section-heading">
      <div><span class="ehri-eyebrow">Roadmap</span><h2 id="roadmap-title">The quest line</h2></div>
      <p>${progress.complete} verified · ${progress.active} active · ${progress.blocked} blocked. Expand any quest to inspect the evidence behind it.</p>
    </div>
    <div class="ehri-quest-layout">
      <nav class="ehri-minimap" aria-label="Roadmap minimap">
        <span class="ehri-minimap__label">Quest map</span>
        <ol>
          ${steps
            .map(
              (step, index) => `<li><a href="#quest-${safeId(step.entity.key)}" data-state="${escapeHtml(
                normalizeState(step.entity.state),
              )}"><span>${String(index + 1).padStart(2, "0")}</span><span>${escapeHtml(
                step.entity.title,
              )}</span></a></li>`,
            )
            .join("\n")}
        </ol>
      </nav>
      <ol class="ehri-quest-line">
        ${steps.map((step, index) => renderQuestStep(step, index, steps.length)).join("\n")}
      </ol>
    </div>
  </section>`;
}

function renderLineage(label, entities) {
  if (!entities?.length) return "";
  return `<div class="ehri-lineage-row"><span>${escapeHtml(label)}</span><div>${entities
    .map((entity) => {
      const fragment =
        normalizeState(entity.kind) === "architecture_decision"
          ? `#decision-${safeId(entity.key)}`
          : normalizeState(entity.kind) === "roadmap_step"
            ? `#quest-${safeId(entity.key)}`
            : safeHref(entity.canonical_url);
      return fragment
        ? `<a href="${escapeHtml(fragment)}">${escapeHtml(entity.key)}</a>`
        : `<span>${escapeHtml(entity.key)}</span>`;
    })
    .join("")}</div></div>`;
}

export function renderDecisionLedger(snapshot) {
  const decisions = snapshot.views.decisions.decisions;
  return `<section class="ehri-section ehri-decisions" id="decisions" aria-labelledby="decisions-title">
    <div class="ehri-section-heading">
      <div><span class="ehri-eyebrow">Decision history</span><h2 id="decisions-title">The decision chain</h2></div>
      <p>A historical lineage, not an immutable ledger. Supersession remains visible instead of rewriting the past.</p>
    </div>
    ${
      decisions.length === 0
        ? renderStatePanel("empty", {
            title: "No decision records projected",
            message: "The repository may not have adopted the ADR contract yet.",
          })
        : `<ol class="ehri-decision-chain">
            ${decisions
              .map((decision, index) => {
                const entity = decision.entity;
                const evidence = collectEvidence(decision);
                return `<li class="ehri-decision" id="decision-${safeId(entity.key)}" data-filter-item data-state="${escapeHtml(
                  normalizeState(entity.state),
                )}" data-kind="architecture_decision" data-search="${escapeHtml(
                  recordSearchText(decision),
                )}">
                  <div class="ehri-decision__link" aria-hidden="true"><span>${index + 1}</span></div>
                  <article>
                    <header><div><span class="ehri-decision__id">${escapeHtml(
                      entity.key,
                    )} · ${escapeHtml(decision.decision_scope ?? "repository")}</span><h3>${escapeHtml(
                      entity.title,
                    )}</h3></div>${statusPill(entity.state, entity.freshness)}</header>
                    <p><strong>Implementation:</strong> ${escapeHtml(
                      stateLabel(decision.implementation_status ?? "unknown"),
                    )}</p>
                    ${renderLineage("Supersedes", decision.supersedes)}
                    ${renderLineage("Superseded by", decision.superseded_by)}
                    ${renderLineage("Informs", decision.informs)}
                    ${renderEvidenceDrawer(evidence, {
                      title: "Decision evidence",
                      id: `${entity.key}-decision-evidence`,
                    })}
                  </article>
                </li>`;
              })
              .join("\n")}
          </ol>`
    }
  </section>`;
}

export function renderJourneyEvent(event, index, total) {
  const entity = event.subject_entity ?? {};
  const kind = normalizeState(entity.kind ?? event.type?.split(".")[0]);
  const state = normalizeState(entity.state ?? "recorded");
  return `<li class="ehri-event" data-filter-item data-event-id="${escapeHtml(
    event.id,
  )}" data-kind="${escapeHtml(kind)}" data-state="${escapeHtml(
    state,
  )}" data-occurred-at="${escapeHtml(event.occurred_at)}" data-search="${escapeHtml(
    recordSearchText(entity) + " " + String(event.type ?? ""),
  )}" aria-posinset="${index + 1}" aria-setsize="${total}">
    <time datetime="${escapeHtml(event.occurred_at)}">${escapeHtml(
      formatDate(event.occurred_at),
    )}</time>
    <span class="ehri-event__rail" aria-hidden="true"><span></span></span>
    <article>
      <div class="ehri-event__meta"><span>${escapeHtml(displayKind(kind))}</span><span>${escapeHtml(
        String(event.type ?? "recorded").replaceAll("_", " "),
      )}</span></div>
      <h4>${escapeHtml(entity.title ?? event.subject ?? "Recorded event")}</h4>
      <div class="ehri-event__footer">${statusPill(state, event.freshness)}${
        safeHref(entity.canonical_url)
          ? `<a href="${escapeHtml(safeHref(entity.canonical_url))}">Inspect <span aria-hidden="true">↗</span></a>`
          : ""
      }</div>
    </article>
  </li>`;
}

export function renderJourneyWindow(events, window) {
  return `${
    window.before
      ? `<li class="ehri-virtual-space" style="block-size:${window.before}px" aria-hidden="true"></li>`
      : ""
  }${window.items
    .map((event, index) => renderJourneyEvent(event, window.start + index, events.length))
    .join("\n")}${
    window.after
      ? `<li class="ehri-virtual-space" style="block-size:${window.after}px" aria-hidden="true"></li>`
      : ""
  }`;
}

function renderJourneyChapter(chapter, options = {}) {
  const allEvents = chapter.events ?? [];
  const isVirtual = options.mode === "interactive" && allEvents.length > options.virtualThreshold;
  const window = isVirtual
    ? computeVirtualWindow(allEvents, options.virtualWindow)
    : { start: 0, end: allEvents.length, before: 0, after: 0, items: allEvents };
  const eventsMarkup = renderJourneyWindow(allEvents, window);
  return `<article class="ehri-chapter" data-chapter-id="${escapeHtml(chapter.id)}">
    <header>
      <div><span class="ehri-chapter__range">${escapeHtml(
        formatDate(chapter.start_at, { dateOnly: true }),
      )} — ${escapeHtml(formatDate(chapter.end_at, { dateOnly: true }))}</span><h3>${escapeHtml(
        chapter.title,
      )}</h3></div>
      <span>${allEvents.length} ${allEvents.length === 1 ? "event" : "events"}</span>
    </header>
    ${
      allEvents.length === 0
        ? renderStatePanel("empty", { title: "No events in this time window" })
        : `<div class="ehri-journey-track${isVirtual ? " ehri-journey-track--virtual" : ""}" ${
            isVirtual
              ? `data-virtual-chapter="${escapeHtml(chapter.id)}" data-row-height="${escapeHtml(
                  options.virtualWindow.rowHeight,
                )}" tabindex="0" role="region" aria-label="Virtualized events in ${escapeHtml(
                  chapter.title,
                )}"`
              : ""
          }>
            <ol>
              ${eventsMarkup}
            </ol>
          </div>`
    }
  </article>`;
}

export function renderJourney(snapshot, options = {}) {
  const chapters = options.chapters ?? eventsByChapter(snapshot);
  const settings = {
    mode: options.mode ?? "static",
    virtualThreshold: options.virtualThreshold ?? 60,
    virtualWindow: {
      scrollTop: options.virtualWindow?.scrollTop ?? 0,
      viewportHeight: options.virtualWindow?.viewportHeight ?? 560,
      rowHeight: options.virtualWindow?.rowHeight ?? 132,
      overscan: options.virtualWindow?.overscan ?? 4,
    },
  };
  return `<section class="ehri-section ehri-journey" id="journey" aria-labelledby="journey-title">
    <div class="ehri-section-heading">
      <div><span class="ehri-eyebrow">Delivery history</span><h2 id="journey-title">The Git journey</h2></div>
      <p>Commits become evidence inside meaningful epochs alongside decisions, issues, checks, releases, and deployments.</p>
    </div>
    ${settings.mode === "interactive" ? `<div class="ehri-time-controls" aria-label="Journey time controls">
      <label>From <input type="date" data-journey-from></label>
      <label>To <input type="date" data-journey-to></label>
      <button class="ehri-button ehri-button--quiet" type="button" data-reset-time>Reset range</button>
    </div>` : ""}
    <div class="ehri-chapters" data-journey-chapters>
      ${
        chapters.length
          ? chapters.map((chapter) => renderJourneyChapter(chapter, settings)).join("\n")
          : renderStatePanel("empty", { title: "No delivery history projected" })
      }
    </div>
  </section>`;
}

function renderWorkQueue(snapshot) {
  const work = snapshot.views.work;
  const groups = [
    ["Open issues", work.open_issues],
    ["Open pull requests", work.open_pull_requests],
    ["Ready quests", work.roadmap_queues?.ready],
    ["Blocked quests", work.roadmap_queues?.blocked],
  ];
  return groups
    .map(
      ([label, items]) => `<div class="ehri-compact-group"><h3>${escapeHtml(label)} <span>${
        items?.length ?? 0
      }</span></h3>${
        items?.length
          ? `<div class="ehri-compact-list">${items
              .slice(0, 8)
              .map((entity) => entityLink(entity, { compact: true }))
              .join("")}</div>`
          : `<p>None asserted.</p>`
      }</div>`,
    )
    .join("\n");
}

export function renderDetails(snapshot) {
  const health = snapshot.views.health;
  const dependencies = snapshot.views.dependencies.relationships ?? [];
  const releases = snapshot.views.releases.releases ?? [];
  return `<section class="ehri-section ehri-details" id="details" aria-labelledby="details-title">
    <div class="ehri-section-heading"><div><span class="ehri-eyebrow">Operational context</span><h2 id="details-title">Evidence matrices</h2></div><p>Compact views expose queues and boundaries without flattening their underlying evidence.</p></div>
    <div class="ehri-detail-grid">
      <article><header><span class="ehri-panel-icon" aria-hidden="true">⌁</span><div><span class="ehri-eyebrow">Health</span><h3>Checks &amp; freshness</h3></div></header>
        <div class="ehri-state-counts">${Object.entries(health.check_states ?? {})
          .map(([state, count]) => `<span>${statusPill(state)}<strong>${count}</strong></span>`)
          .join("")}</div>
        <p>${escapeHtml(health.score_reason ?? "No aggregate score asserted.")}</p>
        ${(health.checks ?? []).map((entity) => entityLink(entity, { compact: true })).join("") || renderStatePanel("empty", { title: "No checks projected" })}
      </article>
      <article><header><span class="ehri-panel-icon" aria-hidden="true">⌘</span><div><span class="ehri-eyebrow">Dependencies</span><h3>Edges &amp; external work</h3></div></header>
        <strong class="ehri-panel-number">${dependencies.length}</strong><p>Explicit dependency relationships</p>
        <div class="ehri-compact-list">${dependencies
          .slice(0, 8)
          .map(
            (relationship) => `<div class="ehri-edge"><span>${escapeHtml(
              relationship.source?.key,
            )}</span><span>${escapeHtml(relationship.type)}</span><span>${escapeHtml(
              relationship.target?.key,
            )}</span></div>`,
          )
          .join("")}</div>
      </article>
      <article><header><span class="ehri-panel-icon" aria-hidden="true">◈</span><div><span class="ehri-eyebrow">Releases</span><h3>Published boundaries</h3></div></header>
        ${
          releases.length
            ? releases
                .map(
                  (release) => `<div class="ehri-release"><div>${statusPill(
                    release.entity.state,
                    release.entity.freshness,
                  )}<time>${escapeHtml(formatDate(release.published_at, { dateOnly: true }))}</time></div><h4>${escapeHtml(
                    release.entity.title,
                  )}</h4><p>${release.includes?.length ?? 0} included records · ${
                    release.deployments?.length ?? 0
                  } deployments</p></div>`,
                )
                .join("")
            : renderStatePanel("empty", { title: "No release boundary projected" })
        }
      </article>
      <article><header><span class="ehri-panel-icon" aria-hidden="true">◎</span><div><span class="ehri-eyebrow">Work</span><h3>Queues &amp; next moves</h3></div></header>${renderWorkQueue(
        snapshot,
      )}</article>
    </div>
  </section>`;
}

export function renderComparison(comparison) {
  if (!comparison) return "";
  const total = (delta) =>
    delta.added.length + delta.removed.length + delta.changed.length;
  const changed =
    total(comparison.entities) + total(comparison.relationships) + total(comparison.events);
  return `<aside class="ehri-comparison" aria-label="Snapshot comparison">
    <div><span class="ehri-eyebrow">Compare state</span><strong>${escapeHtml(
      comparison.before.snapshot_id,
    )} → ${escapeHtml(comparison.after.snapshot_id)}</strong></div>
    <div class="ehri-comparison__counts">
      <span><strong>${total(comparison.entities)}</strong> entities</span>
      <span><strong>${total(comparison.relationships)}</strong> relationships</span>
      <span><strong>${total(comparison.events)}</strong> events</span>
      <span><strong>${changed}</strong> total deltas</span>
    </div>
  </aside>`;
}

export function renderRepositoryIntelligence(snapshot, options = {}) {
  assertRepositoryIntelligence(snapshot);
  const comparisonErrors = validateComparison(options.comparison, snapshot.repository.key);
  if (comparisonErrors.length > 0) {
    throw new TypeError(`Invalid Repository Intelligence comparison:\n- ${comparisonErrors.join("\n- ")}`);
  }
  const progress = roadmapProgress(snapshot);
  const title = options.title ?? snapshot.repository.title;
  const routeLabel = options.routeLabel ?? "Repository intelligence";
  const mode = options.mode ?? "static";
  const homeUrl = safeHref(options.homeUrl ?? "./") ?? "./";
  return `<div class="ehri" data-ehri-root data-mode="${escapeHtml(mode)}" data-coverage="${escapeHtml(
    normalizeState(snapshot.coverage?.status),
  )}">
    <a class="ehri-skip" href="#ehri-main">Skip to repository intelligence</a>
    <header class="ehri-hero">
      <nav class="ehri-breadcrumbs" aria-label="Breadcrumb"><ol><li><a href="${escapeHtml(
        homeUrl,
      )}">Intelligence</a></li><li aria-current="page">${escapeHtml(title)}</li></ol></nav>
      <div class="ehri-hero__body">
        <div class="ehri-hero__copy">
          <span class="ehri-kicker"><span aria-hidden="true"></span>${escapeHtml(routeLabel)}</span>
          <h1>${escapeHtml(title)}</h1>
          <p>Trace intent, decisions, delivery, and evidence as one explorable journey.</p>
          <div class="ehri-hero__meta">${statusPill(
            snapshot.repository.state,
            snapshot.repository.freshness,
          )}<span>Observed ${escapeHtml(
            formatDate(snapshot.observed_at, { dateOnly: true }),
          )}</span><code>${escapeHtml(String(snapshot.represented_commit).slice(0, 8))}</code></div>
        </div>
        <div class="ehri-orbit" style="--ehri-orbit-progress:${progress.percentage}" role="img" aria-label="${progress.percentage}% of roadmap quests verified">
          <div><strong>${progress.percentage}%</strong><span>quest progress</span></div>
          <i></i><i></i><i></i>
        </div>
      </div>
      ${renderComparison(options.comparison)}
      ${mode === "interactive" ? `<div class="ehri-command-bar">
        <label class="ehri-search"><span class="ehri-visually-hidden">Search repository intelligence</span><span aria-hidden="true">⌕</span><input type="search" placeholder="Search quests, ADRs, commits…" data-intelligence-search autocomplete="off"></label>
        <label class="ehri-filter"><span>State</span><select data-state-filter><option value="all">All states</option>${[
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
          "stale",
          "unknown",
        ]
          .map((state) => `<option value="${state}">${escapeHtml(stateLabel(state))}</option>`)
          .join("")}</select></label>
        <label class="ehri-filter"><span>Evidence</span><select data-kind-filter><option value="all">All kinds</option>${Object.entries(
          KIND_LABELS,
        )
          .map(([kind, label]) => `<option value="${kind}">${escapeHtml(label)}</option>`)
          .join("")}</select></label>
        <output class="ehri-results" data-filter-results aria-live="polite">Showing the full repository story</output>
      </div>` : ""}
    </header>
    <nav class="ehri-section-nav" aria-label="Repository Intelligence views">
      <a href="#overview">Now</a><a href="#roadmap">Roadmap</a><a href="#decisions">Decisions</a><a href="#journey">Journey</a><a href="#details">Evidence</a>
    </nav>
    <main id="ehri-main">
      ${renderSummary(snapshot)}
      ${renderRoadmap(snapshot)}
      ${renderDecisionLedger(snapshot)}
      ${renderJourney(snapshot, { mode })}
      ${renderDetails(snapshot)}
      <div class="ehri-no-results" data-no-results hidden>${renderStatePanel("empty", {
        title: "No matching evidence",
        message: "Clear a filter or widen the time range to continue exploring.",
      })}</div>
    </main>
    <footer class="ehri-footer"><span>Rendered from <code>${escapeHtml(
      snapshot.schema,
    )}</code></span><a href="#ehri-main">Back to top ↑</a></footer>
  </div>`;
}
