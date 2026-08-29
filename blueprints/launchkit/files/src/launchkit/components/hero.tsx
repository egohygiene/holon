import type { LaunchKitContent } from "../types";
import { ActionLinks } from "./actions";

export function Hero({ content }: { content: LaunchKitContent }) {
  return (
    <section aria-labelledby="hero-title" className="hero">
      {content.announcement ? (
        <a className="announcement" href={content.announcement.href}>
          <span>New</span> {content.announcement.label} <span aria-hidden="true">→</span>
        </a>
      ) : null}
      <p className="eyebrow">{content.hero.eyebrow}</p>
      <h1 id="hero-title">{content.hero.title}</h1>
      <p className="hero-description">{content.hero.description}</p>
      <ActionLinks actions={content.hero.actions} />
      {content.demo ? (
        <div className="product-window">
          <div aria-hidden="true" className="window-bar">
            <span />
            <span />
            <span />
          </div>
          <div className="product-window-body">
            <div>
              <p className="eyebrow">{content.demo.eyebrow}</p>
              <h2>{content.demo.title}</h2>
              <p>{content.demo.description}</p>
            </div>
            {content.demo.asset ? (
              <img alt={content.demo.asset.alt} src={content.demo.asset.src} />
            ) : (
              <dl className="metrics">
                {content.demo.metrics.map((metric) => (
                  <div key={metric.label}>
                    <dt>{metric.label}</dt>
                    <dd>{metric.value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
