import type { LaunchKitContent } from "../types";
import { ActionLinks, LinkList } from "./actions";

export function FinalCta({ content }: { content: NonNullable<LaunchKitContent["finalCta"]> }) {
  return (
    <section aria-labelledby="final-cta-title" className="final-cta">
      <div>
        <h2 id="final-cta-title">{content.title}</h2>
        <p>{content.description}</p>
      </div>
      <ActionLinks actions={content.actions} />
    </section>
  );
}

export function Footer({ content }: { content: LaunchKitContent }) {
  return (
    <footer className="site-footer">
      <div className="footer-grid">
        <div>
          <p className="footer-wordmark">{content.identity.wordmark}</p>
          <p>{content.footer.summary}</p>
        </div>
        {content.footer.groups.map((group) => (
          <div key={group.title}>
            <h2>{group.title}</h2>
            <LinkList links={group.links} />
          </div>
        ))}
      </div>
      <div className="footer-legal">
        <small>
          Materialized from Holon launchkit@1.0.0 · LaunchKit design reference by Evil Martians
        </small>
        <LinkList className="legal-links" links={content.footer.legal} />
      </div>
    </footer>
  );
}
