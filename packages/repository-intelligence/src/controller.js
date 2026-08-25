import {
  assertRepositoryIntelligence,
  computeVirtualWindow,
  eventsByChapter,
  filterEvents,
  normalizeState,
} from "./model.js";
import {
  renderRepositoryIntelligence,
  renderJourneyWindow,
} from "./render.js";

const THEME_PROPERTIES = Object.freeze({
  canvas: "--ehri-canvas",
  canvasRaised: "--ehri-canvas-raised",
  surface: "--ehri-surface",
  surfaceStrong: "--ehri-surface-strong",
  text: "--ehri-text",
  textMuted: "--ehri-text-muted",
  primary: "--ehri-primary",
  accent: "--ehri-accent",
  information: "--ehri-information",
  success: "--ehri-success",
  caution: "--ehri-caution",
  danger: "--ehri-danger",
  unknown: "--ehri-unknown",
  border: "--ehri-border",
  borderStrong: "--ehri-border-strong",
  shadow: "--ehri-shadow",
  fontSans: "--ehri-font-sans",
  fontMono: "--ehri-font-mono",
  radius: "--ehri-radius",
});

function safeCssValue(value) {
  return typeof value === "string" && value.trim() !== "" && !/[;{}<>]/u.test(value);
}

export function applyRepositoryTheme(root, theme = {}) {
  const tokens = theme.tokens ?? theme;
  for (const [name, property] of Object.entries(THEME_PROPERTIES)) {
    const value = tokens[name];
    if (safeCssValue(value)) {
      root.style.setProperty(property, value);
    }
  }
}

function setupSectionNavigation(root, cleanup) {
  const links = [...root.querySelectorAll(".ehri-section-nav a")];
  const handler = (event) => {
    const current = links.indexOf(event.currentTarget);
    if (current < 0) return;
    let next = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      next = (current + 1) % links.length;
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      next = (current - 1 + links.length) % links.length;
    } else if (event.key === "Home") {
      next = 0;
    } else if (event.key === "End") {
      next = links.length - 1;
    }
    if (next !== null) {
      event.preventDefault();
      links[next].focus();
    }
  };
  for (const link of links) {
    link.addEventListener("keydown", handler);
    cleanup.push(() => link.removeEventListener("keydown", handler));
  }

  if ("IntersectionObserver" in globalThis) {
    const observer = new IntersectionObserver(
      (entries) => {
        const current = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
        if (!current) return;
        for (const link of links) {
          const active = link.hash === `#${current.target.id}`;
          link.toggleAttribute("aria-current", active);
        }
      },
      { rootMargin: "-20% 0px -65%", threshold: [0.05, 0.25, 0.6] },
    );
    for (const link of links) {
      const section = root.querySelector(link.hash);
      if (section) observer.observe(section);
    }
    cleanup.push(() => observer.disconnect());
  }
}

function setupVirtualJourneys(root, snapshot, filters, cleanup) {
  const chapters = new Map(eventsByChapter(snapshot).map((chapter) => [chapter.id, chapter]));
  const listeners = [];
  let frame = null;

  const renderTrack = (track, { reset = false } = {}) => {
    const chapter = chapters.get(track.dataset.virtualChapter);
    if (!chapter) return;
    const rowHeight = Number(track.dataset.rowHeight || 132);
    const matching = filterEvents(chapter.events, filters);
    if (reset) track.scrollTop = 0;
    const window = computeVirtualWindow(matching, {
      scrollTop: track.scrollTop,
      viewportHeight: track.clientHeight || 560,
      rowHeight,
      overscan: 4,
    });
    const list = track.querySelector("ol");
    if (list) list.innerHTML = renderJourneyWindow(matching, window);
    track.dataset.matchCount = String(matching.length);
  };

  const attach = () => {
    for (const track of root.querySelectorAll("[data-virtual-chapter]")) {
      const handler = () => {
        if (frame !== null) cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          renderTrack(track);
          frame = null;
        });
      };
      track.addEventListener("scroll", handler, { passive: true });
      listeners.push(() => track.removeEventListener("scroll", handler));
      renderTrack(track);
    }
  };

  attach();
  cleanup.push(() => {
    if (frame !== null) cancelAnimationFrame(frame);
    for (const remove of listeners) remove();
  });
  return {
    refresh() {
      for (const track of root.querySelectorAll("[data-virtual-chapter]")) {
        renderTrack(track, { reset: true });
      }
    },
  };
}

function setupFilters(root, snapshot, cleanup) {
  const search = root.querySelector("[data-intelligence-search]");
  const state = root.querySelector("[data-state-filter]");
  const kind = root.querySelector("[data-kind-filter]");
  const from = root.querySelector("[data-journey-from]");
  const to = root.querySelector("[data-journey-to]");
  const resetTime = root.querySelector("[data-reset-time]");
  const output = root.querySelector("[data-filter-results]");
  const empty = root.querySelector("[data-no-results]");
  const filters = { query: "", state: "all", kind: "all", from: "", to: "" };
  const virtualJourneys = setupVirtualJourneys(root, snapshot, filters, cleanup);

  const apply = () => {
    filters.query = search?.value.trim().toLowerCase() ?? "";
    filters.state = state?.value ?? "all";
    filters.kind = kind?.value ?? "all";
    filters.from = from?.value ?? "";
    filters.to = to?.value ?? "";
    virtualJourneys.refresh();

    let visible = 0;
    for (const item of root.querySelectorAll("[data-filter-item]")) {
      const virtualTrack = item.closest("[data-virtual-chapter]");
      const matchesQuery =
        !filters.query || (item.dataset.search ?? "").includes(filters.query);
      const matchesState =
        filters.state === "all" || normalizeState(item.dataset.state) === filters.state;
      const matchesKind =
        filters.kind === "all" || normalizeState(item.dataset.kind) === filters.kind;
      const occurred = item.dataset.occurredAt ? Date.parse(item.dataset.occurredAt) : null;
      const matchesFrom =
        !filters.from || occurred === null || occurred >= Date.parse(filters.from);
      const matchesTo =
        !filters.to ||
        occurred === null ||
        occurred <= Date.parse(filters.to) + 86_399_999;
      const matches =
        matchesQuery && matchesState && matchesKind && matchesFrom && matchesTo;
      item.hidden = !matches;
      if (matches && !virtualTrack) visible += 1;
    }
    const virtualMatches = [...root.querySelectorAll("[data-virtual-chapter]")].reduce(
      (sum, track) => sum + Number(track.dataset.matchCount ?? 0),
      0,
    );
    const resultCount = visible + virtualMatches;
    if (output) {
      output.value =
        filters.query || filters.state !== "all" || filters.kind !== "all" || filters.from || filters.to
          ? `${resultCount} matching records`
          : "Showing the full repository story";
    }
    if (empty) empty.hidden = resultCount > 0;
  };

  const controls = [search, state, kind, from, to].filter(Boolean);
  for (const control of controls) {
    const eventName = control === search ? "input" : "change";
    control.addEventListener(eventName, apply);
    cleanup.push(() => control.removeEventListener(eventName, apply));
  }
  if (resetTime) {
    const reset = () => {
      if (from) from.value = "";
      if (to) to.value = "";
      apply();
    };
    resetTime.addEventListener("click", reset);
    cleanup.push(() => resetTime.removeEventListener("click", reset));
  }

  const shortcut = (event) => {
    const target = event.target;
    const editing =
      target instanceof HTMLElement &&
      ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName);
    if (event.key === "/" && !editing && search) {
      event.preventDefault();
      search.focus();
    }
    if (event.key === "Escape" && document.activeElement === search && search) {
      search.value = "";
      search.blur();
      apply();
    }
  };
  root.addEventListener("keydown", shortcut);
  cleanup.push(() => root.removeEventListener("keydown", shortcut));
  apply();
}

export function mountRepositoryIntelligence(root, options) {
  if (!(root instanceof Element)) {
    throw new TypeError("Repository Intelligence root must be a DOM Element");
  }
  const snapshot = assertRepositoryIntelligence(options.snapshot);
  const cleanup = [];
  root.innerHTML = renderRepositoryIntelligence(snapshot, {
    ...options,
    mode: "interactive",
  });
  root.dataset.ehriEnhanced = "true";
  applyRepositoryTheme(root, options.theme);
  setupSectionNavigation(root, cleanup);
  setupFilters(root, snapshot, cleanup);

  return {
    destroy() {
      for (const dispose of cleanup.splice(0).reverse()) dispose();
      root.removeAttribute("data-ehri-enhanced");
    },
    update(nextOptions) {
      this.destroy();
      return mountRepositoryIntelligence(root, { ...options, ...nextOptions });
    },
  };
}

export function defineRepositoryIntelligenceElement(tagName = "eh-repository-intelligence") {
  if (!("customElements" in globalThis) || customElements.get(tagName)) {
    return globalThis.customElements?.get(tagName) ?? null;
  }
  class RepositoryIntelligenceElement extends HTMLElement {
    #snapshot = null;
    #comparison = null;
    #theme = null;
    #controller = null;

    set snapshot(value) {
      this.#snapshot = value;
      this.#render();
    }

    get snapshot() {
      return this.#snapshot;
    }

    set comparison(value) {
      this.#comparison = value;
      this.#render();
    }

    set theme(value) {
      this.#theme = value;
      this.#render();
    }

    connectedCallback() {
      this.#render();
    }

    disconnectedCallback() {
      this.#controller?.destroy();
      this.#controller = null;
    }

    #render() {
      if (!this.isConnected || !this.#snapshot) return;
      this.#controller?.destroy();
      this.#controller = mountRepositoryIntelligence(this, {
        snapshot: this.#snapshot,
        comparison: this.#comparison,
        theme: this.#theme,
      });
    }
  }
  customElements.define(tagName, RepositoryIntelligenceElement);
  return RepositoryIntelligenceElement;
}
