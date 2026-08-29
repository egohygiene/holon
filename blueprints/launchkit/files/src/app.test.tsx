import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { App } from "./app";
import { launchkitContent } from "./launchkit/content";

describe("LaunchKit landing profile", () => {
  it("renders a complete semantic landing page without browser JavaScript", () => {
    const markup = renderToStaticMarkup(<App basePath="/" pathname="/" />);

    expect(markup).toContain('data-launchkit-static="true"');
    expect(markup).toContain('href="#main-content"');
    expect(markup).toContain('aria-label="Primary navigation"');
    expect(markup).toContain('<main id="main-content">');
    expect(markup).toContain('id="features"');
    expect(markup).not.toContain("Lorem ipsum");
  });

  it("omits unselected sections instead of rendering empty shells", () => {
    const markup = renderToStaticMarkup(<App basePath="/" pathname="/" />);
    const rendered = ["faq", "architecture", "integrations"].filter((id) =>
      markup.includes(`id="${id}"`),
    );
    const selected = [
      launchkitContent.faq ? "faq" : null,
      launchkitContent.architecture ? "architecture" : null,
      launchkitContent.integrations ? "integrations" : null,
    ].filter(Boolean);

    expect(rendered).toEqual(selected);
  });

  it("renders an explicit not-found route", () => {
    const markup = renderToStaticMarkup(<App basePath="/" pathname="/missing/" />);
    expect(markup).toContain("Page not found");
    expect(markup).toContain("Return home");
  });
});
