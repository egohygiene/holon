import { ProductLanding } from "./launchkit/components/product-landing";
import { launchkitContent } from "./launchkit/content";

interface AppProps {
  pathname?: string;
  basePath?: string;
}

function normalizedRoute(pathname: string, basePath: string): string {
  const normalizedBase = basePath.endsWith("/") ? basePath : `${basePath}/`;
  const withoutBase = pathname.startsWith(normalizedBase)
    ? pathname.slice(normalizedBase.length - 1)
    : pathname;
  const withLeadingSlash = withoutBase.startsWith("/") ? withoutBase : `/${withoutBase}`;
  return withLeadingSlash.length > 1 ? withLeadingSlash.replace(/\/+$/, "") : "/";
}

export function App({
  pathname = window.location.pathname,
  basePath = import.meta.env.BASE_URL,
}: AppProps) {
  const route = normalizedRoute(pathname, basePath);
  if (route !== "/") {
    return (
      <main className="not-found" id="main-content">
        <p className="eyebrow">404</p>
        <h1>Page not found</h1>
        <p>This LaunchKit profile publishes one focused product landing route.</p>
        <a className="button primary" href={basePath}>
          Return home
        </a>
      </main>
    );
  }
  return <ProductLanding content={launchkitContent} homeHref={basePath} />;
}
