const SITE_TITLE = {{parameter_json.site_title}};
// biome-ignore format: consumer-provided literal width varies by manifest
const SITE_DESCRIPTION =
  {{parameter_json.site_description}};

interface AppProps {
  pathname?: string;
}

function normalizePath(pathname: string, basePath: string): string {
  const normalizedBase = basePath.endsWith("/") ? basePath : `${basePath}/`;
  const withoutBase = pathname.startsWith(normalizedBase)
    ? pathname.slice(normalizedBase.length - 1)
    : pathname;
  const withLeadingSlash = withoutBase.startsWith("/") ? withoutBase : `/${withoutBase}`;
  return withLeadingSlash.length > 1 ? withLeadingSlash.replace(/\/+$/, "") : "/";
}

function withBasePath(path: string): string {
  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`;
  return path === "/" ? base : `${base}${path.replace(/^\//, "")}`;
}

function HomePage() {
  return (
    <>
      <p className="eyebrow">Generic React/Vite foundation</p>
      <h1>{SITE_TITLE}</h1>
      <p className="lede">{SITE_DESCRIPTION}</p>
      <section aria-labelledby="foundation-heading" className="panel">
        <h2 id="foundation-heading">A small, inspectable starting point</h2>
        <p>
          This shell keeps framework infrastructure separate from product identity and landing-page
          presentation. Replace content through governed consumer source, not by forking Holon.
        </p>
      </section>
    </>
  );
}

function AboutPage() {
  return (
    <>
      <p className="eyebrow">Architecture</p>
      <h1>How this foundation is composed</h1>
      <p className="lede">
        React and Vite own the application shell. Identity supplies reviewed semantic tokens. Holon
        owns deterministic materialization, and Relay may own deployment.
      </p>
    </>
  );
}

function NotFoundPage() {
  return (
    <>
      <p className="eyebrow">404</p>
      <h1>Page not found</h1>
      <p className="lede">The requested route is not part of this generated site profile.</p>
      <a className="button" href={withBasePath("/")}>
        Return home
      </a>
    </>
  );
}

export function App({ pathname = window.location.pathname }: AppProps) {
  const route = normalizePath(pathname, import.meta.env.BASE_URL);
  const content =
    route === "/" ? <HomePage /> : route === "/about" ? <AboutPage /> : <NotFoundPage />;

  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="site-header">
        <a className="wordmark" href={withBasePath("/")}>
          {SITE_TITLE}
        </a>
        <nav aria-label="Primary navigation">
          <a aria-current={route === "/" ? "page" : undefined} href={withBasePath("/")}>
            Home
          </a>
          <a aria-current={route === "/about" ? "page" : undefined} href={withBasePath("/about/")}>
            About
          </a>
        </nav>
      </header>
      <main className="shell" id="main-content">
        {content}
      </main>
      <footer className="site-footer">
        <small>Materialized from Holon blueprint react-vite@1.0.0.</small>
      </footer>
    </>
  );
}
