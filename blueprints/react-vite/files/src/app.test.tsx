import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { App } from "./app";

describe("generic application shell", () => {
  it("renders semantic navigation and accessibility landmarks", () => {
    const markup = renderToStaticMarkup(<App pathname="/" />);

    expect(markup).toContain('href="#main-content"');
    expect(markup).toContain('aria-label="Primary navigation"');
    expect(markup).toContain('<main class="shell" id="main-content">');
    expect(markup).toContain("Generic React/Vite foundation");
  });

  it("renders an explicit not-found state for an unknown route", () => {
    const markup = renderToStaticMarkup(<App pathname="/missing/" />);

    expect(markup).toContain("Page not found");
    expect(markup).toContain("Return home");
  });
});
