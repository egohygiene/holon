// Minimal DOM seam for the public adapter's lifecycle and listener contract.
// It does not emulate layout, a browser HTML parser or accessibility behavior.
export function withRepositoryIntelligenceDOM(run) {
  class Style {
    values = new Map();
    setProperty(name, value, priority = "") { this.values.set(name, { value, priority }); }
    getPropertyValue(name) { return this.values.get(name)?.value ?? ""; }
    getPropertyPriority(name) { return this.values.get(name)?.priority ?? ""; }
    removeProperty(name) {
      const prior = this.getPropertyValue(name);
      this.values.delete(name);
      return prior;
    }
  }
  class FakeElement {
    style = new Style();
    dataset = {};
    listeners = new Map();
    controls = new Map();
    links = [];
    value = "";
    tagName = "DIV";
    isConnected = false;
    _html = "";
    get innerHTML() { return this._html; }
    set innerHTML(value) {
      this._html = value;
      this.controls = new Map();
      for (const attribute of [
        "data-intelligence-search", "data-state-filter", "data-kind-filter",
        "data-journey-from", "data-journey-to", "data-reset-time",
        "data-filter-results", "data-no-results",
      ]) {
        if (!value.includes(attribute)) continue;
        const control = new FakeElement();
        control.tagName = attribute.includes("filter") ? "SELECT" : "INPUT";
        control.value = ["data-state-filter", "data-kind-filter"].includes(attribute) ? "all" : "";
        this.controls.set(`[${attribute}]`, control);
      }
      this.links = value.includes('class="ehri-section-nav"')
        ? ["overview", "roadmap", "decisions", "journey", "details"].map((id) => {
          const link = new FakeElement();
          link.tagName = "A";
          link.hash = `#${id}`;
          return link;
        })
        : [];
    }
    querySelector(selector) { return this.controls.get(selector) ?? null; }
    querySelectorAll(selector) { return selector === ".ehri-section-nav a" ? this.links : []; }
    addEventListener(type, listener) {
      if (!this.listeners.has(type)) this.listeners.set(type, new Set());
      this.listeners.get(type).add(listener);
    }
    removeEventListener(type, listener) { this.listeners.get(type)?.delete(listener); }
    listenerCount(type) { return this.listeners.get(type)?.size ?? 0; }
    emit(type, extra = {}) {
      const event = { target: this, currentTarget: this, preventDefault() {}, ...extra };
      for (const listener of this.listeners.get(type) ?? []) listener(event);
    }
    focus() { document.activeElement = this; }
    blur() { document.activeElement = null; }
    removeAttribute(name) {
      if (name === "data-ehri-enhanced") delete this.dataset.ehriEnhanced;
    }
  }
  const names = ["Element", "HTMLElement", "customElements", "document", "IntersectionObserver"];
  const prior = new Map(names.map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
  const registry = new Map();
  try {
    for (const [name, value] of Object.entries({
      Element: FakeElement,
      HTMLElement: FakeElement,
      document: { activeElement: null },
      customElements: {
        get(name) { return registry.get(name); },
        define(name, value) { registry.set(name, value); },
      },
    })) Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
    delete globalThis.IntersectionObserver;
    return run({
      Element: FakeElement,
      connect(element) { element.isConnected = true; element.connectedCallback(); },
      disconnect(element) { element.isConnected = false; element.disconnectedCallback(); },
    });
  } finally {
    for (const [name, descriptor] of prior) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  }
}
