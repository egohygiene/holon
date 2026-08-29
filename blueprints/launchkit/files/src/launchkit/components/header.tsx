import type { LaunchKitContent } from "../types";
import { LinkList } from "./actions";

interface HeaderProps {
  content: LaunchKitContent;
  homeHref: string;
}

export function Header({ content, homeHref }: HeaderProps) {
  return (
    <header className="site-header">
      <a aria-label={`${content.identity.wordmark} home`} className="brand" href={homeHref}>
        {content.identity.logo ? (
          <img alt={content.identity.logo.alt} src={content.identity.logo.src} />
        ) : null}
        <span>{content.identity.wordmark}</span>
      </a>
      {content.navigation?.length ? (
        <nav aria-label="Primary navigation">
          <LinkList className="nav-links" links={content.navigation} />
        </nav>
      ) : null}
    </header>
  );
}
