import type { LaunchKitContent } from "../types";
import { FinalCta, Footer } from "./footer";
import { Header } from "./header";
import { Hero } from "./hero";
import { Architecture, CodeSection, Faq, Features, OptionalCards, Proof, Trust } from "./sections";

export function ProductLanding({
  content,
  homeHref,
}: {
  content: LaunchKitContent;
  homeHref: string;
}) {
  return (
    <div data-launchkit-static="true">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <Header content={content} homeHref={homeHref} />
      <main id="main-content">
        <Hero content={content} />
        {content.proof ? <Proof content={content.proof} /> : null}
        <Features content={content.features} />
        <OptionalCards content={content.useCases} id="use-cases" />
        {content.code ? <CodeSection content={content.code} /> : null}
        {content.architecture ? <Architecture content={content.architecture} /> : null}
        <OptionalCards content={content.integrations} id="integrations" />
        {content.trust ? <Trust content={content.trust} /> : null}
        {content.faq?.items.length ? <Faq content={content.faq} /> : null}
        {content.finalCta ? <FinalCta content={content.finalCta} /> : null}
      </main>
      <Footer content={content} />
    </div>
  );
}
