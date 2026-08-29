import type { Card, LaunchKitContent, SectionCards } from "../types";
import { LinkList } from "./actions";

function SectionHeading({
  eyebrow,
  title,
  description,
  id,
}: Omit<SectionCards, "items"> & { id: string }) {
  return (
    <div className="section-heading">
      <p className="eyebrow">{eyebrow}</p>
      <h2 id={id}>{title}</h2>
      <p>{description}</p>
    </div>
  );
}

function CardItem({ card, index }: { card: Card; index?: number }) {
  const content = (
    <>
      {index === undefined ? null : <span className="step-number">{index + 1}</span>}
      {card.eyebrow ? <p className="card-eyebrow">{card.eyebrow}</p> : null}
      <h3>{card.title}</h3>
      <p>{card.description}</p>
      {card.href ? <span className="card-link">Learn more →</span> : null}
    </>
  );
  return card.href ? (
    <a className="feature-card linked" href={card.href}>
      {content}
    </a>
  ) : (
    <article className="feature-card">{content}</article>
  );
}

function CardsSection({ content, id }: { content: SectionCards; id: string }) {
  return (
    <section aria-labelledby={`${id}-title`} className="content-section" id={id}>
      <SectionHeading
        description={content.description}
        eyebrow={content.eyebrow}
        id={`${id}-title`}
        title={content.title}
      />
      <div className="card-grid">
        {content.items.map((item) => (
          <CardItem card={item} key={item.title} />
        ))}
      </div>
    </section>
  );
}

export function Proof({ content }: { content: NonNullable<LaunchKitContent["proof"]> }) {
  return (
    <section aria-label={content.title} className="proof-strip">
      <p>{content.title}</p>
      <ul>
        {content.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

export function Features({ content }: { content: LaunchKitContent["features"] }) {
  return (
    <section aria-labelledby="features-title" className="content-section" id="features">
      <SectionHeading
        description={content.description}
        eyebrow={content.eyebrow}
        id="features-title"
        title={content.title}
      />
      <div className="card-grid feature-grid">
        {content.items.map((item) => (
          <CardItem card={item} key={item.title} />
        ))}
      </div>
    </section>
  );
}

export function OptionalCards({ content, id }: { content: SectionCards | undefined; id: string }) {
  return content ? <CardsSection content={content} id={id} /> : null;
}

export function CodeSection({ content }: { content: NonNullable<LaunchKitContent["code"]> }) {
  return (
    <section aria-labelledby="code-title" className="code-section content-section" id="code">
      <SectionHeading
        description={content.description}
        eyebrow={content.eyebrow}
        id="code-title"
        title={content.title}
      />
      <div className="code-window">
        <div className="code-label">{content.language}</div>
        <pre>
          <code>{content.value}</code>
        </pre>
      </div>
    </section>
  );
}

export function Architecture({
  content,
}: {
  content: NonNullable<LaunchKitContent["architecture"]>;
}) {
  return (
    <section aria-labelledby="architecture-title" className="content-section" id="architecture">
      <SectionHeading
        description={content.description}
        eyebrow={content.eyebrow}
        id="architecture-title"
        title={content.title}
      />
      <div className="steps">
        {content.items.map((item, index) => (
          <CardItem card={item} index={index} key={item.title} />
        ))}
      </div>
    </section>
  );
}

export function Trust({ content }: { content: NonNullable<LaunchKitContent["trust"]> }) {
  return (
    <section aria-labelledby="trust-title" className="trust-section content-section" id="trust">
      <SectionHeading
        description={content.description}
        eyebrow={content.eyebrow}
        id="trust-title"
        title={content.title}
      />
      <LinkList className="trust-links" links={content.links} />
    </section>
  );
}

export function Faq({ content }: { content: NonNullable<LaunchKitContent["faq"]> }) {
  return (
    <section aria-labelledby="faq-title" className="content-section faq" id="faq">
      <SectionHeading
        description={content.description}
        eyebrow={content.eyebrow}
        id="faq-title"
        title={content.title}
      />
      <div className="faq-list">
        {content.items.map((item) => (
          <details key={item.question}>
            <summary>{item.question}</summary>
            <p>{item.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
